"""Conciliação ANEEL × BDGD × visão (src/spatial/conciliacao.py): etapas 4, 6 e 7 com dados sintéticos.

Os números são pequenos e escolhidos à mão para a conta caber num comentário: o teste diz o valor
esperado e de onde ele vem. Nenhum dado real é necessário (nem BDGD, nem ANEEL, nem imagem).
"""
import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Point, box

from src.spatial import conciliacao as C
from src.spatial.areas_trafo import celulas

SUSP = {"inicio": "2025-09-23", "fim": "2025-11-13", "acumulo_dias": 90}
BASE = pd.Timestamp("2025-12-31")
REF = pd.Timestamp("2026-03-31")
CRS = "EPSG:31983"


def _serie(linhas, data_ref=REF):
    """linhas: (município, data, kW); cada linha é um empreendimento."""
    cad = pd.DataFrame(linhas, columns=["mun", "data", "pot_aneel_kw"])
    cad["data"] = pd.to_datetime(cad["data"])
    return C.serie_aneel(cad, data_ref, SUSP)


# Município A: 30 kW até a data-base, +4 kW até 2026-01-28 (data da imagem), +8 kW até data_ref,
# +7 kW DEPOIS de data_ref (não pode entrar em nada). Defasagem = 42 - 30 = 12 kW.
SERIE_A = [("A", "2025-06-01", 10.0), ("A", "2025-12-01", 20.0), ("A", "2026-01-10", 4.0),
           ("A", "2026-02-15", 8.0), ("A", "2026-05-01", 7.0)]


# --------------------------------------------------------------------------- etapa 4
def test_defasagem_e_a_diferenca_da_capacidade_aneel_entre_as_datas():
    s = _serie(SERIE_A)
    d = C.defasagem(s, ["A"], {"A": BASE}, REF).iloc[0]
    assert d.capacidade_aneel_data_base == 30.0
    assert d.capacidade_aneel_data_ref == 42.0
    assert d.defasagem_kw == 12.0


def test_nada_posterior_a_data_ref_entra_na_serie_nem_na_defasagem():
    s = _serie(SERIE_A)
    assert s["data"].max() <= REF  # a conexão de 2026-05-01 ficou de fora
    com_futuro = pd.concat([s, s.tail(1).assign(data=pd.Timestamp("2026-06-01"))])
    with pytest.raises(ValueError, match="posterior a data_ref"):
        C.defasagem(com_futuro, ["A"], {"A": BASE}, REF)


def test_data_base_posterior_a_data_ref_e_erro():
    with pytest.raises(ValueError, match="data-base"):
        C.defasagem(_serie(SERIE_A), ["A"], {"A": pd.Timestamp("2026-06-30")}, REF)


def test_municipio_sem_cadastro_tem_defasagem_zero():
    d = C.defasagem(_serie(SERIE_A), ["A", "B"], {"A": BASE, "B": BASE}, REF).set_index("municipio")
    assert d.loc["B", "defasagem_kw"] == 0.0


def test_janela_de_suspensao_da_aneel_vira_flag_e_nao_correcao():
    s = _serie([("A", "2025-10-01", 1.0), ("A", "2025-12-01", 1.0), ("A", "2026-03-01", 1.0)])
    f = s.set_index("data")
    assert f.loc["2025-10-01", "flag_suspensao"] and not f.loc["2025-10-01", "flag_pos_suspensao"]
    assert f.loc["2025-12-01", "flag_pos_suspensao"]          # 18 dias depois do fim: acúmulo
    assert not f.loc["2026-03-01", "flag_pos_suspensao"]      # 108 dias depois: fora da janela
    assert s["potencia_kw_acumulada"].iloc[-1] == 3.0         # a potência não é mexida


# --------------------------------------------------------------------------- etapa 6
def _trafos(cap, exc, tem, data):
    return pd.DataFrame({"trafo_id": [f"t{i}" for i in range(1, len(cap) + 1)], "municipio": "A",
                         "capacidade_bdgd_kw": cap, "excesso_det": exc, "tem_imagem": tem,
                         "data_imagem": pd.to_datetime(data), "n_unidades_bdgd": [1] * len(cap)})


def _alocar(t, serie=None):
    serie = _serie(SERIE_A) if serie is None else serie
    return C.alocar(t, C.defasagem(serie, ["A"], {"A": BASE}, REF), serie, {"A": BASE}, REF).set_index("trafo_id")


def test_defasagem_ate_a_imagem_vai_por_excesso_so_entre_os_com_imagem():
    # pesos fallback w = 10/40, 10/40, 20/40. D = 12; até a imagem (28/01): 4 kW.
    # fallback puro: 3, 3, 6. O grupo com imagem (t1, t2) tem 4 × 0,5 = 2 kW de "até a imagem",
    # redistribuídos por excesso (t1 = 2, t2 = 0): t1 = 3 - 1 + 2 = 4; t2 = 3 - 1 + 0 = 2; t3 = 6.
    t = _alocar(_trafos([10, 10, 20], [2, 0, 0], [True, True, False], ["2026-01-28", "2026-01-28", None]))
    assert t["parcela_defasagem_kw"].to_dict() == pytest.approx({"t1": 4.0, "t2": 2.0, "t3": 6.0})
    assert t.loc[["t1", "t2"], "metodo_alocacao"].eq("visao").all()
    assert t.loc["t3", "metodo_alocacao"] == "fallback"


def test_conservacao_por_municipio():
    for exc in ([2, 0, 0], [0, 0, 0], [5, 1, 0]):
        t = _alocar(_trafos([10, 10, 20], exc, [True, True, False], ["2026-01-28", "2026-01-28", None]))
        assert t["parcela_defasagem_kw"].sum() == pytest.approx(12.0)


def test_sem_excesso_no_municipio_so_fallback():
    t = _alocar(_trafos([10, 10, 20], [0, 0, 0], [True, True, False], ["2026-01-28", "2026-01-28", None]))
    assert t["parcela_defasagem_kw"].to_dict() == pytest.approx({"t1": 3.0, "t2": 3.0, "t3": 6.0})
    assert t["metodo_alocacao"].eq("fallback").all()


def test_imagem_anterior_a_data_base_nao_aloca_por_visao():
    # imagem de 2025-05-25 (antes da BDGD de 31/12/2025): nenhuma conexão "até a imagem" depois da base
    t = _alocar(_trafos([10, 10, 20], [9, 0, 0], [True, True, False], ["2025-05-25", "2025-05-25", None]))
    assert t["parcela_defasagem_kw"].to_dict() == pytest.approx({"t1": 3.0, "t2": 3.0, "t3": 6.0})
    assert t["metodo_alocacao"].eq("fallback").all()


def test_imagem_posterior_a_data_ref_so_conta_ate_data_ref():
    # imagem em 2026-06-01 (> data_ref): o "até a imagem" é cortado em data_ref (12 kW, tudo)
    t = _alocar(_trafos([10, 10, 20], [1, 0, 0], [True, True, False], ["2026-06-01", "2026-06-01", None]))
    # pool = 12 × 0,5 = 6 -> t1 = 3 - 3 + 6 = 6; t2 = 3 - 3 + 0 = 0; t3 = 6
    assert t["parcela_defasagem_kw"].to_dict() == pytest.approx({"t1": 6.0, "t2": 0.0, "t3": 6.0})


def test_capacidade_bdgd_zero_no_municipio_reparte_em_partes_iguais():
    t = _alocar(_trafos([0, 0, 0], [0, 0, 0], [False] * 3, [None] * 3))
    assert t["parcela_defasagem_kw"].tolist() == pytest.approx([4.0, 4.0, 4.0])
    assert t["fallback_uniforme"].all()


def test_nenhuma_capacidade_negativa_e_corrigida_e_bdgd_mais_parcela():
    t = _alocar(_trafos([10, 0, 20], [7, 0, 3], [True, True, True], ["2026-01-28"] * 3))
    for col in ("parcela_defasagem_kw", "capacidade_corrigida_kw", "faixa_min_kw", "faixa_max_kw"):
        assert (t[col] >= 0).all()
    assert (t["capacidade_corrigida_kw"] == t["capacidade_bdgd_kw"] + t["parcela_defasagem_kw"]).all()


# --------------------------------------------------------------------------- etapa 7
def test_faixa_vai_da_alocacao_com_visao_a_100pct_fallback():
    t = _alocar(_trafos([10, 10, 20], [2, 0, 0], [True, True, False], ["2026-01-28", "2026-01-28", None]))
    # t1: com visão 4, fallback 3 -> [13, 14]; t2: 2 e 3 -> [12, 13]; t3: 6 e 6 -> [26, 26]
    assert (t["faixa_min_kw"].to_dict(), t["faixa_max_kw"].to_dict()) == (
        pytest.approx({"t1": 13.0, "t2": 12.0, "t3": 26.0}), pytest.approx({"t1": 14.0, "t2": 13.0, "t3": 26.0}))
    assert ((t["faixa_min_kw"] <= t["capacidade_corrigida_kw"]) & (t["capacidade_corrigida_kw"] <= t["faixa_max_kw"])).all()


def _residuo(exc, data, limiar=2.0):
    t = _trafos([10, 10, 20], exc, [True, True, False], [data, data, None])
    return C.residuo(t, _serie(SERIE_A), {"A": BASE}, REF, limiar).iloc[0]


def test_residuo_quando_o_excesso_supera_muito_as_conexoes_esperadas():
    # Conexões ANEEL entre a base e 28/01: 1 empreendimento. Fatia da área varrida: 2 de 3 unidades
    # BDGD -> esperado 2/3. Excesso 10 > 2 × 2/3 -> resíduo = 10 - 2/3.
    assert _residuo([6, 4, 0], "2026-01-28").residuo_satelite == pytest.approx(10 - 2 / 3, abs=0.01)
    # Excesso 1 <= 2 × 2/3: dentro do esperado, sem resíduo.
    assert _residuo([1, 0, 0], "2026-01-28").residuo_satelite == 0.0


def test_imagem_anterior_a_base_todo_excesso_e_residuo():
    assert _residuo([6, 4, 0], "2025-05-25").residuo_satelite == pytest.approx(10.0)


def test_residuo_nao_entra_na_capacidade():
    # Mesma defasagem, excesso pequeno ou enorme: a capacidade total do município é a mesma.
    pouco = _alocar(_trafos([10, 10, 20], [1, 0, 0], [True, True, False], ["2026-01-28", "2026-01-28", None]))
    muito = _alocar(_trafos([10, 10, 20], [500, 0, 0], [True, True, False], ["2026-01-28", "2026-01-28", None]))
    assert pouco["capacidade_corrigida_kw"].sum() == pytest.approx(muito["capacidade_corrigida_kw"].sum()) == 52.0


# --------------------------------------------------------------------------- etapas 2 e 5 (apoio)
def test_retrato_usa_potencia_da_aneel_pelo_ceg_e_tira_o_que_nao_e_solar():
    ug = pd.DataFrame({"ceg": ["GD.1", "GD.2", "GD.3", "GD.1"], "trafo_id": ["x", "x", "y", "x"],
                       "mun": "A", "pot_bdgd_kw": [1.0, 2.0, 3.0, 1.0]})
    an = pd.DataFrame({"ceg": ["GD.1", "GD.3"], "pot_aneel_kw": [5.0, 9.0], "tipo": ["UFV", "UTE"]})
    u = C.retrato_bdgd(ug, an, "UFV")
    assert set(u["ceg"]) == {"GD.1", "GD.2"}       # GD.3 é térmica; GD.1 repetido conta uma vez
    pt = C.por_trafo(u).set_index("trafo_id")
    assert pt.loc["x", "capacidade_bdgd_kw"] == 7.0  # 5 (ANEEL) + 2 (POT_INST, sem cadastro)
    assert pt.loc["x", "kw_sem_aneel"] == 2.0 and pt.loc["x", "n_unidades_bdgd"] == 2


def test_excesso_e_por_grupo_colocalizado_e_so_com_imagem():
    sinal = pd.DataFrame({"trafo_id": ["a", "b", "c"], "grupo": ["g1", "g1", "g2"], "n_no_grupo": [2, 2, 1],
                          "n_det_grupo": [5.0, 5.0, 4.0], "tem_imagem": [True, True, False]})
    trafos = pd.DataFrame({"trafo_id": ["a", "b", "c"], "n_unidades_bdgd": [1, 0, 0]})
    e = C.excesso(sinal, trafos)
    assert e.to_dict() == {"a": 2.0, "b": 2.0, "c": 0.0}  # (5 - 1) / 2 no grupo; sem imagem = 0


def test_celulas_particionam_o_municipio_e_respeitam_o_raio():
    mun = gpd.GeoDataFrame({"codarea": ["A"]}, geometry=[box(0, 0, 1000, 1000)], crs=CRS)
    pts = gpd.GeoDataFrame({"trafo_id": ["t1", "t2", "t3"], "municipio": "A"},
                           geometry=[Point(250, 500), Point(750, 500), Point(750, 500)], crs=CRS)
    c = celulas(pts, mun, raio_m=10_000).set_index("trafo_id")
    assert c.loc["t2", "grupo"] == c.loc["t3", "grupo"] and c.loc["t2", "n_no_grupo"] == 2
    assert c.drop_duplicates("grupo").geometry.area.sum() == pytest.approx(1_000_000)
    pequeno = celulas(pts, mun, raio_m=100)
    assert (pequeno.geometry.area <= 3.1416 * 100 ** 2 + 1).all()


def test_sinal_visao_conta_so_confianca_minima_e_imagem_ate_data_ref():
    mun = gpd.GeoDataFrame({"codarea": ["A"]}, geometry=[box(0, 0, 1000, 1000)], crs=CRS)
    pts = gpd.GeoDataFrame({"trafo_id": ["t1", "t2"], "municipio": "A"},
                           geometry=[Point(250, 500), Point(750, 500)], crs=CRS)
    areas = celulas(pts, mun, raio_m=10_000)
    cob = gpd.GeoDataFrame({"data_imagem": ["2026-01-28"]}, geometry=[box(0, 0, 500, 1000)], crs=CRS)
    det = gpd.GeoDataFrame({"confianca": [0.9, 0.3, 0.8], "data_imagem": ["2026-01-28"] * 3},
                           geometry=[Point(100, 100), Point(200, 200), Point(300, 300)], crs=CRS)
    s = C.sinal_visao(areas, det, cob, 0.6, 0.95, REF, CRS).set_index("trafo_id")
    assert s.loc["t1", "tem_imagem"] and s.loc["t1", "n_det_grupo"] == 2  # a de 0,3 não conta
    assert not s.loc["t2", "tem_imagem"] and pd.isna(s.loc["t2", "data_imagem"])
    # a mesma imagem, se fosse posterior a data_ref, não vale
    s2 = C.sinal_visao(areas, det, cob.assign(data_imagem="2026-06-01"), 0.6, 0.95, REF, CRS)
    assert not s2["tem_imagem"].any()
