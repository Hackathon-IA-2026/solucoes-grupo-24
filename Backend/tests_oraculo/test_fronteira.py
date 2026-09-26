# -*- coding: utf-8 -*-
"""Correlacao fronteira T-D: SED (ANEEL) x SE de fronteira (ONS).

Sem rede: os leitores da ANEEL rodam sobre arquivos sinteticos no formato
real, e a correlacao sobre a base demonstrativa. O teste que mais importa e o
de CONSERVACAO: nenhum kWh e nenhum kW de GD pode ser criado ou perdido entre
a fonte e as SEs de fronteira -- ou ele chega a uma SE, ou aparece declarado
como nao alocado.
"""
from __future__ import annotations

import io
import json
import zipfile

import numpy as np
import pytest

from oraculo import config
from oraculo.fronteira import base as B
from oraculo.fronteira import correlacao as C
from oraculo.fronteira import fontes as F
from oraculo.substations.registry import Substation


# ------------------------------------------------------------ utilitarios
def test_haversine_rio_sao_paulo():
    d = F.haversine_km(-22.9068, -43.1729, -23.5505, -46.6333)
    assert 355 < d < 365


def test_haversine_vetorizado():
    d = F.haversine_km(0.0, 0.0, np.array([0.0, 1.0]), np.array([1.0, 0.0]))
    assert d.shape == (2,) and np.allclose(d, 111.19, atol=0.2)


@pytest.mark.parametrize("entrada,esperado", [
    ("RE1", "residencial"), ("CO3", "comercial"), ("IN", "industrial"),
    ("RU2", "rural"), ("PP1", "comercial"), ("SP", "comercial"),
    ("REBR", "residencial"), ("REBR ", "residencial"),
    ("Residencial", "residencial"), ("Iluminação pública", "comercial"),
    ("Poder Público", "comercial"), ("Industrial", "industrial"),
])
def test_classe_clm(entrada, esperado):
    assert F.classe_clm(entrada) == esperado


def test_uf_do_municipio():
    assert F.uf_of_mun("3304557") == "RJ"
    assert F.uf_of_mun("3550308") == "SP"


def test_centroide_de_quadrado():
    geom = {"type": "Polygon",
            "coordinates": [[[0, 0], [2, 0], [2, 2], [0, 2], [0, 0]]]}
    assert F.polygon_centroid(geom) == (1.0, 1.0)


def test_token_de_grupo_ignora_palavras_genericas():
    assert C.group_token("CPFL-PAULISTA") == "CPFL"
    assert C.group_token("", "COMPANHIA ENERGETICA DE MINAS GERAIS") == "ENERGETICA"
    assert C.group_token("RGE SUL") == "RGE"


# ------------------------------------------------------------ BDGD
UCMT_HEAD = ("COD_ID_ENCR;DIST;PN_CON;PAC;CTMT;UNI_TR_AT;SUB;CONJ;MUN;CEG_GD;"
             "LGRD;BRR;CEP;CLAS_SUB;CNAE;TIP_CC;FAS_CON;GRU_TEN;TEN_FORN;"
             "GRU_TAR;SIT_ATIV;DAT_CON;CAR_INST;LIV;ARE_LOC;TIP_SIST;DEM_CONT;" +
             ";".join("DEM_%02d" % m for m in range(1, 13)) + ";" +
             ";".join("ENE_%02d" % m for m in range(1, 13)) +
             ";POINT_X;POINT_Y")


def _ucmt_row(dist, sub, mun, cls, ativo, ene, dem, lon, lat, ceg=""):
    cols = ["x", dist, "1", "p", "c", "t", sub, "1", mun, ceg,
            "RUA SIGILOSA 1", "BAIRRO", "00000-000", cls, "0000", "t", "ABC",
            "MT", "1", "A4", ativo, "01/01/2000", "100", "0", "UB", "RD", "0"]
    cols += [str(dem)] * 12 + [str(ene)] * 12 + [str(lon), str(lat)]
    return ";".join(cols)


@pytest.fixture
def ucmt_file(tmp_path):
    rows = [
        _ucmt_row("385", "SUB1", "3550308", "CO1", "AT", 1000, 50, -46.6, -23.5,
                  "GD.SP.000.000.001"),
        _ucmt_row("385", "SUB1", "3550308", "IN", "AT", 3000, 80, -46.7, -23.6),
        _ucmt_row("385", "SUB1", "3509502", "RU", "AT", 500, 10, -46.8, -23.7),
        _ucmt_row("385", "SUB2", "3509502", "CO1", "AT", 200, 5, -47.0, -22.9),
        _ucmt_row("385", "SUB2", "3509502", "CO1", "DS", 9999, 99, -47.0, -22.9),
        _ucmt_row("385", "", "3509502", "CO1", "AT", 9999, 99, -47.0, -22.9),
        _ucmt_row("385", "SUB3", "3509502", "CO1", "AT", 9999, 99, 10.0, 10.0),
    ]
    p = tmp_path / "ucmt_pj.csv"
    p.write_text(UCMT_HEAD + "\n" + "\n".join(rows) + "\n", encoding="utf-8")
    return p


def test_aggregate_uc_filtra_e_soma(ucmt_file):
    out = F.aggregate_uc(ucmt_file, tensao="MT")
    rep, seds = out["report"], out["seds"]
    assert rep["inactive"] == 1 and rep["no_sub"] == 1 and rep["no_point"] == 1
    assert set(seds) == {"385|SUB1", "385|SUB2"}
    s1 = seds["385|SUB1"]
    assert s1["n_mt"] == 3
    assert s1["e_class"]["comercial"] == pytest.approx(12 * 1000)
    assert s1["e_class"]["industrial"] == pytest.approx(12 * 3000)
    assert s1["e_class"]["rural"] == pytest.approx(12 * 500)
    assert s1["dem_kw"] == pytest.approx(50 + 80 + 10)
    assert s1["ceg"] == ["GD.SP.000.000.001"]
    assert s1["mun"] == {"3550308": 2, "3509502": 1}


def test_posicao_da_sed_e_a_mediana(ucmt_file):
    seds = F.finalize_seds(F.aggregate_uc(ucmt_file, tensao="MT")["seds"])
    s1 = next(s for s in seds if s["key"] == "385|SUB1")
    assert s1["lat"] == pytest.approx(-23.6) and s1["lon"] == pytest.approx(-46.7)
    assert s1["uf"] == "SP"
    assert len(s1["e_month"]) == 12


def test_aggregate_uc_nao_guarda_endereco(ucmt_file):
    seds = F.finalize_seds(F.aggregate_uc(ucmt_file, tensao="MT")["seds"])
    blob = json.dumps(seds)
    assert "SIGILOSA" not in blob and "00000-000" not in blob


def test_aggregate_uc_alta_tensao_soma_ponta_e_fora(tmp_path):
    head = ("DIST;SUB;MUN;CEG_GD;CLAS_SUB;SIT_ATIV;CAR_INST;" +
            ";".join("DEM_P_%02d;DEM_F_%02d" % (m, m) for m in range(1, 13)) + ";" +
            ";".join("ENE_P_%02d;ENE_F_%02d" % (m, m) for m in range(1, 13)) +
            ";POINT_X;POINT_Y")
    row = (["10", "ATX", "3304557", "", "IN", "AT", "0"] +
           ["100", "300"] * 12 + ["10", "90"] * 12 + ["-43.2", "-22.9"])
    p = tmp_path / "ucat_pj.csv"
    p.write_text(head + "\n" + ";".join(row) + "\n", encoding="utf-8")
    s = F.aggregate_uc(p, tensao="AT")["seds"]["10|ATX"]
    assert s["n_at"] == 1
    assert s["e_class"]["industrial"] == pytest.approx(12 * 100)
    assert s["dem_kw"] == pytest.approx(300)


# ------------------------------------------------------------ cadastro de GD
GD_HEAD = ('"DatGeracaoConjuntoDados";"NumCNPJDistribuidora";"SigAgente";'
           '"NomAgente";"DscClasseConsumo";"CodMunicipioIbge";"NumCPFCNPJ";'
           '"CodEmpreendimento";"SigTipoGeracao";"MdaPotenciaInstaladaKW";'
           '"NomTitularEmpreendimento"')


def _gd_zip(tmp_path, rows):
    buf = io.StringIO()
    buf.write(GD_HEAD + "\n")
    for r in rows:
        buf.write(";".join('"%s"' % x for x in r) + "\n")
    p = tmp_path / "gd.zip"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("empreendimento-geracao-distribuida.csv",
                   buf.getvalue().encode("utf-8"))
    return p


def test_aggregate_gd_vinculo_direto_e_privacidade(tmp_path):
    p = _gd_zip(tmp_path, [
        ["2026", "11111111000191", "DIST-A", "DISTRIBUIDORA A", "Residencial",
         "3550308", "12345678900", "GD.SP.000.000.001", "UFV", "10,5",
         "FULANO DE TAL"],
        ["2026", "11111111000191", "DIST-A", "DISTRIBUIDORA A", "Comercial",
         "3550308", "98765432100", "GD.SP.000.000.002", "UFV", "4,5",
         "BELTRANO"],
    ])
    out = F.aggregate_gd(p, {"GD.SP.000.000.001": "385|SUB1"})
    m = out["mun"]["3550308"]
    assert m["kw"] == pytest.approx(15.0) and m["n"] == 2
    assert m["kw_direct"] == pytest.approx(10.5)
    assert out["sed"]["385|SUB1"]["kw"] == pytest.approx(10.5)
    assert out["report"]["kw_direct"] == pytest.approx(10.5)
    blob = json.dumps(out, ensure_ascii=False)
    for segredo in ("12345678900", "98765432100", "FULANO", "BELTRANO"):
        assert segredo not in blob, segredo


# ------------------------------------------------------------ associacao
def _se(sub_id, lat, lon, mva, uf="SP", agent="TRANSMISSORA X"):
    return Substation(sub_id=sub_id, name=sub_id, uf=uf, state_name="",
                      subsystem="SE", agent=agent, lat=lat, lon=lon,
                      voltage_kv=345.0, capacity_mva=mva, frontier_mva=mva,
                      secondary_kv_min=138.0)


def test_mesma_capacidade_vence_a_mais_proxima():
    g = C.Gravity([_se("A", -23.0, -46.0, 300), _se("B", -23.0, -46.5, 300)])
    lk = g.link(-23.0, -46.05, "SP", "")
    assert g.f[lk.idx].sub_id == "A" and lk.p > 0.5


def test_mesma_distancia_vence_a_maior_capacidade():
    g = C.Gravity([_se("A", -23.0, -46.1, 100), _se("B", -23.0, -45.9, 900)])
    lk = g.link(-23.0, -46.0, "SP", "")
    assert g.f[lk.idx].sub_id == "B"
    # alfa = 0,5: 900 MVA pesa 3x, nao 9x
    assert lk.p == pytest.approx(0.75, abs=0.01)


def test_fora_do_raio_nao_associa():
    g = C.Gravity([_se("A", -3.0, -60.0, 300)])
    assert g.link(-23.0, -46.0, "SP", "").idx == -1


def test_bonus_de_grupo_economico():
    g = C.Gravity([_se("A", -23.0, -46.1, 300, agent="CPFL T"),
                   _se("B", -23.0, -45.9, 300)])
    lk = g.link(-23.0, -46.0, "SP", "CPFL")
    assert g.f[lk.idx].sub_id == "A" and lk.agent_match
    assert lk.p == pytest.approx(config.FRONTEIRA["bonus_agente"] /
                                 (1 + config.FRONTEIRA["bonus_agente"]), abs=1e-6)


def test_vinculo_ambiguo():
    g = C.Gravity([_se("A", -23.0, -46.1, 300), _se("B", -23.0, -45.9, 300)])
    lk = g.link(-23.0, -46.0, "SP", "")
    assert lk.p == pytest.approx(0.5, abs=1e-6)
    g2 = C.Gravity([_se("A", -23.0, -46.1, 300), _se("B", -23.0, -45.9, 300),
                    _se("C", -22.9, -46.0, 300)])
    assert g2.link(-23.0, -46.0, "SP", "").ambiguous


def test_identidade_da_distribuidora_por_municipio():
    seds = [{"dist": "385", "mun": {"3550308": 10, "3509502": 1}}]
    mun = {"3550308": {"dist": {"111|ENEL SP|ENEL": 90, "222|CPFL|CPFL": 10}},
           "3509502": {"dist": {"222|CPFL|CPFL": 50}}}
    ident = C.dist_identity(seds, mun)
    assert ident["385"]["sigla"] == "ENEL SP"
    assert 0.5 < ident["385"]["confianca"] < 1.0


# ------------------------------------------------------------ conservacao
@pytest.fixture(scope="module")
def demo():
    from oraculo.substations.registry import _demo_registry
    frontier = _demo_registry().frontier()
    b = B.demo_base(frontier)
    return b, frontier, C.correlate(b, frontier)


def test_energia_mtat_conservada(demo):
    b, _, r = demo
    fonte = sum(sum(s["e_class"].values()) for s, lk in zip(r.seds, r.links)
                if lk.idx >= 0)
    chegou = sum(f["e_mtat_gwh"] for f in r.per_frontier) * 1e6
    assert chegou == pytest.approx(fonte, rel=1e-6)


def test_baixa_tensao_conservada(demo):
    b, _, r = demo
    fonte = sum(sum(d["kwh_class"].values()) for d in b["samp"].values()) / 1e9
    rep = r.report
    assert rep["bt_allocated_twh"] + rep["bt_unallocated_twh"] == pytest.approx(
        fonte, abs=0.02)
    chegou = sum(f["e_bt_gwh"] for f in r.per_frontier) / 1000.0
    assert chegou == pytest.approx(rep["bt_allocated_twh"], abs=0.02)


def test_mmgd_conservada(demo):
    b, _, r = demo
    total = sum(g["kw"] for g in b["mun"].values())
    chegou = sum(f["gd_kw"] for f in r.per_frontier)
    nao = r.report["gd_unallocated_mw"] * 1000.0
    # vinculo direto usa o agregado por SED; o municipal, o restante
    direto = sum(g["kw"] for g in b["sed_gd"].values())
    mun_direto = sum(g["kw_direct"] for g in b["mun"].values())
    assert chegou + nao == pytest.approx(total - mun_direto + direto, rel=1e-4)


def test_composicao_soma_um(demo):
    for f in demo[2].per_frontier:
        if f["e_total_gwh"] > 0:
            assert sum(f["weights"].values()) == pytest.approx(1.0, abs=1e-3)


def test_sensibilidade_tem_nove_linhas_e_uma_em_uso(demo):
    b, frontier, _ = demo
    s = C.sensitivity(b, frontier)
    assert len(s) == 9
    assert sum(1 for x in s if x["current"]) == 1


def test_base_demo_nao_tem_campo_pessoal(demo):
    blob = json.dumps(demo[0], ensure_ascii=False)
    for campo in ("NumCPFCNPJ", "NomTitularEmpreendimento", "LGRD", "CEP"):
        assert campo not in blob


def test_premissas_mudam_sem_reconstruir(demo):
    b, frontier, r = demo
    r2 = C.correlate(b, frontier, {"lambda_km": 5.0})
    assert r2.report["distance_km"] == r.report["distance_km"]  # mesmas SEDs
    p1 = r.report["probability"]["mean"]
    p2 = r2.report["probability"]["mean"]
    assert p2 >= p1 - 1e-9          # lambda menor concentra a probabilidade


# ------------------------------------------------------------ API
@pytest.fixture(autouse=True)
def _modo_demo(request):
    """Os testes de API rodam SEMPRE sobre a base demonstrativa.

    Outro teste da suite (POST /api/ingest) recarrega o bundle do ONS a
    partir do cache, e o servico sai do modo demo. Sem esta fixture, a secao
    tentaria construir a base real -- baixando da ANEEL no meio da suite.
    """
    if "client" not in request.fixturenames:
        yield
        return
    from oraculo.api.service import SERVICE, Service
    if SERVICE.mode() != "demo":
        SERVICE.ensure(force_demo=True, refresh=True)
        Service._registry = None
        Service._profiles = {}
    Service._fr_base = None
    Service._fr_result = None
    Service._fr_sens = None
    Service._fr_job = {"state": "idle", "stage": "", "progress": 0.0,
                       "error": "", "started": 0.0}
    yield


CONTRATO = {
    "/api/fronteira/status": ["state", "stage", "progress", "stages", "base_mode",
                              "built_at", "ttl_days"],
    "/api/fronteira/resumo": ["filters", "ufs", "subsystems", "kpis", "rows",
                              "map", "report", "premises", "pipeline"],
    "/api/fronteira/qualidade": ["report", "hist_distance", "hist_probability",
                                 "hist_loading", "ons_coverage", "sensitivity",
                                 "flagged", "premises", "privacy", "limits"],
}


@pytest.mark.parametrize("rota,campos", sorted(CONTRATO.items()))
def test_contrato_da_api(client, rota, campos):
    body = client.get(rota).json()
    assert body["ok"] is True and isinstance(body["provenance"], list)
    faltando = [c for c in campos if c not in body["data"]]
    assert not faltando, faltando


def test_status_pronto_no_modo_demo(client):
    body = client.get("/api/fronteira/status").json()
    assert body["data"]["state"] == "ready"
    assert body["mode"] == "demo"


def test_detalhe_da_se(client):
    rows = client.get("/api/fronteira/resumo").json()["data"]["rows"]
    sid = next(r["sub_id"] for r in rows if r["n_sed"] > 0)
    d = client.get("/api/fronteira/se/" + sid).json()["data"]
    for k in ("seds", "weights", "e_month_mtat_gwh", "e_month_bt_gwh", "clm",
              "comparison", "gd_kw", "loading"):
        assert k in d, k
    s = d["seds"][0]
    for k in ("sub", "distribuidora", "p", "d_km", "alternatives", "ambiguous"):
        assert k in s, k


def test_fracao_motora_igual_nas_duas_telas(client):
    from oraculo.substations import mapper
    rows = client.get("/api/fronteira/resumo").json()["data"]["rows"]
    sid = next(r["sub_id"] for r in rows if r["n_sed"] > 0)
    d = client.get("/api/fronteira/se/" + sid).json()["data"]
    assert d["clm"]["fracao_motor_estimada"] == mapper.motor_fraction(d["weights"])


def test_cartao_clm_pela_bdgd(client):
    rows = client.get("/api/fronteira/resumo").json()["data"]["rows"]
    sid = next(r["sub_id"] for r in rows if r["n_sed"] > 0)
    body = client.get("/api/clm/cartao?sub_id=%s&fonte=bdgd" % sid).json()
    assert body["ok"] is True
    assert "BDGD" in body["data"]["fonte_composicao"]
    det = client.get("/api/fronteira/se/" + sid).json()["data"]
    mix = body["data"]["fracoes"]["mix"]
    for c, v in det["weights"].items():
        assert mix.get(c, 0.0) == pytest.approx(v, abs=1e-3)


def test_se_inexistente_404(client):
    r = client.get("/api/fronteira/se/NAO-EXISTE")
    assert r.status_code == 404


def test_reconstruir_no_modo_demo_e_recusado(client):
    r = client.post("/api/fronteira/reconstruir")
    assert r.status_code == 400


def test_restos_de_construcao_morta_sao_apagados(tmp_path, monkeypatch):
    import os
    import tempfile
    import time
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    velho = tmp_path / (F.TEMP_PREFIX + "morto")
    velho.mkdir()
    (velho / "ucmt_pj.csv").write_text("dado granular", encoding="utf-8")
    t = time.time() - 7200
    os.utime(velho, (t, t))
    novo = F.temp_dir()
    assert not velho.exists()
    assert novo.exists()
    F.cleanup(novo)
