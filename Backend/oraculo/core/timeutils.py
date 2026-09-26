# -*- coding: utf-8 -*-
"""Utilidades de tempo: parsing do formato do ONS e grade horaria."""
from __future__ import annotations

from datetime import datetime, timezone

import numpy as np

ONS_FORMAT = "%Y-%m-%d %H:%M:%S"


def parse_instante(s: str) -> np.datetime64:
    """Converte 'YYYY-MM-DD HH:MM:SS' do ONS em datetime64[s].

    Devolve NaT quando o valor for invalido, para que a ingestao possa
    descartar e contabilizar em vez de quebrar.
    """
    if not s:
        return np.datetime64("NaT")
    t = str(s).strip().replace("T", " ")
    if len(t) == 10:
        t += " 00:00:00"
    if len(t) == 16:
        t += ":00"
    try:
        return np.datetime64(datetime.strptime(t[:19], ONS_FORMAT), "s")
    except ValueError:
        try:
            return np.datetime64(t[:19], "s")
        except Exception:
            return np.datetime64("NaT")


def hour_of_day(ts: np.ndarray) -> np.ndarray:
    """Hora do dia (0-23) para datetime64[s]."""
    day = ts.astype("datetime64[D]").astype("datetime64[s]")
    return ((ts - day).astype("i8") // 3600).astype("i8")


def day_of_week(ts: np.ndarray) -> np.ndarray:
    """0 = segunda ... 6 = domingo."""
    days = ts.astype("datetime64[D]").astype("i8")
    return ((days + 3) % 7).astype("i8")  # 1970-01-01 foi quinta (=3)


def day_of_year(ts: np.ndarray) -> np.ndarray:
    years = ts.astype("datetime64[Y]")
    return ((ts.astype("datetime64[D]") - years.astype("datetime64[D]"))
            .astype("i8") + 1).astype("i8")


def hourly_grid(start: np.datetime64, end: np.datetime64) -> np.ndarray:
    """Grade horaria fechada em ambos os extremos."""
    return np.arange(start, end + np.timedelta64(1, "h"),
                     np.timedelta64(1, "h"), dtype="datetime64[s]")


def reindex_hourly(ts: np.ndarray, values: np.ndarray) -> tuple[np.ndarray, np.ndarray, int]:
    """Coloca a serie numa grade horaria completa; lacunas viram NaN.

    Devolve (grade, valores, n_lacunas).
    """
    if len(ts) == 0:
        return ts, values, 0
    ts = ts.astype("datetime64[s]")
    order = np.argsort(ts)
    ts, values = ts[order], np.asarray(values, dtype="f8")[order]
    grid = hourly_grid(ts[0], ts[-1])
    lut = {int(t.astype("i8")): i for i, t in enumerate(ts)}
    out = np.full(len(grid), np.nan)
    for i, t in enumerate(grid):
        j = lut.get(int(t.astype("i8")))
        if j is not None:
            out[i] = values[j]
    return grid, out, int(np.isnan(out).sum())


def iso_list(ts: np.ndarray) -> list[str]:
    return [str(t) for t in ts.astype("datetime64[s]")]


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def to_datetime64(s: str) -> np.datetime64:
    return parse_instante(s)
