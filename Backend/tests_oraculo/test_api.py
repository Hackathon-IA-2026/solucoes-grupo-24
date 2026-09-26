# -*- coding: utf-8 -*-
"""Contrato HTTP.

O teste mais importante desta suite e o do envelope: a ausencia de
`provenance` em qualquer rota e falha de contrato (RNF-04).
"""
from __future__ import annotations

import json
import math

import pytest

from oraculo import config
from oraculo.api import envelope

GET_ROUTES = [
    "/api/health",
    "/api/meta",
    "/api/catalog",
    "/api/series?area=SE",
    "/api/decomposition?area=SE&hours=48",
    "/api/forecast?area=SE&horizon=3h",
    "/api/profiles?area=SE",
    "/api/risk?horizon=d1",
    "/api/validation?area=SE",
    "/api/triangulation",
    "/api/provenance",
]


# ======================================================= envelope
@pytest.mark.parametrize("route", GET_ROUTES)
def test_toda_rota_devolve_envelope_com_proveniencia(client, route):
    r = client.get(route)
    assert r.status_code == 200, route
    body = r.json()
    assert body["ok"] is True
    assert "provenance" in body, "%s sem envelope de proveniencia" % route
    assert isinstance(body["provenance"], list)
    assert body["mode"] in ("live", "cache", "demo")
    assert body["generated_at"].endswith("Z")
    assert "data" in body


@pytest.mark.parametrize("route", GET_ROUTES)
def test_payload_nao_contem_nan(client, route):
    """NaN e aceito por json.dumps mas quebra JSON.parse no navegador."""
    raw = client.get(route).text
    assert "NaN" not in raw and "Infinity" not in raw, route
    json.loads(raw)


def test_modo_e_declarado_em_toda_resposta(client):
    body = client.get("/api/health").json()
    assert body["mode"] == "demo", "a suite roda no modo demonstrativo"
    assert any(config.DEMO_BANNER in n for n in body["notes"])


def test_notas_advertem_que_mmgd_e_estimada(client):
    notes = " ".join(client.get("/api/series?area=SE").json()["notes"]).lower()
    assert "estimad" in notes


# ======================================================= erros
def test_horizonte_invalido_devolve_400(client):
    r = client.get("/api/forecast?area=SE&horizon=42h")
    assert r.status_code == 400
    body = r.json()
    assert body["ok"] is False
    assert body["error"]["code"] == "BAD_REQUEST"


def test_area_desconhecida_cai_para_o_padrao(client):
    body = client.get("/api/series?area=XPTO").json()
    assert body["data"]["area"] == config.DEFAULT_AREA


def test_conjunto_inexistente_nao_quebra(client):
    r = client.get("/api/catalog/conjunto-que-nao-existe")
    assert r.status_code in (200, 404, 503)


def test_codigos_de_erro_mapeiam_status_http():
    assert envelope.status_for("BAD_REQUEST") == 400
    assert envelope.status_for("NOT_FOUND") == 404
    assert envelope.status_for("INSUFFICIENT_DATA") == 422
    assert envelope.status_for("UPSTREAM_UNAVAILABLE") == 503
    assert envelope.status_for("qualquer-coisa") == 500


def test_sanitize_converte_nan_em_null():
    out = envelope.sanitize({"a": float("nan"), "b": [1.0, math.inf], "c": "x"})
    assert out["a"] is None and out["b"][1] is None and out["c"] == "x"


def test_envelope_de_erro_tem_codigo_valido():
    e = envelope.error("CODIGO-INVENTADO", "msg")
    assert e["error"]["code"] == "INTERNAL"


# ======================================================= payloads
def test_forecast_respeita_ordem_dos_quantis(client):
    d = client.get("/api/forecast?area=SE&horizon=3h").json()["data"]
    for lo, mid, hi in zip(d["p10"], d["p50"], d["p90"]):
        if None in (lo, mid, hi):
            continue
        assert lo <= mid + 1e-6 <= hi + 1e-6


def test_forecast_expoe_baselines_skill_e_drivers(client):
    d = client.get("/api/forecast?area=SE&horizon=3h").json()["data"]
    assert "baseline_persistence" in d and "baseline_seasonal" in d
    assert "vs_persistence" in d["skill"]
    assert d["drivers"] and "group" in d["drivers"][0]
    assert d["loss"]["loss"].startswith("pinball")


def test_assimetria_pode_ser_desligada_pela_api(client):
    on = client.get("/api/forecast?area=SE&horizon=3h&asymmetric=1").json()["data"]
    off = client.get("/api/forecast?area=SE&horizon=3h&asymmetric=0").json()["data"]
    assert on["asymmetric"] is True and off["asymmetric"] is False
    assert on["loss"]["loss"] != off["loss"]["loss"]


def test_decomposition_verifica_a_identidade(client):
    d = client.get("/api/decomposition?area=SE&hours=48").json()["data"]
    assert d["identity_residual_max"] == pytest.approx(0.0, abs=1e-9)
    assert len(d["index"]) == len(d["carga_global"]) == len(d["mmgd_estimada"])


def test_series_alinha_indice_e_series(client):
    d = client.get("/api/series?area=SE&hours=72").json()["data"]
    n = len(d["index"])
    for k, v in d["series"].items():
        assert len(v) == n, "serie %s desalinhada" % k


def test_risk_devolve_probabilidade_e_motivo(client):
    d = client.get("/api/risk?horizon=d1").json()["data"]
    assert d["areas"], "o modo demo precisa produzir areas"
    for a in d["areas"]:
        assert 0.0 <= a["probability"] <= 1.0
        assert a["expected_mw"] >= 0.0
        assert 0.0 <= a["severity"] <= 1.0
        assert sum(a["reason_weights"].values()) == pytest.approx(1.0, abs=1e-3)


def test_risk_ordena_eventos_por_severidade(client):
    ev = client.get("/api/risk?horizon=d1").json()["data"]["events"]
    sev = [e["severity"] for e in ev]
    assert sev == sorted(sev, reverse=True)


def test_risk_eventos_trazem_evidencia_e_acoes(client):
    ev = client.get("/api/risk?horizon=d1").json()["data"]["events"]
    for e in ev[:3]:
        assert e["evidence"] and all(i["source"] for i in e["evidence"])
        assert e["recommended_actions"]


def test_risk_filtra_por_probabilidade_minima(client):
    todos = client.get("/api/risk?horizon=d1&min_probability=0").json()["data"]["events"]
    altos = client.get("/api/risk?horizon=d1&min_probability=0.99").json()["data"]["events"]
    assert len(altos) <= len(todos)


def test_validation_declara_ausencia_de_vazamento(client):
    d = client.get("/api/validation?area=SE").json()["data"]
    assert d["split"]["leakage_free"] is True
    assert len(d["horizons"]) == 3
    assert "asymmetry_effect" in d
    assert set(d["patamares"]) == set(config.PATAMARES)


def test_validation_traz_calibracao_por_horizonte(client):
    d = client.get("/api/validation?area=SE").json()["data"]
    for h in d["horizons"]:
        if h.get("calibration"):
            for c in h["calibration"]:
                assert 0.0 <= c["nominal"] <= 1.0


def test_profiles_traz_tres_dias_tipo(client):
    d = client.get("/api/profiles?area=SE").json()["data"]
    kinds = {t["kind"] for t in d["typedays"]}
    assert kinds == {"util", "sabado", "domingo_feriado"}
    assert d["clm_inputs"]
    assert "não são parâmetros do CLM" in d["note"].lower() or d["note"]


def test_triangulation_cobre_matriz_camadas_e_classes(client):
    d = client.get("/api/triangulation").json()["data"]
    assert len(d["layers"]) == 3
    assert len(d["matrix"]) == 4
    assert d["areas"]
    for a in d["areas"]:
        assert a["correction_factor"] >= 1.0 - 1e-9
        assert sum(a["matrix"].values()) == a["units_total"]


def test_catalog_lista_conjuntos_e_curadoria(client):
    d = client.get("/api/catalog").json()["data"]
    assert d["count"] >= len(d["curated"])
    assert d["curated"] and d["planned"] and d["external"]


def test_meta_expoe_pesos_e_patamares(client):
    d = client.get("/api/meta").json()["data"]
    assert d["areas"] and d["horizons"]
    assert "ponta_noturna" in d["weights"]
    assert d["weights"]["ponta_noturna"]["subestimacao"] > \
           d["weights"]["ponta_noturna"]["superestimacao"]


def test_provenance_expoe_manifesto_de_cache(client):
    d = client.get("/api/provenance").json()["data"]
    assert "cache" in d and "entries" in d and "reports" in d


def test_ingest_aceita_post(client):
    r = client.post("/api/ingest", json={"force": False})
    assert r.status_code == 200
    assert r.json()["data"]["areas_ready"]


# ======================================================= estaticos
def test_interface_e_servida_na_raiz(client):
    r = client.get("/legado")
    assert r.status_code == 200
    assert "O.R.A.C.U.L.O." in r.text


def test_interface_nao_referencia_cdn_externo(client):
    """RF-53: a aplicacao precisa carregar com a rede externa bloqueada."""
    html = client.get("/legado").text
    for needle in ("http://", "https://cdn", "unpkg", "jsdelivr", "googleapis"):
        if needle == "http://":
            continue
        assert needle not in html, "referencia externa encontrada: %s" % needle
    for asset in ("/css/oraculo.css", "/js/charts.js", "/js/api.js",
                  "/js/app.js", "/js/views/operacao.js"):
        assert client.get(asset).status_code == 200, asset
