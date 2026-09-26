# -*- coding: utf-8 -*-
"""Calendario brasileiro: feriados nacionais e dia-tipo.

Feriados moveis sao calculados (algoritmo de Meeus/Butcher para a Pascoa), nao
tabelados, para que o modelo funcione em qualquer ano sem manutencao.
"""
from __future__ import annotations

from datetime import date, timedelta
from functools import lru_cache

import numpy as np

TYPEDAY_UTIL = "util"
TYPEDAY_SATURDAY = "sabado"
TYPEDAY_SUNHOL = "domingo_feriado"
TYPEDAYS = (TYPEDAY_UTIL, TYPEDAY_SATURDAY, TYPEDAY_SUNHOL)

TYPEDAY_LABELS = {
    TYPEDAY_UTIL: "Dia útil",
    TYPEDAY_SATURDAY: "Sábado",
    TYPEDAY_SUNHOL: "Domingo / feriado",
}


def easter(year: int) -> date:
    """Domingo de Pascoa (calendario gregoriano), algoritmo de Meeus/Butcher."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    lo = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * lo) // 451
    month = (h + lo - 7 * m + 114) // 31
    day = ((h + lo - 7 * m + 114) % 31) + 1
    return date(year, month, day)


@lru_cache(maxsize=64)
def holidays(year: int) -> dict[date, str]:
    """Feriados nacionais do ano, fixos e moveis."""
    e = easter(year)
    out: dict[date, str] = {
        date(year, 1, 1): "Confraternização Universal",
        date(year, 4, 21): "Tiradentes",
        date(year, 5, 1): "Dia do Trabalho",
        date(year, 9, 7): "Independência",
        date(year, 10, 12): "Nossa Senhora Aparecida",
        date(year, 11, 2): "Finados",
        date(year, 11, 15): "Proclamação da República",
        date(year, 11, 20): "Consciência Negra",
        date(year, 12, 25): "Natal",
        e - timedelta(days=48): "Carnaval (segunda)",
        e - timedelta(days=47): "Carnaval (terça)",
        e - timedelta(days=2): "Sexta-feira Santa",
        e + timedelta(days=60): "Corpus Christi",
    }
    return out


def is_holiday(d: date) -> bool:
    return d in holidays(d.year)


def holiday_name(d: date) -> str:
    return holidays(d.year).get(d, "")


def typeday(d: date) -> str:
    """Dia-tipo usado nos perfis representativos do Eixo 1."""
    if is_holiday(d) or d.weekday() == 6:
        return TYPEDAY_SUNHOL
    if d.weekday() == 5:
        return TYPEDAY_SATURDAY
    return TYPEDAY_UTIL


def is_holiday_eve(d: date) -> bool:
    return is_holiday(d + timedelta(days=1))


# ------------------------------------------------------------ vetorizado
def typeday_array(ts: np.ndarray) -> np.ndarray:
    """Dia-tipo para um vetor datetime64[s]."""
    days = ts.astype("datetime64[D]").astype(object)
    return np.array([typeday(d) for d in days], dtype=object)


def holiday_flags(ts: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(feriado, vespera_de_feriado) para um vetor datetime64[s]."""
    days = ts.astype("datetime64[D]").astype(object)
    hol = np.array([1.0 if is_holiday(d) else 0.0 for d in days])
    eve = np.array([1.0 if is_holiday_eve(d) else 0.0 for d in days])
    return hol, eve
