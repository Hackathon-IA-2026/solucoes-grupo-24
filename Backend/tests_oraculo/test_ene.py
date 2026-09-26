# -*- coding: utf-8 -*-
"""Projecao do corte por razao energetica e BESS futuro.

O ajuste precisa RECUPERAR parametros conhecidos numa serie sintetica, e a
projecao precisa respeitar a fisica: mais MMGD -> mais corte; mais
flexibilidade -> menos corte; a carga liquida usa a geracao POTENCIAL.
"""
from __future__ import annotations

import numpy as np
import pytest

from oraculo.ene import modelo as M
from oraculo.ene import series as S


def _synthetic(alpha=0.7, theta_base=40000.0, days=400, seed=3):
    rng = np.random.default_rng(seed)
    h = np.arange(24)
    solar = np.clip(np.sin(np.pi * (h - 6) / 12), 0, None)
    bal, es, allc, mm = {}, {}, {}, {}
    d0 = np.datetime64("2024-04-01")
    theta = {m: theta_base + 2000 * np.cos(2 * np.pi * (m - 3) / 12) for m in range(1, 13)}
    for i in range(days):
        d = str(d0 + i)
        m = int(d[5:7])
        sup = 60000 + 6000 * np.sin(np.pi * (h - 4) / 16) + rng.normal(0, 300, 24)
        vre = 12000 + 26000 * solar * (0.7 + 0.5 * rng.random())
        cut = alpha * np.maximum(0, theta[m] - (sup - vre))
        # o balanco registra a geracao VERIFICADA, ja descontado o corte
        bal[d] = {"sup": sup, "eol": np.full(24, 12000.0) - cut * 0.2,
                  "sol": vre - 12000.0 - cut * 0.8}
        es[d] = cut
        allc[d] = cut
        mm[d] = 8000 * solar
    return bal, es, allc, mm, theta


def test_ajuste_recupera_alfa_e_teta():
    bal, es, allc, _, theta = _synthetic()
    X = M.assemble(sorted(bal), bal, es, allc)
    p = M.fit(X)
    assert p["alpha"] == pytest.approx(0.7, abs=0.051)
    for m in (4, 7, 10):
        assert p["theta"][m] == pytest.approx(theta[m], rel=0.03)


def test_carga_liquida_usa_geracao_potencial():
    bal, es, allc, _, _ = _synthetic()
    X = M.assemble(sorted(bal), bal, es, allc)
    # potencial = verificada + cortada
    assert np.allclose(X["vre_pot"], X["vre_obs"] + X["cut_all"])


def test_backtest_tem_as_metricas():
    bal, es, allc, _, _ = _synthetic(days=520)
    X = M.assemble(sorted(bal), bal, es, allc)
    bt = M.backtest(X, "2025-04")
    for k in ("mape_model", "mape_naive", "hourly_corr", "test_bias", "monthly"):
        assert k in bt
    assert bt["hourly_corr"] > 0.95
    assert bt["mape_model"] < 0.10


def test_mais_mmgd_mais_corte_e_mais_flexibilidade_menos_corte():
    bal, es, allc, mm, _ = _synthetic()
    days = sorted(bal)
    X = M.assemble(days, bal, es, allc, mm)
    p = M.fit(X)
    base = M.project(X, p, 1.10, 1.0, 1.04, 0.0, 2).sum()
    com_mmgd = M.project(X, p, 1.10, 1.69, 1.04, 0.0, 2).sum()
    com_flex = M.project(X, p, 1.10, 1.69, 1.04, 2.0, 2).sum()
    assert com_mmgd > base
    assert com_flex < com_mmgd


def test_bess_no_sin_pelo_ciclo_marginal():
    bal, es, allc, _, _ = _synthetic()
    X = M.assemble(sorted(bal), bal, es, allc)
    b = M.bess_potential(X["es"])
    assert b["p_gw"] > 0 and b["hours"] in (2.0, 4.0, 6.0)
    assert b["marginal_cycles"] >= 200
    assert 0 < b["delivered_twh"] < b["ene_twh"]


def test_taxa_de_crescimento_da_serie_acumulada():
    months = ["2024-%02d" % m for m in range(1, 13)] + ["2025-%02d" % m for m in range(1, 13)]
    cum = [10.0 + k for k in range(24)]
    g = S.growth_rate(months, cum, "2025-12")
    assert g == pytest.approx(33.0 / 21.0 - 1)
    assert S.growth_rate(months, cum, "2024-06") is None


def test_historico_comeca_quando_cada_fonte_e_publicada():
    w = S.history_months((2024, 5))
    assert ("eol", 2021, 10) in w and ("fv", 2024, 4) in w
    assert ("fv", 2024, 3) not in w


# ------------------------------------------------------------ API
@pytest.fixture(autouse=True)
def _modo_demo(request):
    if "client" not in request.fixturenames:
        yield
        return
    from oraculo.api.service import SERVICE, Service
    if SERVICE.mode() != "demo":
        SERVICE.ensure(force_demo=True, refresh=True)
        Service._registry = None
    Service._ene_data = None
    Service._ene_cache = {}
    Service._ene_job = {"state": "idle", "stage": "", "done": 0, "total": 0,
                        "error": "", "started": 0.0}
    Service._bs_months = Service._bs_rows = None
    Service._bs_meta = {}
    yield


def test_contrato_da_projecao(client):
    body = client.get("/api/ene/projecao").json()
    assert body["ok"] is True and isinstance(body["provenance"], list)
    d = body["data"]
    for k in ("history", "reference", "backtest", "rates", "scenarios", "years",
              "duck_ref", "mmgd_series", "allocation", "premises", "params"):
        assert k in d, k
    nomes = [s["name"] for s in d["scenarios"]]
    assert nomes == ["PLAN 2026-2030 (2ª RQ)", "PAR/PEL 2025", "tendência observada"]
    for s in d["scenarios"]:
        assert len(s["years"]) == len(d["years"])
        for y in s["years"]:
            assert "ene_sem_mmgd_twh" in y and "bess" in y


def test_cenario_personalizado_pela_query(client):
    d = client.get("/api/ene/projecao?g_mmgd=0.4&flex_gw=1").json()["data"]
    p = d["scenarios"][-1]
    assert p["name"] == "personalizado"
    assert p["params"]["g_mmgd"] == pytest.approx(0.4)
    assert p["params"]["flex_gw"] == pytest.approx(1.0)


def test_referencia_segue_a_trajetoria_ano_a_ano_do_plan(client):
    from oraculo import config
    d = client.get("/api/ene/projecao").json()["data"]
    ref = d["scenarios"][0]
    plan = config.ENE["plan"]
    b0 = plan["ano_base"]
    for k, y in enumerate(ref["years"], start=1):
        ano = b0 + k
        assert y["mult"]["load"] == pytest.approx(
            plan["carga_global_mwmed"][ano] / plan["carga_global_mwmed"][b0], abs=1e-4)
        assert y["mult"]["mmgd"] == pytest.approx(
            plan["mmgd_mwmed"][ano] / plan["mmgd_mwmed"][b0], abs=1e-4)
    # o nivel da MMGD horaria passa a ser o oficial do ano base
    assert d["reference"]["mmgd_plan_mwmed"] == plan["mmgd_mwmed"][b0]


def test_multiplicadores_trajetoria_ou_taxa():
    s_traj = {"traj": {"vre": [1.1, 1.2], "mmgd": [1.3, 1.6], "load": [1.05, 1.1]}}
    assert M.multipliers(s_traj, 2) == (1.2, 1.6, 1.1)
    s_taxa = {"g_vre": 0.1, "g_mmgd": 0.0, "g_load": 0.02}
    mv, mm, ml = M.multipliers(s_taxa, 2)
    assert mv == pytest.approx(1.21) and mm == 1.0 and ml == pytest.approx(1.0404)


def test_status_pronto_no_demo(client):
    assert client.get("/api/ene/status").json()["data"]["state"] == "ready"
