"""Modelos de carga: split cronológico, treino sem ver o teste, quantis em ordem, métricas."""
import copy

import numpy as np
import pandas as pd
import pytest

from src.models import carga as mc
from src.models import metricas as mt


def test_lightgbm_treina():
    """Fit mínimo: a 4.7.0 no Windows dava access violation na DLL (pyproject fixa <4.7)."""
    import lightgbm as lgb
    rng = np.random.default_rng(0)
    m = lgb.LGBMRegressor(objective="quantile", alpha=0.9, n_estimators=5, verbose=-1)
    m.fit(rng.random((200, 3)), rng.random(200))
    assert m.predict(rng.random((3, 3))).shape == (3,)


def test_split_da_config_e_cronologico():
    sp = mc.split()
    idx = pd.date_range("2019-01-01", "2026-12-31", freq="30min")
    for h in mc.cfg()["horizontes"].values():
        treino, teste = idx[sp.treino(idx)], idx[sp.teste(idx, h)]
        # todo alvo de treino é anterior a toda EMISSÃO de teste
        assert treino.max() < (teste - h * pd.Timedelta("30min")).min()


def test_split_fora_de_ordem_e_recusado(monkeypatch):
    c = copy.deepcopy(mc.cfg())
    c["split"]["inicio_teste"] = c["split"]["fim_treino"]
    monkeypatch.setattr(mc, "cfg", lambda: c)
    with pytest.raises(ValueError, match="split inválido"):
        mc.split()


def test_correcao_conformal_abre_a_banda_ate_a_cobertura():
    rng = np.random.default_rng(0)
    real = rng.normal(0, 1, 5000)
    estreita = np.column_stack([np.full(5000, -0.1), np.zeros(5000), np.full(5000, 0.1)])
    corr = mc.correcao_conformal(estreita, real, 0.8)
    cobre = np.mean((estreita[:, 0] - corr <= real) & (real <= estreita[:, 2] + corr))
    assert corr > 0 and cobre == pytest.approx(0.8, abs=0.01)
    # banda larga demais -> correção negativa (fecha)
    larga = np.column_stack([np.full(5000, -5.0), np.zeros(5000), np.full(5000, 5.0)])
    assert mc.correcao_conformal(larga, real, 0.8) < 0


def test_ordenar_quantis():
    q = mc.ordenar_quantis(np.array([[3.0, 1.0, 2.0], [1.0, 2.0, 3.0]]))
    assert (np.diff(q, axis=1) >= 0).all()


# --------------------------------------------------------------------------- ponta a ponta
def _dados_sinteticos(ruido_teste=False):
    idx = pd.date_range("2025-01-01", "2025-03-31 23:30", freq="30min", name="timestamp")
    futuro = pd.date_range(idx[-1] + pd.Timedelta("30min"), periods=48, freq="30min")
    grade = idx.append(futuro).rename("timestamp")
    rng = np.random.default_rng(1)
    hora = grade.hour + grade.minute / 60
    base = 1000 + 200 * np.sin(2 * np.pi * (hora - 6) / 24)
    y = pd.DataFrame({s: base * k + rng.normal(0, 10, len(grade))
                      for s, k in zip(("SE", "S", "NE", "N"), (4, 2, 1.5, 1))}, index=grade)
    y.loc[futuro] = np.nan
    if ruido_teste:  # "futuro" do treino totalmente diferente
        y.loc[y.index >= "2025-03-01"] *= 3
    y["SIN"] = y[["SE", "S", "NE", "N"]].sum(axis=1, min_count=4)
    mmgd = y * 0.05
    cal = pd.DataFrame({"hora_decimal": hora, "dia_semana_efetivo": grade.dayofweek, "eh_feriado": 0,
                        "dia_dos_pais": 0, "mes": grade.month, "dia_do_ano": grade.dayofyear,
                        "patamar": 0}, index=grade)
    return mc.Dados(y=y, mmgd=mmgd, cal=cal)


@pytest.fixture
def cfg_pequena(monkeypatch, tmp_path):
    c = copy.deepcopy(mc.cfg())
    c["split"] = {"inicio_treino": "2025-01-08 00:00", "fim_treino": "2025-02-28 23:30",
                  "inicio_teste": "2025-03-01 00:00"}
    c["lightgbm"] = {**c["lightgbm"], "n_estimators": 20, "n_jobs": 1}
    c["calibracao_dias"] = 14
    monkeypatch.setattr(mc, "cfg", lambda: c)
    monkeypatch.setattr(mc, "DIR", tmp_path)
    monkeypatch.setattr(mc, "ARQ_MODELOS", tmp_path / "m.joblib")
    monkeypatch.setattr(mc, "ARQ_PREVISOES", tmp_path / "p.parquet")
    return c


def test_previsoes_sao_todas_fora_da_amostra(cfg_pequena):
    dados = _dados_sinteticos()
    mc.treinar(dados)
    mc.prever(dados)
    prev = mc.ler_previsoes()
    assert (prev["emissao"] >= pd.Timestamp("2025-03-01")).all()
    assert (prev["emissao"] <= dados.ultimo_dado).all()
    assert (prev["p10"] <= prev["p50"]).all() and (prev["p50"] <= prev["p90"]).all()
    assert set(prev["modelo"]) == set(mc.MODELOS_TODOS)
    # o D+1 chega a 48 passos além do último dado (previsão "do agora" para frente)
    d1 = prev[(prev["serie"] == "SIN") & (prev["horizonte"] == "D+1") & (prev["modelo"] == "lightgbm")]
    assert d1["alvo"].max() == dados.ultimo_dado + 48 * pd.Timedelta("30min")
    assert d1[d1["alvo"] > dados.ultimo_dado]["real"].isna().all()


def test_treino_nao_depende_do_periodo_de_teste(cfg_pequena):
    """Mudar tudo a partir do início do teste não pode mudar nada do que foi treinado."""
    import joblib
    mc.treinar(_dados_sinteticos())
    a = joblib.load(mc.ARQ_MODELOS)
    mc.treinar(_dados_sinteticos(ruido_teste=True))
    b = joblib.load(mc.ARQ_MODELOS)
    for k in a["residuos"]:
        np.testing.assert_allclose(a["residuos"][k], b["residuos"][k])
    x = np.random.default_rng(2).normal(1000, 100, (5, len(a["features"][("SIN", "D+1")])))
    for k, modelos in a["lightgbm"].items():
        for q, m in modelos.items():
            np.testing.assert_allclose(m.predict(x), b["lightgbm"][k][q].predict(x))


def test_prever_recusa_modelo_de_outro_split(cfg_pequena):
    dados = _dados_sinteticos()
    mc.treinar(dados)
    cfg_pequena["split"] = {**cfg_pequena["split"], "fim_treino": "2025-02-27 23:30"}
    with pytest.raises(RuntimeError, match="outro split"):
        mc.prever(dados)


# --------------------------------------------------------------------------- métricas
def test_metricas_basicas():
    g = pd.DataFrame({"real": [100.0, 200.0], "p10": [90.0, 150.0], "p50": [110.0, 190.0],
                      "p90": [120.0, 195.0]})
    m = mt.basicas(g)
    assert m["mae"] == 10 and m["rmse"] == 10 and m["vies"] == 0
    assert m["mape"] == pytest.approx(100 * (0.1 + 0.05) / 2)
    assert m["cobertura"] == 50  # 200 fica acima do P90 = 195
    # pinball do P50 = 0,5 × |erro| = 5; P10: (0,1×10 + 0,1×50)/2 = 3; P90: (0,1×20 + 0,9×5)/2 = 3,25
    assert m["pinball"] == pytest.approx((3 + 5 + 3.25) / 3)


def test_extremos_diarios_so_em_dias_completos():
    t = pd.date_range("2025-01-01", periods=48 + 10, freq="30min")
    hora = t.hour
    pat = np.where((hora >= 9) & (hora < 16), "minima_diurna",
                   np.where((hora >= 19) & (hora < 22), "ponta_noturna", "outro"))
    real = np.where(pat == "minima_diurna", 50.0, np.where(pat == "ponta_noturna", 150.0, 100.0))
    p = pd.DataFrame({"serie": "SIN", "horizonte": "D+1", "modelo": "m", "alvo": t, "real": real,
                      "p50": real + np.where(pat == "ponta_noturna", 10.0, 0.0),
                      "patamar": pat, "data": t.normalize()})
    e = mt.extremos_diarios(p).iloc[0]
    assert e["erro_pico"] == 10 and e["erro_vale"] == 0 and e["erro_rampa"] == 10
