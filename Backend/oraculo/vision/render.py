# -*- coding: utf-8 -*-
"""Renderizacao PNG da cena com as deteccoes sobrepostas.

Serve a interface: o operador precisa VER o que o detector marcou, com a caixa,
a confianca e a grade de ladrilhos. Sem isso, a deteccao e um numero sem
auditoria visual.
"""
from __future__ import annotations

import io

import numpy as np

try:
    from PIL import Image, ImageDraw
except ImportError:  # pragma: no cover
    Image = None  # type: ignore
    ImageDraw = None  # type: ignore

COLOR_DET = (79, 209, 197)        # teal
COLOR_TRUTH = (240, 176, 48)      # ambar
COLOR_TILE = (60, 76, 116)
COLOR_MISS = (239, 91, 91)        # carmim


def available() -> bool:
    return Image is not None


def scene_png(rgb: np.ndarray, *, detections=None, truth_boxes=None,
              tiles=None, scale: int = 1, show_scores: bool = True,
              missed=None) -> bytes:
    """Compoe o PNG. `detections` sao objetos com .box e .score."""
    if Image is None:  # pragma: no cover
        raise RuntimeError("Pillow indisponível")
    arr = np.asarray(rgb, dtype="uint8")
    img = Image.fromarray(arr, mode="RGB")
    if scale and scale != 1:
        img = img.resize((img.width * scale, img.height * scale), Image.NEAREST)
    d = ImageDraw.Draw(img, "RGBA")
    s = max(1, int(scale))

    if tiles:
        for t in tiles:
            d.rectangle([t.x0 * s, t.y0 * s, t.x1 * s - 1, t.y1 * s - 1],
                        outline=COLOR_TILE + (110,), width=1)

    if truth_boxes is not None:
        for b in np.asarray(truth_boxes, dtype="f8").reshape(-1, 4):
            d.rectangle([b[0] * s, b[1] * s, b[2] * s, b[3] * s],
                        outline=COLOR_TRUTH + (200,), width=1)

    if missed is not None:
        for b in np.asarray(missed, dtype="f8").reshape(-1, 4):
            d.rectangle([b[0] * s - 2, b[1] * s - 2, b[2] * s + 2, b[3] * s + 2],
                        outline=COLOR_MISS + (230,), width=2)

    for det in (detections or []):
        x0, y0, x1, y1 = [v * s for v in det.box]
        d.rectangle([x0, y0, x1, y1], outline=COLOR_DET + (255,), width=2)
        if show_scores and (x1 - x0) > 26:
            label = "%.2f" % det.score
            d.rectangle([x0, max(0, y0 - 11), x0 + 26, y0],
                        fill=(10, 16, 32, 205))
            d.text((x0 + 2, max(0, y0 - 11)), label, fill=COLOR_DET + (255,))

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def tile_png(rgb: np.ndarray, tile, detections=None, scale: int = 2) -> bytes:
    """Recorta um ladrilho e desenha apenas as deteccoes que caem nele."""
    patch = np.asarray(rgb)[tile.y0:tile.y1, tile.x0:tile.x1]
    local = []
    for det in (detections or []):
        x0, y0, x1, y1 = det.box
        if x1 < tile.x0 or x0 > tile.x1 or y1 < tile.y0 or y0 > tile.y1:
            continue
        shifted = type(det)(
            box=(x0 - tile.x0, y0 - tile.y0, x1 - tile.x0, y1 - tile.y0),
            score=det.score, area_px=det.area_px)
        local.append(shifted)
    return scene_png(patch, detections=local, scale=scale)


def feature_png(feature: np.ndarray, *, cmap: str = "teal",
                scale: int = 1) -> bytes:
    """Visualiza um canal de caracteristica (indice de azul, borda) em PNG.

    Deixa visivel POR QUE o detector marcou o que marcou — a camada de
    explicabilidade da visao computacional.
    """
    if Image is None:  # pragma: no cover
        raise RuntimeError("Pillow indisponível")
    f = np.asarray(feature, dtype="f8")
    finite = f[np.isfinite(f)]
    lo = float(np.percentile(finite, 2)) if finite.size else 0.0
    hi = float(np.percentile(finite, 98)) if finite.size else 1.0
    if hi <= lo:
        hi = lo + 1e-6
    norm = np.clip((f - lo) / (hi - lo), 0.0, 1.0)
    base = {"teal": (79, 209, 197), "amber": (240, 176, 48),
            "crimson": (239, 91, 91)}.get(cmap, (79, 209, 197))
    rgb = np.zeros(f.shape + (3,), dtype="uint8")
    for i, c in enumerate(base):
        rgb[..., i] = (norm * c).astype("uint8")
    img = Image.fromarray(rgb, mode="RGB")
    if scale != 1:
        img = img.resize((img.width * scale, img.height * scale), Image.NEAREST)
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
