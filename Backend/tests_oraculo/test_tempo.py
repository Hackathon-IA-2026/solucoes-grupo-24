# -*- coding: utf-8 -*-
"""Curva do pato pelo tempo: radiacao prevista x MMGD.

Sem rede. O modelo fotovoltaico, a calibracao e a regressao de sensibilidade
precisam recuperar valores conhecidos; o backtest precisa mostrar que o tempo
ajuda quando a carga depende dele.
"""
from __future__ import annotations

import ssl

import numpy as np
import pytest

from oraculo.tempo import clima as W
from oraculo.tempo import pato as P


def test_tls_valida_cadeia_e_nome():
    ctx = W.ssl_context()
    assert ctx.verify_mode == ssl.CERT_REQUIRED
    assert ctx.check_hostname is True
    if hasattr(ssl, "VERIFY_X509_STRICT"):
        assert not ctx.verify_flags & ssl.VERIFY_X509_STRICT


def test_earth2_declarado_indisponivel():
    st = {p["k"]: p for p in W.providers_status()}
    assert st["ecmwf_aifs025_single"]["available"] and st["ecmwf_aifs025_single"]["kind"] == "IA"
    assert not st["earth2"]["available"] and "GPU" in st["earth2"]["note"]


def test_pv_sem_sol_nao_gera_e_calor_reduz():
    cap, pr = np.array([100.0]), np.array([0.8])
    assert P.pv_mw(np.array([[0.0]]), np.array([[30.0]]), cap, pr)[0, 0] == 0
    frio = P.pv_mw(np.array([[1000.0]]), np.array([[10.0]]), cap, pr)[0, 0]
    quente = P.pv_mw(np.array([[1000.0]]), np.array([[35.0]]), cap, pr)[0, 0]
    assert frio > quente
    # 1000 W/m2 a 25 C de celula: P = C * PR
    ref = P.pv_mw(np.array([[1000.0]]), np.array([[-5.0]]), cap, pr)[0, 0]
    assert ref == pytest.approx(80.0, rel=1e-6)


def test_alinhamento_hora_seguinte():
    times = ["2026-01-01T%02d:00" % h for h in range(24)] + ["2026-01-02T00:00"]
    v = np.arange(25, dtype=float)
    d = P.to_daily(times, v, shift=1)
    assert d["2026-01-01"][10] == 11            # hora 10 do ONS <- rotulo 11


def test_celulas_preservam_a_potencia_total():
    mun = {"3550308": {"kw": 500_000.0}, "3509502": {"kw": 5_000.0},
           "4106902": {"kw": 200_000.0}}
    cen = {"3550308": [-23.5, -46.6], "3509502": [-22.9, -47.1], "4106902": [-25.4, -49.3]}
    pts = P.clusters(mun, cen, min_mw=20)
    assert sum(p["mw"] for p in pts) == pytest.approx(705.0)
    assert {p["ss"] for p in pts} == {"SE", "S"}


def _weather(ghi_scale, days):
    times, g, t = [], [], []
    for d in days:
        for h in range(24):
            times.append("%sT%02d:00" % (d, h))
            g.append(max(0.0, np.sin(np.pi * (h - 6) / 12)) * 900 * ghi_scale.get(d, 1.0))
            t.append(22 + 6 * max(0.0, np.sin(np.pi * (h - 6) / 12)))
    return {"time": times, "_": {"shortwave_radiation": [g], "temperature_2m": [t]}}


def test_calibracao_do_pr_reproduz_o_alvo():
    days = [str(np.datetime64("2026-01-01") + np.timedelta64(i, "D")) for i in range(30)]
    era = _weather({}, days)
    pts = [{"ss": "SE", "mw": 1000.0, "lat": -23.0, "lon": -46.0, "mun": 1}]
    pr = P.calibrate_pr(era, pts, {"SE": 150.0}, set(days))
    mm = P.mmgd_by_ss(era, "_", pts, pr)["SE"]
    mean = np.nanmean([mm[d] for d in days[:-1]])
    assert mean == pytest.approx(150.0, rel=0.02)


def test_sensibilidade_recupera_beta_e_gama():
    rng = np.random.default_rng(1)
    days = [str(np.datetime64("2026-01-05") + np.timedelta64(i, "D")) for i in range(84)]
    days = [d for d in days if P._is_regular(d)]
    sup, mm, tt = {s: {} for s in P.SUBS}, {s: {} for s in P.SUBS}, {s: {} for s in P.SUBS}
    h = np.arange(24)
    solar = np.clip(np.sin(np.pi * (h - 6) / 12), 0, None)
    for d in days:
        cloud = rng.uniform(0.3, 1.0)
        temp = 24 + 8 * solar * cloud + rng.normal(0, 0.3, 24)
        m = 10000 * solar * cloud
        base = 40000 + 5000 * np.sin(np.pi * (h - 4) / 16)
        for s in P.SUBS:
            sup[s][d] = base - 0.8 * m + 900 * (temp - 24) + rng.normal(0, 50, 24)
            mm[s][d], tt[s][d] = m, temp
    sens = P.fit_sensitivity(sup, mm, tt, days)
    assert sens["SE"]["beta"] == pytest.approx(0.8, abs=0.05)
    assert sens["SE"]["gamma"] == pytest.approx(900, rel=0.08)
    assert sens["SE"]["r2"] > sens["SE"]["r2_mmgd_only"]


def test_metricas_da_barriga_e_da_rampa():
    obs = np.full(24, 50000.0)
    obs[10:16] = 40000
    obs[18] = 60000
    fc = obs.copy()
    fc[12] = 38000
    m = P.day_metrics(fc, obs)
    assert m["err_min"] == pytest.approx(-2000)
    assert m["err_ramp"] == pytest.approx(2000)


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
    Service._tp_data = None
    Service._tp_job = {"state": "idle", "stage": "", "error": "", "started": 0.0}
    yield


def test_contrato_da_curva_do_pato(client):
    body = client.get("/api/tempo/pato").json()
    assert body["ok"] is True and isinstance(body["provenance"], list)
    d = body["data"]
    for k in ("points", "pr", "sensitivity", "metrics", "backtest_window",
              "backtest_sample", "operational", "providers", "premises"):
        assert k in d, k
    for ss in ("SIN", "SE", "S", "NE", "N"):
        dia = d["operational"][ss][0]
        for k in ("ensemble", "low", "high", "mmgd", "min_mw", "min_hour", "ramp_mw"):
            assert k in dia, (ss, k)
        assert len(dia["ensemble"]) == 24
        assert 10 <= dia["min_hour"] <= 15


def test_status_e_reconstrucao_no_demo(client):
    assert client.get("/api/tempo/status").json()["data"]["state"] == "ready"
    assert client.post("/api/tempo/reconstruir").status_code == 400
