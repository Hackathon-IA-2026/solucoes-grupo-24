# -*- coding: utf-8 -*-
"""Backtest cronologico.

Divisao aleatoria e proibida: as variaveis de defasagem (y(t-1), y(t-24))
vazariam informacao do futuro para o treino, inflando artificialmente a
acuracia. O teste automatizado verifica max(idx_treino) < min(idx_teste).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..config import BACKTEST_TRAIN_FRACTION, HORIZONS, QUANTILES
from ..core.timeutils import hour_of_day
from ..features.builder import FeatureMatrix
from ..models import baselines
from ..models.quantile import QuantileModel
from . import metrics as M


@dataclass
class Split:
    train_idx: np.ndarray
    test_idx: np.ndarray
    cut_at: str

    @property
    def leakage_free(self) -> bool:
        if not len(self.train_idx) or not len(self.test_idx):
            return True
        return int(self.train_idx.max()) < int(self.test_idx.min())

    def to_dict(self) -> dict:
        return {
            "train_rows": int(len(self.train_idx)),
            "test_rows": int(len(self.test_idx)),
            "cut_at": self.cut_at,
            "leakage_free": self.leakage_free,
        }


def chronological_split(index: np.ndarray, valid: np.ndarray,
                        train_fraction: float = BACKTEST_TRAIN_FRACTION,
                        embargo: int = 0) -> Split:
    """Corte cronologico com embargo opcional entre treino e teste.

    O embargo remove `embargo` pontos logo apos o corte, evitando que uma
    defasagem longa do teste toque o fim do treino.
    """
    idx = np.flatnonzero(np.asarray(valid, dtype=bool))
    if len(idx) < 10:
        return Split(idx, np.array([], dtype="i8"), "")
    k = max(1, int(len(idx) * train_fraction))
    train = idx[:k]
    test = idx[k + embargo:]
    cut = str(np.asarray(index, dtype="datetime64[s]")[train[-1]]) if len(train) else ""
    return Split(train, test, cut)


@dataclass
class HorizonResult:
    horizon: str
    steps: int
    point: dict = field(default_factory=dict)
    by_patamar: dict = field(default_factory=dict)
    pinball: float = float("nan")
    calibration: list = field(default_factory=list)
    interval_width: float = float("nan")
    peak: dict = field(default_factory=dict)
    baselines: dict = field(default_factory=dict)
    skill: dict = field(default_factory=dict)
    series: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "horizon": self.horizon,
            "steps": self.steps,
            **self.point,
            "pinball": None if np.isnan(self.pinball) else round(self.pinball, 3),
            "interval_width_mw": None if np.isnan(self.interval_width)
                                 else round(self.interval_width, 1),
            "by_patamar": self.by_patamar,
            "calibration": self.calibration,
            "peak": self.peak,
            "baselines": self.baselines,
            "skill": self.skill,
        }


def shift_target(y: np.ndarray, steps: int) -> np.ndarray:
    """Alvo deslocado: y_alvo(t) = y(t + steps)."""
    y = np.asarray(y, dtype="f8")
    out = np.full(len(y), np.nan)
    if steps == 0:
        return y.copy()
    if steps < len(y):
        out[: len(y) - steps] = y[steps:]
    return out


def run(fm: FeatureMatrix, y: np.ndarray, *, asymmetric: bool = True,
        horizons: dict[str, int] | None = None,
        keep_series: bool = True) -> dict:
    """Executa o backtest para todos os horizontes.

    Para cada horizonte, o alvo e deslocado ANTES do corte, garantindo que
    nenhum ponto de teste tenha sido visto como alvo no treino.
    """
    horizons = horizons or HORIZONS
    y = np.asarray(y, dtype="f8")
    hours = hour_of_day(fm.index)
    results: list[HorizonResult] = []
    split_info: dict = {}

    for name, steps in horizons.items():
        y_t = shift_target(y, steps)
        valid = fm.valid & np.isfinite(y_t)
        split = chronological_split(fm.index, valid, embargo=steps)
        if not split_info:
            split_info = split.to_dict()
        if len(split.train_idx) < fm.p + 10 or len(split.test_idx) < 5:
            results.append(HorizonResult(name, steps))
            continue

        model = QuantileModel(quantiles=QUANTILES, asymmetric=asymmetric)
        model.fit(fm.X[split.train_idx], y_t[split.train_idx],
                  fm.patamar[split.train_idx], names=fm.names)
        pred = model.predict(fm.X[split.test_idx])

        yte = y_t[split.test_idx]
        p50 = pred[0.50]
        res = HorizonResult(
            horizon=name,
            steps=steps,
            point=M.point_metrics(yte, p50),
            by_patamar=M.by_patamar(yte, p50, hours[split.test_idx]),
            pinball=M.pinball_loss(yte, pred),
            calibration=M.calibration(yte, pred),
            interval_width=M.interval_width(pred[0.10], pred[0.90]),
            peak=M.peak_error(yte, p50),
        )

        # Baselines avaliados no MESMO conjunto de teste.
        for bname, bfn in baselines.ALL.items():
            bhat_full = bfn(y, steps)
            bhat = bhat_full[split.test_idx]
            bm = M.point_metrics(yte, bhat)
            res.baselines[bname] = {"label": baselines.LABELS[bname], **bm}
            res.skill[bname] = round(
                baselines.skill(res.point["mae"], bm["mae"]), 4
            ) if np.isfinite(bm.get("mae", float("nan"))) else None

        if keep_series:
            n = min(len(split.test_idx), 24 * 14)
            sel = split.test_idx[:n]
            res.series = {
                "index": [str(t) for t in fm.index[sel]],
                "observed": _round_list(y_t[sel]),
                "p10": _round_list(pred[0.10][:n]),
                "p50": _round_list(pred[0.50][:n]),
                "p90": _round_list(pred[0.90][:n]),
                "persistencia": _round_list(baselines.persistence(y, steps)[sel]),
            }
        results.append(res)

    return {
        "split": split_info,
        "asymmetric": asymmetric,
        "horizons": [r.to_dict() for r in results],
        "series": {r.horizon: r.series for r in results if r.series},
    }


def compare_asymmetry(fm: FeatureMatrix, y: np.ndarray,
                      horizon: str = "3h") -> dict:
    """Efeito de ligar e desligar a perda assimetrica, no mesmo teste.

    E o que transforma o argumento do deck em evidencia mensuravel.
    """
    steps = HORIZONS.get(horizon, 3)
    out = {}
    for label, asym in (("assimetrica", True), ("simetrica", False)):
        r = run(fm, y, asymmetric=asym, horizons={horizon: steps},
                keep_series=False)
        h = r["horizons"][0]
        out[label] = {
            "mae": h.get("mae"),
            "rmse": h.get("rmse"),
            "pinball": h.get("pinball"),
            "by_patamar": {
                k: {"mae": v.get("mae"), "bias": v.get("bias")}
                for k, v in (h.get("by_patamar") or {}).items()
            },
        }
    return out


def _round_list(v: np.ndarray, nd: int = 1) -> list:
    return [None if not np.isfinite(x) else round(float(x), nd) for x in v]
