# -*- coding: utf-8 -*-
"""Metricas de ponto, probabilisticas e por patamar.

Uma melhoria de MAE global que piora a ponta noturna e uma piora operacional.
Por isso toda metrica de ponto e reportada tambem por patamar.
"""
from __future__ import annotations

import numpy as np

from ..config import PATAMARES
from ..models.quantile import pinball


def _pair(y: np.ndarray, yhat: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    y = np.asarray(y, dtype="f8")
    yhat = np.asarray(yhat, dtype="f8")
    ok = np.isfinite(y) & np.isfinite(yhat)
    return y[ok], yhat[ok]


def mae(y, yhat) -> float:
    y, yhat = _pair(y, yhat)
    return float(np.mean(np.abs(y - yhat))) if len(y) else float("nan")


def rmse(y, yhat) -> float:
    y, yhat = _pair(y, yhat)
    return float(np.sqrt(np.mean((y - yhat) ** 2))) if len(y) else float("nan")


def mape(y, yhat) -> float:
    y, yhat = _pair(y, yhat)
    ok = np.abs(y) > 1e-6
    if not ok.any():
        return float("nan")
    return float(np.mean(np.abs((y[ok] - yhat[ok]) / y[ok])) * 100.0)


def bias(y, yhat) -> float:
    y, yhat = _pair(y, yhat)
    return float(np.mean(yhat - y)) if len(y) else float("nan")


def ramp_mae(y, yhat) -> float:
    """Erro medio absoluto da rampa horaria, em MW/h."""
    y = np.asarray(y, dtype="f8")
    yhat = np.asarray(yhat, dtype="f8")
    if len(y) < 2:
        return float("nan")
    dy, dyh = np.diff(y), np.diff(yhat)
    ok = np.isfinite(dy) & np.isfinite(dyh)
    return float(np.mean(np.abs(dy[ok] - dyh[ok]))) if ok.any() else float("nan")


def peak_error(y, yhat) -> dict:
    """Erro no valor e no instante do pico e do vale."""
    y = np.asarray(y, dtype="f8")
    yhat = np.asarray(yhat, dtype="f8")
    ok = np.isfinite(y) & np.isfinite(yhat)
    if not ok.any():
        return {}
    yi, yhi = y[ok], yhat[ok]
    return {
        "peak_mw_error": round(float(np.max(yhi) - np.max(yi)), 2),
        "peak_hour_shift": int(np.argmax(yhi) - np.argmax(yi)),
        "valley_mw_error": round(float(np.min(yhi) - np.min(yi)), 2),
        "valley_hour_shift": int(np.argmin(yhi) - np.argmin(yi)),
    }


def pinball_loss(y, quantile_preds: dict[float, np.ndarray]) -> float:
    """Media da perda pinball sobre todos os quantis."""
    y = np.asarray(y, dtype="f8")
    losses = []
    for tau, yhat in quantile_preds.items():
        yy, yh = _pair(y, yhat)
        if len(yy):
            losses.append(float(np.mean(pinball(yy - yh, tau))))
    return float(np.mean(losses)) if losses else float("nan")


def coverage(y, yhat_q: np.ndarray, tau: float) -> float:
    """Fracao empirica de y <= yhat_tau. Deveria aproximar tau."""
    y, yhat_q = _pair(y, yhat_q)
    return float(np.mean(y <= yhat_q)) if len(y) else float("nan")


def interval_width(lo: np.ndarray, hi: np.ndarray) -> float:
    lo, hi = _pair(lo, hi)
    return float(np.mean(hi - lo)) if len(lo) else float("nan")


def calibration(y, quantile_preds: dict[float, np.ndarray]) -> list[dict]:
    out = []
    for tau in sorted(quantile_preds):
        emp = coverage(y, quantile_preds[tau], tau)
        out.append({
            "quantile": tau,
            "nominal": round(tau, 3),
            "empirical": None if np.isnan(emp) else round(emp, 4),
            "deviation_pp": None if np.isnan(emp) else round((emp - tau) * 100.0, 2),
        })
    return out


def point_metrics(y, yhat) -> dict:
    return {
        "mae": round(mae(y, yhat), 2),
        "rmse": round(rmse(y, yhat), 2),
        "mape": round(mape(y, yhat), 3),
        "bias": round(bias(y, yhat), 2),
        "ramp_mae_mw_h": round(ramp_mae(y, yhat), 2),
        "n": int(np.sum(np.isfinite(np.asarray(y, dtype="f8"))
                        & np.isfinite(np.asarray(yhat, dtype="f8")))),
    }


def by_patamar(y, yhat, hours: np.ndarray) -> dict:
    """Metricas de ponto restritas a cada patamar operativo."""
    hours = np.asarray(hours)
    out: dict[str, dict] = {}
    for name, (a, b) in PATAMARES.items():
        sel = (hours >= a) & (hours <= b)
        if sel.any():
            out[name] = point_metrics(np.asarray(y)[sel], np.asarray(yhat)[sel])
        else:
            out[name] = {}
    return out


# --------------------------------------------------------- classificacao
def roc_auc(y_true: np.ndarray, score: np.ndarray) -> float:
    """AUC pelo posto de Mann-Whitney, tolerante a empates."""
    y = np.asarray(y_true).astype("f8")
    s = np.asarray(score, dtype="f8")
    ok = np.isfinite(y) & np.isfinite(s)
    y, s = y[ok], s[ok]
    pos, neg = y > 0.5, y <= 0.5
    npos, nneg = int(pos.sum()), int(neg.sum())
    if npos == 0 or nneg == 0:
        return float("nan")
    order = np.argsort(s, kind="mergesort")
    ranks = np.empty(len(s), dtype="f8")
    ranks[order] = np.arange(1, len(s) + 1, dtype="f8")
    # corrige empates pela media dos postos
    uniq, inv, counts = np.unique(s, return_inverse=True, return_counts=True)
    sums = np.zeros(len(uniq))
    np.add.at(sums, inv, ranks)
    ranks = (sums / counts)[inv]
    return float((ranks[pos].sum() - npos * (npos + 1) / 2.0) / (npos * nneg))


def precision_recall(y_true: np.ndarray, pred: np.ndarray) -> dict:
    y = np.asarray(y_true).astype(bool)
    p = np.asarray(pred).astype(bool)
    tp = int(np.sum(y & p))
    fp = int(np.sum(~y & p))
    fn = int(np.sum(y & ~p))
    tn = int(np.sum(~y & ~p))
    prec = tp / (tp + fp) if (tp + fp) else float("nan")
    rec = tp / (tp + fn) if (tp + fn) else float("nan")
    f1 = (2 * prec * rec / (prec + rec)) if (prec and rec and
                                             np.isfinite(prec) and np.isfinite(rec)) else float("nan")
    return {
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision": None if np.isnan(prec) else round(prec, 4),
        "recall": None if np.isnan(rec) else round(rec, 4),
        "f1": None if np.isnan(f1) else round(f1, 4),
    }


def brier(y_true: np.ndarray, prob: np.ndarray) -> float:
    y = np.asarray(y_true).astype("f8")
    p = np.asarray(prob, dtype="f8")
    ok = np.isfinite(y) & np.isfinite(p)
    return float(np.mean((p[ok] - y[ok]) ** 2)) if ok.any() else float("nan")
