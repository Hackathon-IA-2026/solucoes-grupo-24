"""Área atendida por transformador MT/BT (BDGD, camada UNTRMT) nos municípios da área piloto.

A plataforma só tinha área de influência por SUBESTAÇÃO (src/spatial/areas_influencia.py). A
conciliação precisa de uma por transformador, para saber a qual deles pertence cada painel detectado.

Método (mesma família do de subestação: Voronoi em CRS métrico):
1. pontos dos transformadores do município (UNTRMT.MUN = código IBGE; nenhum sai sem município);
2. transformadores no MESMO ponto (bancos e postos com mais de um trafo: ~12% no Rio) viram um
   grupo com uma célula só. Separar a célula entre eles seria inventar geografia;
3. célula de Voronoi de cada ponto, recortada pelo município (malha do IBGE, qualidade máxima) e
   por um círculo de `raio_max_m` em volta do transformador (sem o círculo, o trafo da borda da
   Floresta da Tijuca "atenderia" dezenas de km² de mata).

Saída: uma linha por transformador (trafo_id, distribuidora, municipio, grupo, n_no_grupo,
area_m2, geometry). O grupo repete a geometria: quem conta detecção por área agrega por `grupo`.
"""
from __future__ import annotations

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

from src.spatial import bdgd
from src.spatial.conciliacao_cfg import cfg, piloto, saida
from src.utils.config import arquivo_direto
from src.utils.paths import ensure


def celulas(pontos: gpd.GeoDataFrame, municipios: gpd.GeoDataFrame, raio_m: float) -> gpd.GeoDataFrame:
    """Células por transformador. Função pura (testada com pontos sintéticos).

    `pontos`: trafo_id, municipio, geometry (Point), em CRS MÉTRICO. `municipios`: codarea, geometry,
    no mesmo CRS. Devolve as colunas de `pontos` + grupo, n_no_grupo, area_m2 e a célula na geometry.
    """
    if pontos.crs is None or not pontos.crs.is_projected:
        raise ValueError("celulas: os pontos precisam estar num CRS métrico (config espacial.yaml)")
    partes = []
    for mun, pts in pontos.groupby("municipio", sort=True):
        limite = municipios.loc[municipios["codarea"] == mun, "geometry"]
        if limite.empty:
            raise KeyError(f"município {mun} ausente da malha do IBGE")
        limite = limite.union_all()
        # Grupo = coordenada arredondada a 0,1 m (a BDGD repete o mesmo ponto para trafos do mesmo posto).
        chave = [f"{mun}:{x:.1f}:{y:.1f}" for x, y in zip(pts.geometry.x, pts.geometry.y)]
        pts = pts.assign(grupo=chave)
        unicos = pts.drop_duplicates("grupo")
        if len(unicos) == 1:  # um ponto só: a "célula" é o município inteiro
            vor = [limite]
        else:
            # ordered=True (shapely >= 2.1): a i-ésima célula é a do i-ésimo ponto.
            env = limite.buffer(raio_m).envelope
            vor = list(shapely.voronoi_polygons(shapely.MultiPoint(list(unicos.geometry)), extend_to=env,
                                                ordered=True).geoms)
        circulo = shapely.buffer(np.asarray(unicos.geometry.values), raio_m)
        shapely.prepare(limite)
        cel = shapely.intersection(shapely.intersection(np.asarray(vor), circulo), limite)
        mapa = dict(zip(unicos["grupo"], cel))
        pts["geometry"] = [mapa[g] for g in pts["grupo"]]
        partes.append(pts)
    out = gpd.GeoDataFrame(pd.concat(partes, ignore_index=True), geometry="geometry", crs=pontos.crs)
    out["n_no_grupo"] = out.groupby("grupo")["trafo_id"].transform("size")
    out["area_m2"] = out.geometry.area.round(1)
    return out


def trafos_piloto() -> gpd.GeoDataFrame:
    """Transformadores MT/BT dos municípios da área piloto (CRS métrico), com a distribuidora."""
    crs = bdgd.cfg()["geometria"]["crs_metrico"]
    por_sigla = {d.sigla: d for d in bdgd.distribuidoras()}
    partes = []
    for sigla, muns in piloto().items():
        t = bdgd.trafos_distribuicao(por_sigla[sigla])
        t = t[t["MUN"].isin(muns)]
        wgs = t.geometry.to_crs("EPSG:4326")  # posição do trafo: é o ponto da camada do mapa
        partes.append(gpd.GeoDataFrame({"trafo_id": t["trafo_id"], "distribuidora": sigla,
                                        "municipio": t["MUN"], "area_id": t["area_id"],
                                        "lat": wgs.y.round(6), "lon": wgs.x.round(6),
                                        "geometry": t.geometry}, crs=t.crs).to_crs(crs))
    out = pd.concat(partes, ignore_index=True)
    if out["municipio"].isna().any() or out["trafo_id"].isna().any():
        raise ValueError("transformador sem município ou sem código na BDGD da área piloto")
    if out["trafo_id"].duplicated().any():
        raise ValueError("trafo_id repetido: COD_ID do UNTRMT não é único na distribuidora")
    return gpd.GeoDataFrame(out, geometry="geometry", crs=crs)


def municipios_rj() -> gpd.GeoDataFrame:
    """Malha municipal do RJ (IBGE, qualidade máxima), codarea como texto."""
    m = gpd.read_file(arquivo_direto("ibge_malha_municipios_rj"))
    m["codarea"] = m["codarea"].astype(str)
    return m


def construir() -> gpd.GeoDataFrame:
    """Calcula e grava as áreas atendidas (GeoParquet em EPSG:4326)."""
    crs = bdgd.cfg()["geometria"]["crs_metrico"]
    cel = celulas(trafos_piloto(), municipios_rj().to_crs(crs), float(cfg()["areas_trafo"]["raio_max_m"]))
    vazias = cel.geometry.is_empty
    if vazias.any():  # célula vazia = ponto fora do próprio município (erro de cadastro na BDGD)
        print(f"areas_trafo: {int(vazias.sum())} transformadores com ponto fora do município (célula vazia)")
    out = cel.to_crs("EPSG:4326")
    destino = saida("areas_trafo")
    ensure(destino.parent)
    out.to_parquet(destino, index=False)
    print(f"areas_trafo: {len(out)} transformadores, {out['grupo'].nunique()} células -> {destino}")
    return out


if __name__ == "__main__":
    construir()
