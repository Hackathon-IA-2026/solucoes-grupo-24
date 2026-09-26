# -*- coding: utf-8 -*-
"""Detecção de painéis em imagem de satélite REAL (Esri World Imagery).

O banco de ensaio do protótipo (``tiles.synth_scene``) roda o detector numa ortoimagem sintética,
com verdade fundamental conhecida: serve para medir o detector, mas o que ele desenha não existe no
chão. Este módulo faz o caminho real, com o MESMO detector e o MESMO ``scan_scene``:

1. baixa os ladrilhos da Esri World Imagery (o mesmo fundo de satélite do dashboard, sem chave)
   que cobrem um quadrado de ``lado_m`` metros em volta de (lat, lon), no zoom ``ZOOM``;
2. costura os ladrilhos e recorta o quadrado exato; a georreferência é a ``GeoTransform`` local
   do protótipo (centro + GSD), que em ~250 m coincide com a Web Mercator bem abaixo de 1 pixel;
3. roda ``scan_scene`` (ladrilhamento, NMS, deduplicação, georreferência, área e kWp).

Decisões:
- Cache em disco dos ladrilhos (``CACHE_DIR/satelite_esri/z/x/y.jpg``) e do resultado por ponto:
  a mesma cena não é baixada nem analisada duas vezes.
- Não há verdade fundamental em imagem real: a resposta traz as detecções e os sinais de cada
  uma, e diz explicitamente que precisão e revocação não são medidas aqui (as do banco de ensaio
  valem para a imagem sintética, e o detector clássico foi calibrado nela).
- Cada detecção sai também como polígono em lat/lon (os quatro cantos da caixa), para o mapa
  desenhar a bounding box sem refazer a conta da georreferência no navegador.
"""
from __future__ import annotations

import hashlib
import io
import json
import math
import threading
from pathlib import Path

import numpy as np

from .. import config
from ..core.timeutils import now_iso
from . import detector as D
from .tiles import GeoTransform

try:
    import httpx
except ImportError:  # pragma: no cover
    httpx = None  # type: ignore

# Fonte: a mesma do fundo "Satélite" do dashboard (Frontend/.../MapaOsm.tsx, SATELITE_URL).
URL_LADRILHO = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
ATRIBUICAO = "Imagem © Esri, Maxar, Earthstar Geographics e comunidade de usuários GIS"
# Zoom 19: ~0,28 m/pixel no Rio de Janeiro, a resolução do banco de ensaio (0,3 m).
ZOOM = 19
LADRILHO_PX = 256
# Circunferência da Terra no equador / 256 px: metros por pixel no zoom 0 (Web Mercator).
M_POR_PX_Z0 = 156543.03392804097
# Lado padrão da cena: o mesmo do banco de ensaio (768 px × 0,3 m = 230,4 m).
LADO_PADRAO_M = 230.4
LADO_MAX_M = 600.0

DIR_CACHE = Path(config.CACHE_DIR) / "satelite_esri"
_trava = threading.Lock()


def gsd_m(lat: float, zoom: int = ZOOM) -> float:
    """Metros por pixel da Web Mercator na latitude (isotrópico)."""
    return M_POR_PX_Z0 * math.cos(math.radians(lat)) / (2 ** zoom)


def pixel_global(lat: float, lon: float, zoom: int = ZOOM) -> tuple[float, float]:
    """Posição (x, y) em pixels globais da Web Mercator no zoom dado."""
    n = LADRILHO_PX * (2 ** zoom)
    x = (lon + 180.0) / 360.0 * n
    s = math.sin(math.radians(lat))
    y = (0.5 - math.log((1 + s) / (1 - s)) / (4 * math.pi)) * n
    return x, y


def _ladrilho(cliente, z: int, x: int, y: int) -> np.ndarray:
    """Um ladrilho RGB 256×256, do cache ou da Esri."""
    from PIL import Image

    arq = DIR_CACHE / str(z) / str(x) / f"{y}.jpg"
    if arq.exists():
        dados = arq.read_bytes()
    else:
        if cliente is None:
            raise ConnectionError("rede indisponível (offline ou sem httpx) e ladrilho fora do cache")
        r = cliente.get(URL_LADRILHO.format(z=z, x=x, y=y))
        r.raise_for_status()
        dados = r.content
        arq.parent.mkdir(parents=True, exist_ok=True)
        arq.write_bytes(dados)
    return np.asarray(Image.open(io.BytesIO(dados)).convert("RGB"))


def mosaico(lat: float, lon: float, lado_m: float = LADO_PADRAO_M, zoom: int = ZOOM) -> tuple[np.ndarray, GeoTransform, dict]:
    """Imagem RGB real do quadrado de ``lado_m`` em volta de (lat, lon) + georreferência."""
    gsd = gsd_m(lat, zoom)
    meio = int(round(lado_m / gsd / 2))
    cx, cy = pixel_global(lat, lon, zoom)
    x0, y0 = int(math.floor(cx)) - meio, int(math.floor(cy)) - meio
    x1, y1 = x0 + 2 * meio, y0 + 2 * meio
    tx0, ty0 = x0 // LADRILHO_PX, y0 // LADRILHO_PX
    tx1, ty1 = (x1 - 1) // LADRILHO_PX, (y1 - 1) // LADRILHO_PX

    offline = httpx is None or config.FORCE_OFFLINE
    cliente = None if offline else httpx.Client(timeout=config.HTTP_TIMEOUT, follow_redirects=True)
    try:
        linhas = []
        for ty in range(ty0, ty1 + 1):
            linhas.append(np.concatenate([_ladrilho(cliente, zoom, tx, ty) for tx in range(tx0, tx1 + 1)], axis=1))
        grande = np.concatenate(linhas, axis=0)
    finally:
        if cliente is not None:
            cliente.close()
    ox, oy = x0 - tx0 * LADRILHO_PX, y0 - ty0 * LADRILHO_PX
    rgb = np.ascontiguousarray(grande[oy:oy + 2 * meio, ox:ox + 2 * meio])
    # Centro da GeoTransform = centro exato do recorte (o pixel inteiro mais próximo de lat/lon).
    geo = GeoTransform(center_lat=lat, center_lon=lon, gsd_m=gsd, width_px=rgb.shape[1], height_px=rgb.shape[0])
    fonte = {
        "fonte": "Esri World Imagery",
        "url": URL_LADRILHO,
        "atribuicao": ATRIBUICAO,
        "zoom": zoom,
        "ladrilhos": (tx1 - tx0 + 1) * (ty1 - ty0 + 1),
        "gsd_m": round(gsd, 4),
    }
    return rgb, geo, fonte


def _poligono(geo: GeoTransform, box) -> list[list[float]]:
    """Os 4 cantos da caixa (x0, y0, x1, y1) em [lat, lon]."""
    x0, y0, x1, y1 = box
    return [[round(v, 7) for v in geo.to_latlon(px, py)] for px, py in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]


def analisar(lat: float, lon: float, lado_m: float = LADO_PADRAO_M) -> dict:
    """Roda o detector ativo do protótipo na imagem real do ponto. Resultado em cache por ponto."""
    if not (-34.0 <= lat <= 6.0 and -74.0 <= lon <= -28.0):
        raise ValueError("ponto fora do Brasil (lat, lon) = (%s, %s)" % (lat, lon))
    lado_m = float(min(max(lado_m, 50.0), LADO_MAX_M))
    det = D.build_detector()
    chave = hashlib.sha1(("%.6f|%.6f|%.1f|%d|%s" % (lat, lon, lado_m, ZOOM, det.info().kind)).encode()).hexdigest()[:16]
    arq = DIR_CACHE / "analises" / f"{chave}.json"
    with _trava:
        if arq.exists():
            out = json.loads(arq.read_text(encoding="utf-8"))
            out["cache"] = True
            return out
        rgb, geo, fonte = mosaico(lat, lon, lado_m)
        scan = D.scan_scene(rgb, geo, det)
        s = scan.to_dict()
        dets = []
        for d, dd in zip(scan.detections, s["detections"]):
            dd["poligono"] = _poligono(geo, d.box)
            dets.append(dd)
        (w_m, h_m) = geo.extent_m
        sw = geo.to_latlon(0, geo.height_px)
        ne = geo.to_latlon(geo.width_px, 0)
        out = {
            "centro": [lat, lon],
            "lado_m": round(w_m, 1),
            "limites": [[round(sw[0], 7), round(sw[1], 7)], [round(ne[0], 7), round(ne[1], 7)]],
            "imagem": fonte,
            "detector": s["detector"],
            "tiles": s["tiles"],
            "raw_count": s["raw_count"],
            "kept_count": s["kept_count"],
            "duplicates_removed": s["duplicates_removed"],
            "total_area_m2": s["total_area_m2"],
            "total_kwp": s["total_kwp"],
            "area_calibration": s["area_calibration"],
            "watt_per_m2": s["watt_per_m2"],
            "detections": dets,
            "analisado_em": now_iso(),
            "aviso": (
                "Imagem real, sem verdade fundamental: precisão e revocação NÃO são medidas aqui. "
                "O detector clássico foi calibrado na ortoimagem sintética do banco de ensaio; em imagem "
                "real, esperar falsos positivos (telhados e superfícies escuras e azuladas) e painéis perdidos."
            ),
            "cache": False,
        }
        arq.parent.mkdir(parents=True, exist_ok=True)
        arq.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
        return out
