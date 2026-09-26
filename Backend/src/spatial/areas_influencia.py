"""Áreas de influência das subestações: um polígono por subestação, cobrindo o estado sem sobreposição.

Herdado de Backend/RDX/extrator.py (run_pipeline, preencher_buracos_rj,
processar_classificacao_e_hierarquia). O método é o mesmo; mudanças:
- Tudo é calculado em CRS métrico (config: crs_metrico). O RDX fazia as diferenças de
  polígonos em graus (EPSG:4326) e só projetava em alguns passos.
- O Voronoi usa `ordered=True` (shapely 2.1): cada célula sai na ordem do seu ponto, sem a
  busca "qual ponto está nesta célula" do RDX (que falhava com pontos na borda da célula).
- Área de influência que o recorte deixa vazia NÃO some em silêncio (o RDX descartava): fica com
  `geometria_vazia=True` e continua nas tabelas (a MMGD dela é contada; o ponto da
  subestação continua existindo para o mapa).
- Limite do estado: malha do IBGE baixada pela ingestão (o RDX usava o pacote geobr).

Passos (`construir_areas`):
1. Área inicial: fecho convexo dos transformadores MT/BT de cada subestação; sem transformadores
   suficientes, um círculo mínimo em volta da subestação (a "semente" que depois reclama
   território no Voronoi; ex.: subestações de transporte).
2. Sobreposições: onde os fechos de várias subestações se sobrepõem, cada ponto fica com a
   subestação MAIS PRÓXIMA entre as que o cobrem (mudança em relação ao RDX, ver
   `resolver_sobreposicoes`).
3. Vazios no estado: vazio com uma vizinha é absorvido por ela; com várias, é dividido por
   Voronoi entre as subestações vizinhas.
4. Recorte pelo limite do estado e simplificação (1 m).
"""
from __future__ import annotations

from collections import deque

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from shapely.geometry import MultiPoint
from shapely.ops import unary_union

from src.spatial import bdgd


def _geo(cfg: dict) -> dict:
    return cfg["geometria"]


# --------------------------------------------------------------------------- 1. áreas iniciais
def areas_iniciais(subs: gpd.GeoDataFrame, trafos: gpd.GeoDataFrame, cfg: dict) -> gpd.GeoDataFrame:
    """Fecho convexo dos trafos de cada subestação, ou semente em volta dela (CRS métrico).

    `subs`: area_id, potencia_nominal_mva, geometry; `trafos`: area_id, geometry.
    Devolve area_id, potencia_nominal_mva, ponto_sub (centroide da subestação), origem
    ("fecho_trafos" | "semente"), n_trafos, geometry.
    """
    g, crs = _geo(cfg), _geo(cfg)["crs_metrico"]
    subs, trafos = subs.to_crs(crs), trafos.to_crs(crs)
    n = trafos.groupby("area_id").size()
    fechos = (trafos[trafos["area_id"].isin(n[n >= g["min_trafos_fecho"]].index)]
              .dissolve("area_id").convex_hull)
    out = gpd.GeoDataFrame(subs[["area_id", "potencia_nominal_mva"]].copy(),
                           geometry=subs.geometry.centroid, crs=crs)
    out["ponto_sub"] = out.geometry
    out["n_trafos"] = out["area_id"].map(n).fillna(0).astype(int)
    tem_fecho = out["area_id"].isin(fechos.index)
    out["origem"] = np.where(tem_fecho, "fecho_trafos", "semente")
    out["geometry"] = [fechos[m] if f else p.buffer(g["raio_semente_m"])
                       for m, f, p in zip(out["area_id"], tem_fecho, out["ponto_sub"])]
    return out.set_geometry("geometry")


# --------------------------------------------------------------------------- 2. sobreposições
def resolver_sobreposicoes(areas: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Cada ponto do mapa fica com uma área de influência só: a da subestação mais próxima entre
    as que o cobrem.

    Para cada par de fechos que se sobrepõem, a parte da sobreposição mais perto da outra
    subestação (lado dela da mediatriz entre as duas) sai desta área. O resultado:
    - sem sobreposição (um ponto só fica do lado da mais próxima);
    - nada que era coberto fica descoberto (o ponto fica com a mais próxima de quem o cobria);
    - toda subestação fica com o próprio entorno, se o fecho dela o cobria.
    Por que mudou: o RDX fazia "quem vem antes na fila (profundidade de contenção, depois
    potência) leva a sobreposição inteira". Com fechos que se cobrem mutuamente (Barra e Barra 2,
    Mackenzie e Camerino, Parada Angélica e Nova Parada Angélica, Saturnino Braga e Goitacazes),
    a primeira da fila levava inclusive o ponto da outra subestação, que ficava fora da própria
    área de influência. A regra da mais próxima também dispensa a fila: as internas e as sementes
    ficam com o entorno delas porque ele está mais perto delas.
    `profundidade` (quantos fechos alheios contêm a subestação) continua calculada, só como
    informação.
    """
    areas = areas.reset_index(drop=True)
    pontos = np.asarray(areas["ponto_sub"])
    i_ponto, i_area = areas.sindex.query(pontos, predicate="within")
    areas["profundidade"] = np.bincount(i_ponto[i_area != i_ponto], minlength=len(areas))

    geoms = list(areas.geometry)
    i_esq, i_dir = areas.sindex.query(areas.geometry.values, predicate="intersects")
    novas = []
    for i, geom in enumerate(geoms):
        pi = pontos[i]
        for j in i_dir[(i_esq == i) & (i_dir != i)]:
            pj = pontos[j]
            if pi.equals(pj):
                # subestações no mesmo ponto: não há mediatriz; a sobreposição fica com a que vem
                # antes na camada (senão as duas ficariam com ela e haveria sobreposição)
                if j < i:
                    geom = geom.difference(geoms[j])
                continue
            sobre = geom.intersection(geoms[j])
            if sobre.is_empty or sobre.area == 0:
                continue
            # Semiplano só do tamanho do par: um semiplano de 1.000 km (1ª versão) cortava com
            # vértices de coordenada enorme e deixava a geometria à beira da instabilidade numérica.
            x0, y0, x1, y1 = geom.union(geoms[j]).bounds
            alcance = 2 * max(x1 - x0, y1 - y0, 1.0)
            geom = geom.difference(sobre.intersection(_semiplano_de(pj, pi, alcance)))
        novas.append(shapely.make_valid(geom))
    areas["geometry"] = novas
    return areas


def _semiplano_de(pj, pi, alcance: float) -> shapely.Polygon:
    """Semiplano dos pontos mais perto de `pj` que de `pi` (lado de pj da mediatriz)."""
    mx, my = (pi.x + pj.x) / 2, (pi.y + pj.y) / 2
    dx, dy = pj.x - pi.x, pj.y - pi.y
    n = (dx * dx + dy * dy) ** 0.5
    dx, dy = dx / n * alcance, dy / n * alcance      # direção de pi para pj
    px, py = -dy, dx                                  # perpendicular (ao longo da mediatriz)
    return shapely.Polygon([(mx + px, my + py), (mx + px + dx, my + py + dy),
                            (mx - px + dx, my - py + dy), (mx - px, my - py)])


# --------------------------------------------------------------------------- 3. vazios
def preencher_vazios(areas: gpd.GeoDataFrame, limite: shapely.Geometry, cfg: dict) -> gpd.GeoDataFrame:
    """Divide o que sobrou do estado (fora de toda área de influência) entre as áreas de influência vizinhas.

    - vazio que toca uma área de influência só: é absorvido por ela;
    - vazio que toca várias: Voronoi das subestações vizinhas, recortado pelo vazio;
    - vazio que não toca nenhuma (ilha sem rede, por exemplo): fica sem dono.
    `limite` no mesmo CRS métrico de `areas`.
    """
    g = _geo(cfg)
    vazio = limite.difference(unary_union(list(areas.geometry)))
    pedacos = [p for p in getattr(vazio, "geoms", [vazio]) if not p.is_empty and p.area > g["area_min_buraco_m2"]]
    pecas: dict[int, list] = {i: [geom] for i, geom in zip(areas.index, areas.geometry)}
    for buraco in pedacos:
        viz = areas.index[areas.intersects(buraco.buffer(g["toque_buraco_m"]))]
        if len(viz) == 0:
            continue
        if len(viz) == 1:
            pecas[viz[0]].append(buraco)
            continue
        # Pontos repetidos (duas subestações no mesmo lugar) quebrariam a correspondência
        # célula -> ponto: fica a primeira de cada coordenada.
        pts = areas.loc[viz, "ponto_sub"]
        pts = pts[~pd.Series([p.wkb for p in pts], index=pts.index).duplicated()]
        if len(pts) == 1:
            pecas[pts.index[0]].append(buraco)
            continue
        envelope = buraco.buffer(g["folga_voronoi_m"]).envelope
        celulas = shapely.voronoi_polygons(MultiPoint(list(pts)), extend_to=envelope, ordered=True)
        for i, celula in zip(pts.index, celulas.geoms):
            parte = celula.intersection(buraco)
            if not parte.is_empty:
                pecas[i].append(parte)
    areas = areas.copy()
    areas["geometry"] = [limpar(unary_union(pecas[i])) for i in areas.index]
    return areas


def limpar(geom: shapely.Geometry, folga_m: float = 0.1, tolerancia: float = 1e-3) -> shapely.Geometry:
    """Fecha as frestas entre peças (buffer +e/−e, como no RDX) sem nunca encolher a área.

    O buffer negativo do GEOS falha com vértices quase colineares: ele zerou áreas de 482 km²
    (Areal, Enel RJ). Se a limpeza perder mais que `tolerancia` da área, vale a geometria só
    corrigida (make_valid): uma fresta de 10 cm é melhor que uma área sumida.
    """
    base = shapely.make_valid(geom)
    limpo = shapely.make_valid(base.buffer(folga_m).buffer(-folga_m))
    if base.area > 0 and limpo.area < base.area * (1 - tolerancia):
        return base
    return limpo


# --------------------------------------------------------------------------- 4. classificação
def classificar(subs: pd.DataFrame, trafos: pd.DataFrame, circuitos: pd.DataFrame,
                linhas_at: gpd.GeoDataFrame, polig_subs: gpd.GeoDataFrame, cfg: dict) -> pd.DataFrame:
    """Tipo de cada subestação e quem a alimenta (mesma lógica do RDX).

    - "Distribuição plena": os alimentadores dos seus trafos saem dela mesma;
    - "Distribuição satélite": os trafos são alimentados por circuitos de OUTRA subestação
      (a "mãe");
    - "Distribuição plena (circuito não mapeado)": tem trafos, mas nenhum circuito conhecido;
    - "Transformadora pura": sem trafos MT/BT, mas com transformação AT/MT;
    - "Transporte/manobra": nenhum dos dois.
    Transformadoras e de transporte sem mãe: busca em largura na malha AT (linhas ligadas pelos
    pontos de conexão PAC) até a primeira linha que toca uma subestação plena.
    `subs`: area_id, potencia_nominal_mva; `trafos`: area_id, CTMT; `circuitos`: COD_ID,
    area_id (de origem); `polig_subs`: area_id + polígono da subestação.
    """
    h = cfg["hierarquia"]
    orig = circuitos.set_index("COD_ID")["area_id"]
    maes = (trafos.assign(mae=trafos["CTMT"].map(orig)).dropna(subset=["mae"])
            .groupby("area_id")["mae"].agg(lambda s: sorted(set(s))))
    com_trafo = set(trafos["area_id"])
    classe, mae_de = {}, {}
    for m, pot in zip(subs["area_id"], subs["potencia_nominal_mva"]):
        ms = maes.get(m, [])
        if ms == [m]:
            classe[m] = "Distribuição plena"
        elif ms:
            classe[m] = "Distribuição satélite"
            outras = [x for x in ms if x != m]
            mae_de[m] = outras[0]
        elif m in com_trafo:
            classe[m] = "Distribuição plena (circuito não mapeado)"
        elif pot > 0:
            classe[m] = "Transformadora pura"
        else:
            classe[m] = "Transporte/manobra"

    # Grafo da malha AT: segmento <-> PAC, e quais subestações cada segmento toca.
    crs = _geo(cfg)["crs_metrico"]
    linhas = linhas_at.to_crs(crs).reset_index(drop=True)
    toque = gpd.sjoin(linhas, gpd.GeoDataFrame(polig_subs[["area_id"]],
                                               geometry=polig_subs.to_crs(crs).buffer(h["toque_linha_at_m"])),
                      predicate="intersects")
    subs_do_seg = toque.groupby(level=0)["area_id"].agg(set).to_dict()
    segs_da_sub = toque.reset_index().groupby("area_id")["index"].agg(set).to_dict()
    pac_segs: dict[str, set] = {}
    for i, (a, b) in enumerate(zip(linhas["PAC_1"], linhas["PAC_2"])):
        for p in (a, b):
            pac_segs.setdefault(str(p), set()).add(i)

    plenas = {m for m, c in classe.items() if c == "Distribuição plena"}
    for m, c in classe.items():
        if m in mae_de or c not in ("Transformadora pura", "Transporte/manobra"):
            continue
        inicio = segs_da_sub.get(m, set())
        vistos, fila = set(inicio), deque((s, 0) for s in inicio)
        while fila:
            s, saltos = fila.popleft()
            achou = next((x for x in subs_do_seg.get(s, ()) if x != m and x in plenas), None)
            if achou:
                mae_de[m] = achou
                break
            if saltos < h["max_saltos"]:
                for p in (str(linhas.at[s, "PAC_1"]), str(linhas.at[s, "PAC_2"])):
                    for viz in pac_segs.get(p, ()):
                        if viz not in vistos:
                            vistos.add(viz)
                            fila.append((viz, saltos + 1))
    return pd.DataFrame({"area_id": list(classe), "classificacao": list(classe.values()),
                         "area_mae": [mae_de.get(m) for m in classe]})


# --------------------------------------------------------------------------- orquestração
def construir_areas(limite_uf: gpd.GeoDataFrame, cfg: dict | None = None) -> gpd.GeoDataFrame:
    """Áreas de influência de todas as distribuidoras da área piloto (EPSG:4326).

    Colunas: area_id, distribuidora, cod_sub, nome, potencia_nominal_mva, n_trafos, origem,
    profundidade, classificacao, area_mae, lat_sub, lon_sub, area_km2, geometria_vazia,
    recorte_ignorado, geometry. `limite_uf`: polígono do estado (malha do IBGE).
    """
    cfg = cfg or bdgd.cfg()
    crs = _geo(cfg)["crs_metrico"]
    subs, iniciais, classes = [], [], []
    for d in bdgd.distribuidoras():
        s, t, ct = bdgd.subestacoes(d), bdgd.trafos_distribuicao(d), bdgd.circuitos(d)
        subs.append(s)
        iniciais.append(areas_iniciais(s, t, cfg))
        classes.append(classificar(s, t, ct, bdgd.segmentos_at(d), s, cfg))
    subs = pd.concat(subs, ignore_index=True)
    areas = gpd.GeoDataFrame(pd.concat(iniciais, ignore_index=True), crs=crs)
    areas = resolver_sobreposicoes(areas)
    limite = unary_union(list(limite_uf.to_crs(crs).geometry))
    areas = preencher_vazios(areas, limite, cfg)
    # Recorte pelo estado (fechos de trafos do litoral entram no mar). Se o recorte apagar uma
    # área de influência inteira, o errado é o limite (ilha ou faixa de praia fora da malha), não a rede:
    # a área de influência fica com a geometria sem recorte. Simplificação final.
    recortada = areas.geometry.intersection(limite)
    apagou = recortada.is_empty & ~areas.geometry.is_empty
    areas["geometry"] = recortada.where(~apagou, areas.geometry)
    areas["recorte_ignorado"] = apagou
    areas["geometry"] = areas.geometry.simplify(_geo(cfg)["simplificacao_m"], preserve_topology=True)
    areas["geometria_vazia"] = areas.geometry.is_empty
    areas["area_km2"] = (areas.geometry.area / 1e6).round(3)
    pontos = gpd.GeoSeries(areas["ponto_sub"], crs=crs).to_crs("EPSG:4326")
    areas["lat_sub"], areas["lon_sub"] = pontos.y.round(6), pontos.x.round(6)
    areas = areas.drop(columns="ponto_sub").merge(pd.concat(classes, ignore_index=True), on="area_id")
    areas = areas.merge(subs[["area_id", "distribuidora", "cod_sub", "nome"]], on="area_id")
    return so_validas(areas.to_crs("EPSG:4326"))


def so_validas(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Corrige (make_valid, só a parte poligonal) e EXIGE geometria válida em toda linha.

    Simplificação e reprojeção podem gerar autointerseções (47 áreas na 1ª versão); uma geometria
    inválida quebra operações seguintes (o set_precision da camada do mapa estourou com
    "TopologyException"). Corrigir aqui, na saída, e conferir, torna isso impossível a jusante.
    """
    gdf = gdf.copy()
    gdf["geometry"] = [g if g.is_empty else _so_poligonos(shapely.make_valid(g)) for g in gdf.geometry]
    ruins = gdf.loc[~gdf.geometry.is_valid, "area_id"].tolist()
    if ruins:
        raise ValueError(f"áreas de influência com geometria inválida mesmo após make_valid: {ruins[:10]}")
    return gdf


def _so_poligonos(g: shapely.Geometry) -> shapely.Geometry:
    """make_valid pode devolver coleção com linhas/pontos soltos: fica só a parte de área."""
    if g.geom_type in ("Polygon", "MultiPolygon"):
        return g
    partes = [p for p in getattr(g, "geoms", []) if p.geom_type in ("Polygon", "MultiPolygon")]
    return unary_union(partes) if partes else shapely.Polygon()
