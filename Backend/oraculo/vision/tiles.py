# -*- coding: utf-8 -*-
"""Ladrilhamento georreferenciado e ortoimagem sintetica de demonstracao.

Duas responsabilidades:

1. **Geo-transformacao** — converte latitude/longitude em pixel e de volta,
   monta a grade de ladrilhos com sobreposicao e calcula a resolucao em
   metros por pixel. E o que permite transformar uma deteccao em pixel numa
   coordenada e, dai, numa area em metros quadrados de painel.

2. **Ortoimagem sintetica** — gera ladrilhos proceduralmente com verdade
   fundamental conhecida (telhados, ruas, vegetacao, paineis fotovoltaicos).

A imagem e sintetica; o DETECTOR que roda sobre ela e o mesmo que roda em
ortoimagem real. Como a verdade fundamental e conhecida, a precisao e a
revocacao medidas no painel sao medicoes de verdade do detector, nao numeros
inventados. Ver 08-limitacoes.md.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

EARTH_RADIUS_M = 6_378_137.0
# Resolucao tipica de ortoimagem de satelite de alta resolucao.
DEFAULT_GSD_M = 0.30          # ground sample distance, metros por pixel
DEFAULT_TILE_PX = 256
DEFAULT_OVERLAP_PX = 32


# --------------------------------------------------------------- geo
@dataclass(frozen=True)
class GeoTransform:
    """Transformacao local plana em torno de um centro (lat, lon).

    Para as distancias envolvidas (poucos quilometros) a aproximacao plana
    introduz erro muito abaixo da resolucao da imagem.
    """

    center_lat: float
    center_lon: float
    gsd_m: float = DEFAULT_GSD_M
    width_px: int = 1024
    height_px: int = 1024

    @property
    def meters_per_deg_lat(self) -> float:
        return np.pi * EARTH_RADIUS_M / 180.0

    @property
    def meters_per_deg_lon(self) -> float:
        return self.meters_per_deg_lat * float(np.cos(np.deg2rad(self.center_lat)))

    @property
    def extent_m(self) -> tuple[float, float]:
        return self.width_px * self.gsd_m, self.height_px * self.gsd_m

    def pixel_area_m2(self) -> float:
        return self.gsd_m ** 2

    def to_pixel(self, lat: float, lon: float) -> tuple[float, float]:
        dx_m = (lon - self.center_lon) * self.meters_per_deg_lon
        dy_m = (lat - self.center_lat) * self.meters_per_deg_lat
        return (self.width_px / 2.0 + dx_m / self.gsd_m,
                self.height_px / 2.0 - dy_m / self.gsd_m)

    def to_latlon(self, px: float, py: float) -> tuple[float, float]:
        dx_m = (px - self.width_px / 2.0) * self.gsd_m
        dy_m = (self.height_px / 2.0 - py) * self.gsd_m
        return (self.center_lat + dy_m / self.meters_per_deg_lat,
                self.center_lon + dx_m / self.meters_per_deg_lon)

    def box_area_m2(self, box: tuple[float, float, float, float]) -> float:
        x0, y0, x1, y1 = box
        return max(0.0, (x1 - x0)) * max(0.0, (y1 - y0)) * self.pixel_area_m2()

    def to_dict(self) -> dict:
        w_m, h_m = self.extent_m
        return {
            "center_lat": round(self.center_lat, 6),
            "center_lon": round(self.center_lon, 6),
            "gsd_m": self.gsd_m,
            "width_px": self.width_px,
            "height_px": self.height_px,
            "extent_m": [round(w_m, 1), round(h_m, 1)],
            "extent_km2": round(w_m * h_m / 1e6, 4),
        }


@dataclass(frozen=True)
class Tile:
    """Um ladrilho na grade, com posicao em pixel na imagem completa."""

    index: int
    row: int
    col: int
    x0: int
    y0: int
    size: int

    @property
    def x1(self) -> int:
        return self.x0 + self.size

    @property
    def y1(self) -> int:
        return self.y0 + self.size

    def to_dict(self) -> dict:
        return {"index": self.index, "row": self.row, "col": self.col,
                "x0": self.x0, "y0": self.y0, "size": self.size}


def tile_grid(width: int, height: int, tile: int = DEFAULT_TILE_PX,
              overlap: int = DEFAULT_OVERLAP_PX) -> list[Tile]:
    """Grade de ladrilhos com sobreposicao.

    A sobreposicao evita cortar um painel na fronteira; a deduplicacao em
    `nms.soft_dedupe` desfaz a contagem dupla que ela cria.
    """
    step = max(1, tile - overlap)
    xs = list(range(0, max(1, width - overlap), step))
    ys = list(range(0, max(1, height - overlap), step))
    xs = [min(x, max(0, width - tile)) for x in xs]
    ys = [min(y, max(0, height - tile)) for y in ys]
    xs = sorted(set(xs))
    ys = sorted(set(ys))
    out: list[Tile] = []
    k = 0
    for r, y in enumerate(ys):
        for c, x in enumerate(xs):
            out.append(Tile(k, r, c, x, y, tile))
            k += 1
    return out


# --------------------------------------------------- ortoimagem sintetica
@dataclass
class SyntheticScene:
    """Ortoimagem sintetica com verdade fundamental."""

    rgb: np.ndarray                  # (H, W, 3) uint8
    panel_boxes: np.ndarray          # (N, 4) x0,y0,x1,y1 — verdade
    panel_mask: np.ndarray           # (H, W) bool — verdade
    roof_boxes: np.ndarray           # (M, 4) telhados
    roof_class: np.ndarray           # (M,) "residencial"|"comercial"|"industrial"
    geo: GeoTransform
    seed: int

    def truth_count(self) -> int:
        return int(len(self.panel_boxes))

    def roof_area_m2(self) -> dict[str, float]:
        out: dict[str, float] = {}
        for cls in ("residencial", "comercial", "industrial"):
            sel = self.roof_class == cls
            if not sel.any():
                out[cls] = 0.0
                continue
            b = self.roof_boxes[sel]
            areas = (b[:, 2] - b[:, 0]) * (b[:, 3] - b[:, 1]) * self.geo.pixel_area_m2()
            out[cls] = float(areas.sum())
        return out

    def roof_counts(self) -> dict[str, int]:
        return {cls: int((self.roof_class == cls).sum())
                for cls in ("residencial", "comercial", "industrial")}


# Paleta em RGB aproximando ortoimagem: asfalto, vegetacao, solo, telhados.
_ASPHALT = (78, 80, 84)
_VEG = (74, 104, 58)
_SOIL = (146, 128, 100)
_ROOF_COLORS = {
    "residencial": [(172, 118, 92), (150, 104, 82), (186, 132, 104), (128, 96, 84)],
    "comercial": [(178, 178, 182), (160, 162, 168), (196, 194, 190)],
    "industrial": [(186, 190, 196), (170, 176, 184), (200, 202, 206)],
}
# Paineis: escuros, com excesso de azul e baixa saturacao relativa.
_PANEL_BASE = (34, 44, 78)


def _rect(img: np.ndarray, x0: int, y0: int, x1: int, y1: int,
          color, noise: float, rng: np.random.Generator) -> None:
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(img.shape[1], x1), min(img.shape[0], y1)
    if x1 <= x0 or y1 <= y0:
        return
    h, w = y1 - y0, x1 - x0
    patch = np.array(color, dtype="f4")[None, None, :].repeat(h, 0).repeat(w, 1)
    if noise > 0:
        patch = patch + rng.normal(0.0, noise, patch.shape)
    img[y0:y1, x0:x1] = np.clip(patch, 0, 255)


# Modulo fotovoltaico comercial: cerca de 1,0 m x 2,0 m.
MODULE_W_M = 1.0
MODULE_H_M = 2.0


def _panel_texture(h: int, w: int, rng: np.random.Generator,
                   gsd_m: float = DEFAULT_GSD_M) -> np.ndarray:
    """Textura de painel: modulos escuros separados por vaos claros.

    O modulo tem tamanho FISICO fixo, nao proporcional ao painel. Isso importa:
    com modulo proporcional, um painel industrial grande teria pouquissimas
    linhas e densidade de borda baixa, e o detector o perderia. Em ortoimagem
    real o modulo mede sempre o mesmo, e e essa periodicidade invariante de
    escala que torna a textura um sinal utilizavel em qualquer porte de usina.
    """
    base = np.array(_PANEL_BASE, dtype="f4")[None, None, :].repeat(h, 0).repeat(w, 1)
    base += rng.normal(0.0, 4.0, base.shape)
    step_x = max(3, int(round(MODULE_W_M / gsd_m)))
    step_y = max(3, int(round(MODULE_H_M / gsd_m)))
    for y in range(0, h, step_y):
        base[y:y + 1, :, :] += 30.0
    for x in range(0, w, step_x):
        base[:, x:x + 1, :] += 30.0
    base[0, :, :] += 38.0
    base[-1, :, :] += 38.0
    base[:, 0, :] += 38.0
    base[:, -1, :] += 38.0
    return np.clip(base, 0, 255)


def synth_scene(center_lat: float, center_lon: float, *,
                size_px: int = 768, gsd_m: float = DEFAULT_GSD_M,
                urban_class: str = "misto", panel_rate: float = 0.18,
                seed: int = 0) -> SyntheticScene:
    """Gera uma cena com telhados, ruas, vegetacao e paineis.

    `urban_class` controla a morfologia construida:

    * residencial -- muitos telhados pequenos e densos;
    * comercial -- telhados medios ao longo de vias;
    * industrial -- poucos galpoes muito grandes;
    * misto -- combinacao.

    `panel_rate` e a fracao de telhados que recebem paineis.
    """
    rng = np.random.default_rng(seed)
    H = W = int(size_px)
    img = np.zeros((H, W, 3), dtype="f4")

    # fundo: solo e vegetacao em manchas suaves
    img[:] = np.array(_SOIL, dtype="f4")
    blobs = rng.integers(6, 12)
    for _ in range(blobs):
        cx, cy = rng.integers(0, W), rng.integers(0, H)
        r = rng.integers(40, 130)
        yy, xx = np.ogrid[:H, :W]
        m = (xx - cx) ** 2 + (yy - cy) ** 2 <= r * r
        img[m] = np.array(_VEG, dtype="f4") + rng.normal(0, 6.0, 3)
    img += rng.normal(0.0, 3.0, img.shape)

    # malha viaria
    road_w = max(3, int(round(8.0 / gsd_m / 3.0)))
    block = int(round(90.0 / gsd_m))          # quadra de ~90 m
    for x in range(block // 2, W, block):
        _rect(img, x, 0, x + road_w, H, _ASPHALT, 3.0, rng)
    for y in range(block // 2, H, block):
        _rect(img, 0, y, W, y + road_w, _ASPHALT, 3.0, rng)

    # telhados
    specs = {
        "residencial": {"n": 150, "wm": (7.0, 16.0), "hm": (7.0, 14.0)},
        "comercial": {"n": 44, "wm": (16.0, 34.0), "hm": (14.0, 28.0)},
        "industrial": {"n": 12, "wm": (45.0, 110.0), "hm": (30.0, 70.0)},
        "misto": {"n": 90, "wm": (8.0, 40.0), "hm": (8.0, 32.0)},
    }
    plan = {
        "residencial": [("residencial", 1.0)],
        "comercial": [("comercial", 0.66), ("residencial", 0.34)],
        "industrial": [("industrial", 0.72), ("comercial", 0.28)],
        "misto": [("residencial", 0.55), ("comercial", 0.32), ("industrial", 0.13)],
    }[urban_class]

    roof_boxes: list[list[float]] = []
    roof_cls: list[str] = []
    total_n = specs[urban_class]["n"]
    for cls, share in plan:
        sp = specs[cls]
        n = max(1, int(round(total_n * share)))
        for _ in range(n):
            wm = rng.uniform(*sp["wm"])
            hm = rng.uniform(*sp["hm"])
            w = max(3, int(round(wm / gsd_m)))
            h = max(3, int(round(hm / gsd_m)))
            x0 = int(rng.integers(0, max(1, W - w)))
            y0 = int(rng.integers(0, max(1, H - h)))
            box = [x0, y0, x0 + w, y0 + h]
            if _overlaps(box, roof_boxes, pad=2):
                continue
            color = _ROOF_COLORS[cls][int(rng.integers(0, len(_ROOF_COLORS[cls])))]
            _rect(img, x0, y0, x0 + w, y0 + h, color, 5.0, rng)
            roof_boxes.append(box)
            roof_cls.append(cls)

    # paineis sobre uma fracao dos telhados
    panel_boxes: list[list[float]] = []
    mask = np.zeros((H, W), dtype=bool)
    for box, cls in zip(roof_boxes, roof_cls):
        if rng.random() > panel_rate:
            continue
        x0, y0, x1, y1 = box
        rw, rh = x1 - x0, y1 - y0
        if min(rw, rh) < 8:
            continue
        # painel ocupa parte do telhado, com recuo
        fw = rng.uniform(0.35, 0.72)
        fh = rng.uniform(0.35, 0.72)
        pw = max(5, int(rw * fw))
        ph = max(5, int(rh * fh))
        px = x0 + int(rng.uniform(0.1, 0.9) * max(1, rw - pw))
        py = y0 + int(rng.uniform(0.1, 0.9) * max(1, rh - ph))
        px1, py1 = min(W, px + pw), min(H, py + ph)
        if px1 - px < 5 or py1 - py < 5:
            continue
        img[py:py1, px:px1] = _panel_texture(py1 - py, px1 - px, rng, gsd_m)
        mask[py:py1, px:px1] = True
        panel_boxes.append([px, py, px1, py1])

    geo = GeoTransform(center_lat, center_lon, gsd_m, W, H)
    return SyntheticScene(
        rgb=np.clip(img, 0, 255).astype("uint8"),
        panel_boxes=np.asarray(panel_boxes, dtype="f8").reshape(-1, 4),
        panel_mask=mask,
        roof_boxes=np.asarray(roof_boxes, dtype="f8").reshape(-1, 4),
        roof_class=np.asarray(roof_cls, dtype=object),
        geo=geo,
        seed=seed,
    )


def _overlaps(box: list[float], others: list[list[float]], pad: int = 0) -> bool:
    x0, y0, x1, y1 = box
    for o in others:
        if (x0 - pad < o[2] and x1 + pad > o[0] and
                y0 - pad < o[3] and y1 + pad > o[1]):
            return True
    return False


def crop(scene_rgb: np.ndarray, t: Tile) -> np.ndarray:
    return scene_rgb[t.y0:t.y1, t.x0:t.x1]
