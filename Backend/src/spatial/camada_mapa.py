"""Camada de polígonos do Mapa Híbrido: áreas de influência das subestações em GeoJSON.

Lê só saídas já processadas (output/areas_influencia_rj.geojson) e o pico de excedente calculado
na publicação. Não lê dado bruto. Fica separada de construir.py pelo mesmo motivo de saidas.py:
a publicação importa daqui sem puxar o código que monta as áreas.

Decisões:
- Simplificação própria para a web (config espacial.yaml: mapa.simplificacao_m). O arquivo em
  output/ tem 1 m de tolerância, o que é preciso para cálculo e pesado demais para o navegador.
  A topologia é preservada. Área que a simplificação apagaria mantém a geometria original.
- Coordenadas arredondadas (mapa.casas_decimais; 5 casas ≈ 1 m): JSON menor sem perda visível.
- Área com geometria vazia (ex.: duas subestações no mesmo ponto) fica de fora da camada, porque
  GeoJSON sem polígono não desenha nada. A MMGD dela continua nas tabelas e na densidade.
"""
from __future__ import annotations

import geopandas as gpd
import pandas as pd
import shapely

from src.spatial.areas_influencia import _so_poligonos, so_validas


def _nulo(v):
    """NaN/None do pandas -> None do JSON."""
    return None if v is None or (isinstance(v, float) and pd.isna(v)) or v is pd.NA else v


def feicoes(geo: gpd.GeoDataFrame, pico: pd.DataFrame, simplificacao_m: float, crs_metrico: str,
            casas: int) -> list[dict]:
    """Features GeoJSON (dicts no formato do contrato AreasInfluencia).

    `geo`: output/areas_influencia_rj.geojson; `pico`: saída de excedentes.pico_por_area (uma
    linha por subestação de fronteira). Subestação que não é fronteira fica com excedente null.
    """
    g = geo[[x is not None and not x.is_empty for x in geo.geometry]].copy()
    g = so_validas(g)  # o arquivo pode vir de uma versão anterior: nunca simplificar inválida
    original = g.geometry.values
    simples = g.to_crs(crs_metrico).geometry.simplify(simplificacao_m, preserve_topology=True)
    web = shapely.set_precision(gpd.GeoSeries(simples, crs=crs_metrico).to_crs("EPSG:4326").values, 10 ** -casas)
    # Simplificação + arredondamento podem reduzir uma área pequena (semente de 10 m) a um
    # polígono vazio ou degenerado. Nesse caso fica a geometria original, sem simplificar:
    # a camada nunca perde uma área que existe (SESD Serra Alta sumia assim).
    web = [so_validas_geom(w) for w in web]
    ruim = shapely.is_empty(web) | ~shapely.is_valid(web) | (shapely.area(web) == 0)
    g["geometry"] = [o if r else w for o, w, r in zip(original, web, ruim)]
    exc = pico.set_index("area_id")[["excedente_mw", "horizonte"]]

    out = []
    for r in g.itertuples():
        geom = shapely.geometry.mapping(r.geometry)
        if geom["type"] not in ("Polygon", "MultiPolygon"):  # set_precision pode gerar coleção
            geom = shapely.geometry.mapping(shapely.make_valid(r.geometry).buffer(0))
        tem_exc = r.area_id in exc.index
        out.append({
            "type": "Feature",
            "geometry": {"type": geom["type"], "coordinates": _listas(geom["coordinates"])},
            "properties": {
                "areaId": r.area_id, "nome": r.nome, "distribuidora": r.distribuidora,
                "classificacao": r.classificacao, "areaMae": _nulo(r.area_mae) or None,
                "latSub": r.lat_sub, "lonSub": r.lon_sub, "areaKm2": float(r.area_km2),
                "capacidadeMmgdMw": round(float(r.capacidade_mmgd_corrigida_kw) / 1000, 3),
                "capacidadeLagMw": round(float(r.capacidade_lag_kw) / 1000, 3),
                "fatorCorrecao": _nulo(r.fator_correcao),
                "excedenteMw": round(float(exc.at[r.area_id, "excedente_mw"]), 2) if tem_exc else None,
                "horizonteExcedente": exc.at[r.area_id, "horizonte"] if tem_exc else None,
            },
        })
    return out


def _listas(c):
    """Tuplas do shapely -> listas (JSON puro)."""
    return [_listas(x) for x in c] if isinstance(c, (list, tuple)) and c and isinstance(c[0], (list, tuple)) \
        else list(c)


def so_validas_geom(g):
    """Uma geometria: válida e só com a parte de área (ver areas_influencia.so_validas)."""
    return g if g.is_empty or g.is_valid else _so_poligonos(shapely.make_valid(g))
