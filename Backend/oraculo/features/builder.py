# -*- coding: utf-8 -*-
"""Matriz de projeto para os modelos preditivos.

Grupos de variaveis (ver 06-modelos-analiticos.md, secao 6.3):
calendario, Fourier, solar, clima, defasagens e regime.

O nome de cada coluna carrega o grupo como prefixo, o que permite agregar
importancia por grupo sem manter um mapa paralelo.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..config import FOURIER_ORDERS, LAG_HOURS, SUBSYSTEMS, patamar_of_hour
from ..core.calendar_br import holiday_flags, typeday_array
from ..core.timeutils import day_of_week, day_of_year, hour_of_day
from ..models import solar

GROUPS = ("calendario", "fourier", "solar", "clima", "defasagem", "regime")


@dataclass
class FeatureMatrix:
    X: np.ndarray                 # (n, p)
    names: list[str]
    index: np.ndarray             # datetime64[s]
    valid: np.ndarray             # bool: linhas sem NaN nas features
    patamar: np.ndarray           # rotulo do patamar por linha

    @property
    def n(self) -> int:
        return int(self.X.shape[0])

    @property
    def p(self) -> int:
        return int(self.X.shape[1])

    def group_of(self, name: str) -> str:
        return name.split(".", 1)[0] if "." in name else "outro"

    def group_weights(self, coef: np.ndarray) -> list[dict]:
        """Importancia relativa por grupo, a partir dos coeficientes.

        Usa nanstd: as colunas de defasagem tem NaN nas primeiras horas, e
        np.std propagaria NaN para o peso de todos os grupos.
        """
        mag: dict[str, float] = {}
        scale = np.nanstd(self.X, axis=0)
        scale = np.where(np.isfinite(scale) & (scale > 0), scale, 1.0)
        contrib = np.abs(np.asarray(coef, dtype="f8")[: self.p]) * scale
        contrib = np.nan_to_num(contrib, nan=0.0, posinf=0.0, neginf=0.0)
        for name, c in zip(self.names, contrib):
            g = self.group_of(name)
            mag[g] = mag.get(g, 0.0) + float(c)
        total = sum(mag.values()) or 1.0
        out = [{"group": g, "weight": round(v / total, 4)} for g, v in mag.items()]
        out.sort(key=lambda d: -d["weight"])
        return out


# ----------------------------------------------------------------- clima
def synthetic_weather(index: np.ndarray, area: str, seed: int = 7) -> dict[str, np.ndarray]:
    """Proxy determinístico de temperatura e ponto de orvalho.

    Substituivel por ECMWF/GFS/WRF e INMET em producao (ver 10-roadmap.md).
    Aqui a sazonalidade anual e o ciclo diario sao reproduzidos com amplitude
    tipica da regiao, o que basta para exercitar as variaveis climaticas.
    """
    index = np.asarray(index, dtype="datetime64[s]")
    geo = SUBSYSTEMS.get(area, SUBSYSTEMS["SIN"])
    lat = abs(geo["lat"])
    doy = day_of_year(index).astype("f8")
    hod = hour_of_day(index).astype("f8")

    base = 27.0 - 0.28 * (lat - 5.0)                 # mais frio ao sul
    annual = 4.5 * np.cos(2 * np.pi * (doy - 15) / 365.25)   # verao em janeiro
    diurnal = 4.0 * np.sin(2 * np.pi * (hod - 9.0) / 24.0)
    rng = np.random.default_rng(seed + abs(hash(area)) % 9973)
    noise = np.convolve(rng.normal(0.0, 1.1, len(index)),
                        np.ones(6) / 6.0, mode="same")
    temp = base - annual + diurnal + noise
    dew = temp - (5.0 + 2.0 * np.sin(2 * np.pi * doy / 365.25))
    return {"temperature": temp, "dewpoint": dew}


def discomfort_index(temp: np.ndarray, dew: np.ndarray) -> np.ndarray:
    """Indice de desconforto termico (Thom), em graus Celsius."""
    t = np.asarray(temp, dtype="f8")
    d = np.asarray(dew, dtype="f8")
    return 0.4 * (t + d) + 4.8


# ----------------------------------------------------------------- lags
def _lag(v: np.ndarray, k: int) -> np.ndarray:
    out = np.full(len(v), np.nan)
    if k < len(v):
        out[k:] = np.asarray(v, dtype="f8")[:-k] if k else v
    return out


def _rolling_mean(v: np.ndarray, w: int) -> np.ndarray:
    v = np.asarray(v, dtype="f8")
    out = np.full(len(v), np.nan)
    if len(v) < w:
        return out
    csum = np.nancumsum(np.nan_to_num(v, nan=0.0))
    cnt = np.cumsum(np.isfinite(v).astype("f8"))
    out[w - 1:] = (csum[w - 1:] - np.concatenate(([0.0], csum[:-w]))) / np.maximum(
        cnt[w - 1:] - np.concatenate(([0.0], cnt[:-w])), 1.0
    )
    return out


def append_column(fm: FeatureMatrix, name: str, values: np.ndarray) -> FeatureMatrix:
    """Acrescenta uma variavel a matriz de projeto, preservando os metadados."""
    v = np.asarray(values, dtype="f8").reshape(-1, 1)
    if v.shape[0] != fm.X.shape[0]:
        raise ValueError("coluna com %d linhas; matriz tem %d"
                         % (v.shape[0], fm.X.shape[0]))
    X = np.hstack([fm.X, v])
    return FeatureMatrix(X=X, names=list(fm.names) + [name], index=fm.index,
                         valid=fm.valid & np.isfinite(v[:, 0]),
                         patamar=fm.patamar)


def mask_valid(fm: FeatureMatrix, mask: np.ndarray) -> FeatureMatrix:
    """Restringe as linhas consideradas validas, sem reindexar a matriz.

    Preserva o alinhamento temporal (necessario para as defasagens e para o
    corte cronologico) e apenas remove linhas do conjunto de ajuste.
    """
    m = np.asarray(mask, dtype=bool)
    return FeatureMatrix(X=fm.X, names=list(fm.names), index=fm.index,
                         valid=fm.valid & m, patamar=fm.patamar)


# ----------------------------------------------------------------- build
def build(
    index: np.ndarray,
    *,
    area: str,
    target: np.ndarray | None = None,
    mmgd: np.ndarray | None = None,
    ger_eolica: np.ndarray | None = None,
    margem_controlavel: np.ndarray | None = None,
    intercambio: np.ndarray | None = None,
    weather: dict[str, np.ndarray] | None = None,
) -> FeatureMatrix:
    index = np.asarray(index, dtype="datetime64[s]")
    n = len(index)
    geo = SUBSYSTEMS.get(area, SUBSYSTEMS["SIN"])

    hod = hour_of_day(index).astype("f8")
    dow = day_of_week(index).astype("f8")
    doy = day_of_year(index).astype("f8")
    hol, eve = holiday_flags(index)
    kinds = typeday_array(index)

    cols: list[np.ndarray] = []
    names: list[str] = []

    def add(name: str, v: np.ndarray) -> None:
        cols.append(np.asarray(v, dtype="f8"))
        names.append(name)

    # --- calendario
    add("calendario.const", np.ones(n))
    add("calendario.hora", hod / 23.0)
    add("calendario.fim_de_semana", (dow >= 5).astype("f8"))
    add("calendario.feriado", hol)
    add("calendario.vespera_feriado", eve)
    add("calendario.domingo_ou_feriado", (kinds == "domingo_feriado").astype("f8"))
    add("calendario.sabado", (kinds == "sabado").astype("f8"))

    # --- Fourier
    for k in range(1, FOURIER_ORDERS["daily"] + 1):
        add("fourier.dia_sin%d" % k, np.sin(2 * np.pi * k * hod / 24.0))
        add("fourier.dia_cos%d" % k, np.cos(2 * np.pi * k * hod / 24.0))
    for k in range(1, FOURIER_ORDERS["weekly"] + 1):
        add("fourier.sem_sin%d" % k, np.sin(2 * np.pi * k * dow / 7.0))
        add("fourier.sem_cos%d" % k, np.cos(2 * np.pi * k * dow / 7.0))
    for k in range(1, FOURIER_ORDERS["yearly"] + 1):
        add("fourier.ano_sin%d" % k, np.sin(2 * np.pi * k * doy / 365.25))
        add("fourier.ano_cos%d" % k, np.cos(2 * np.pi * k * doy / 365.25))

    # --- solar
    prof = solar.solar_profile(index, geo["lat"], geo["lon"])
    add("solar.cos_zenith", np.maximum(prof["cos_zenith"], 0.0))
    add("solar.ghi_norm", prof["ghi_norm"])
    add("solar.janela_solar", prof["is_day"])
    if mmgd is not None:
        scale = max(float(np.nanmax(mmgd)) if np.isfinite(mmgd).any() else 1.0, 1.0)
        add("solar.mmgd_norm", np.nan_to_num(np.asarray(mmgd, dtype="f8") / scale))

    # --- clima
    w = weather or synthetic_weather(index, area)
    temp, dew = w["temperature"], w["dewpoint"]
    di = discomfort_index(temp, dew)
    add("clima.temperatura", temp / 40.0)
    add("clima.ponto_orvalho", dew / 40.0)
    add("clima.desconforto", di / 40.0)
    for k in (1, 3, 24):
        add("clima.temp_lag%d" % k, np.nan_to_num(_lag(temp, k), nan=float(np.nanmean(temp))) / 40.0)
    add("clima.temp_media72h", np.nan_to_num(_rolling_mean(temp, 72),
                                             nan=float(np.nanmean(temp))) / 40.0)

    # --- defasagens do alvo
    if target is not None:
        y = np.asarray(target, dtype="f8")
        ys = max(float(np.nanmax(np.abs(y))) if np.isfinite(y).any() else 1.0, 1.0)
        for k in LAG_HOURS:
            add("defasagem.y_lag%d" % k, _lag(y, k) / ys)
        add("defasagem.y_media24h", _lag(_rolling_mean(y, 24), 1) / ys)

    # --- regime
    for label, series in (("ger_eolica", ger_eolica),
                          ("margem_controlavel", margem_controlavel),
                          ("intercambio", intercambio)):
        if series is not None:
            v = np.asarray(series, dtype="f8")
            sc = max(float(np.nanmax(np.abs(v))) if np.isfinite(v).any() else 1.0, 1.0)
            add("regime.%s" % label, np.nan_to_num(v / sc))

    X = np.column_stack(cols)
    valid = np.all(np.isfinite(X), axis=1)
    patamar = np.array([patamar_of_hour(int(h)) for h in hod], dtype=object)
    return FeatureMatrix(X=X, names=names, index=index, valid=valid, patamar=patamar)
