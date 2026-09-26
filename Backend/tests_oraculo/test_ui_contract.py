# -*- coding: utf-8 -*-
"""Contrato entre a interface e a API.

Cada painel de `web/js/views/*.js` consome um conjunto explicito de campos.
Este modulo declara esse conjunto e falha se a API parar de entrega-lo: e a
rede de seguranca que substitui o teste manual de tela.

Tambem faz checagem estatica dos arquivos da interface (balanceamento de
delimitadores e ausencia de referencia a CDN), porque o ambiente-alvo nao tem
runtime JavaScript disponivel.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from oraculo.config import WEB_DIR

# ------------------------------------------------------------------ contrato
# rota -> campos de primeiro nivel de `data` que a interface le
CONTRACT: dict[str, list[str]] = {
    "/api/meta": [
        "app", "subtitle", "team", "version", "areas", "horizons",
        "patamares", "weights", "quantiles", "sources", "demo_banner",
    ],
    "/api/health": [
        "version", "mode", "network", "cache_entries", "cache_bytes",
        "areas_ready", "datasets", "sources",
    ],
    "/api/series?area=SE&hours=72": [
        "area", "area_name", "index", "units", "gaps", "series", "mmgd",
    ],
    "/api/decomposition?area=SE&hours=72": [
        "area", "index", "carga_global", "mmgd_estimada", "carga_supervisionada",
        "mmgd_share", "cloud_factor", "ghi_norm", "identity_residual_max",
        "mmgd_share_peak", "min_supervised_mw", "min_supervised_at",
        "daily_amplitude_mw", "max_ramp_mw_h", "clm_inputs", "mmgd",
    ],
    "/api/forecast?area=SE&horizon=3h": [
        "area", "horizon", "asymmetric", "index", "observed", "p10", "p50",
        "p90", "baseline_persistence", "baseline_seasonal", "metrics",
        "by_patamar", "calibration", "skill", "drivers", "loss", "train",
    ],
    "/api/profiles?area=SE": ["area", "area_name", "typedays", "clm_inputs", "note"],
    "/api/risk?horizon=d1": ["horizon", "level", "areas", "events", "model",
                             "reasons", "origins"],
    "/api/validation?area=SE": [
        "area", "split", "asymmetric", "horizons", "series",
        "asymmetry_effect", "baseline_labels", "patamares", "weights",
    ],
    "/api/triangulation": ["areas", "layers", "matrix", "classes", "sample", "note"],
    "/api/catalog": ["count", "packages", "curated", "planned", "external",
                     "reasons", "origins", "cache"],
    "/api/provenance": ["cache", "entries", "bundle", "reports", "mode"],
}


@pytest.mark.parametrize("route,fields", sorted(CONTRACT.items()))
def test_api_entrega_os_campos_que_a_interface_consome(client, route, fields):
    data = client.get(route).json()["data"]
    missing = [f for f in fields if f not in data]
    assert not missing, "%s nao entregou: %s" % (route, missing)


# ---------------------------------------------- estruturas aninhadas lidas
def test_metricas_de_previsao_tem_os_campos_da_tabela(client):
    d = client.get("/api/forecast?area=SE&horizon=3h").json()["data"]
    for k in ("mae", "rmse", "mape", "bias", "ramp_mae_mw_h", "n"):
        assert k in d["metrics"], k
    for k in ("vs_persistence", "vs_seasonal"):
        assert k in d["skill"], k
    for g in d["drivers"]:
        assert "group" in g and "weight" in g
    assert "loss" in d["loss"] and "weights_by_patamar" in d["loss"]
    for k in ("train_rows", "test_rows", "cut_at", "leakage_free"):
        assert k in d["train"], k


def test_patamares_da_previsao_batem_com_a_configuracao(client):
    from oraculo.config import PATAMARES
    d = client.get("/api/forecast?area=SE&horizon=3h").json()["data"]
    assert set(d["by_patamar"]) == set(PATAMARES)


def test_evento_de_risco_tem_tudo_que_o_cartao_de_alerta_mostra(client):
    events = client.get("/api/risk?horizon=d1").json()["data"]["events"]
    assert events
    for e in events[:3]:
        for k in ("id", "area", "subsystem", "point_of_connection", "probability",
                  "expected_mw", "severity", "reason", "reason_label",
                  "reason_weights", "patamar", "window", "peak_hour",
                  "evidence", "recommended_actions"):
            assert k in e, k
        for ev in e["evidence"]:
            assert set(ev) >= {"label", "value", "source"}


def test_area_de_risco_tem_serie_horaria_para_o_grafico(client):
    areas = client.get("/api/risk?horizon=d1").json()["data"]["areas"]
    for a in areas[:3]:
        assert len(a["hourly_index"]) == len(a["hourly_probability"])
        for k in ("history", "criticality", "window", "auc_oos"):
            assert k in a, k
        for k in ("occurrence_rate", "total_cut_gwh", "peak_cut_mw",
                  "threshold_mw", "reason_shares", "hours"):
            assert k in a["history"], k


def test_perfil_por_dia_tipo_tem_as_series_do_grafico(client):
    for td in client.get("/api/profiles?area=SE").json()["data"]["typedays"]:
        for k in ("kind", "label", "hours", "carga_p10", "carga_p50",
                  "carga_p90", "mmgd_p50", "samples"):
            assert k in td, k
        n = len(td["hours"])
        for k in ("carga_p10", "carga_p50", "carga_p90", "mmgd_p50", "samples"):
            assert len(td[k]) == n, k


def test_horizonte_de_validacao_tem_o_que_as_tabelas_mostram(client):
    d = client.get("/api/validation?area=SE").json()["data"]
    for h in d["horizons"]:
        for k in ("horizon", "steps", "mae", "rmse", "mape", "bias", "pinball",
                  "interval_width_mw", "ramp_mae_mw_h", "by_patamar",
                  "calibration", "baselines", "skill"):
            assert k in h, k
        for name in ("persistencia", "sazonal_diario", "sazonal_semanal"):
            assert name in h["baselines"], name
            assert "label" in h["baselines"][name]
    for k in ("assimetrica", "simetrica"):
        assert k in d["asymmetry_effect"], k


def test_serie_de_teste_do_painel_de_validacao(client):
    s = client.get("/api/validation?area=SE").json()["data"]["series"]
    assert "3h" in s
    blk = s["3h"]
    n = len(blk["index"])
    for k in ("observed", "p10", "p50", "p90", "persistencia"):
        assert len(blk[k]) == n, k


def test_triangulacao_tem_o_que_a_matriz_e_as_tabelas_mostram(client):
    d = client.get("/api/triangulation").json()["data"]
    for a in d["areas"]:
        for k in ("area", "units_total", "matrix", "capacity_declared_mw",
                  "capacity_corrected_mw", "capacity_unhomologated_mw",
                  "correction_factor", "coverage", "implied_capacity_mwp"):
            assert k in a, k
    for l in d["layers"]:
        assert set(l) >= {"layer", "name", "source", "question", "cadence",
                          "limitation"}
    for u in d["sample"]:
        assert set(u) >= {"unit_id", "area", "capacity_kwp", "detected",
                          "in_bdgd", "in_aneel", "classification", "label",
                          "counts_in_correction"}
    for key, c in d["classes"].items():
        assert set(c) >= {"label", "note", "counts"}


def test_catalogo_tem_o_que_o_explorador_lista(client):
    d = client.get("/api/catalog").json()["data"]
    for p in d["packages"][:5]:
        assert "id" in p and "curated" in p
    for c in d["curated"]:
        for k in ("package", "title", "role", "granularity", "lag_note",
                  "fields", "approx_bytes"):
            assert k in c, k
    for e in d["external"]:
        assert set(e) >= {"name", "role", "cadence", "status"}


def test_relatorio_de_ingestao_tem_as_colunas_da_tabela(client):
    for r in client.get("/api/provenance").json()["data"]["reports"]:
        for k in ("dataset", "resource", "mode", "rows", "bytes_read",
                  "discarded_bad_time", "discarded_short_line", "duplicates",
                  "error"):
            assert k in r, k


# ------------------------------------------------- checagem estatica do front
JS_FILES = [
    "js/charts.js", "js/api.js", "js/app.js",
    "js/views/operacao.js", "js/views/analise.js", "js/views/confianca.js",
    "js/views/mapa.js",
]

VIEW_FILES = ("js/views/operacao.js", "js/views/analise.js",
              "js/views/confianca.js", "js/views/mapa.js",
              "js/views/clm.js", "js/views/fronteira.js",
              "js/views/bess.js", "js/views/projecao.js",
              "js/views/pato.js")

PANEL_IDS = {"operacao", "risco", "curtailment", "perfis", "triangulacao",
             "validacao", "dados", "mapa", "visao", "classes", "clm",
             "fronteira", "correlacao", "bess", "bessmetodo",
             "projecao", "pato"}


def _strip_js(src: str) -> str:
    """Remove comentarios e literais de string, para contar delimitadores."""
    out, i, n = [], 0, len(src)
    while i < n:
        c = src[i]
        nxt = src[i + 1] if i + 1 < n else ""
        if c == "/" and nxt == "/":
            i = src.find("\n", i)
            if i < 0:
                break
            continue
        if c == "/" and nxt == "*":
            j = src.find("*/", i + 2)
            i = n if j < 0 else j + 2
            continue
        if c in "\"'`":
            quote = c
            i += 1
            while i < n:
                if src[i] == "\\":
                    i += 2
                    continue
                if src[i] == quote:
                    i += 1
                    break
                i += 1
            out.append('""')
            continue
        out.append(c)
        i += 1
    return "".join(out)


@pytest.mark.parametrize("name", JS_FILES)
def test_arquivos_da_interface_existem_e_estao_balanceados(name):
    path = WEB_DIR / name
    assert path.exists(), "arquivo ausente: %s" % name
    code = _strip_js(path.read_text(encoding="utf-8"))
    pairs = {"(": ")", "[": "]", "{": "}"}
    closing = {v: k for k, v in pairs.items()}
    stack: list[str] = []
    for ch in code:
        if ch in pairs:
            stack.append(ch)
        elif ch in closing:
            assert stack, "%s: fechamento %r sem abertura" % (name, ch)
            assert stack.pop() == closing[ch], "%s: delimitador cruzado em %r" % (name, ch)
    assert not stack, "%s: %d delimitadores abertos" % (name, len(stack))


@pytest.mark.parametrize("name", JS_FILES + ["index.html"])
def test_interface_nao_referencia_recurso_externo(name):
    path = (WEB_DIR / name).resolve()
    text = path.read_text(encoding="utf-8")
    # Referencia a documentacao do ONS em atributo href e permitida; o que nao
    # pode existir e carregamento de script, folha de estilo ou fonte externa.
    for pattern in (r"""<script[^>]+src=['"]https?://""",
                    r"""<link[^>]+href=['"]https?://(?!www\.ons|dados\.ons)""",
                    r"cdn\.jsdelivr", r"unpkg\.com", r"fonts\.googleapis",
                    r"cdnjs\.cloudflare"):
        assert not re.search(pattern, text, re.I), \
            "%s carrega recurso externo (%s)" % (path.name, pattern)


def test_views_registram_todos_os_paineis():
    """Os identificadores da navegacao precisam existir como views."""
    app_js = (WEB_DIR / "js/app.js").read_text(encoding="utf-8")
    nav_ids = set(re.findall(r'\{\s*id:\s*"([a-z]+)"', app_js))
    assert nav_ids == PANEL_IDS, nav_ids
    registered: set[str] = set()
    for name in VIEW_FILES:
        src = (WEB_DIR / name).read_text(encoding="utf-8")
        registered |= set(re.findall(r"V\.([a-z]+)\s*=\s*\{", src))
    assert nav_ids <= registered, "views nao registradas: %s" % (nav_ids - registered)


def test_cada_painel_declara_titulo_e_renderizador():
    for name in VIEW_FILES:
        src = (WEB_DIR / name).read_text(encoding="utf-8")
        for block in re.findall(r"V\.[a-z]+\s*=\s*\{(.*?)\n  \};", src, re.S):
            assert "title:" in block
            assert "async render(" in block


def test_paineis_novos_nao_quebram_os_antigos():
    """As views originais seguem registradas nos seus arquivos de origem."""
    originais = {
        "js/views/operacao.js": {"operacao", "risco"},
        "js/views/analise.js": {"curtailment", "perfis", "triangulacao"},
        "js/views/confianca.js": {"validacao", "dados"},
        "js/views/mapa.js": {"mapa", "visao", "classes"},
        "js/views/clm.js": {"clm"},
    }
    for name, expected in originais.items():
        src = (WEB_DIR / name).read_text(encoding="utf-8")
        found = set(re.findall(r"V\.([a-z]+)\s*=\s*\{", src))
        assert found == expected, "%s registra %s, esperado %s" % (name, found, expected)


def test_clm_le_a_lista_de_subestacoes_pela_chave_certa():
    """O payload de subestacoes entrega a lista em `rows`.

    A primeira versao da view leu `substations`, que nao existe: o seletor
    ficava vazio sem erro visivel. Este teste amarra o contrato.
    """
    src = (WEB_DIR / "js/views/clm.js").read_text(encoding="utf-8")
    assert "subsBody.data.rows" in src
    assert "data.substations" not in src


def test_html_carrega_os_scripts_na_ordem_de_dependencia():
    html = (WEB_DIR / "index.html").read_text(encoding="utf-8")
    order = re.findall(r'<script src="/js/([^"]+)"', html)
    assert order[0] == "charts.js", "charts.js precisa vir antes das views"
    assert order.index("app.js") < order.index("views/operacao.js")
    assert "App.boot()" in html


def test_arquivos_da_interface_exigem_revalidacao(client):
    """Sem isso, o navegador serve o app.js antigo e painel novo nao aparece."""
    for rota in ("/js/app.js", "/js/views/fronteira.js", "/css/oraculo.css"):
        r = client.get(rota)
        assert r.status_code == 200, rota
        assert "no-cache" in r.headers.get("cache-control", ""), rota
