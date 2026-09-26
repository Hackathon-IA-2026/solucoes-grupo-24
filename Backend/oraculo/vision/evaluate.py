# -*- coding: utf-8 -*-
"""Avaliacao do detector contra verdade fundamental.

Casamento guloso por IoU descendente, como na pratica de deteccao de objetos:
cada deteccao casa com no maximo uma caixa verdadeira, e vice-versa. Devolve
precisao, revocacao, F1, IoU medio dos pares casados e erro de contagem e de
area — este ultimo e o que realmente importa, porque a area alimenta a
estimativa de kWp e, dai, o indicador de MMGD.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .nms import iou_matrix


@dataclass
class MatchResult:
    tp: int
    fp: int
    fn: int
    iou_mean: float
    pairs: list[tuple[int, int, float]]      # (indice_det, indice_verdade, iou)
    iou_threshold: float

    @property
    def precision(self) -> float:
        d = self.tp + self.fp
        return self.tp / d if d else float("nan")

    @property
    def recall(self) -> float:
        d = self.tp + self.fn
        return self.tp / d if d else float("nan")

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        if not np.isfinite(p) or not np.isfinite(r) or (p + r) == 0:
            return float("nan")
        return 2 * p * r / (p + r)

    def to_dict(self) -> dict:
        return {
            "iou_threshold": self.iou_threshold,
            "tp": self.tp, "fp": self.fp, "fn": self.fn,
            "precision": _r(self.precision),
            "recall": _r(self.recall),
            "f1": _r(self.f1),
            "iou_mean": _r(self.iou_mean),
        }


def _r(v: float, nd: int = 4):
    return None if v is None or not np.isfinite(v) else round(float(v), nd)


def match(pred_boxes: np.ndarray, truth_boxes: np.ndarray,
          iou_threshold: float = 0.30) -> MatchResult:
    """Casamento guloso por IoU descendente."""
    p = np.asarray(pred_boxes, dtype="f8").reshape(-1, 4)
    t = np.asarray(truth_boxes, dtype="f8").reshape(-1, 4)
    if not len(p) or not len(t):
        return MatchResult(0, len(p), len(t), float("nan"), [], iou_threshold)

    M = iou_matrix(p, t)
    pairs: list[tuple[int, int, float]] = []
    used_p: set[int] = set()
    used_t: set[int] = set()
    flat = [(float(M[i, j]), i, j) for i in range(len(p)) for j in range(len(t))
            if M[i, j] >= iou_threshold]
    flat.sort(reverse=True)
    for v, i, j in flat:
        if i in used_p or j in used_t:
            continue
        used_p.add(i)
        used_t.add(j)
        pairs.append((i, j, v))
    tp = len(pairs)
    iou_mean = float(np.mean([v for _, _, v in pairs])) if pairs else float("nan")
    return MatchResult(tp, len(p) - tp, len(t) - tp, iou_mean, pairs, iou_threshold)


def pr_curve(pred_boxes: np.ndarray, scores: np.ndarray,
             truth_boxes: np.ndarray, iou_threshold: float = 0.30,
             steps: int = 12) -> list[dict]:
    """Precisao e revocacao ao varrer o limiar de confianca."""
    s = np.asarray(scores, dtype="f8").ravel()
    if not len(s):
        return []
    lo, hi = float(s.min()), float(s.max())
    out: list[dict] = []
    for thr in np.linspace(lo, hi, steps):
        sel = s >= thr
        m = match(np.asarray(pred_boxes)[sel], truth_boxes, iou_threshold)
        out.append({"threshold": round(float(thr), 4), **m.to_dict(),
                    "n_pred": int(sel.sum())})
    return out


def average_precision(curve: list[dict]) -> float:
    """AP por interpolacao dos pontos da curva PR (regra do trapezio)."""
    pts = [(c["recall"], c["precision"]) for c in curve
           if c["recall"] is not None and c["precision"] is not None]
    if len(pts) < 2:
        return float("nan")
    pts.sort()
    ap = 0.0
    for (r0, p0), (r1, p1) in zip(pts[:-1], pts[1:]):
        ap += (r1 - r0) * (p0 + p1) / 2.0
    return float(ap)


def area_error(pred_area_m2: float, truth_area_m2: float) -> dict:
    """Erro de area agregada — o que propaga para o kWp e para o indicador."""
    if truth_area_m2 <= 0:
        return {"pred_m2": _r(pred_area_m2, 1), "truth_m2": 0.0,
                "abs_error_m2": None, "rel_error": None}
    err = pred_area_m2 - truth_area_m2
    return {
        "pred_m2": _r(pred_area_m2, 1),
        "truth_m2": _r(truth_area_m2, 1),
        "abs_error_m2": _r(err, 1),
        "rel_error": _r(err / truth_area_m2),
    }


def mask_iou(pred_mask: np.ndarray, truth_mask: np.ndarray) -> float:
    """IoU pixel a pixel: mede a qualidade da segmentacao, nao da caixa."""
    a = np.asarray(pred_mask, dtype=bool)
    b = np.asarray(truth_mask, dtype=bool)
    if a.shape != b.shape:
        return float("nan")
    inter = float(np.logical_and(a, b).sum())
    union = float(np.logical_or(a, b).sum())
    return inter / union if union > 0 else float("nan")


def boxes_to_mask(boxes: np.ndarray, height: int, width: int) -> np.ndarray:
    m = np.zeros((height, width), dtype=bool)
    for b in np.asarray(boxes, dtype="f8").reshape(-1, 4):
        x0, y0, x1, y1 = [int(round(v)) for v in b]
        x0, y0 = max(0, x0), max(0, y0)
        x1, y1 = min(width, x1), min(height, y1)
        if x1 > x0 and y1 > y0:
            m[y0:y1, x0:x1] = True
    return m


def evaluate_scene(result, scene, iou_threshold: float = 0.30) -> dict:
    """Relatorio completo de uma cena com verdade conhecida."""
    pred = np.array([d.box for d in result.detections], dtype="f8").reshape(-1, 4)
    scores = np.array([d.score for d in result.detections], dtype="f8")
    truth = scene.panel_boxes
    m = match(pred, truth, iou_threshold)
    curve = pr_curve(pred, scores, truth, iou_threshold)
    px_m2 = scene.geo.pixel_area_m2()
    truth_area = float(scene.panel_mask.sum() * px_m2)
    pred_mask = boxes_to_mask(pred, *scene.panel_mask.shape)
    return {
        "match": m.to_dict(),
        "count": {"pred": int(len(pred)), "truth": int(len(truth)),
                  "error": int(len(pred) - len(truth))},
        "area": area_error(result.total_area_m2(), truth_area),
        "area_raw": area_error(result.total_area_raw_m2(), truth_area),
        "mask_iou": _r(mask_iou(pred_mask, scene.panel_mask)),
        "pr_curve": curve,
        "average_precision": _r(average_precision(curve)),
        "note": ("Verdade fundamental da ortoimagem sintética. As métricas são "
                 "medições reais do detector; a imagem é de demonstração."),
    }
