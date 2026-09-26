"""Classificador de curtailment: sem vazamento temporal, códigos de usina estáveis, fora da amostra."""
import copy

import numpy as np
import pandas as pd
import pytest

from src.features import curtailment as fcur
from src.features.calendario import montar_calendario
from src.models import curtailment as mcur

INICIO, FIM = "2025-01-01", "2025-03-31"
FEATURES = {"defasagens_recentes": [0, 1, 2, 6], "defasagens_sazonais": [48, 336], "janelas_media": [6, 48, 336]}
USINAS = {"eolica:A": ("NE", "BA"), "eolica:B": ("NE", "RN"), "solar:C": ("SE", "MG")}


def _painel(perturbar_depois: pd.Timestamp | None = None, codigos=None, sem=()):
    rng = np.random.default_rng(0)
    ts = pd.date_range(INICIO, f"{FIM} 23:30", freq="30min")
    hora = ts.hour
    linhas = []
    for chave in USINAS:
        if chave in sem:
            continue
        # corte ENE mais provável no meio do dia (padrão aprendível); CNF raro
        p = np.where((hora >= 10) & (hora < 15), 0.6, 0.05)
        ene = rng.random(len(ts)) < p
        cnf = rng.random(len(ts)) < 0.03
        df = pd.DataFrame({"chave": chave, "timestamp": ts, "flag_ENE": ene, "flag_CNF": cnf,
                           "corte_MW_ENE": np.where(ene, rng.uniform(5, 50, len(ts)), 0.0),
                           "corte_MW_CNF": np.where(cnf, rng.uniform(5, 50, len(ts)), 0.0)})
        linhas.append(df)
    rot = pd.concat(linhas, ignore_index=True)
    carga = pd.concat([pd.DataFrame({"subsistema": s, "timestamp": ts,
                                     "carga_supervisionada": 1000 + 100 * np.sin(hora / 24 * 6.28),
                                     "mmgd_estimada": 50.0}) for s in ("SE", "S", "NE", "N")])
    if perturbar_depois is not None:  # o "futuro" vira lixo
        fut = rot["timestamp"] > perturbar_depois
        rot.loc[fut, ["flag_ENE", "flag_CNF"]] = True
        rot.loc[fut, ["corte_MW_ENE", "corte_MW_CNF"]] = 9e6
        carga.loc[carga["timestamp"] > perturbar_depois, ["carga_supervisionada", "mmgd_estimada"]] = -9e6
    atributos = pd.DataFrame([{"chave": k, "nom_usina": k.upper(), "uf": uf, "subsistema": sub,
                               "fonte": k.split(":")[0], "id_ons": k.split(":")[1]}
                              for k, (sub, uf) in USINAS.items()])
    cal = montar_calendario(INICIO, FIM)
    return fcur.montar_painel(rot, atributos, carga, cal, ["ENE", "CNF"], pd.Timestamp(INICIO), 48, codigos)


@pytest.mark.parametrize("h", [1, 6, 48])
def test_features_de_curtailment_nao_enxergam_depois_da_emissao(h):
    alvo = pd.Timestamp("2025-03-20 12:00")
    emissao = alvo - h * pd.Timedelta("30min")
    a, b = _painel(), _painel(perturbar_depois=emissao)
    xa = fcur.matriz_usina(a, fcur.estado_do_sistema(a), "eolica:A", h, FEATURES).loc[alvo]
    xb = fcur.matriz_usina(b, fcur.estado_do_sistema(b), "eolica:A", h, FEATURES).loc[alvo]
    pd.testing.assert_series_equal(xa, xb)


def test_codigos_de_usina_do_treino_nunca_mudam():
    treino = fcur.codigos_usinas(["eolica:A", "eolica:B", "solar:C"], None)
    # outro painel: uma usina saiu, uma entrou -> as antigas mantêm o código, a nova ganha um novo
    depois = fcur.codigos_usinas(["eolica:B", "solar:C", "solar:D"], treino)
    assert depois["eolica:B"] == treino["eolica:B"] and depois["solar:C"] == treino["solar:C"]
    assert depois["solar:D"] == treino.max() + 1
    p = _painel(codigos=treino, sem=("eolica:A",))
    assert p.usinas.loc["solar:C", "codigo"] == treino["solar:C"]


@pytest.fixture
def cfg_pequena(monkeypatch, tmp_path):
    c = copy.deepcopy(mcur.cfg())
    c["split"] = {"inicio_treino": "2025-01-10 00:00", "fim_treino": "2025-02-28 23:30",
                  "inicio_teste": "2025-03-01 00:00"}
    c["amostra_treino"] = 5000
    c["lightgbm_classificador"] = {**c["lightgbm_classificador"], "n_estimators": 20, "n_jobs": 1}
    c["lightgbm_montante"] = {**c["lightgbm_montante"], "n_estimators": 20, "n_jobs": 1,
                              "min_child_samples": 5}
    monkeypatch.setattr(mcur, "cfg", lambda: c)
    monkeypatch.setattr(mcur, "ARQ_MODELOS", tmp_path / "m.joblib")
    monkeypatch.setattr(mcur, "ARQ_PREVISOES", tmp_path / "p.parquet")
    monkeypatch.setattr(mcur, "ARQ_USINAS", tmp_path / "u.parquet")
    monkeypatch.setattr(mcur, "DIR", tmp_path)
    return c


def test_previsoes_de_curtailment_fora_da_amostra(cfg_pequena):
    painel = _painel()
    mcur.treinar(painel)
    mcur.prever(_painel(codigos=mcur.ler_modelos()["codigos"]))
    prev = mcur.ler_previsoes()
    assert (prev["emissao"] >= pd.Timestamp("2025-03-01")).all()
    assert prev["p_ene"].between(0, 1).all() and (prev["montante_ene"] >= 0).all()
    # o padrão sintético (corte no meio do dia) precisa ser aprendido
    meio_dia = prev["alvo"].dt.hour.between(10, 14)
    assert prev.loc[meio_dia, "p_ene"].mean() > prev.loc[~meio_dia, "p_ene"].mean() + 0.2  # 20 árvores só
    # D+1 vai até 48 passos além do último dado
    d1 = prev[prev["horizonte"] == "D+1"]
    assert d1["alvo"].max() == painel.ultimo_dado + 48 * pd.Timedelta("30min")


def test_prever_recusa_modelo_de_outro_split(cfg_pequena):
    mcur.treinar(_painel())
    cfg_pequena["split"] = {**cfg_pequena["split"], "fim_treino": "2025-02-27 23:30"}
    with pytest.raises(RuntimeError, match="outro split"):
        mcur.prever(_painel())


def test_toda_feature_tem_rotulo_de_explicacao():
    """Feature nova sem rótulo quebraria o Detalhe do Alerta na publicação: pega aqui."""
    p = _painel()
    for h in (1, 6, 48):
        cols = fcur.matriz_usina(p, fcur.estado_do_sistema(p), "solar:C", h, FEATURES).columns
        rotulos = {fcur.rotulo_explicacao(c) for c in cols}
        assert "Histórico de cortes ENE da usina" in rotulos and "Carga supervisionada do SIN" in rotulos


def test_severidade_e_id_do_risco():
    from src.publicacao.montar import _id_risco, _severidade
    lim = mcur.cfg()["publicacao"]["severidade"]
    assert [_severidade(v, lim) for v in (95, 80, 79.9, 60, 45, 3)] == \
        ["critical", "critical", "high", "high", "medium", "low"]
    assert _id_risco("eolica:BACLA2X") == "eolica-bacla2x"
