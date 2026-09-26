# -*- coding: utf-8 -*-
"""Geometria solar e irradiancia de ceu claro.

Tudo determinístico e vetorizado em numpy. Referencias das formulas:
  - Equacao do tempo e declinacao: Spencer (1971), "Fourier series
    representation of the position of the sun".
  - Ceu claro: Haurwitz (1945), modelo de um parametro. Escolhido porque nao
    exige turbidez de Linke nem perfil de aerossol, dados que o prototipo nao
    tem. A limitacao esta declarada em 08-limitacoes.md.
"""
from __future__ import annotations

import numpy as np

from ..config import TZ_OFFSET_HOURS
from ..core.timeutils import day_of_year

SOLAR_CONSTANT = 1367.0  # W/m2
STC_IRRADIANCE = 1000.0  # W/m2


def fractional_year(doy: np.ndarray) -> np.ndarray:
    """Angulo fracionario do ano, em radianos."""
    return 2.0 * np.pi * (np.asarray(doy, dtype="f8") - 1.0) / 365.0


def equation_of_time(gamma: np.ndarray) -> np.ndarray:
    """Equacao do tempo em minutos (Spencer, 1971)."""
    return 229.18 * (
        0.000075
        + 0.001868 * np.cos(gamma)
        - 0.032077 * np.sin(gamma)
        - 0.014615 * np.cos(2 * gamma)
        - 0.040849 * np.sin(2 * gamma)
    )


def declination(gamma: np.ndarray) -> np.ndarray:
    """Declinacao solar em radianos (Spencer, 1971)."""
    return (
        0.006918
        - 0.399912 * np.cos(gamma)
        + 0.070257 * np.sin(gamma)
        - 0.006758 * np.cos(2 * gamma)
        + 0.000907 * np.sin(2 * gamma)
        - 0.002697 * np.cos(3 * gamma)
        + 0.001480 * np.sin(3 * gamma)
    )


def cos_zenith(ts: np.ndarray, lat: float, lon: float,
               tz_offset: float = TZ_OFFSET_HOURS) -> np.ndarray:
    """Cosseno do angulo zenital solar. Negativo significa noite."""
    ts = np.asarray(ts, dtype="datetime64[s]")
    doy = day_of_year(ts).astype("f8")
    day = ts.astype("datetime64[D]").astype("datetime64[s]")
    hours_local = (ts - day).astype("i8").astype("f8") / 3600.0

    gamma = fractional_year(doy)
    eot = equation_of_time(gamma)                       # minutos
    dec = declination(gamma)                            # radianos

    # Tempo solar verdadeiro: corrige longitude e equacao do tempo.
    # O meridiano padrao do fuso e 15 deg por hora de offset.
    lstm = 15.0 * tz_offset
    tc_minutes = 4.0 * (lon - lstm) + eot
    tsv = hours_local + tc_minutes / 60.0
    omega = np.deg2rad(15.0 * (tsv - 12.0))             # angulo horario

    phi = np.deg2rad(lat)
    cz = np.sin(phi) * np.sin(dec) + np.cos(phi) * np.cos(dec) * np.cos(omega)
    return np.clip(cz, -1.0, 1.0)


def extraterrestrial(ts: np.ndarray, cz: np.ndarray) -> np.ndarray:
    """Irradiancia extraterrestre no plano horizontal, W/m2."""
    doy = day_of_year(np.asarray(ts, dtype="datetime64[s]")).astype("f8")
    gamma = fractional_year(doy)
    e0 = 1.0 + 0.033 * np.cos(gamma)
    out = SOLAR_CONSTANT * e0 * cz
    return np.where(cz > 0, out, 0.0)


def clearsky_ghi(cz: np.ndarray) -> np.ndarray:
    """Irradiancia global horizontal de ceu claro, W/m2 (Haurwitz)."""
    cz = np.asarray(cz, dtype="f8")
    safe = np.where(cz > 1e-6, cz, 1.0)
    ghi = 1098.0 * safe * np.exp(-0.059 / safe)
    return np.where(cz > 1e-6, np.maximum(ghi, 0.0), 0.0)


def solar_noon_hour(ts_day: np.datetime64, lon: float,
                    tz_offset: float = TZ_OFFSET_HOURS) -> float:
    """Hora local (decimal) do meio-dia solar verdadeiro."""
    doy = float(day_of_year(np.array([ts_day], dtype="datetime64[s]"))[0])
    gamma = fractional_year(np.array([doy]))[0]
    eot = float(equation_of_time(np.array([gamma]))[0])
    lstm = 15.0 * tz_offset
    tc_minutes = 4.0 * (lon - lstm) + eot
    return 12.0 - tc_minutes / 60.0


def is_daylight(cz: np.ndarray) -> np.ndarray:
    return np.asarray(cz) > 1e-6


def solar_profile(ts: np.ndarray, lat: float, lon: float) -> dict[str, np.ndarray]:
    """Conjunto de variaveis solares usado pelo estimador e pelas features."""
    cz = cos_zenith(ts, lat, lon)
    ghi = clearsky_ghi(cz)
    return {
        "cos_zenith": cz,
        "ghi_clearsky": ghi,
        "ghi_norm": ghi / STC_IRRADIANCE,
        "extraterrestrial": extraterrestrial(ts, cz),
        "is_day": is_daylight(cz).astype("f8"),
    }
