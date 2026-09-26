"""Espacialização (Fase 6) com geometrias e tabelas sintéticas: sem BDGD, sem rede.

Cada teste trava uma regra do método (docs/metodo_espacial.md) ou um bug já visto:
- filtro de MMGD pelo CEG (o RDX somava usinas grandes da UGAT);
- toda semente sobrevive à resolução de sobreposições; áreas de influência não se sobrepõem;
- os vazios do estado são divididos entre as áreas de influência vizinhas;
- desempate BDGD × ANEEL: categorias, rateio do lag conserva potência;
- capacidade levada à fronteira conserva potência;
- carga bruta na subestação de origem (alimentador exportador);
- previsão sem vazamento temporal (nenhum dado depois do agora muda o resultado);
- área de influência com MMGD e sem carga não some da previsão.
"""
import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import Point, box

from src.spatial import bdgd, excedentes as ex, areas_influencia, mmgd

CFG = bdgd.cfg()
CRS = CFG["geometria"]["crs_metrico"]


# --------------------------------------------------------------------------- BDGD
def test_so_ceg_de_gd_e_mmgd():
    ceg = pd.Series(["GD.RJ.001.915.444", " GD.RJ.003.519.927 ", "UHE.PH.RJ.001", "", None, "PCH123"])
    assert bdgd.eh_mmgd(ceg, CFG["padrao_ceg_mmgd"]).tolist() == [True, True, False, False, False, False]


def test_area_id_nunca_fica_so_com_a_sigla():
    ids = bdgd._area_id("LIGHT", pd.Series(["123", "", None, " 45 "], dtype="string"))
    assert ids.iloc[0] == "LIGHT:123" and ids.iloc[3] == "LIGHT:45"
    assert ids.iloc[1:3].isna().all()


# --------------------------------------------------------------------------- áreas de influência
def _subs(pontos: dict[str, tuple[float, float]], pot: dict[str, float]) -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame({"area_id": list(pontos), "potencia_nominal_mva": [pot[k] for k in pontos]},
                            geometry=[Point(*xy).buffer(1) for xy in pontos.values()], crs=CRS)


def _trafos(pontos: list[tuple[str, float, float]]) -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame({"area_id": [p[0] for p in pontos]},
                            geometry=[Point(p[1], p[2]) for p in pontos], crs=CRS)


def test_areas_iniciais_fecho_ou_semente():
    subs = _subs({"A": (0, 0), "B": (5000, 0)}, {"A": 10, "B": 0})
    trafos = _trafos([("A", 0, 0), ("A", 1000, 0), ("A", 0, 1000), ("B", 5000, 10)])  # B só tem 1 trafo
    a = areas_influencia.areas_iniciais(subs, trafos, CFG).set_index("area_id")
    assert a.loc["A", "origem"] == "fecho_trafos" and a.loc["A", "geometry"].area == pytest.approx(5e5)
    assert a.loc["B", "origem"] == "semente"
    assert a.loc["B", "geometry"].area == pytest.approx(np.pi * CFG["geometria"]["raio_semente_m"] ** 2, rel=0.02)


def test_sobreposicao_semente_sobrevive_e_nada_se_sobrepoe():
    # A (grande, potente) cobre o ponto de B (semente de transporte) e se sobrepõe a C.
    subs = _subs({"A": (0, 0), "B": (500, 500), "C": (1800, 0)}, {"A": 100, "B": 0, "C": 50})
    trafos = _trafos([("A", -1000, -1000), ("A", 1000, -1000), ("A", 1000, 1000), ("A", -1000, 1000),
                      ("C", 800, -500), ("C", 2500, -500), ("C", 2500, 500), ("C", 800, 500)])
    r = areas_influencia.resolver_sobreposicoes(areas_influencia.areas_iniciais(subs, trafos, CFG)).set_index("area_id")
    assert not r.geometry.is_empty.any()
    assert r.loc["B", "geometry"].contains(Point(500, 500))  # a subestação fica na própria área de influência
    g = list(r.geometry)
    assert all(g[i].intersection(g[j]).area < 1e-6 for i in range(3) for j in range(i + 1, 3))


def test_vazios_do_estado_vao_para_as_vizinhas():
    areas = gpd.GeoDataFrame({"area_id": ["A", "B"], "potencia_nominal_mva": [1, 1],
                              "ponto_sub": [Point(500, 500), Point(3500, 500)]},
                             geometry=[box(0, 0, 1000, 1000), box(3000, 0, 4000, 1000)], crs=CRS)
    limite = box(0, 0, 4000, 1000)  # o meio (1000..3000) é vazio e toca as duas
    cheio = areas_influencia.preencher_vazios(areas, limite, CFG)
    assert cheio.geometry.union_all().area == pytest.approx(limite.area, rel=1e-4)
    # Voronoi: cada uma fica com a metade do vazio mais perto da sua subestação
    assert cheio.geometry.iloc[0].area == pytest.approx(2e6, rel=1e-3)


# --------------------------------------------------------------------------- desempate
def _bd(linhas):
    return pd.DataFrame(linhas, columns=["ceg", "area_id", "ctmt", "mun", "pot_bdgd_kw"])


def _an(linhas):
    df = pd.DataFrame(linhas, columns=["ceg", "mun", "pot_aneel_kw", "data"])
    df["data"] = pd.to_datetime(df["data"])
    df["tipo"] = "UFV"
    return df


def test_desempate_categorias_e_rateio_do_lag_conserva_potencia():
    bd = _bd([("GD1", "X:A", "c1", "100", 1.0), ("GD2", "X:B", "c2", "100", 3.0), ("GD9", "X:A", "c1", "100", 5.0)])
    an = _an([("GD1", "100", 10.0, "2025-01-01"), ("GD2", "100", 30.0, "2025-01-01"),
              ("GD3", "100", 8.0, "2026-03-01"),    # lag no município 100: rateado 1:3 entre A e B
              ("GD4", "200", 4.0, "2026-03-01")])   # lag num município só com trafos de C
    trafos = pd.DataFrame({"area_id": ["X:C"], "MUN": ["200"], "POT_NOM": [75.0]})
    u = mmgd.ratear_lag(mmgd.desempatar(bd, an), trafos)
    cat = u.drop_duplicates("ceg").set_index("ceg")["categoria"]
    assert cat.to_dict() == {"GD1": "bdgd_e_aneel", "GD2": "bdgd_e_aneel", "GD3": "lag_sistema",
                             "GD4": "lag_sistema", "GD9": "bdgd_sem_homologacao"}
    u["pot_kw"] = u["pot_aneel_kw"] * u["fracao"]
    gd3 = u[u["ceg"] == "GD3"].set_index("area_id")["pot_kw"]
    assert gd3.to_dict() == pytest.approx({"X:A": 2.0, "X:B": 6.0})
    assert u[u["ceg"] == "GD4"]["area_id"].tolist() == ["X:C"]
    # potência de cada empreendimento homologado é conservada no rateio
    homol = u[u["categoria"] != "bdgd_sem_homologacao"]
    assert homol.groupby("ceg")["pot_kw"].sum().to_dict() == pytest.approx({"GD1": 10, "GD2": 30, "GD3": 8, "GD4": 4})


def test_capacidade_levada_a_fronteira_conserva_potencia():
    u = pd.DataFrame({"area_id": ["S", "S", "S", "P"], "area_fronteira": ["P", "Q", np.nan, np.nan],
                      "pot_kw": [30.0, 10.0, 8.0, 5.0]})  # S é satélite de P e Q; a 3ª linha é lag
    f = mmgd.para_fronteira(u)
    assert f["pot_kw"].sum() == pytest.approx(53.0)
    por = f.groupby("area_fronteira")["pot_kw"].sum()
    assert por.to_dict() == pytest.approx({"P": 30 + 6 + 5, "Q": 10 + 2})


# --------------------------------------------------------------------------- carga e excedentes
MESES_ENE = {f"ENE_{m}": 0.0 for m in bdgd.MESES}


def test_carga_bruta_soma_mmgd_na_subestacao_de_origem():
    ct = pd.DataFrame([{"COD_ID": "c1", "area_id": "A", **MESES_ENE, "ENE_01": -10.0},
                       {"COD_ID": "c2", "area_id": "B", **MESES_ENE, "ENE_01": 70.0}])
    uc = pd.DataFrame([{"area_id": "B", **MESES_ENE, "ENE_01": 10.0},
                       {"area_id": pd.NA, **MESES_ENE, "ENE_01": 20.0}])  # SUB em branco
    gd = pd.DataFrame([{"area_id": "A", **{f"ene_{m}": 0.0 for m in bdgd.MESES}, "ene_01": 30.0}])
    p = ex.pesos_carga(ct, uc, gd)
    jan = p[p["mes"] == 1].set_index("area_id")
    assert set(jan.index) == {"A", "B"}                   # a energia sem SUB não vira área de influência...
    assert jan.loc["A", "energia_kwh"] == pytest.approx(20)  # -10 medido + 30 da MMGD = bruta
    assert jan.loc["A", "peso"] == pytest.approx(20 / 120)   # ...mas conta no denominador


def _fator(agora, n_dias=3):
    ts = pd.date_range(agora - pd.Timedelta(days=n_dias), agora + pd.Timedelta(days=2), freq="30min")
    hora = ts.hour + ts.minute / 60
    sol = np.clip(np.sin((hora - 6) / 12 * np.pi), 0, None)
    return pd.DataFrame({"timestamp": ts, "carga_global": 1000.0, "fator_mmgd": 0.8 * sol})


def test_previsao_nao_usa_dado_depois_do_agora():
    agora = pd.Timestamp("2026-09-25 23:30")
    f = _fator(agora)
    cap = pd.Series({"A": 50.0, "B": 5.0})
    pesos = pd.DataFrame({"area_id": ["A", "B"] * 12, "mes": np.repeat(range(1, 13), 2), "peso": 0.01})
    base = ex.prever(f, cap, pesos, agora, 48, 48)
    futuro = f.copy()
    futuro.loc[futuro["timestamp"] > agora, ["carga_global", "fator_mmgd"]] = [1e9, 99.0]
    assert base.equals(ex.prever(futuro, cap, pesos, agora, 48, 48))
    assert (base["origem"] <= agora).all()
    with pytest.raises(ValueError, match="vazaria"):
        ex.prever(f, cap, pesos, agora, 49, 48)


def test_area_com_mmgd_e_sem_carga_nao_some_e_pico_tem_horizonte():
    agora = pd.Timestamp("2026-09-25 10:00")
    pesos = pd.DataFrame({"area_id": ["A"] * 12, "mes": range(1, 13), "peso": 0.01})
    prev = ex.prever(_fator(agora), pd.Series({"A": 50.0, "SAT": 5.0}), pesos, agora, 48, 48)
    assert set(prev["area_id"]) == {"A", "SAT"}
    pico = ex.pico_por_area(prev, CFG["excedentes"]["horizontes"]).set_index("area_id")
    # sol máximo às 12:00 (4 passos depois das 10:00): cai no horizonte de 3 h
    assert pico.loc["A", "alvo"] == pd.Timestamp("2026-09-25 12:00")
    assert pico.loc["A", "horizonte"] == "3h"
    assert pico.loc["SAT", "excedente_mw"] == pytest.approx(0.8 * 5.0)  # sem carga: tudo exporta
    assert np.isinf(pico.loc["SAT", "penetracao"])


def test_prioridade_e_densidade():
    lim = CFG["excedentes"]["prioridade"]
    assert ex.prioridade(0.0, lim) == "low" and ex.prioridade(max(lim.values()), lim) == "critical"
    pts = ex.pontos_densidade(pd.DataFrame({"lat_rep": [-22.9, -22.5, -22.1], "lon_rep": [-43.2, -43.0, -42.0],
                                            "capacidade_mmgd_corrigida_kw": [100.0, 50.0, 0.0]}))
    assert [p[2] for p in pts] == [1.0, 0.5]  # área de influência sem MMGD fica fora do calor
