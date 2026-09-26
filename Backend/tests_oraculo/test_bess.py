# -*- coding: utf-8 -*-
"""Alocacao de BESS pelo corte observado.

Sem rede: o leitor roda sobre um CSV sintetico no formato real do ONS e a API
sobre a base demonstrativa. Os testes que mais importam sao os que mudam a
decisao: o codigo da SE (6 caracteres), a simulacao do BESS conferida a mao e
o dimensionamento pelo ciclo MARGINAL.
"""
from __future__ import annotations

import numpy as np
import pytest

from oraculo import config
from oraculo.bess import analise as A
from oraculo.bess import fontes as F


# ------------------------------------------------------------ ponto -> SE
@pytest.mark.parametrize("pid,code", [
    ("RNACT-500-A", "RNACT"), ("MGJBA3500-A", "MGJBA3"), ("BABJS-69--A", "BABJS"),
    ("CEJGII230-A", "CEJGII"), ("MGPR4-138-B", "MGPR4"), ("SPDRA-138", "SPDRA"),
])
def test_codigo_da_se_tem_largura_fixa(pid, code):
    assert F.se_code(pid) == code


@pytest.mark.parametrize("nome,esperado", [
    ("PARACATU 4 - 500 kV (A)", "PARACATU 4"), ("SE Paracatu 4 500 kV", "PARACATU 4"),
    ("SE PARACATU 4 138,0 kV", "PARACATU 4"), ("ACU III500kVA", "ACU III"),
    ("J. CAMARA III - 500 kV (A)", "J. CAMARA III"),
])
def test_nome_do_ponto_normalizado(nome, esperado):
    assert F.ponto_name(nome) == esperado


def test_ceg_sem_versao():
    assert F.ceg_key("UFV.RS.BA.034153-3.01") == F.ceg_key("UFV.RS.BA.034153-3.1")


def test_janela_so_com_meses_completos():
    w = F.months_window(3, today=(2026, 1))
    assert w == [(2025, 10), (2025, 11), (2025, 12)]


# ------------------------------------------------------------ agregacao
HEAD = ("id_subsistema;nom_subsistema;id_estado;nom_estado;nom_usina;id_ons;ceg;"
        "din_instante;val_geracao;val_geracaolimitada;val_disponibilidade;"
        "val_geracaoreferencia;val_geracaoreferenciafinal;cod_razaorestricao;"
        "cod_origemrestricao;dsc_restricao;id_pontoconexao;nom_pontoconexao;"
        "nom_agenteoperador;val_geracaonaorealizadaapurada;num_minutos_rel;"
        "num_minutos_cnf;num_minutos_ene;num_minutos_restricao")


def _row(ts, gen, disp, cut, razao="", origem="", usina="U1", pid="RNACT-500-A"):
    return ";".join(["NE", "Nordeste", "RN", "RN", usina, usina, "-", ts, str(gen), "",
                     str(disp), "", "", razao, origem, "", pid, "ACU III500kVA",
                     "AGENTE", str(cut) if cut else "", "", "", "", ""])


def test_agrega_corte_por_ponto_razao_origem_e_meia_hora():
    rows = [
        _row("2026-08-01 11:00:00", 50, 100, 40, "ENE", "SIS"),
        _row("2026-08-01 11:30:00", 50, 100, 20, "CNF", "LOC"),
        _row("2026-08-01 11:30:00", 30, 80, 0, usina="U2"),
        _row("2026-08-02 12:00:00", 90, 100, 0),
    ]
    agg = F.aggregate_month((HEAD + "\n" + "\n".join(rows) + "\n").encode(), "fv")
    p = agg["points"]["RNACT-500-A"]
    assert p["e_cut"] == pytest.approx((40 + 20) * 0.5)
    assert p["e_reason"] == {"ENE": 20.0, "CNF": 10.0}
    assert p["e_origin"] == {"SIS": 20.0, "LOC": 10.0}
    assert p["disp_max"] == pytest.approx(180)       # simultaneo entre usinas
    assert list(p["days"]) == ["2026-08-01"]          # so dias com corte
    serie = p["days"]["2026-08-01"]
    assert serie[22] == 40 and serie[23] == 20        # 11:00 e 11:30
    # so o ENE+SIS entra na serie que a MMGD pode explicar
    es = p["days_es"]["2026-08-01"]
    assert es[22] == 40 and es[23] == 0
    assert set(p["usinas"]) == {"U1", "U2"}


# ------------------------------------------------------------ BESS
def _mat(*days):
    return np.array([np.asarray(d, dtype=float) for d in days])


def test_simulacao_conferida_a_mao():
    # 4 meias-horas de 100 MW de corte num dia; BESS 50 MW / 60 MWh
    d = np.zeros(48)
    d[20:24] = 100
    r = A.simulate(_mat(d), 50, 60, eff=0.9)
    # carga possivel = 50 MW x 4 x 0,5 h = 100 MWh, limitada a E = 60
    assert r["absorbed_mwh"] == pytest.approx(60)
    assert r["delivered_mwh"] == pytest.approx(54)
    assert r["cycles"] == pytest.approx(1)
    assert r["capture"] == pytest.approx(60 / 200)
    assert r["days_full"] == 1


def test_simulacao_anualiza():
    d = np.zeros(48)
    d[20:24] = 100
    r = A.simulate(_mat(d), 50, 60, eff=1.0, annual=365.0)
    assert r["cycles"] == pytest.approx(365)


def test_regra_marginal_nao_escolhe_sempre_o_topo():
    # corte de 1.000 MWh em 1/3 dos dias e 100 MWh no resto: o MWh alem de
    # ~100 so e usado um dia em tres e nao passa do limiar de ciclos
    days = []
    for i in range(365):
        d = np.zeros(48)
        d[18:26] = 250 if i % 3 == 0 else 25
        days.append(d)
    grid = A.sizing_grid(_mat(*days), 500)
    g = A.suggest(grid)
    assert g["utilization"] == "adequada"
    assert g["e_mwh"] < max(x["e_mwh"] for x in grid)
    assert g["marginal_cycles"] >= config.BESS["ciclos_min_ano"]


def test_sem_uso_suficiente_declara_baixa_utilizacao():
    d = np.zeros(48)
    d[20] = 10
    g = A.suggest(A.sizing_grid(_mat(d), 100))
    assert g["utilization"] == "baixa"


def test_posto_percentual_com_empate():
    r = A._rank01(np.array([10.0, 10.0, 30.0, np.nan]))
    assert r[0] == r[1] and r[2] == 1.0 and r[3] == 0.0


# ------------------------------------------------------------ MMGD e pontuacao
def _site(code, cut_mw, es_mw, slots=range(20, 30)):
    """Sitio com um dia de corte: `cut_mw` total, dos quais `es_mw` ENE+SIS."""
    s = A.Site(code=code, name=code, uf="RN", subsystem="NE", lat=-5.0, lon=-36.0,
               method="SE do ONS")
    d, e = np.zeros(48), np.zeros(48)
    for k in slots:
        d[k], e[k] = cut_mw, es_mw
    s.days = {"2026-08-01": d}
    s.days_es = {"2026-08-01": e} if es_mw else {}
    s.e_cut = float(d.sum() * 0.5)
    s.disp_max = 500.0
    return s


def _mmgd(mw):
    return {"2026-08-01": np.full(48, float(mw))}


def test_mmgd_maior_que_o_excedente_explica_todo_o_ene_sis():
    a, b = _site("A", 100, 100), _site("B", 100, 40)
    A.mmgd_induced([a, b], _mmgd(10_000))
    assert a.induced_share == pytest.approx(1.0)
    assert b.induced_share == pytest.approx(0.4)      # 60% e CNF/LOC: nao e da MMGD


def test_mmgd_menor_que_o_excedente_e_rateada():
    a, b = _site("A", 100, 100), _site("B", 100, 100)
    rep = A.mmgd_induced([a, b], _mmgd(50))           # 50 MW para 200 MW de ENE+SIS
    assert a.induced_share == pytest.approx(0.25)
    assert b.induced_share == pytest.approx(0.25)
    assert rep["induced_mwh"] == pytest.approx(50 * 10 * 0.5)


def test_corte_local_nao_e_atribuido_a_mmgd():
    a = _site("A", 100, 0)                             # todo CNF/LOC
    A.mmgd_induced([a], _mmgd(10_000))
    assert a.induced_share == 0.0


def test_sem_mmgd_no_dia_nada_e_atribuido():
    a = _site("A", 100, 100)
    A.mmgd_induced([a], {})
    assert a.induced_share == 0.0


def test_pesos_sao_normalizados_e_mudam_a_ordem():
    grande, pato = _site("A", 400, 0), _site("B", 20, 20)
    A.mmgd_induced([grande, pato], _mmgd(10_000))
    rows = A.analyse([grande, pato], 1)
    so_energia = A.score([dict(r) for r in rows], {"energia": 2, "mmgd": 0,
                                                   "recorrencia": 0, "local": 0})
    so_mmgd = A.score([dict(r) for r in rows], {"energia": 0, "mmgd": 5,
                                                "recorrencia": 0, "local": 0})
    assert so_energia[0]["site"].code == "A"
    assert so_mmgd[0]["site"].code == "B"
    assert sum(so_mmgd[0]["weights"].values()) == pytest.approx(1.0)


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
    Service._fr_base = Service._fr_result = None
    Service._bs_months = Service._bs_rows = Service._bs_sites = None
    Service._bs_meta = {}
    Service._bs_job = {"state": "idle", "stage": "", "done": 0, "total": 0,
                       "error": "", "started": 0.0}
    yield


CONTRATO = {
    "/api/bess/status": ["state", "done", "total", "mode", "months"],
    "/api/bess/ranking": ["filters", "weights", "default_weights", "ufs", "kpis",
                          "rows", "map", "stability", "months", "premises", "pipeline",
                          "duck", "load_side"],
    "/api/bess/metodo": ["location", "unlocated", "reasons", "origins", "stability",
                         "premises", "limits"],
}


@pytest.mark.parametrize("rota,campos", sorted(CONTRATO.items()))
def test_contrato_da_api(client, rota, campos):
    body = client.get(rota).json()
    assert body["ok"] is True and isinstance(body["provenance"], list)
    faltando = [c for c in campos if c not in body["data"]]
    assert not faltando, faltando


def test_ranking_ordenado_e_detalhe(client):
    rows = client.get("/api/bess/ranking").json()["data"]["rows"]
    assert [r["rank"] for r in rows] == list(range(1, len(rows) + 1))
    assert all(rows[i]["score"] >= rows[i + 1]["score"] for i in range(len(rows) - 1))
    d = client.get("/api/bess/sitio/" + rows[0]["code"]).json()["data"]
    for k in ("grid", "suggested", "heat", "profile_mwh", "reasoning", "e_reason_gwh",
              "e_origin_gwh", "induced_share", "es_share", "components"):
        assert k in d, k
    assert len(d["profile_mwh"]) == 48


def test_pesos_pela_query(client):
    w = client.get("/api/bess/ranking?w_energia=0&w_mmgd=1&w_recorrencia=0"
                   "&w_local=0").json()["data"]["weights"]
    assert w["mmgd"] == pytest.approx(1.0) and w["energia"] == 0


def test_sitio_inexistente_404(client):
    assert client.get("/api/bess/sitio/NAOEXISTE").status_code == 404


def test_reconstruir_no_modo_demo_e_recusado(client):
    assert client.post("/api/bess/reconstruir").status_code == 400


def test_curva_do_pato_por_subsistema(client):
    d = client.get("/api/bess/ranking").json()["data"]
    for ss, c in d["duck"].items():
        for k in ("carga_global", "supervisionada", "liquida", "corte"):
            assert len(c[k]) == 24, (ss, k)
        # carga com MMGD >= supervisionada em toda hora (a MMGD e >= 0)
        for g, sup in zip(c["carga_global"], c["supervisionada"]):
            if g is not None and sup is not None:
                assert g >= sup - 1e-6
    assert "mmgd_induced_share" in d["kpis"]
