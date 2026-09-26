"""Montagem da carga real do contrato (sem banco, com tabelas processadas sintéticas)."""
import pandas as pd
import pytest

from src.publicacao.montar import ler_mock, resolver_agora, snapshot_carga


def _carga(linhas):
    return pd.DataFrame(linhas, columns=["subsistema", "timestamp", "carga_global", "mmgd_estimada"])


CAP = pd.DataFrame({"uf": ["MG", "MG", "SP"], "data": ["2026-01-01", "2026-09-30", "2026-01-01"],
                    "potencia_acumulada_mw": [100.0, 900.0, 100.0]})


def _completa(t, mmgd=10.0):
    return [(s, t, 1000.0, mmgd) for s in ("SE", "S", "NE", "N")]


def test_usa_a_ultima_semi_hora_com_os_4_subsistemas_completos():
    # 12:30 só tem 3 subsistemas: não pode virar "SIN"; o agora cai em 12:00.
    df = _carga(_completa("2026-09-24 12:00") + _completa("2026-09-24 12:30")[:3])
    s = snapshot_carga(df, CAP)
    assert s.para_json()["timestampUtc"] == "2026-09-24T15:00:00Z"  # 12:00 em UTC-3
    assert s.carga_global_mw == 4000 and s.mmgd_estimada_mw == 40
    assert s.carga_supervisionada_mw == 3960
    assert s.percentual_mmgd_na_geracao == 1.0


def test_capacidade_so_conta_cadastros_ate_a_data_do_agora():
    # Replay em 2026-09-24: o cadastro de MG de 2026-09-30 (900 MW) ainda não existia.
    s = snapshot_carga(_carga(_completa("2026-09-24 12:00", mmgd=25.0)), CAP)
    assert s.mmgd_sobre_capacidade_instalada == pytest.approx(100 / 200)  # 4×25 MW ÷ (100+100)


def test_agora_no_passado_ignora_dados_posteriores():
    df = _carga(_completa("2026-09-24 12:00") + _completa("2026-09-24 13:00", mmgd=99.0))
    s = snapshot_carga(df, CAP, agora=resolver_agora("2026-09-24T12:30:00-03:00"))
    assert s.mmgd_estimada_mw == 40  # a semi-hora das 13:00 é "futuro" para esse agora


def test_agora_sem_fuso_e_recusado():
    with pytest.raises(ValueError, match="sem fuso"):
        resolver_agora("2026-09-24T12:30:00")


def test_mocks_publicados_tem_flag():
    for r in ("previsao", "riscos", "alertas", "excedentes", "validacao", "mmgd_densidade"):
        dados = ler_mock(r)
        assert all(x["mock"] is True for x in (dados if isinstance(dados, list) else [dados]))


# --------------------------------------------------------------------------- previsão e validação
from src.models import carga as mc  # noqa: E402
from src.publicacao.montar import curvas_previsao, metricas_validacao  # noqa: E402

AGORA = pd.Timestamp("2026-09-24 23:30")
TREINO = {"versao": "cfg-teste", "dataTreino": pd.Timestamp("2026-09-20").date()}
FATORES = {h: {"radiacaoSolar": 1, "ventoMs": 1, "temperaturaC": 1, "coberturaNuvensPct": 1}
           for h in ("30min", "3h", "D+1")}


def _prev(modelos=("lightgbm", "climatologia"), real_ate=AGORA):
    """Tabela de previsões sintética no formato de src/models/carga.py::prever."""
    passo = pd.Timedelta("30min")
    linhas = []
    for nome_h, h in mc.cfg()["horizontes"].items():
        alvos = pd.date_range(AGORA - 40 * 48 * passo, AGORA + h * passo, freq="30min")
        for m in modelos:
            erro = 100.0 if m == "lightgbm" else 400.0
            df = pd.DataFrame({"serie": "SIN", "horizonte": nome_h, "modelo": m, "alvo": alvos,
                               "emissao": alvos - h * passo, "real": 1000.0})
            df.loc[df["alvo"] > real_ate, "real"] = float("nan")
            df["p50"] = 1000.0 + erro
            df["p10"], df["p90"] = df["p50"] - 50, df["p50"] + 50
            linhas.append(df)
    return pd.concat(linhas, ignore_index=True)


def test_curvas_terminam_em_agora_mais_h_e_nunca_usam_emissao_futura():
    curvas = {c.horizonte: c for c in curvas_previsao(_prev(), AGORA, FATORES)}
    assert set(curvas) == {"30min", "3h", "D+1"}
    for nome_h, h in mc.cfg()["horizontes"].items():
        pts = curvas[nome_h].pontos
        assert len(pts) == 48
        ultimo = pd.Timestamp(pts[-1].timestamp).tz_convert("Etc/GMT+3").tz_localize(None)
        assert ultimo == AGORA + h * pd.Timedelta("30min")
    # D+1: as próximas 24 h, todas no futuro
    primeiro = pd.Timestamp(curvas["D+1"].pontos[0].timestamp).tz_convert("Etc/GMT+3").tz_localize(None)
    assert primeiro == AGORA + pd.Timedelta("30min")
    # fatores climáticos ainda mock -> registro inteiro mock
    assert all(c.mock for c in curvas.values())


def test_curva_incompleta_e_recusada():
    prev = _prev()
    prev = prev[~((prev["horizonte"] == "D+1") & (prev["alvo"] == AGORA + pd.Timedelta("2h")))]
    with pytest.raises(LookupError, match="47 de 48"):
        curvas_previsao(prev, AGORA, FATORES)


def test_validacao_real_com_skill_e_historico():
    fontes = [{"fonte": "ONS", "online": True,
               "ultima_sincronizacao": pd.Timestamp("2026-09-25T10:00:00Z").to_pydatetime()}]
    v = metricas_validacao(_prev(), AGORA, fontes, TREINO)
    assert v.mock is False
    assert v.erro_medio_absoluto_mw == 100 and v.mape_pct == 10
    assert v.skill_vs_climatologia == pytest.approx(1 - 100 / 400)
    assert len(v.historico_erro30d) == 30                    # só dias completos, os últimos 30
    assert v.historico_erro30d[-1].data.isoformat() == "2026-09-24"
    assert v.para_json()["statusFontes"][0]["ultimaSincronizacao"] == "2026-09-25T10:00:00Z"
    # baseline lado a lado no histórico (mesmos dias do modelo)
    assert v.baseline_nome == "Climatologia"
    assert all(d.mae_baseline == 400 and d.rmse_baseline == 400 for d in v.historico_erro30d)
    # metadados: split da config; teste termina no último dia com real até o agora
    assert v.modelo.versao == "cfg-teste" and v.modelo.data_treino.isoformat() == "2026-09-20"
    sp = mc.split()
    assert v.modelo.periodo_treino.fim == sp.fim_treino.date()
    assert v.modelo.periodo_teste.inicio == sp.inicio_teste.date()
    assert v.modelo.periodo_teste.fim.isoformat() == "2026-09-24"


def test_validacao_ignora_reais_depois_do_agora():
    # replay: um "agora" no passado não pode medir erro com dados que ainda não existiam
    agora = AGORA - pd.Timedelta("10D")
    v = metricas_validacao(_prev(), agora, [], TREINO)
    assert v.historico_erro30d[-1].data.isoformat() == "2026-09-14"
    assert v.modelo.periodo_teste.fim.isoformat() == "2026-09-14"


def test_posicao_uf_cobre_todas_as_ufs_dentro_do_brasil():
    """Toda UF tem sede configurada e dentro da caixa do contrato (nunca um ponto no oceano)."""
    from src.contrato.modelos import RECURSOS
    from src.utils.config import carregar
    pos = carregar("publicacao")["posicao_uf"]
    assert len(pos) == 27
    risco = ler_mock("riscos")[0]
    for uf, (lat, lon) in pos.items():
        RECURSOS["riscos"].modelo.model_validate({**risco, "uf": uf, "lat": lat, "lon": lon})


def test_versao_do_modelo_muda_com_a_config_de_treino(monkeypatch):
    base = mc.versao_config()
    cfg = mc.cfg()
    monkeypatch.setattr(mc, "cfg", lambda: {**cfg, "lightgbm": {**cfg["lightgbm"], "num_leaves": 7}})
    assert mc.versao_config() != base and base.startswith("cfg-")
