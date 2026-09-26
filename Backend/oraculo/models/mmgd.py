# -*- coding: utf-8 -*-
"""Estimador de MMGD.

O Portal de Dados Abertos nao publica a MMGD como serie horaria por area. Ela
aparece apenas implicitamente, como reducao da carga verificada. Estima-la e o
nucleo do produto.

    MMGD_est(t) = C * PR * (GHI_ceu_claro(t) / 1000) * k_nuvem(t)

onde C e a capacidade instalada declarada na area, PR o performance ratio
agregado e k_nuvem o fator de nebulosidade.

Tres metodos de obtencao de k_nuvem:

  "envelope"        (padrao, com dado real) -- compara cada hora com o percentil
                    90 da mesma hora em dias semelhantes do mes. Dias de maior
                    carga observada sao dias de menor geracao distribuida, logo
                    o envelope aproxima a carga global. O deficit observado e
                    atribuido a MMGD.

  "ancora_noturna"  -- ajusta um modelo de carga usando apenas horas sem sol e
                    extrapola para o dia. Mantido como diagnostico: a
                    extrapolacao do dia a partir da noite e mal condicionada,
                    porque os harmonicos diarios sao identificados fora do
                    suporte.

  "proxy"           -- fator pseudoaleatorio suavizado, deterministico, para o
                    modo demonstrativo sem rede.

VIES CONHECIDO E DECLARADO: mesmo os dias de maior carga contem alguma geracao
distribuida. Portanto o envelope subestima a carga global e a estimativa de MMGD
e CONSERVADORA -- um piso, nao um valor central. Ver 08-limitacoes.md.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..config import (MMGD_CLOUD_FACTOR_MAX, MMGD_CLOUD_FACTOR_MIN,
                      MMGD_PERFORMANCE_RATIO, RANDOM_SEED, SUBSYSTEMS,
                      capacity_of)
from ..core.calendar_br import holiday_flags, typeday_array
from ..core.timeutils import day_of_week, hour_of_day
from . import solar

ENVELOPE_PERCENTILE = 90.0
ENVELOPE_MIN_SAMPLES = 3
DAY_THRESHOLD = 0.02           # ghi_norm minimo para considerar hora diurna


@dataclass
class MMGDEstimate:
    mmgd_mw: np.ndarray          # MWmed estimados
    cloud_factor: np.ndarray     # fator de nebulosidade em [min, max]
    ghi_norm: np.ndarray         # irradiancia de ceu claro normalizada
    cos_zenith: np.ndarray
    capacity_mwp: float
    performance_ratio: float
    method: str
    envelope: np.ndarray | None = None      # carga global aproximada
    deficit: np.ndarray | None = None       # envelope - carga observada

    @property
    def potential_mw(self) -> np.ndarray:
        """Geracao se o ceu estivesse limpo."""
        return self.capacity_mwp * self.performance_ratio * self.ghi_norm

    @property
    def is_day(self) -> np.ndarray:
        return self.ghi_norm > DAY_THRESHOLD

    def summary(self) -> dict:
        day = self.is_day
        night = ~day
        return {
            "method": self.method,
            "capacity_mwp": round(self.capacity_mwp, 1),
            "performance_ratio": self.performance_ratio,
            "peak_mw": round(float(np.nanmax(self.mmgd_mw)), 1) if len(self.mmgd_mw) else 0.0,
            "energy_gwh": round(float(np.nansum(self.mmgd_mw)) / 1000.0, 1),
            "capacity_factor": (
                round(float(np.nansum(self.mmgd_mw)) /
                      (self.capacity_mwp * len(self.mmgd_mw)), 4)
                if len(self.mmgd_mw) and self.capacity_mwp else None
            ),
            "mean_cloud_factor_day": (
                round(float(np.nanmean(self.cloud_factor[day])), 3) if day.any() else None
            ),
            "night_is_zero": bool(np.all(self.mmgd_mw[night] == 0.0)) if night.any() else True,
            "bias_note": (
                "Estimativa conservadora: o envelope contém alguma geração "
                "distribuída, portanto o valor é um piso."
                if self.method == "envelope" else
                "Valor demonstrativo, sem calibração por dado observado."
                if self.method == "proxy" else
                "Extrapolação do dia a partir da noite é mal condicionada."
            ),
        }


# ------------------------------------------------------ metodo do envelope
def load_envelope(ts: np.ndarray, load: np.ndarray,
                  percentile: float = ENVELOPE_PERCENTILE) -> np.ndarray:
    """Percentil alto da carga por (mes, dia-tipo, hora).

    Aproxima a carga global: nas horas comparaveis, a maior carga observada
    corresponde ao dia de menor geracao distribuida.
    """
    ts = np.asarray(ts, dtype="datetime64[s]")
    load = np.asarray(load, dtype="f8")
    month = ts.astype("datetime64[M]").astype("i8") % 12
    hod = hour_of_day(ts)
    kinds = typeday_array(ts)

    env = np.full(len(ts), np.nan)
    for m in np.unique(month):
        for k in set(kinds.tolist()):
            base = (month == m) & (kinds == k)
            if not base.any():
                continue
            for h in range(24):
                sel = base & (hod == h)
                if not sel.any():
                    continue
                v = load[sel]
                v = v[np.isfinite(v)]
                if len(v) >= ENVELOPE_MIN_SAMPLES:
                    env[sel] = np.percentile(v, percentile)
                elif len(v):
                    env[sel] = float(np.max(v))
    # Lacunas: cai para o percentil por (dia-tipo, hora), depois por hora.
    if np.isnan(env).any():
        for h in range(24):
            sel = (hod == h) & np.isnan(env)
            if sel.any():
                v = load[hod == h]
                v = v[np.isfinite(v)]
                if len(v):
                    env[sel] = np.percentile(v, percentile)
    return env


# ------------------------------------------------------ ancoragem noturna
def _design_matrix(ts: np.ndarray) -> np.ndarray:
    hod = hour_of_day(ts).astype("f8")
    dow = day_of_week(ts).astype("f8")
    doy = ts.astype("datetime64[D]").astype("i8").astype("f8")
    hol, eve = holiday_flags(ts)
    cols = [np.ones(len(ts))]
    for k in (1, 2, 3):
        cols.append(np.sin(2 * np.pi * k * hod / 24.0))
        cols.append(np.cos(2 * np.pi * k * hod / 24.0))
    for k in (1, 2):
        cols.append(np.sin(2 * np.pi * k * dow / 7.0))
        cols.append(np.cos(2 * np.pi * k * dow / 7.0))
    cols.append(np.sin(2 * np.pi * doy / 365.25))
    cols.append(np.cos(2 * np.pi * doy / 365.25))
    cols.append(doy - doy.mean())
    cols.append(hol)
    cols.append(eve)
    return np.column_stack(cols)


def anchored_load(ts: np.ndarray, load: np.ndarray,
                  cz: np.ndarray) -> tuple[np.ndarray, int]:
    """Carga contrafactual sem efeito solar, ajustada nas horas sem sol."""
    X = _design_matrix(ts)
    night = (cz <= 1e-6) & np.isfinite(load)
    n = int(night.sum())
    if n < X.shape[1] + 10:
        return np.array(load, dtype="f8"), n
    Xn, yn = X[night], np.asarray(load, dtype="f8")[night]
    lam = 1e-6 * float(np.trace(Xn.T @ Xn)) / X.shape[1]
    beta = np.linalg.solve(Xn.T @ Xn + lam * np.eye(X.shape[1]), Xn.T @ yn)
    return X @ beta, n


# ------------------------------------------------------------ estimador
def estimate(
    ts: np.ndarray,
    load_supervised: np.ndarray | None,
    area: str,
    *,
    method: str = "auto",
    capacity_mwp: float | None = None,
    performance_ratio: float = MMGD_PERFORMANCE_RATIO,
) -> MMGDEstimate:
    """Estima a geracao de MMGD na area.

    method: "auto" | "envelope" | "ancora_noturna" | "proxy".
    "auto" usa "envelope" quando ha carga valida suficiente.
    """
    ts = np.asarray(ts, dtype="datetime64[s]")
    geo = SUBSYSTEMS.get(area, SUBSYSTEMS["SIN"])
    cap = capacity_of(area) if capacity_mwp is None else float(capacity_mwp)

    prof = solar.solar_profile(ts, geo["lat"], geo["lon"])
    cz, ghi_norm = prof["cos_zenith"], prof["ghi_norm"]
    potential = cap * performance_ratio * ghi_norm
    day = ghi_norm > DAY_THRESHOLD

    have_load = (
        load_supervised is not None
        and np.isfinite(np.asarray(load_supervised, dtype="f8")).sum() > 24 * 30
    )
    chosen = method
    if method == "auto":
        chosen = "envelope" if have_load else "proxy"
    if chosen in ("envelope", "ancora_noturna") and not have_load:
        chosen = "proxy"

    env = None
    deficit = None
    if chosen == "envelope":
        load = np.asarray(load_supervised, dtype="f8")
        env = load_envelope(ts, load)
        deficit = env - load
        with np.errstate(divide="ignore", invalid="ignore"):
            k = np.where(potential > 1.0, deficit / potential, np.nan)
        k = _fill_and_smooth(k)
    elif chosen == "ancora_noturna":
        load = np.asarray(load_supervised, dtype="f8")
        env, _ = anchored_load(ts, load, cz)
        deficit = env - load
        with np.errstate(divide="ignore", invalid="ignore"):
            k = np.where(potential > 1.0, deficit / potential, np.nan)
        k = _fill_and_smooth(k)
    else:
        k = _proxy_cloud(ts, area)

    mmgd = np.where(day, potential * k, 0.0)
    mmgd = np.clip(mmgd, 0.0, cap * performance_ratio)

    return MMGDEstimate(
        mmgd_mw=mmgd,
        cloud_factor=np.where(day, k, 0.0),
        ghi_norm=ghi_norm,
        cos_zenith=cz,
        capacity_mwp=cap,
        performance_ratio=performance_ratio,
        method=chosen,
        envelope=env,
        deficit=deficit,
    )


def implied_capacity(est: MMGDEstimate) -> float | None:
    """Capacidade implicada pelo deficit observado, em MWp.

    Serve de conferencia cruzada contra a capacidade declarada: uma razao muito
    acima de 1 sugere cadastro defasado (ver triangulacao).
    """
    if est.deficit is None:
        return None
    day = est.is_day & np.isfinite(est.deficit) & (est.ghi_norm > 0.3)
    if not day.any():
        return None
    ratio = est.deficit[day] / (est.ghi_norm[day] * est.performance_ratio)
    ratio = ratio[np.isfinite(ratio) & (ratio > 0)]
    if not len(ratio):
        return None
    return float(np.percentile(ratio, 90))


def _fill_and_smooth(k: np.ndarray, window: int = 3) -> np.ndarray:
    out = np.array(k, dtype="f8")
    idx = np.arange(len(out))
    good = np.isfinite(out)
    if good.sum() == 0:
        return np.full_like(out, 0.55)
    out = np.interp(idx, idx[good], out[good])
    if window > 1:
        out = np.convolve(out, np.ones(window) / window, mode="same")
    return np.clip(out, MMGD_CLOUD_FACTOR_MIN, MMGD_CLOUD_FACTOR_MAX)


def _proxy_cloud(ts: np.ndarray, area: str) -> np.ndarray:
    """Fator de nebulosidade deterministico para o modo demonstrativo."""
    days = ts.astype("datetime64[D]").astype("i8")
    seed = (RANDOM_SEED + abs(hash(area)) % 9973) % (2**31)
    rng = np.random.default_rng(seed)
    uniq = np.unique(days)
    per_day = 0.45 + 0.45 * rng.random(len(uniq))
    lut = {int(d): float(v) for d, v in zip(uniq, per_day)}
    base = np.array([lut[int(d)] for d in days])
    hod = hour_of_day(ts).astype("f8")
    intra = 1.0 + 0.06 * np.sin(2 * np.pi * hod / 24.0 + seed % 7)
    return np.clip(base * intra, MMGD_CLOUD_FACTOR_MIN, MMGD_CLOUD_FACTOR_MAX)
