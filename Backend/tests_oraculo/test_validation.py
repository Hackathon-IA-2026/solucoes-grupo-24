# -*- coding: utf-8 -*-
"""Backtest cronologico, metricas e calibracao.

O teste central desta suite e o de vazamento: divisao aleatoria inflaria a
acuracia pelas variaveis de defasagem e invalidaria todo o resto.
"""
from __future__ import annotations

import numpy as np
import pytest

from oraculo.core.timeutils import hour_of_day
from oraculo.validation import backtest, metrics


# ======================================================= corte cronologico
def test_corte_e_cronologico_sem_vazamento(sin_state):
    fm = sin_state["fm"]
    split = backtest.chronological_split(fm.index, fm.valid)
    assert len(split.train_idx) > 0 and len(split.test_idx) > 0
    assert int(split.train_idx.max()) < int(split.test_idx.min())
    assert split.leakage_free is True


def test_embargo_afasta_treino_do_teste(sin_state):
    fm = sin_state["fm"]
    a = backtest.chronological_split(fm.index, fm.valid, embargo=0)
    b = backtest.chronological_split(fm.index, fm.valid, embargo=24)
    assert int(b.test_idx.min()) - int(a.test_idx.min()) == 24


def test_split_degrada_sem_dados_suficientes():
    idx = np.arange(5).astype("datetime64[s]")
    split = backtest.chronological_split(idx, np.ones(5, dtype=bool))
    assert len(split.test_idx) == 0


def test_shift_target_alinha_o_alvo_no_futuro():
    y = np.arange(6.0)
    s = backtest.shift_target(y, 2)
    assert s[0] == 2.0 and s[3] == 5.0
    assert np.isnan(s[-2:]).all()


def test_shift_target_zero_e_identidade():
    y = np.arange(4.0)
    assert backtest.shift_target(y, 0).tolist() == y.tolist()


# ======================================================= execucao completa
def test_backtest_devolve_todos_os_horizontes(sin_state):
    res = backtest.run(sin_state["fm"], sin_state["dec"].carga_supervisionada,
                       keep_series=False)
    assert res["split"]["leakage_free"] is True
    assert len(res["horizons"]) == 3
    for h in res["horizons"]:
        assert h["horizon"] in ("30min", "3h", "d1")
        assert h["mae"] > 0
        assert "by_patamar" in h
        assert "persistencia" in h["baselines"]
        assert "persistencia" in h["skill"]


def test_backtest_supera_persistencia_em_algum_horizonte(sin_state):
    res = backtest.run(sin_state["fm"], sin_state["dec"].carga_supervisionada,
                       keep_series=False)
    skills = [h["skill"].get("persistencia") for h in res["horizons"]]
    skills = [s for s in skills if s is not None]
    assert any(s > 0 for s in skills), (
        "o modelo precisa ganhar do baseline em pelo menos um horizonte: %s" % skills)


def test_comparacao_de_assimetria_reporta_os_dois_regimes(sin_state):
    out = backtest.compare_asymmetry(sin_state["fm"],
                                     sin_state["dec"].carga_supervisionada, "3h")
    assert set(out.keys()) == {"assimetrica", "simetrica"}
    for k in out:
        assert "mae" in out[k] and "by_patamar" in out[k]


def test_backtest_e_deterministico(sin_state):
    a = backtest.run(sin_state["fm"], sin_state["dec"].carga_supervisionada,
                     horizons={"3h": 3}, keep_series=False)
    b = backtest.run(sin_state["fm"], sin_state["dec"].carga_supervisionada,
                     horizons={"3h": 3}, keep_series=False)
    assert a["horizons"][0]["mae"] == b["horizons"][0]["mae"]


# ======================================================= metricas
def test_metricas_de_ponto_em_caso_perfeito():
    y = np.array([10.0, 20.0, 30.0])
    m = metrics.point_metrics(y, y)
    assert m["mae"] == 0 and m["rmse"] == 0 and m["mape"] == 0
    assert m["n"] == 3


def test_metricas_ignoram_nan():
    y = np.array([1.0, np.nan, 3.0])
    yhat = np.array([1.0, 5.0, 3.0])
    assert metrics.mae(y, yhat) == pytest.approx(0.0)
    assert metrics.point_metrics(y, yhat)["n"] == 2


def test_vies_tem_sinal_correto():
    y = np.array([10.0, 10.0])
    assert metrics.bias(y, np.array([12.0, 12.0])) == pytest.approx(2.0)
    assert metrics.bias(y, np.array([8.0, 8.0])) == pytest.approx(-2.0)


def test_erro_de_rampa_mede_a_diferenca_de_variacao():
    y = np.array([0.0, 10.0, 20.0])       # rampas observadas: 10 e 10
    yhat = np.array([0.0, 5.0, 25.0])     # rampas previstas:   5 e 20
    assert metrics.ramp_mae(y, yhat) == pytest.approx(7.5)


def test_erro_de_rampa_e_zero_quando_a_variacao_coincide():
    y = np.array([0.0, 10.0, 20.0])
    assert metrics.ramp_mae(y, y + 100.0) == pytest.approx(0.0)


def test_cobertura_de_quantil_aproxima_o_nominal():
    rng = np.random.default_rng(3)
    y = rng.normal(0, 1, 20000)
    q90 = np.full_like(y, 1.2816)
    assert metrics.coverage(y, q90, 0.9) == pytest.approx(0.9, abs=0.02)


def test_calibracao_reporta_desvio_em_pontos_percentuais():
    rng = np.random.default_rng(5)
    y = rng.normal(0, 1, 5000)
    preds = {0.1: np.full_like(y, -1.2816), 0.9: np.full_like(y, 1.2816)}
    cal = metrics.calibration(y, preds)
    assert len(cal) == 2
    for c in cal:
        assert abs(c["deviation_pp"]) < 4.0


def test_metricas_por_patamar_cobrem_as_faixas():
    idx = np.arange(np.datetime64("2026-01-01T00:00:00", "s"),
                    np.datetime64("2026-01-03T00:00:00", "s"),
                    np.timedelta64(1, "h"), dtype="datetime64[s]")
    y = np.linspace(100, 200, len(idx))
    out = metrics.by_patamar(y, y + 5.0, hour_of_day(idx))
    for p in ("minima_diurna", "rampa", "ponta_noturna"):
        assert out[p]["mae"] == pytest.approx(5.0)


def test_pinball_loss_e_zero_no_ajuste_perfeito():
    y = np.array([1.0, 2.0, 3.0])
    assert metrics.pinball_loss(y, {0.5: y}) == pytest.approx(0.0)


# ======================================================= classificacao
def test_roc_auc_separacao_perfeita():
    y = np.array([0, 0, 1, 1])
    assert metrics.roc_auc(y, np.array([0.1, 0.2, 0.8, 0.9])) == pytest.approx(1.0)


def test_roc_auc_aleatorio_fica_perto_de_meio():
    rng = np.random.default_rng(11)
    y = rng.integers(0, 2, 4000)
    auc = metrics.roc_auc(y, rng.random(4000))
    assert 0.45 < auc < 0.55


def test_roc_auc_indefinido_sem_as_duas_classes():
    assert np.isnan(metrics.roc_auc(np.zeros(5), np.random.random(5)))


def test_precisao_e_revocacao():
    y = np.array([1, 1, 0, 0])
    p = np.array([1, 0, 1, 0])
    r = metrics.precision_recall(y, p)
    assert r["tp"] == 1 and r["fp"] == 1 and r["fn"] == 1 and r["tn"] == 1
    assert r["precision"] == pytest.approx(0.5)
    assert r["recall"] == pytest.approx(0.5)


def test_brier_score():
    y = np.array([1.0, 0.0])
    assert metrics.brier(y, np.array([1.0, 0.0])) == pytest.approx(0.0)
    assert metrics.brier(y, np.array([0.0, 1.0])) == pytest.approx(1.0)
