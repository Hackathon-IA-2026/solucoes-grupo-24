# -*- coding: utf-8 -*-
"""Mapa Inteligente: classes de consumo, registro de subestacoes e rotas.

Desafio Radix + AXIA + Cepel. Verifica as duas respostas exigidas por
subestacao e que as abas anteriores seguem intactas.
"""
from __future__ import annotations

import numpy as np
import pytest

from oraculo.core.timeutils import hourly_grid
from oraculo.profiles import classes as C
from oraculo.substations import mapper, registry


# ================================================= perfis canonicos
def test_perfis_canonicos_somam_um():
    for k, prof in C.CANONICAL.items():
        assert len(prof) == 24
        assert float(prof.sum()) == pytest.approx(1.0, abs=1e-9), k


def test_residencial_tem_ponta_noturna():
    p = C.CANONICAL["residencial"]
    assert int(np.argmax(p)) in range(18, 22), "pico deveria cair na ponta"


def test_comercial_tem_plato_de_expediente():
    p = C.CANONICAL["comercial"]
    assert p[9:17].mean() > p[0:6].mean() * 3.0


def test_industrial_e_quase_plano():
    p = C.CANONICAL["industrial"]
    assert (p.max() - p.min()) / p.mean() < 0.30


def test_rural_bombeia_de_madrugada():
    p = C.CANONICAL["rural"]
    assert p[0:5].mean() > p[9:15].mean()


def test_assinatura_de_fim_de_semana_separa_comercial_de_industrial():
    assert C.WEEKEND_RATIO["comercial"] < C.WEEKEND_RATIO["industrial"]
    assert C.WEEKEND_RATIO["residencial"] > C.WEEKEND_RATIO["comercial"]


# ================================================= decomposicao NNLS
def _synthetic_load(mix: dict[str, float], days: int = 60,
                    weekend_effect: bool = True) -> tuple:
    """Constroi uma curva a partir de uma composicao conhecida."""
    idx = hourly_grid(np.datetime64("2026-01-01T00:00:00", "s"),
                      np.datetime64("2026-01-01T00:00:00", "s")
                      + np.timedelta64(days * 24 - 1, "h"))
    from oraculo.core.calendar_br import typeday_array
    from oraculo.core.timeutils import hour_of_day
    hod = hour_of_day(idx)
    kinds = typeday_array(idx)
    base = np.zeros(len(idx))
    for cls, w in mix.items():
        base += w * C.CANONICAL[cls][hod] * 1000.0
    if weekend_effect:
        ratio = sum(w * C.WEEKEND_RATIO[c] for c, w in mix.items())
        base = np.where(kinds == "domingo_feriado", base * ratio, base)
    return idx, base


def test_nnls_recupera_composicao_pura():
    for cls in C.CLASSES:
        idx, load = _synthetic_load({cls: 1.0})
        mix = C.decompose(idx, load)
        assert mix.dominant == cls, (cls, mix.weights)
        assert mix.weights[cls] > 0.75, (cls, mix.weights)
        assert mix.r2 > 0.95, (cls, mix.r2)


def test_nnls_recupera_mistura_conhecida():
    alvo = {"residencial": 0.6, "comercial": 0.4}
    idx, load = _synthetic_load(alvo)
    mix = C.decompose(idx, load)
    assert mix.weights["residencial"] == pytest.approx(0.6, abs=0.18)
    assert mix.weights["comercial"] == pytest.approx(0.4, abs=0.18)


def test_pesos_sao_nao_negativos_e_somam_um():
    idx, load = _synthetic_load({"comercial": 0.5, "industrial": 0.5})
    mix = C.decompose(idx, load)
    assert all(v >= 0.0 for v in mix.weights.values())
    assert sum(mix.weights.values()) == pytest.approx(1.0, abs=1e-6)


def test_classificacao_mista_quando_nenhuma_classe_domina():
    mix = C.ClassMix(weights={"residencial": 0.3, "comercial": 0.3,
                              "industrial": 0.2, "rural": 0.2},
                     dominant="residencial", residual=0.0, r2=0.9)
    assert mix.is_mixed is True
    assert "Misto" in mix.label()


def test_classificacao_pura_quando_uma_classe_domina():
    mix = C.ClassMix(weights={"residencial": 0.7, "comercial": 0.1,
                              "industrial": 0.1, "rural": 0.1},
                     dominant="residencial", residual=0.0, r2=0.9)
    assert mix.is_mixed is False
    assert mix.label() == C.CLASS_LABELS["residencial"]


def test_razao_de_fim_de_semana_e_calculada():
    idx, load = _synthetic_load({"comercial": 1.0})
    r = C.weekend_weekday_ratio(idx, load)
    assert 0.4 < r < 0.9, r


# ================================================= morfologia
def test_morfologia_classifica_por_area_de_telhado():
    assert C.classify_footprint(120.0) == "residencial"
    assert C.classify_footprint(600.0) == "comercial"
    assert C.classify_footprint(5000.0) == "industrial"


def test_morfologia_pondera_por_area_nao_por_contagem():
    """Um galpao de 5.000 m2 pesa mais que dez casas de 120 m2."""
    areas = np.array([120.0] * 10 + [5000.0])
    m = C.from_morphology(areas, extent_km2=1.0)
    assert m.dominant == "industrial"
    assert m.counts["residencial"] == 10
    assert m.counts["industrial"] == 1
    assert m.weights["industrial"] > m.weights["residencial"]


def test_morfologia_de_bairro_residencial():
    areas = np.random.default_rng(3).uniform(80.0, 200.0, 200)
    m = C.from_morphology(areas, extent_km2=0.5)
    assert m.dominant == "residencial"
    assert m.density_per_km2 == pytest.approx(400.0, rel=0.01)


def test_morfologia_vazia_nao_quebra():
    m = C.from_morphology(np.array([]), extent_km2=1.0)
    assert m.dominant == "residencial"
    assert sum(m.weights.values()) == pytest.approx(1.0)


# ================================================= combinacao
def test_combinacao_reporta_divergencia():
    load = C.decompose(*_synthetic_load({"residencial": 1.0}))
    morph = C.from_morphology(np.array([6000.0, 7000.0]), 1.0)  # industrial
    out = C.combine(load, morph, w_load=0.5)
    assert out["sources_agree"] is False
    assert out["divergence"] > 0.4
    assert sum(out["weights"].values()) == pytest.approx(1.0, abs=5e-4)


def test_combinacao_concorda_quando_as_fontes_concordam():
    load = C.decompose(*_synthetic_load({"residencial": 1.0}))
    morph = C.from_morphology(np.array([120.0] * 50), 1.0)
    out = C.combine(load, morph, w_load=0.5)
    assert out["sources_agree"] is True
    assert out["divergence"] < 0.3
    assert out["confidence"] > 0.5


def test_peso_zero_no_prior_deixa_a_morfologia_decidir():
    load = C.ClassMix(weights={c: 0.25 for c in C.CLASSES},
                      dominant="residencial", residual=0.0, r2=0.0)
    morph = C.from_morphology(np.array([6000.0]), 1.0)
    out = C.combine(load, morph, w_load=0.0)
    assert out["dominant"] == "industrial"


def test_payload_canonico_traz_o_que_a_interface_desenha():
    p = C.canonical_payload()
    assert p["hours"] == list(range(24))
    assert len(p["classes"]) == 4
    for c in p["classes"]:
        assert len(c["profile"]) == 24
        assert c["label"] and c["note"]
    assert "residencial_max" in p["footprint_thresholds_m2"]


# ================================================= registro
@pytest.fixture(scope="module")
def demo_reg():
    return registry.load_registry(force_demo=True)


def test_registro_demo_tem_coordenadas_no_brasil(demo_reg):
    assert len(demo_reg.items) > 5
    for s in demo_reg.items:
        assert -34.0 <= s.lat <= 6.0
        assert -74.0 <= s.lon <= -34.0


def test_raio_cresce_com_a_capacidade_de_fronteira():
    a = registry.Substation("A", "A", "SP", "SP", "SE", "x", -23.0, -46.0,
                            230.0, frontier_mva=60.0)
    b = registry.Substation("B", "B", "SP", "SP", "SE", "x", -23.0, -46.0,
                            230.0, frontier_mva=600.0)
    assert b.radius_km > a.radius_km


def test_raio_respeita_os_limites():
    tiny = registry.Substation("T", "T", "SP", "SP", "SE", "x", -23.0, -46.0,
                               230.0, frontier_mva=0.5)
    huge = registry.Substation("H", "H", "SP", "SP", "SE", "x", -23.0, -46.0,
                               230.0, frontier_mva=99_000.0)
    assert tiny.radius_km == pytest.approx(registry.RADIUS_MIN_KM)
    assert huge.radius_km == pytest.approx(registry.RADIUS_MAX_KM)


def test_fronteira_exige_secundario_de_distribuicao():
    frontier = registry.Substation("F", "F", "SP", "SP", "SE", "x", -23.0,
                                   -46.0, 230.0, secondary_kv_min=69.0)
    bulk = registry.Substation("B", "B", "SP", "SP", "SE", "x", -23.0, -46.0,
                               500.0, secondary_kv_min=500.0)
    sem = registry.Substation("S", "S", "SP", "SP", "SE", "x", -23.0, -46.0,
                              230.0, secondary_kv_min=0.0)
    assert frontier.is_frontier is True
    assert bulk.is_frontier is False
    assert sem.is_frontier is False


def test_filtro_por_uf_e_fronteira(demo_reg):
    assert all(s.uf == "BA" for s in demo_reg.filter(uf="BA"))
    assert all(s.is_frontier for s in demo_reg.filter(frontier_only=True))


def test_registro_declara_proveniencia(demo_reg):
    assert demo_reg.provenance_dicts()
    assert demo_reg.mode == "demo"


# ================================================= mapper
def test_morfologia_urbana_usa_sinais_independentes():
    """A versao antiga usava densidade MVA/km2, que era circular: o raio e
    calculado a partir do MVA, logo a densidade era constante."""
    centro = registry.Substation("C", "C", "SP", "SP", "SE", "ENEL SP",
                                 -23.5, -46.6, 345.0, frontier_mva=900.0,
                                 secondary_kv_min=34.5)
    bairro = registry.Substation("B", "B", "SP", "SP", "SE", "ENEL SP",
                                 -23.5, -46.6, 138.0, frontier_mva=40.0,
                                 secondary_kv_min=13.8)
    assert mapper.urban_hint_for(centro) == "comercial"
    assert mapper.urban_hint_for(bairro) == "residencial"


def test_morfologia_urbana_nao_afirma_industrial_pelo_cadastro():
    """Sem base de classe de consumo, esse rotulo nao se sustenta."""
    no_regional = registry.Substation("R", "R", "MG", "MG", "SE", "TAESA",
                                      -19.9, -43.9, 500.0, frontier_mva=2000.0,
                                      secondary_kv_min=138.0)
    assert mapper.urban_hint_for(no_regional) != "industrial"


def test_agente_de_distribuicao_e_reconhecido():
    assert mapper.is_distribution_agent("ENEL DISTRIBUICAO SP") is True
    assert mapper.is_distribution_agent("CEMIG D") is True
    assert mapper.is_distribution_agent("FURNAS") is False


def test_classe_de_penetracao_respeita_as_faixas():
    assert mapper.penetration_class(50.0) == "baixa"
    assert mapper.penetration_class(400.0) == "média"
    assert mapper.penetration_class(5000.0) == "alta"


def test_faixas_de_penetracao_sao_continuas():
    bins = mapper.PENETRATION_BINS
    for (_, _, hi), (_, lo2, _) in zip(bins[:-1], bins[1:]):
        assert hi == lo2, "as faixas precisam ser contíguas"


def test_taxa_de_paineis_e_realista():
    """A penetracao media brasileira e da ordem de 3% das unidades."""
    for mw in (0.0, 500.0, 6000.0):
        s = registry.Substation("X", "X", "SP", "SP", "SE", "x", -23.0, -46.0,
                                230.0, frontier_mva=200.0, tipo3_mw=mw)
        r = mapper._panel_rate(s)
        assert 0.01 <= r <= 0.12, (mw, r)


def test_semente_e_estavel_por_subestacao():
    s = registry.Substation("ABC", "N", "SP", "SP", "SE", "x", -23.0, -46.0, 230.0)
    assert mapper._seed_for(s) == mapper._seed_for(s)


@pytest.fixture(scope="module")
def profile(demo_reg):
    sub = demo_reg.frontier()[0]
    idx, load = _synthetic_load({"residencial": 0.7, "comercial": 0.3})
    return mapper.analyse(sub, subsystem_index=idx, subsystem_load=load)


def test_analise_responde_as_duas_perguntas_do_desafio(profile):
    """1) perfil predominante com percentual; 2) presenca de GD em tres niveis."""
    lc = profile.load_class
    assert lc["label"]
    assert lc["dominant"] in C.CLASSES
    assert sum(lc["weights"].values()) == pytest.approx(1.0, abs=5e-4)
    assert 0.0 <= lc["confidence"] <= 1.0

    m = profile.mmgd
    assert m["level"] in ("baixa", "média", "alta")
    assert m["kwp_per_km2"] >= 0.0
    assert m["kwp_total"] >= 0.0
    assert m["panels"] >= 0


def test_analise_declara_a_amostragem(profile):
    m = profile.mmgd
    assert m["sample_km2"] > 0
    assert m["samples"] >= 1
    assert m["extrapolation_factor"] > 1.0
    assert 0.0 < m["built_up_fraction"] <= 1.0
    assert m["sample_adequacy"] in ("boa", "limitada", "insuficiente")
    assert any("amostra" in n.lower() for n in profile.notes)


def test_analise_declara_que_a_imagem_e_sintetica(profile):
    assert any("sintética" in n for n in profile.notes)


def test_prior_regional_nao_e_tratado_como_segunda_medida(profile):
    lc = profile.load_class
    assert "regional_prior" in lc and "local_evidence" in lc
    assert "deviation_from_regional" in lc
    assert "sources_agree" not in lc, (
        "comparar prior regional com evidencia local de igual para igual "
        "produziria divergencia por construcao")
    assert lc["weight_load"] <= 0.30, "o prior deve ter peso pequeno"


def test_linha_da_tabela_tem_o_que_o_mapa_mostra(profile):
    r = profile.row()
    for k in ("sub_id", "name", "uf", "lat", "lon", "class_label",
              "class_dominant", "class_weights", "class_confidence",
              "mmgd_level", "mmgd_kwp", "mmgd_kwp_per_km2", "mmgd_panels"):
        assert k in r, k


def test_agregado_do_lote(demo_reg):
    idx, load = _synthetic_load({"residencial": 1.0})
    profs = mapper.analyse_many(demo_reg.frontier()[:3],
                                subsystem_series={"NE": {"index": idx, "load": load},
                                                  "SE": {"index": idx, "load": load},
                                                  "S": {"index": idx, "load": load},
                                                  "N": {"index": idx, "load": load}})
    a = mapper.aggregate(profs)
    assert a["substations"] == 3
    assert sum(a["by_class"].values()) == 3
    assert sum(a["by_mmgd_level"].values()) == 3
    assert 0.0 <= a["mean_deviation_from_regional"] <= 1.0


def test_insumo_clm_declara_que_nao_e_parametro_pronto(profile):
    an = mapper.clm_hint(profile)
    assert 0.0 <= an["fracao_motor_estimada"] <= 1.0
    assert "conjunto de parâmetros pronto" in an["aviso"].lower() or \
           "não é conjunto de parâmetros pronto" in an["aviso"].lower()
    assert an["fracao_motor_premissas"]["industrial"] > \
           an["fracao_motor_premissas"]["residencial"]


def test_analise_e_deterministica(demo_reg):
    sub = demo_reg.frontier()[0]
    idx, load = _synthetic_load({"comercial": 1.0})
    a = mapper.analyse(sub, subsystem_index=idx, subsystem_load=load)
    b = mapper.analyse(sub, subsystem_index=idx, subsystem_load=load)
    assert a.mmgd["kwp_per_km2"] == b.mmgd["kwp_per_km2"]
    assert a.load_class["weights"] == b.load_class["weights"]


# ================================================= rotas
MAPA_ROUTES = [
    "/api/mapa/substations?limit=3",
    "/api/mapa/vision",
    "/api/mapa/classes",
]


@pytest.mark.parametrize("route", MAPA_ROUTES)
def test_rotas_do_mapa_tem_envelope_de_proveniencia(client, route):
    body = client.get(route).json()
    assert body["ok"] is True
    assert isinstance(body["provenance"], list)
    assert body["mode"] in ("live", "cache", "demo")


@pytest.mark.parametrize("route", MAPA_ROUTES)
def test_rotas_do_mapa_nao_emitem_nan(client, route):
    raw = client.get(route).text
    assert "NaN" not in raw and "Infinity" not in raw


def test_lista_de_subestacoes_tem_as_duas_respostas(client):
    d = client.get("/api/mapa/substations?limit=4").json()["data"]
    assert d["rows"]
    for r in d["rows"]:
        assert r["class_label"]
        assert r["mmgd_level"] in ("baixa", "média", "alta")
    assert d["pipeline"] and d["penetration_bins"]


def test_detalhe_de_subestacao_traz_imagem_e_insumo_clm(client):
    sid = client.get("/api/mapa/substations?limit=1").json()["data"]["rows"][0]["sub_id"]
    d = client.get("/api/mapa/substations/" + sid).json()["data"]
    assert d["image_url"].endswith(".png")
    assert d["clm"]["aviso"]
    assert d["vision"]["detector"]["kind"] in ("classico", "yolo")
    assert d["evaluation"]["match"]


def test_subestacao_inexistente_devolve_404(client):
    assert client.get("/api/mapa/substations/NAO_EXISTE").status_code == 404


def test_cena_devolve_png(client):
    sid = client.get("/api/mapa/substations?limit=1").json()["data"]["rows"][0]["sub_id"]
    r = client.get("/api/mapa/scene/" + sid)
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    assert r.content[:8] == b"\x89PNG\r\n\x1a\n"


@pytest.mark.parametrize("q", ["", "?truth=1&tiles=1", "?channel=azul",
                               "?channel=borda", "?channel=luminancia"])
def test_banco_de_ensaio_devolve_png(client, q):
    r = client.get("/api/mapa/bench.png" + q)
    assert r.status_code == 200
    assert r.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_visao_declara_os_dois_backends_e_o_motivo(client):
    d = client.get("/api/mapa/vision").json()["data"]
    kinds = {b["kind"] for b in d["backends"]}
    assert kinds == {"classico", "yolo"}
    yolo = [b for b in d["backends"] if b["kind"] == "yolo"][0]
    if not yolo["available"]:
        assert yolo["reason"]
    assert d["active"]["available"] is True
    assert "PyPI" in d["yolo_note"]
    assert d["aggregate"]["f1"] >= 0.80
    assert d["area_calibration"]["factor"] > 1.0


def test_classes_traz_canonicos_e_decomposicao_real(client):
    d = client.get("/api/mapa/classes").json()["data"]
    assert len(d["canonical"]["classes"]) == 4
    assert d["subsystems"]
    for s in d["subsystems"]:
        # pesos vem arredondados em 4 casas no payload
        assert sum(s["weights"].values()) == pytest.approx(1.0, abs=5e-4)
        assert s["fit_quality"] in ("bom", "moderado", "fraco")
        assert len(s["observed"]) == 24 and len(s["fitted"]) == 24


# ================================================= nao regressao
ROTAS_ANTERIORES = [
    "/api/health", "/api/meta", "/api/catalog", "/api/series?area=SE",
    "/api/decomposition?area=SE", "/api/forecast?area=SE&horizon=3h",
    "/api/profiles?area=SE", "/api/risk?horizon=d1",
    "/api/validation?area=SE", "/api/triangulation", "/api/provenance",
]


@pytest.mark.parametrize("route", ROTAS_ANTERIORES)
def test_abas_anteriores_seguem_funcionando(client, route):
    """As abas que ja funcionavam nao podem ter sido afetadas."""
    r = client.get(route)
    assert r.status_code == 200, route
    body = r.json()
    assert body["ok"] is True
    assert isinstance(body["provenance"], list)
