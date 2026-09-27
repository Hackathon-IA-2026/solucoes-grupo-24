"""Conciliação da capacidade de MMGD por transformador: ANEEL × BDGD × visão computacional.

Cada fonte entra no que ela tem de melhor:
- ANEEL (cadastro de MMGD): QUANTO foi conectado e QUANDO. Só localiza por município.
- BDGD: ONDE NA REDE (transformador MT/BT) estava a MMGD na data-base do extrato.
- Visão computacional: ONDE FISICAMENTE surgiu painel, inclusive depois da data-base.
Princípio: conciliar AGREGADOS por município e por transformador, nunca casar telhado com registro.
A área do painel NÃO vira kW aqui: das detecções só entram contagem e localização.

Etapas (numeração do pedido; cada uma é uma função pura, testada em tests/test_conciliacao.py):
1. serie_aneel / capacidade_aneel: potência acumulada (kW) por município × data, só UFV.
2. retrato_bdgd: potência e nº de unidades geradoras por transformador na data-base.
3. cobertura: capacidade BDGD do município ÷ capacidade ANEEL na data-base, com faixa de confiança.
4. defasagem: capacidade_aneel(m, data_ref) − capacidade_aneel(m, data_base).
5. sinal_visao: detecções (confiança mínima) por área atendida; excesso = max(0, detecções − unidades).
6. alocar: distribui a defasagem entre os transformadores do município.
7. alocar (faixa) e residuo: incerteza entre a alocação com visão e a 100% fallback; resíduo à parte.

Decisões:
- Potência da BDGD = a do CADASTRO da ANEEL para o mesmo CEG (registro com registro, decisão do Luiz
  em 2026-09-27). Na BDGD 2025 da Enel o POT_INST vem ~5× menor que o cadastro para o mesmo
  empreendimento; na LIGHT bate. CEG que a ANEEL não tem: fica o POT_INST, com flag.
- Etapa 6, como a regra "parte da defasagem até a data da imagem vai só para os transformadores com
  imagem" foi lida: cada transformador começa com a parte fallback (defasagem × participação na
  capacidade BDGD do município). No grupo com imagem de data d, a parte de cada um que corresponde
  às conexões até d (ANEEL entre data-base e d) é juntada e redistribuída por excesso de detecções.
  Assim o que o município inteiro conectou até d não vai todo para a pequena área varrida: a área
  varrida recebe a fatia que o fallback já lhe daria, só que dividida pelo que a imagem mostra.
  Conservação exata por construção (testada), e nada fica negativo.
- Imagem anterior à data-base (Rio: 25/05 e 07/12/2025 contra BDGD de 31/12/2025): não há conexão
  ANEEL "até a imagem" depois da data-base, então a visão não aloca nada; o excesso vai para o resíduo.
- Transformadores no mesmo ponto (mesmo posto) dividem a área atendida: o excesso é calculado no
  grupo e repartido em partes iguais.
- Nada posterior a data_ref entra: cadastro cortado em data_ref, imagem de data posterior = sem imagem.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import geopandas as gpd
import numpy as np
import pandas as pd

from src.spatial import bdgd, mmgd
from src.spatial.relatorio_conciliacao import escrever
from src.spatial.conciliacao_cfg import caminho, cfg, piloto, saida
from src.utils.paths import ensure

TOL = 1e-6  # tolerância relativa das checagens de conservação


def _flags(*pares) -> str:
    """'a;b' com as flags cujo teste é verdadeiro (texto vazio = nenhuma)."""
    return ";".join(nome for nome, cond in pares if cond)


# --------------------------------------------------------------------------- 1. série ANEEL
def serie_aneel(cad: pd.DataFrame, data_ref: pd.Timestamp, susp: dict) -> pd.DataFrame:
    """Potência acumulada por município × data (kW), só até data_ref.

    `cad`: mun, data, pot_aneel_kw (já filtrado por tipo e distribuidora). Devolve municipio, data,
    potencia_kw_dia, n_dia, potencia_kw_acumulada, n_acumulado, flag_suspensao, flag_pos_suspensao.
    """
    c = cad[cad["data"] <= data_ref].dropna(subset=["mun", "data", "pot_aneel_kw"])
    s = (c.groupby(["mun", "data"]).agg(potencia_kw_dia=("pot_aneel_kw", "sum"), n_dia=("pot_aneel_kw", "size"))
         .reset_index().rename(columns={"mun": "municipio"}).sort_values(["municipio", "data"]))
    s["potencia_kw_acumulada"] = s.groupby("municipio")["potencia_kw_dia"].cumsum()
    s["n_acumulado"] = s.groupby("municipio")["n_dia"].cumsum()
    ini, fim = pd.Timestamp(susp["inicio"]), pd.Timestamp(susp["fim"])
    s["flag_suspensao"] = s["data"].between(ini, fim)
    s["flag_pos_suspensao"] = (s["data"] > fim) & (s["data"] <= fim + pd.Timedelta(days=int(susp["acumulo_dias"])))
    return s.reset_index(drop=True)


def capacidade_aneel(serie: pd.DataFrame, municipio: str, data: pd.Timestamp, coluna: str = "potencia_kw_acumulada") -> float:
    """Potência acumulada (ou nº de empreendimentos, coluna='n_acumulado') do município até a data."""
    s = serie[(serie["municipio"] == municipio) & (serie["data"] <= data)]
    return float(s[coluna].iloc[-1]) if len(s) else 0.0


# --------------------------------------------------------------------------- 2. retrato BDGD
def retrato_bdgd(ug: pd.DataFrame, an: pd.DataFrame, tipo: str) -> pd.DataFrame:
    """Uma linha por empreendimento da BDGD com a potência conciliada.

    `ug`: ceg, trafo_id, mun, pot_bdgd_kw (unidades_mmgd). `an`: ceg, pot_aneel_kw, tipo.
    Potência = a da ANEEL pelo CEG; sem CEG na ANEEL, POT_INST da BDGD (sem_aneel=True).
    Empreendimento que a ANEEL diz não ser do `tipo` (ex.: térmica) sai.
    """
    u = ug.drop_duplicates("ceg").merge(an.drop_duplicates("ceg")[["ceg", "pot_aneel_kw", "tipo"]], on="ceg", how="left")
    u = u[u["tipo"].isna() | (u["tipo"] == tipo)].copy()
    u["sem_aneel"] = u["pot_aneel_kw"].isna()
    u["pot_kw"] = u["pot_aneel_kw"].fillna(u["pot_bdgd_kw"]).astype(float)
    return u


def por_trafo(u: pd.DataFrame) -> pd.DataFrame:
    """capacidade_bdgd_kw e n_unidades_bdgd por transformador (só unidades de BT têm trafo)."""
    t = u.dropna(subset=["trafo_id"]).assign(kw_sem_aneel=lambda d: d["pot_kw"].where(d["sem_aneel"], 0.0))
    return (t.groupby("trafo_id").agg(capacidade_bdgd_kw=("pot_kw", "sum"), n_unidades_bdgd=("ceg", "size"),
                                      kw_sem_aneel=("kw_sem_aneel", "sum"))
            .reset_index())


# --------------------------------------------------------------------------- 3. cobertura
def cobertura(cap_bdgd_mun: float, cap_aneel_base: float, faixa: tuple[float, float]) -> tuple[float | None, bool]:
    """(razão BDGD/ANEEL na data-base, baixa_confiabilidade). ANEEL zero: razão indefinida."""
    if cap_aneel_base <= 0:
        return None, True
    r = cap_bdgd_mun / cap_aneel_base
    return r, not (faixa[0] <= r <= faixa[1])


# --------------------------------------------------------------------------- 4. defasagem
def defasagem(serie: pd.DataFrame, municipios: list[str], data_base: dict[str, pd.Timestamp],
              data_ref: pd.Timestamp) -> pd.DataFrame:
    """defasagem_kw(m) = capacidade_aneel(m, data_ref) − capacidade_aneel(m, data_base(m)).

    Só usa a série até data_ref (a série já vem cortada; aqui a checagem é explícita).
    """
    if (serie["data"] > data_ref).any():
        raise ValueError("série ANEEL com data posterior a data_ref")
    linhas = []
    for m in municipios:
        base = data_base[m]
        if base > data_ref:
            raise ValueError(f"município {m}: data-base da BDGD ({base.date()}) posterior a data_ref ({data_ref.date()})")
        a_base, a_ref = capacidade_aneel(serie, m, base), capacidade_aneel(serie, m, data_ref)
        linhas.append({"municipio": m, "capacidade_aneel_data_base": a_base, "capacidade_aneel_data_ref": a_ref,
                       "defasagem_kw": a_ref - a_base})
    return pd.DataFrame(linhas)


# --------------------------------------------------------------------------- 5. sinal da visão
def sinal_visao(areas: gpd.GeoDataFrame, deteccoes: gpd.GeoDataFrame, cobertura_img: gpd.GeoDataFrame,
                conf_min: float, cobertura_min: float, data_ref: pd.Timestamp, crs_metrico: str) -> pd.DataFrame:
    """Por transformador: n_deteccoes, tem_imagem, data_imagem e a fração coberta por imagem.

    `areas`: trafo_id, grupo, n_no_grupo, geometry (área atendida). `deteccoes`: pontos (lat/lon da
    detecção) com confianca e data_imagem. `cobertura_img`: polígonos varridos com data_imagem.
    Detecção abaixo de conf_min ou com imagem posterior a data_ref não conta; imagem posterior a
    data_ref não vale como imagem. Um transformador "tem imagem" se >= cobertura_min da área atendida
    está varrida; a data é a da imagem que cobre a maior parte dela.
    """
    a = areas[["trafo_id", "grupo", "n_no_grupo", "geometry"]].to_crs(crs_metrico)
    celulas = a.drop_duplicates("grupo")[["grupo", "geometry"]]
    celulas = celulas[~celulas.geometry.is_empty]
    out = a[["trafo_id", "grupo", "n_no_grupo"]].copy()

    grupos = pd.Index(out["grupo"].unique(), name="grupo")
    g = pd.DataFrame({"fracao_imagem": 0.0, "data_imagem": pd.NaT, "n_det_grupo": 0.0}, index=grupos)

    cob = cobertura_img.to_crs(crs_metrico)
    cob = cob[pd.to_datetime(cob["data_imagem"]) <= data_ref]  # imagem depois de data_ref = sem imagem
    if len(cob) and len(celulas):
        inter = gpd.overlay(celulas, cob[["data_imagem", "geometry"]], how="intersection", keep_geom_type=True)
        if len(inter):
            inter["a"] = inter.geometry.area
            area_cel = celulas.set_index("grupo").geometry.area
            frac = inter.groupby("grupo")["a"].sum() / area_cel.reindex(inter["grupo"].unique())
            # data da imagem que cobre a MAIOR parte da área (empate: a mais antiga)
            dom = (inter.sort_values(["a", "data_imagem"], ascending=[False, True])
                   .drop_duplicates("grupo").set_index("grupo")["data_imagem"])
            g.loc[frac.index, "fracao_imagem"] = frac.clip(upper=1.0).values
            g.loc[dom.index, "data_imagem"] = pd.to_datetime(dom).values

    d = deteccoes[deteccoes["confianca"] >= conf_min]
    d = d[pd.to_datetime(d["data_imagem"]) <= data_ref]
    if len(d) and len(celulas):
        j = gpd.sjoin(d.to_crs(crs_metrico)[["geometry"]], celulas, predicate="within", how="inner")
        n = j.groupby("grupo").size()
        g.loc[n.index, "n_det_grupo"] = n.values.astype(float)
    g["tem_imagem"] = g["fracao_imagem"] >= cobertura_min
    out = out.merge(g, left_on="grupo", right_index=True, how="left")
    out["data_imagem"] = pd.to_datetime(out["data_imagem"]).where(out["tem_imagem"])
    return out


def excesso(sinal: pd.DataFrame, trafos: pd.DataFrame) -> pd.Series:
    """excesso_det por transformador = max(0, detecções − unidades BDGD) do GRUPO, em partes iguais.

    Só onde há imagem (sem imagem, detecção zero não é evidência de nada). `trafos`: trafo_id,
    n_unidades_bdgd. Devolve uma Series indexada por trafo_id.
    """
    s = sinal.merge(trafos[["trafo_id", "n_unidades_bdgd"]], on="trafo_id", how="left").fillna({"n_unidades_bdgd": 0})
    ug_grupo = s.groupby("grupo")["n_unidades_bdgd"].transform("sum")
    exc = (s["n_det_grupo"] - ug_grupo).clip(lower=0) / s["n_no_grupo"]
    return pd.Series(np.where(s["tem_imagem"], exc, 0.0), index=s["trafo_id"], name="excesso_det")


# --------------------------------------------------------------------------- 6 e 7. alocação
def alocar(t: pd.DataFrame, defas: pd.DataFrame, serie: pd.DataFrame, data_base: dict[str, pd.Timestamp],
           data_ref: pd.Timestamp) -> pd.DataFrame:
    """Parcela da defasagem por transformador, com visão e 100% fallback (faixa de incerteza).

    `t`: trafo_id, municipio, capacidade_bdgd_kw, excesso_det, tem_imagem, data_imagem.
    `defas`: saída de `defasagem`. Devolve `t` com parcela_defasagem_kw, parcela_fallback_kw,
    capacidade_corrigida_kw, faixa_min_kw, faixa_max_kw, metodo_alocacao, fallback_uniforme.
    """
    partes = []
    for m, g in t.groupby("municipio", sort=True):
        g = g.copy()
        D = float(defas.loc[defas["municipio"] == m, "defasagem_kw"].iloc[0]) if (defas["municipio"] == m).any() else 0.0
        base = data_base[m]
        tot = g["capacidade_bdgd_kw"].sum()
        # participação na capacidade BDGD do município; sem nenhuma capacidade, partes iguais (flag)
        w = g["capacidade_bdgd_kw"] / tot if tot > 0 else pd.Series(1.0 / len(g), index=g.index)
        g["fallback_uniforme"] = tot <= 0
        g["parcela_fallback_kw"] = D * w
        parcela = g["parcela_fallback_kw"].copy()
        metodo = pd.Series("fallback", index=g.index)
        a_base = capacidade_aneel(serie, m, base)
        for d, grupo in g[g["tem_imagem"] & g["data_imagem"].notna()].groupby("data_imagem"):
            # conexões ANEEL entre a data-base e a imagem (nunca além de data_ref)
            d_ate = max(0.0, capacidade_aneel(serie, m, min(pd.Timestamp(d), data_ref)) - a_base)
            e = grupo["excesso_det"]
            if d_ate <= 0 or e.sum() <= 0:
                continue  # imagem anterior à data-base, ou nada a mais na imagem: fica o fallback
            pool = d_ate * w[grupo.index].sum()
            parcela[grupo.index] = parcela[grupo.index] - d_ate * w[grupo.index] + pool * e / e.sum()
            metodo[grupo.index] = "visao"
        g["parcela_defasagem_kw"] = parcela
        g["metodo_alocacao"] = metodo
        partes.append(g)
    out = pd.concat(partes) if partes else t.iloc[0:0]
    out["capacidade_corrigida_kw"] = out["capacidade_bdgd_kw"] + out["parcela_defasagem_kw"]
    out["faixa_min_kw"] = out["capacidade_bdgd_kw"] + np.minimum(out["parcela_defasagem_kw"], out["parcela_fallback_kw"])
    out["faixa_max_kw"] = out["capacidade_bdgd_kw"] + np.maximum(out["parcela_defasagem_kw"], out["parcela_fallback_kw"])
    return out


def residuo(t: pd.DataFrame, serie: pd.DataFrame, data_base: dict[str, pd.Timestamp], data_ref: pd.Timestamp,
            limiar: float) -> pd.DataFrame:
    """Resíduo do satélite por município (nº de instalações): NÃO entra na capacidade.

    Para cada grupo de imagem (data d): excesso total de detecções contra as conexões ANEEL esperadas
    na área varrida entre a data-base e d (conexões do município × fatia das unidades BDGD que estão na
    área varrida). Excesso > limiar × esperado -> resíduo = excesso − esperado. Imagem anterior à
    data-base: esperado = 0, todo excesso é resíduo. `t`: municipio, excesso_det, tem_imagem,
    data_imagem, n_unidades_bdgd.
    """
    linhas = []
    for m, g in t.groupby("municipio", sort=True):
        n_mun = g["n_unidades_bdgd"].sum()
        n_base = capacidade_aneel(serie, m, data_base[m], "n_acumulado")
        res, exc_tot, esp_tot = 0.0, 0.0, 0.0
        for d, grupo in g[g["tem_imagem"] & g["data_imagem"].notna()].groupby("data_imagem"):
            conexoes = max(0.0, capacidade_aneel(serie, m, min(pd.Timestamp(d), data_ref), "n_acumulado") - n_base)
            esperado = conexoes * (grupo["n_unidades_bdgd"].sum() / n_mun if n_mun > 0 else 0.0)
            exc = float(grupo["excesso_det"].sum())
            exc_tot, esp_tot = exc_tot + exc, esp_tot + esperado
            if exc > limiar * esperado:
                res += exc - esperado
        linhas.append({"municipio": m, "residuo_satelite": round(res, 2), "excesso_det_total": exc_tot,
                       "conexoes_esperadas_area_varrida": esp_tot})
    return pd.DataFrame(linhas)


def checar(trafo: pd.DataFrame, mun: pd.DataFrame, serie: pd.DataFrame, data_ref: pd.Timestamp) -> None:
    """Checagens obrigatórias. Qualquer falha interrompe a publicação (nada sai errado em silêncio)."""
    soma = trafo.groupby("municipio")["parcela_defasagem_kw"].sum()
    for r in mun.itertuples():
        if abs(soma.get(r.municipio, 0.0) - r.defasagem_kw) > TOL * max(1.0, abs(r.defasagem_kw)):
            raise AssertionError(f"conservação: município {r.municipio} alocou {soma.get(r.municipio, 0.0)} "
                                 f"de {r.defasagem_kw} kW")
    for col in ("capacidade_bdgd_kw", "parcela_defasagem_kw", "capacidade_corrigida_kw", "faixa_min_kw", "faixa_max_kw"):
        if (trafo[col] < -TOL).any():
            raise AssertionError(f"capacidade negativa em {col}")
    if trafo["municipio"].isna().any() or (trafo["municipio"].astype(str) == "").any():
        raise AssertionError("transformador sem município")
    if (serie["data"] > data_ref).any() or (trafo["data_imagem"].dropna() > data_ref).any():
        raise AssertionError("dado posterior a data_ref no cálculo")


# --------------------------------------------------------------------------- orquestração
def _deteccoes() -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame, dict]:
    """Detecções (pontos) e cobertura varrida do pipeline de visão. Ausentes -> vazias (sem imagem)."""
    v = cfg()["visao"]
    arq_det, arq_cob = caminho(v["saida_deteccoes"]), caminho(v["saida_cobertura"])
    if not (arq_det.exists() and arq_cob.exists()):
        vazio = gpd.GeoDataFrame({"confianca": [], "data_imagem": []}, geometry=[], crs="EPSG:4326")
        return vazio, gpd.GeoDataFrame({"data_imagem": []}, geometry=[], crs="EPSG:4326"), {}
    dados = json.loads(arq_det.read_text(encoding="utf-8"))
    props = [f["properties"] for f in dados["features"]]
    det = gpd.GeoDataFrame(pd.DataFrame(props, columns=["confianca", "data_imagem", "lat", "lon"]),
                           geometry=gpd.points_from_xy([p["lon"] for p in props], [p["lat"] for p in props]),
                           crs="EPSG:4326")
    return det, gpd.read_parquet(arq_cob), dados.get("properties", {})


def construir() -> dict[str, pd.DataFrame]:
    """Roda as etapas 1-7 na área piloto e grava as saídas (parquets, camada do mapa, relatório)."""
    c = cfg()
    crs = bdgd.cfg()["geometria"]["crs_metrico"]
    pil = piloto()
    dists = {d.sigla: d for d in bdgd.distribuidoras()}
    areas = gpd.read_parquet(saida("areas_trafo"))

    # --- ANEEL: só UFV, só a distribuidora do piloto em cada município
    an = mmgd.cadastro_aneel([dists[s].agente_aneel for s in pil])
    an = an[an["tipo"] == c["aneel"]["tipo_geracao"]]
    mun_dist = {m: s for s, ms in pil.items() for m in ms}
    agente_do_mun = {m: dists[s].agente_aneel for m, s in mun_dist.items()}
    an = an[an["agente"] == an["mun"].map(agente_do_mun)]  # município fora do piloto: NaN, sai
    data_ref = pd.Timestamp(c["data_ref"]) if c["data_ref"] else an["data"].max()
    data_geracao = an["data_geracao"].max()
    serie = serie_aneel(an, data_ref, c["aneel"]["suspensao"])
    data_base = {m: bdgd.data_referencia(dists[s]) for m, s in mun_dist.items()}

    # --- BDGD: empreendimentos (potência ANEEL pelo CEG) e retrato por transformador
    ugs = []
    for s in pil:
        ug = bdgd.unidades_mmgd(dists[s])
        ug = ug[ug["mun"].isin(pil[s]) | ug["trafo_id"].isin(areas["trafo_id"])]
        ugs.append(retrato_bdgd(ug, an[an["agente"] == dists[s].agente_aneel], c["aneel"]["tipo_geracao"]))
    u = pd.concat(ugs, ignore_index=True)
    pt = por_trafo(u)
    t = areas[["trafo_id", "distribuidora", "municipio", "grupo", "n_no_grupo", "lat", "lon"]].merge(pt, on="trafo_id", how="left")
    t = t.fillna({"capacidade_bdgd_kw": 0.0, "n_unidades_bdgd": 0, "kw_sem_aneel": 0.0})

    # --- defasagem e cobertura por município
    defas = defasagem(serie, sorted(mun_dist), data_base, data_ref)
    cap_mun = u[u["mun"].isin(mun_dist)].groupby("mun")["pot_kw"].sum()

    # --- visão
    det, cob, meta_visao = _deteccoes()
    sv = sinal_visao(areas, det, cob, float(c["conciliacao"]["confianca_minima"]),
                     float(c["conciliacao"]["cobertura_imagem_minima"]), data_ref, crs)
    t = t.merge(sv.drop(columns=["grupo", "n_no_grupo"]), on="trafo_id", how="left")
    t["excesso_det"] = t["trafo_id"].map(excesso(sv, t))

    # --- alocação, faixa e resíduo
    t = alocar(t, defas, serie, data_base, data_ref)
    res = residuo(t, serie, data_base, data_ref, float(c["conciliacao"]["limiar_residuo"]))

    # --- flags
    faixa = tuple(c["cobertura"]["faixa"])
    susp = c["aneel"]["suspensao"]
    fim_acumulo = pd.Timestamp(susp["fim"]) + pd.Timedelta(days=int(susp["acumulo_dias"]))
    linhas = []
    for r in defas.itertuples():
        razao, baixa = cobertura(float(cap_mun.get(r.municipio, 0.0)), r.capacidade_aneel_data_base, faixa)
        g = t[t["municipio"] == r.municipio]
        rr = res.set_index("municipio").loc[r.municipio]
        datas_img = g.loc[g["tem_imagem"], "data_imagem"].dropna().unique()
        base = data_base[r.municipio]
        linhas.append({
            "municipio": r.municipio, "capacidade_aneel_data_base": round(r.capacidade_aneel_data_base, 3),
            "capacidade_aneel_data_ref": round(r.capacidade_aneel_data_ref, 3), "defasagem_kw": round(r.defasagem_kw, 3),
            "razao_cobertura_bdgd": None if razao is None else round(razao, 4),
            "residuo_satelite": float(rr["residuo_satelite"]),
            "flags": _flags(
                ("baixa_confiabilidade_cobertura", baixa),
                ("suspensao_aneel_no_intervalo", pd.Timestamp(susp["inicio"]) <= data_ref and fim_acumulo > base),
                ("data_ref_sujeita_a_atraso", (data_geracao - data_ref).days < int(c["aneel"]["atraso_insercao_dias"])),
                ("residuo_satelite", rr["residuo_satelite"] > 0),
                ("fallback_uniforme", bool(g["fallback_uniforme"].any())),
                ("multiplas_datas_imagem", len(datas_img) > 1),
                ("imagem_anterior_data_base", any(pd.Timestamp(d) <= base for d in datas_img)),
                ("sem_imagem", len(datas_img) == 0)),
            "data_base_bdgd": base.date().isoformat(), "data_ref": data_ref.date().isoformat(),
        })
    mun = pd.DataFrame(linhas)
    baixa_conf = set(mun.loc[mun["flags"].str.contains("baixa_confiabilidade"), "municipio"])
    t["flags"] = [
        _flags(("ponto_fora_do_municipio", cel_vazia), ("imagem_parcial", 0 < fr < 1 and not tem),
               ("grupo_colocalizado", n > 1), ("municipio_baixa_confiabilidade", m in baixa_conf),
               ("imagem_anterior_data_base", tem and pd.notna(di) and di <= data_base[m]),
               ("kw_sem_cadastro_aneel", kw > 0))
        for cel_vazia, fr, tem, n, m, di, kw in zip(
            t["trafo_id"].isin(areas.loc[areas.geometry.is_empty, "trafo_id"]), t["fracao_imagem"].fillna(0),
            t["tem_imagem"].fillna(False), t["n_no_grupo"], t["municipio"], t["data_imagem"], t["kw_sem_aneel"])]
    t["tem_imagem"] = t["tem_imagem"].fillna(False).astype(bool)

    checar(t, mun, serie, data_ref)

    # --- saídas
    cols = ["id_transformador", "municipio", "capacidade_bdgd_kw", "parcela_defasagem_kw", "capacidade_corrigida_kw",
            "faixa_min_kw", "faixa_max_kw", "metodo_alocacao", "tem_imagem", "data_imagem", "flags"]
    trafo = t.rename(columns={"trafo_id": "id_transformador"})
    for col in ("capacidade_bdgd_kw", "parcela_defasagem_kw", "capacidade_corrigida_kw", "faixa_min_kw", "faixa_max_kw"):
        trafo[col] = trafo[col].astype(float)
    trafo_out = trafo[cols].sort_values(["municipio", "id_transformador"]).reset_index(drop=True)
    mun_out = mun[["municipio", "capacidade_aneel_data_base", "capacidade_aneel_data_ref", "defasagem_kw",
                   "razao_cobertura_bdgd", "residuo_satelite", "flags", "data_base_bdgd", "data_ref"]]
    for nome, df in (("capacidade_trafo", trafo_out), ("defasagem_municipio", mun_out), ("serie_aneel", serie)):
        destino = saida(nome)
        ensure(destino.parent)
        df.to_parquet(destino, index=False)
    camada_mapa(trafo)
    # Empreendimento da BDGD cuja data no cadastro é posterior à data-base: está no retrato E na
    # defasagem (a data da ANEEL é a do último recadastro). Medido para o relatório, não corrigido.
    datas = an.drop_duplicates("ceg").set_index("ceg")["data"]
    uu = u.assign(data_aneel=u["ceg"].map(datas))
    dupla = {m: float(uu.loc[(uu["mun"] == m) & (uu["data_aneel"] > data_base[m]), "pot_kw"].sum()) for m in sorted(mun_dist)}
    escrever(trafo, mun, res, serie, u, data_base, data_ref, data_geracao, meta_visao, det, c, dupla)
    print(f"conciliação: {len(trafo_out)} transformadores, {len(mun_out)} municípios, data_ref {data_ref.date()}")
    return {"trafo": trafo_out, "municipio": mun_out, "serie": serie}


def camada_mapa(trafo: pd.DataFrame) -> dict:
    """Camada do Mapa Híbrido no MESMO formato do heatmap do contrato (DensidadeMmgd).

    Um ponto por transformador com capacidade corrigida > 0 (posição do trafo na BDGD). Intensidade
    = capacidade ÷ percentil 99 (limitada a 1): com o máximo, uma minigeração grande apagaria o resto.
    Validada com o modelo do contrato: o dashboard lê com o mesmo esquema do heatmap existente.
    """
    from src.contrato.modelos import DensidadeMmgd

    p = trafo[(trafo["capacidade_corrigida_kw"] > 0) & trafo["lat"].notna()]
    ref = float(np.percentile(p["capacidade_corrigida_kw"], 99)) if len(p) else 1.0
    pontos = [[round(float(la), 6), round(float(lo), 6), round(min(1.0, float(k) / ref), 4)]
              for la, lo, k in zip(p["lat"], p["lon"], p["capacidade_corrigida_kw"])]
    corpo = DensidadeMmgd(mock=False, descricao=cfg()["saidas"]["descricao_camada"], pontos=pontos).para_json()
    corpo["geradoEm"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    corpo["referenciaKw"] = round(ref, 2)  # capacidade (kW) que vale intensidade 1
    destino = saida("camada_mapa")
    ensure(destino.parent)
    destino.write_text(json.dumps(corpo, ensure_ascii=False), encoding="utf-8")
    return corpo


if __name__ == "__main__":
    construir()
