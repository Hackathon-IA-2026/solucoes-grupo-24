# -*- coding: utf-8 -*-
"""Baselines obrigatorios.

Nenhum numero de acuracia e publicado sem o skill score correspondente. Estes
sao os pisos de referencia contra os quais o modelo tem de ganhar, por
horizonte (ver 07-validacao.md).
"""
from __future__ import annotations

import numpy as np


def persistence(y: np.ndarray, horizon: int) -> np.ndarray:
    """y_hat(t+h) = y(t). Previsao alinhada ao instante alvo."""
    y = np.asarray(y, dtype="f8")
    out = np.full(len(y), np.nan)
    if horizon < len(y):
        out[horizon:] = y[: len(y) - horizon]
    return out


def seasonal_naive(y: np.ndarray, horizon: int, period: int = 24) -> np.ndarray:
    """y_hat(t+h) = y(t+h-period). Para h < period usa o ciclo anterior."""
    y = np.asarray(y, dtype="f8")
    out = np.full(len(y), np.nan)
    lag = period if horizon <= period else period * int(np.ceil(horizon / period))
    if lag < len(y):
        out[lag:] = y[: len(y) - lag]
    return out


def weekly_naive(y: np.ndarray, horizon: int) -> np.ndarray:
    return seasonal_naive(y, horizon, period=168)


ALL = {
    "persistencia": persistence,
    "sazonal_diario": seasonal_naive,
    "sazonal_semanal": weekly_naive,
}

LABELS = {
    "persistencia": "Persistência",
    "sazonal_diario": "Sazonal-ingênuo diário (t−24h)",
    "sazonal_semanal": "Sazonal-ingênuo semanal (t−168h)",
}


def compute_all(y: np.ndarray, horizon: int) -> dict[str, np.ndarray]:
    return {name: fn(y, horizon) for name, fn in ALL.items()}


def skill(mae_model: float, mae_baseline: float) -> float:
    """skill = 1 - MAE_modelo / MAE_baseline. Positivo significa ganho."""
    if not np.isfinite(mae_baseline) or mae_baseline <= 0:
        return float("nan")
    return float(1.0 - mae_model / mae_baseline)
