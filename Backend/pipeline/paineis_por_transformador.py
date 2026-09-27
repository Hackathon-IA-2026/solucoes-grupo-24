"""Painéis solares em imagem de satélite nas áreas atendidas pelos transformadores do recorte.

Base: github.com/Linkfy-Project/Hackaton-Radix, Solar/solar_panels_rj_2stage.py (ladrilhos XYZ que
tocam as áreas, YOLOv8-seg `best.pt` com o ladrilho ampliado para imgsz 640, checkpoint SQLite que
retoma de onde parou). Mudanças em relação ao Radix, e por quê:
- Imagem da Esri World Imagery (config conciliacao.yaml, visao.url_ladrilho) e não do Google: a
  conciliação precisa da DATA da imagem, e a Esri a publica por footprint (serviço de metadados,
  consultado no centro de cada ladrilho). O Google não publica a data nem permite baixar assim.
  Zoom 19 (~0,27 m/px): é o nível máximo da Esri no RJ.
- Recorte = áreas atendidas pelos transformadores das subestações da config (src/spatial/areas_trafo.py),
  e não a área da subestação: todo transformador do recorte fica com a área inteira varrida.
- Um ladrilho é inferido uma vez só; download e metadados em paralelo (threads com Session HTTP).
- Checkpoint: um SELECT para saber o que já foi feito e UM commit por lote (o Radix fazia um SELECT
  e um commit por ladrilho, o que dominava o tempo).
- A inferência roda a `confianca_inferencia` (0,25, como no Radix) e guarda tudo; o limiar de uso
  fica na conciliação. Trocar o limiar não exige refazer a inferência (--so-exportar).
- Na exportação, partes a menos de `agrupar_m` viram UMA detecção: painel cortado na borda de dois
  ladrilhos contava duas vezes no Radix.
- Coordenada do contorno pela Web Mercator exata (o Radix interpolava a latitude linearmente).
- A área em m² sai só para conferência: nesta etapa ela NÃO vira kW (a conciliação usa contagem e posição).

Uso (de dentro de Backend/, depois de `python -m src.spatial.areas_trafo`):
    python -m pipeline.paineis_por_transformador               # varre (retoma se interrompido)
    python -m pipeline.paineis_por_transformador --max-tiles 50  # teste curto
    python -m pipeline.paineis_por_transformador --so-exportar   # refaz o GeoJSON do checkpoint

Tempo: ~2.700 ladrilhos no recorte padrão; na CPU, ~10-20 min (download + YOLO).
"""
from __future__ import annotations

import argparse
import hashlib
import math
import sqlite3
import threading
import time
from collections.abc import Iterable, Sequence
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd
import requests
import shapely

from pipeline import visao_comum as vc
from src.spatial.conciliacao_cfg import caminho, cfg, saida
from src.utils.paths import ensure

LADO_PX = 256  # ladrilho XYZ padrão
CRS_METRICO = "EPSG:31983"


def cfg_visao() -> dict[str, Any]:
    return cfg()["visao"]


# --------------------------------------------------------------------------- Web Mercator (XYZ)
def lon_do_tile(x: float, z: int) -> float:
    """Longitude da borda OESTE da coluna x (aceita frações: x + coluna/256)."""
    return x / 2 ** z * 360.0 - 180.0


def lat_do_tile(y: float, z: int) -> float:
    """Latitude da borda NORTE da linha y (aceita frações), pela Web Mercator exata."""
    return math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / 2 ** z))))


def tile_do_ponto(lon: float, lat: float, z: int) -> tuple[int, int]:
    n = 2 ** z
    x = int((lon + 180.0) / 360.0 * n)
    y = int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n)
    return x, y


def limites_do_tile(x: int, y: int, z: int) -> tuple[float, float, float, float]:
    """(lon_min, lat_min, lon_max, lat_max)."""
    return lon_do_tile(x, z), lat_do_tile(y + 1, z), lon_do_tile(x + 1, z), lat_do_tile(y, z)


def pixel_para_lonlat(x: int, y: int, z: int, px: float, py: float) -> tuple[float, float]:
    return lon_do_tile(x + px / LADO_PX, z), lat_do_tile(y + py / LADO_PX, z)


def tiles_da_geometria(geom, z: int) -> list[tuple[int, int]]:
    """Ladrilhos que tocam a geometria (EPSG:4326). Interseção vetorizada: uma chamada por linha."""
    lon0, lat0, lon1, lat1 = geom.bounds
    x0, y0 = tile_do_ponto(lon0, lat1, z)
    x1, y1 = tile_do_ponto(lon1, lat0, z)
    shapely.prepare(geom)
    xs = np.arange(x0, x1 + 1)
    out = []
    for y in range(y0, y1 + 1):
        caixas = shapely.box(lon_do_tile(xs, z), lat_do_tile(y + 1, z), lon_do_tile(xs + 1, z), lat_do_tile(y, z))
        out += [(int(x), y) for x in xs[shapely.intersects(geom, caixas)]]
    return out


# --------------------------------------------------------------------------- recorte
def recorte() -> gpd.GeoDataFrame:
    """Áreas atendidas dos transformadores das subestações da config (EPSG:4326)."""
    areas = gpd.read_parquet(saida("areas_trafo"))
    sel = areas[areas["area_id"].isin(cfg_visao()["subestacoes"]) & ~areas.geometry.is_empty]
    if sel.empty:
        raise vc.ErroVisao("nenhum transformador das subestações de visao.subestacoes: rode "
                           "python -m src.spatial.areas_trafo e confira os area_id na config")
    return sel


# --------------------------------------------------------------------------- download e metadados
class Baixador:
    """Ladrilhos e metadados da Esri, com cache em disco e uma Session HTTP por thread."""

    def __init__(self, c: dict[str, Any]):
        self.c = c
        self.cache = ensure(caminho(c["cache_ladrilhos"]))
        self._local = threading.local()

    def _sessao(self) -> requests.Session:
        if not hasattr(self._local, "s"):
            self._local.s = requests.Session()
            self._local.s.headers["User-Agent"] = "ORACULO-hackathon-COPPE/1.0"
        return self._local.s

    def ladrilho(self, z: int, x: int, y: int) -> Path | None:
        """Caminho do ladrilho em cache (baixa se faltar). None se a Esri não tiver o ladrilho."""
        arq = self.cache / str(z) / str(x) / f"{y}.jpg"
        if arq.exists() and arq.stat().st_size > 0:
            return arq
        for tentativa in range(3):
            try:
                r = self._sessao().get(self.c["url_ladrilho"].format(z=z, x=x, y=y), timeout=20)
                if r.status_code == 404:
                    return None
                r.raise_for_status()
                ensure(arq.parent)
                arq.write_bytes(r.content)
                return arq
            except requests.RequestException:
                time.sleep(1 + tentativa)
        return None

    def metadados(self, z: int, x: int, y: int) -> tuple[str | None, float | None, str | None]:
        """(data AAAA-MM-DD, resolução m, fonte) da imagem exibida no centro do ladrilho."""
        lon0, lat0, lon1, lat1 = limites_do_tile(x, y, z)
        lon, lat = (lon0 + lon1) / 2, (lat0 + lat1) / 2
        params = {"geometry": f"{lon},{lat}", "geometryType": "esriGeometryPoint", "sr": 4326,
                  "layers": "all", "tolerance": 0, "mapExtent": f"{lon0},{lat0},{lon1},{lat1}",
                  "imageDisplay": f"{LADO_PX},{LADO_PX},96", "returnGeometry": "false", "f": "json"}
        for tentativa in range(3):
            try:
                res = self._sessao().get(self.c["url_metadados"], params=params, timeout=30).json()["results"]
                break
            except (requests.RequestException, KeyError, ValueError):
                time.sleep(1 + tentativa)
        else:
            return None, None, None
        # A camada 0 ("World Imagery") é o footprint efetivamente desenhado; só vale se cobre este zoom.
        for r in res:
            a = r.get("attributes", {})
            try:
                cobre = int(a.get("MinMapLevel", 0)) <= z <= int(a.get("MaxMapLevel", 99))
            except (TypeError, ValueError):
                cobre = False
            data = str(a.get("DATE (YYYYMMDD)") or a.get("SRC_DATE") or "")
            if r.get("layerId") == 0 and cobre and len(data) == 8 and data.isdigit():
                return f"{data[:4]}-{data[4:6]}-{data[6:]}", float(a.get("RESOLUTION (M)") or "nan"), \
                    a.get("SOURCE_INFO") or a.get("NICE_NAME")
        return None, None, None


# --------------------------------------------------------------------------- checkpoint
class Checkpoint:
    """SQLite: ladrilhos feitos (com a data da imagem) e as detecções de cada um."""

    def __init__(self, arquivo: Path, chave: str):
        ensure(arquivo.parent)
        self.con = sqlite3.connect(arquivo)
        self.chave = chave
        self.con.executescript("""
            CREATE TABLE IF NOT EXISTS tiles (chave TEXT, z INT, x INT, y INT, data_imagem TEXT,
                resolucao_m REAL, fonte TEXT, n_det INT, em REAL, PRIMARY KEY (chave, z, x, y));
            CREATE TABLE IF NOT EXISTS deteccoes (chave TEXT, z INT, x INT, y INT, k INT, confianca REAL,
                area_m2 REAL, wkt TEXT, PRIMARY KEY (chave, z, x, y, k));
        """)

    def feitos(self, z: int) -> set[tuple[int, int]]:
        return {(x, y) for x, y in self.con.execute("SELECT x, y FROM tiles WHERE chave=? AND z=?", (self.chave, z))}

    def gravar(self, z: int, lote: Sequence[tuple[int, int, tuple, list]]) -> None:
        """Um commit por lote: [(x, y, (data, res, fonte), [(k, conf, area, wkt), ...]), ...]."""
        agora = time.time()
        with self.con:
            for x, y, meta, dets in lote:
                self.con.execute("DELETE FROM deteccoes WHERE chave=? AND z=? AND x=? AND y=?", (self.chave, z, x, y))
                self.con.execute("INSERT OR REPLACE INTO tiles VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                 (self.chave, z, x, y, *meta, len(dets), agora))
                self.con.executemany("INSERT INTO deteccoes VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                                     [(self.chave, z, x, y, *d) for d in dets])

    def ler(self, z: int) -> tuple[pd.DataFrame, pd.DataFrame]:
        tiles = pd.read_sql("SELECT x, y, data_imagem, resolucao_m, fonte FROM tiles WHERE chave=? AND z=?",
                            self.con, params=(self.chave, z))
        dets = pd.read_sql("SELECT x, y, k, confianca, area_m2, wkt FROM deteccoes WHERE chave=? AND z=?",
                           self.con, params=(self.chave, z))
        return tiles, dets


def chave_da_execucao(arquivo_modelo: Path, c: dict[str, Any]) -> str:
    """Modelo (hash do arquivo) + limiar + imgsz + fonte: mudar qualquer um é outra execução."""
    h = hashlib.sha256(arquivo_modelo.read_bytes()).hexdigest()[:12]
    fonte = hashlib.sha256(c["url_ladrilho"].encode()).hexdigest()[:6]
    return f"{h}-c{c['confianca_inferencia']}-s{c['imgsz']}-{fonte}"


# --------------------------------------------------------------------------- inferência
def deteccoes_do_tile(resultado: Any, tarefa: str, x: int, y: int, z: int) -> list[tuple]:
    """Resultado do ultralytics para um ladrilho -> [(k, confiança, área m², WKT lon/lat)]."""
    out = []
    for k, d in enumerate(vc.deteccoes_do_resultado(resultado, tarefa)):
        anel = [pixel_para_lonlat(x, y, z, px, py) for px, py in d.poligono]
        anel.append(anel[0])
        poly = shapely.make_valid(shapely.Polygon(anel))
        if poly.is_empty or poly.area == 0:
            continue
        out.append((k, round(d.confianca, 4), round(vc.area_m2(anel), 2), poly.wkt))
    return out


def _lotes(seq: Sequence, n: int) -> Iterable[Sequence]:
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def varrer(max_tiles: int | None = None) -> str:
    """Baixa, consulta a data e infere os ladrilhos pendentes do recorte. Devolve a chave."""
    c = cfg_visao()
    z = int(c["zoom"])
    arquivo_modelo = vc.resolver_caminho_modelo(None)
    chave = chave_da_execucao(arquivo_modelo, c)
    ck = Checkpoint(caminho(c["checkpoint"]), chave)
    todos = tiles_da_geometria(recorte().geometry.union_all(), z)
    pendentes = sorted(set(todos) - ck.feitos(z))
    if max_tiles is not None:
        pendentes = pendentes[:max_tiles]
    print(f"visão: {len(todos)} ladrilhos z{z} no recorte, {len(pendentes)} pendentes (chave {chave})")
    if not pendentes:
        return chave
    modelo = vc.carregar_modelo(arquivo_modelo)
    tarefa = vc.tarefa_do_modelo(modelo)
    baixa = Baixador(c)
    t0, feitos = time.time(), 0
    with ThreadPoolExecutor(max_workers=int(c["downloads_paralelos"])) as pool:
        for lote in _lotes(pendentes, int(c["lote"]) * 4):
            arquivos = list(pool.map(lambda t: baixa.ladrilho(z, *t), lote))
            metas = list(pool.map(lambda t: baixa.metadados(z, *t), lote))
            gravar, validos = [], [(t, a, m) for t, a, m in zip(lote, arquivos, metas) if a is not None]
            for sub in _lotes(validos, int(c["lote"])):
                res = modelo.predict([str(a) for _, a, _ in sub], conf=float(c["confianca_inferencia"]),
                                     imgsz=int(c["imgsz"]), verbose=False)
                gravar += [(t[0], t[1], m, deteccoes_do_tile(r, tarefa, t[0], t[1], z))
                           for (t, _, m), r in zip(sub, res)]
            # Ladrilho que a Esri não tem: marcado como feito, sem data (fora da cobertura de imagem).
            gravar += [(t[0], t[1], (None, None, None), []) for t, a in zip(lote, arquivos) if a is None]
            ck.gravar(z, gravar)
            feitos += len(lote)
            ritmo = feitos / max(time.time() - t0, 1e-6)
            print(f"  {feitos}/{len(pendentes)} ladrilhos · {ritmo:.1f}/s · faltam ~{(len(pendentes) - feitos) / ritmo / 60:.0f} min")
    return chave


# --------------------------------------------------------------------------- exportação
def agrupar(geoms_m: Sequence, distancia_m: float) -> np.ndarray:
    """Rótulo de grupo por detecção: partes a menos de `distancia_m` (em metros) viram uma só.

    União-busca sobre os pares que a árvore espacial devolve (dwithin): transitivo, então um arranjo
    em três ladrilhos vira um grupo mesmo que as pontas não se toquem.
    """
    arr = np.asarray(geoms_m)
    pai = np.arange(len(arr))

    def raiz(i: int) -> int:
        while pai[i] != i:
            pai[i] = pai[pai[i]]
            i = pai[i]
        return i

    a, b = shapely.STRtree(arr).query(arr, predicate="dwithin", distance=distancia_m)
    for i, j in zip(a, b):
        if i < j:
            ri, rj = raiz(i), raiz(j)
            if ri != rj:
                pai[rj] = ri
    return np.array([raiz(i) for i in range(len(arr))])


def exportar(chave: str | None = None) -> Path:
    """Checkpoint -> GeoJSON de detecções (uma por painel agrupado) + cobertura varrida por data."""
    c = cfg_visao()
    z = int(c["zoom"])
    if chave is None:
        chave = chave_da_execucao(vc.resolver_caminho_modelo(None), c)
    tiles, dets = Checkpoint(caminho(c["checkpoint"]), chave).ler(z)
    if tiles.empty:
        raise vc.ErroVisao("checkpoint vazio: rode a varredura primeiro")

    # Cobertura: um polígono por (data, resolução, fonte), união dos ladrilhos varridos com imagem.
    com_data = tiles.dropna(subset=["data_imagem"])
    caixas = [shapely.box(*limites_do_tile(int(x), int(y), z)) for x, y in zip(com_data["x"], com_data["y"])]
    cob = gpd.GeoDataFrame(com_data[["data_imagem", "resolucao_m", "fonte"]].reset_index(drop=True),
                           geometry=caixas, crs="EPSG:4326")
    cob = cob.dissolve(by=["data_imagem", "resolucao_m", "fonte"], as_index=False)
    destino_cob = caminho(c["saida_cobertura"])
    ensure(destino_cob.parent)
    cob.to_parquet(destino_cob, index=False)

    features = []
    if not dets.empty:
        dets = dets.merge(tiles[["x", "y", "data_imagem", "resolucao_m", "fonte"]], on=["x", "y"], how="left")
        g = gpd.GeoDataFrame(dets, geometry=gpd.GeoSeries.from_wkt(dets["wkt"]), crs="EPSG:4326")
        g["grupo"] = agrupar(g.to_crs(CRS_METRICO).geometry.values, float(c["agrupar_m"]))
        for _, p in g.groupby("grupo"):
            melhor = p.loc[p["confianca"].idxmax()]
            poly = shapely.union_all(p.geometry.values)
            if poly.geom_type not in ("Polygon", "MultiPolygon"):
                poly = poly.convex_hull
            ponto = gpd.GeoSeries([poly], crs="EPSG:4326").to_crs(CRS_METRICO).representative_point().to_crs("EPSG:4326")[0]
            features.append({
                "type": "Feature",
                "geometry": shapely.geometry.mapping(poly),
                "properties": {
                    "id": f"z{z}-{int(melhor.x)}-{int(melhor.y)}-{int(melhor.k)}",
                    "confianca": float(p["confianca"].max()), "n_partes": int(len(p)),
                    "area_m2": round(float(p["area_m2"].sum()), 2),  # só conferência: não vira kW aqui
                    "lat": round(ponto.y, 7), "lon": round(ponto.x, 7),
                    # data mais antiga entre as partes: a detecção só prova o painel a partir dela
                    "data_imagem": min(d for d in p["data_imagem"] if isinstance(d, str)) if p["data_imagem"].notna().any() else None,
                    "resolucao_m": _num(melhor.resolucao_m), "fonte": melhor.fonte,
                    "classe": "solar-panel", "is_mock": False,
                },
            })
    destino = caminho(c["saida_deteccoes"])
    vc.escrever_geojson(features, destino, {
        "is_mock": False, "chave_execucao": chave, "zoom": z, "fonte_imagem": c["url_ladrilho"],
        "atribuicao": c["atribuicao"], "tiles_varridos": int(len(tiles)), "tiles_com_data": int(len(com_data)),
        "confianca_inferencia": c["confianca_inferencia"], "agrupar_m": c["agrupar_m"],
        "subestacoes": c["subestacoes"], "gerado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    })
    print(f"visão: {len(features)} detecções (de {len(dets)} partes) em {len(tiles)} ladrilhos -> {destino}")
    return destino


def _num(v) -> float | None:
    return None if v is None or (isinstance(v, float) and math.isnan(v)) else float(v)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--max-tiles", type=int, default=None, help="limite de ladrilhos nesta execução (teste)")
    ap.add_argument("--so-exportar", action="store_true", help="só refaz o GeoJSON a partir do checkpoint")
    args = ap.parse_args()
    chave = None if args.so_exportar else varrer(args.max_tiles)
    exportar(chave)


if __name__ == "__main__":
    main()
