# -*- coding: utf-8 -*-
"""Supressao nao-maxima e deduplicacao entre ladrilhos.

Peca critica de qualquer detector de janela deslizante, YOLO incluido: um
telhado que cai na sobreposicao de dois ladrilhos e detectado duas vezes, e sem
deduplicacao a contagem de paineis — que alimenta o indicador de MMGD — sai
inflada.

Implementado em numpy puro, testado isoladamente, e usado tanto pelo detector
classico quanto pelo adaptador YOLO.
"""
from __future__ import annotations

import numpy as np


def iou_matrix(boxes_a: np.ndarray, boxes_b: np.ndarray) -> np.ndarray:
    """Interseccao sobre uniao entre dois conjuntos de caixas (x0,y0,x1,y1)."""
    a = np.asarray(boxes_a, dtype="f8").reshape(-1, 4)
    b = np.asarray(boxes_b, dtype="f8").reshape(-1, 4)
    if not len(a) or not len(b):
        return np.zeros((len(a), len(b)))
    x0 = np.maximum(a[:, None, 0], b[None, :, 0])
    y0 = np.maximum(a[:, None, 1], b[None, :, 1])
    x1 = np.minimum(a[:, None, 2], b[None, :, 2])
    y1 = np.minimum(a[:, None, 3], b[None, :, 3])
    inter = np.clip(x1 - x0, 0, None) * np.clip(y1 - y0, 0, None)
    area_a = np.clip(a[:, 2] - a[:, 0], 0, None) * np.clip(a[:, 3] - a[:, 1], 0, None)
    area_b = np.clip(b[:, 2] - b[:, 0], 0, None) * np.clip(b[:, 3] - b[:, 1], 0, None)
    union = area_a[:, None] + area_b[None, :] - inter
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(union > 0, inter / union, 0.0)


def iou_pairwise(box: np.ndarray, boxes: np.ndarray) -> np.ndarray:
    return iou_matrix(np.asarray(box).reshape(1, 4), boxes)[0]


def nms(boxes: np.ndarray, scores: np.ndarray, iou_threshold: float = 0.45
        ) -> np.ndarray:
    """Supressao nao-maxima classica. Devolve os indices mantidos."""
    boxes = np.asarray(boxes, dtype="f8").reshape(-1, 4)
    scores = np.asarray(scores, dtype="f8").ravel()
    if not len(boxes):
        return np.array([], dtype="i8")
    order = np.argsort(-scores, kind="stable")
    keep: list[int] = []
    while len(order):
        i = int(order[0])
        keep.append(i)
        if len(order) == 1:
            break
        rest = order[1:]
        ious = iou_pairwise(boxes[i], boxes[rest])
        order = rest[ious <= iou_threshold]
    return np.asarray(keep, dtype="i8")


def soft_dedupe(boxes: np.ndarray, scores: np.ndarray, *,
                iou_threshold: float = 0.30,
                containment_threshold: float = 0.70) -> np.ndarray:
    """Deduplicacao mais agressiva para a costura entre ladrilhos.

    Alem do IoU, remove caixas majoritariamente contidas em outra de maior
    pontuacao: na borda do ladrilho e comum o mesmo painel aparecer recortado
    numa deteccao e completo na outra, com IoU baixo e contencao alta.
    """
    boxes = np.asarray(boxes, dtype="f8").reshape(-1, 4)
    scores = np.asarray(scores, dtype="f8").ravel()
    if not len(boxes):
        return np.array([], dtype="i8")
    areas = np.clip(boxes[:, 2] - boxes[:, 0], 0, None) * \
            np.clip(boxes[:, 3] - boxes[:, 1], 0, None)
    order = np.argsort(-scores, kind="stable")
    keep: list[int] = []
    suppressed = np.zeros(len(boxes), dtype=bool)
    for idx in order:
        i = int(idx)
        if suppressed[i]:
            continue
        keep.append(i)
        rest = np.array([j for j in range(len(boxes))
                         if j != i and not suppressed[j]], dtype="i8")
        if not len(rest):
            continue
        ious = iou_pairwise(boxes[i], boxes[rest])
        # contencao: quanto da caixa candidata esta dentro da mantida
        x0 = np.maximum(boxes[i, 0], boxes[rest, 0])
        y0 = np.maximum(boxes[i, 1], boxes[rest, 1])
        x1 = np.minimum(boxes[i, 2], boxes[rest, 2])
        y1 = np.minimum(boxes[i, 3], boxes[rest, 3])
        inter = np.clip(x1 - x0, 0, None) * np.clip(y1 - y0, 0, None)
        with np.errstate(divide="ignore", invalid="ignore"):
            contain = np.where(areas[rest] > 0, inter / areas[rest], 0.0)
        drop = rest[(ious > iou_threshold) | (contain > containment_threshold)]
        suppressed[drop] = True
    return np.asarray(sorted(keep), dtype="i8")


def clip_boxes(boxes: np.ndarray, width: int, height: int) -> np.ndarray:
    b = np.asarray(boxes, dtype="f8").reshape(-1, 4).copy()
    b[:, 0] = np.clip(b[:, 0], 0, width)
    b[:, 1] = np.clip(b[:, 1], 0, height)
    b[:, 2] = np.clip(b[:, 2], 0, width)
    b[:, 3] = np.clip(b[:, 3], 0, height)
    return b


def xywh_to_xyxy(boxes: np.ndarray) -> np.ndarray:
    """Formato nativo do YOLO (centro, largura, altura) para canto a canto."""
    b = np.asarray(boxes, dtype="f8").reshape(-1, 4)
    out = np.empty_like(b)
    out[:, 0] = b[:, 0] - b[:, 2] / 2.0
    out[:, 1] = b[:, 1] - b[:, 3] / 2.0
    out[:, 2] = b[:, 0] + b[:, 2] / 2.0
    out[:, 3] = b[:, 1] + b[:, 3] / 2.0
    return out


def xyxy_to_xywh(boxes: np.ndarray) -> np.ndarray:
    b = np.asarray(boxes, dtype="f8").reshape(-1, 4)
    out = np.empty_like(b)
    out[:, 0] = (b[:, 0] + b[:, 2]) / 2.0
    out[:, 1] = (b[:, 1] + b[:, 3]) / 2.0
    out[:, 2] = b[:, 2] - b[:, 0]
    out[:, 3] = b[:, 3] - b[:, 1]
    return out


def letterbox_params(src_w: int, src_h: int, dst: int = 640
                     ) -> tuple[float, float, float]:
    """Escala e deslocamentos do letterbox usado pelo YOLO.

    Devolve (escala, dx, dy). A inversa desfaz o ajuste nas coordenadas
    previstas, sem a qual as caixas saem deslocadas.
    """
    scale = min(dst / float(src_w), dst / float(src_h))
    new_w, new_h = src_w * scale, src_h * scale
    return scale, (dst - new_w) / 2.0, (dst - new_h) / 2.0


def undo_letterbox(boxes: np.ndarray, src_w: int, src_h: int,
                   dst: int = 640) -> np.ndarray:
    """Converte caixas do espaco do letterbox de volta ao ladrilho original."""
    scale, dx, dy = letterbox_params(src_w, src_h, dst)
    b = np.asarray(boxes, dtype="f8").reshape(-1, 4).copy()
    b[:, [0, 2]] = (b[:, [0, 2]] - dx) / scale
    b[:, [1, 3]] = (b[:, [1, 3]] - dy) / scale
    return clip_boxes(b, src_w, src_h)
