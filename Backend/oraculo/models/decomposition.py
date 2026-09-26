# -*- coding: utf-8 -*-
"""Decomposicao da carga e perfis representativos.

    carga_global = carga_supervisionada + mmgd_estimada

`carga_supervisionada` e `val_carga` do balanco de energia -- exatamente a
grandeza que o ONS opera. A identidade e imposta por construcao; o teste
verifica residuo nulo (RF-10).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..core.calendar_br import TYPEDAY_LABELS, TYPEDAYS, typeday_array
from ..core.timeutils import hour_of_day


@dataclass
class Decomposition:
    index: np.ndarray                  # datetime64[s]
    carga_supervisionada: np.ndarray
    mmgd_estimada: np.ndarray
    carga_global: np.ndarray
    area: str

    # ------------------------------------------------------- indicadores
    @property
    def identity_residual_max(self) -> float:
        resid = self.carga_global - (self.carga_supervisionada + self.mmgd_estimada)
        finite = resid[np.isfinite(resid)]
        return float(np.max(np.abs(finite))) if len(finite) else 0.0

    @property
    def mmgd_share(self) -> np.ndarray:
        with np.errstate(divide="ignore", invalid="ignore"):
            return np.where(self.carga_global > 0,
                            self.mmgd_estimada / self.carga_global, np.nan)

    def peak_share(self) -> tuple[float, str]:
        share = self.mmgd_share
        if not np.isfinite(share).any():
            return 0.0, ""
        i = int(np.nanargmax(share))
        return float(share[i]), str(self.index[i])

    def min_supervised(self) -> tuple[float, str]:
        v = self.carga_supervisionada
        if not np.isfinite(v).any():
            return 0.0, ""
        i = int(np.nanargmin(v))
        return float(v[i]), str(self.index[i])

    def max_supervised(self) -> tuple[float, str]:
        v = self.carga_supervisionada
        if not np.isfinite(v).any():
            return 0.0, ""
        i = int(np.nanargmax(v))
        return float(v[i]), str(self.index[i])

    def max_ramp(self) -> tuple[float, str]:
        """Maior rampa horaria de subida da carga supervisionada, em MW/h."""
        v = self.carga_supervisionada
        if len(v) < 2:
            return 0.0, ""
        d = np.diff(v)
        if not np.isfinite(d).any():
            return 0.0, ""
        i = int(np.nanargmax(d))
        return float(d[i]), str(self.index[i + 1])

    def daily_amplitude(self) -> float:
        mn, _ = self.min_supervised()
        mx, _ = self.max_supervised()
        return float(mx - mn)

    def to_dict(self) -> dict:
        share, share_at = self.peak_share()
        mn, mn_at = self.min_supervised()
        mx, mx_at = self.max_supervised()
        ramp, ramp_at = self.max_ramp()
        return {
            "area": self.area,
            "identity_residual_max": self.identity_residual_max,
            "mmgd_share_peak": round(share, 4),
            "mmgd_share_peak_at": share_at,
            "min_supervised_mw": round(mn, 1),
            "min_supervised_at": mn_at,
            "max_supervised_mw": round(mx, 1),
            "max_supervised_at": mx_at,
            "daily_amplitude_mw": round(self.daily_amplitude(), 1),
            "max_ramp_mw_h": round(ramp, 1),
            "max_ramp_at": ramp_at,
            "mmgd_energy_mwh": round(float(np.nansum(self.mmgd_estimada)), 1),
        }


def decompose(index: np.ndarray, supervised: np.ndarray,
              mmgd: np.ndarray, area: str) -> Decomposition:
    supervised = np.asarray(supervised, dtype="f8")
    mmgd = np.asarray(mmgd, dtype="f8")
    return Decomposition(
        index=np.asarray(index, dtype="datetime64[s]"),
        carga_supervisionada=supervised,
        mmgd_estimada=mmgd,
        carga_global=supervised + mmgd,
        area=area,
    )


# --------------------------------------------------------- perfis (Eixo 1)
def typeday_profiles(index: np.ndarray, supervised: np.ndarray,
                     mmgd: np.ndarray) -> list[dict]:
    """Perfis representativos por dia-tipo e hora, com quantis e amostragem.

    Insumo do Eixo 1: caracterizacao de perfis de consumo e da presenca de
    geracao distribuida.
    """
    index = np.asarray(index, dtype="datetime64[s]")
    hod = hour_of_day(index)
    kinds = typeday_array(index)
    out: list[dict] = []
    for kind in TYPEDAYS:
        sel_kind = kinds == kind
        p10, p50, p90, m50, samples = [], [], [], [], []
        for h in range(24):
            sel = sel_kind & (hod == h)
            v = np.asarray(supervised, dtype="f8")[sel]
            g = np.asarray(mmgd, dtype="f8")[sel]
            v = v[np.isfinite(v)]
            g = g[np.isfinite(g)]
            if len(v):
                p10.append(round(float(np.percentile(v, 10)), 1))
                p50.append(round(float(np.percentile(v, 50)), 1))
                p90.append(round(float(np.percentile(v, 90)), 1))
            else:
                p10.append(None); p50.append(None); p90.append(None)
            m50.append(round(float(np.percentile(g, 50)), 1) if len(g) else None)
            samples.append(int(len(v)))
        out.append({
            "kind": kind,
            "label": TYPEDAY_LABELS[kind],
            "hours": list(range(24)),
            "carga_p10": p10,
            "carga_p50": p50,
            "carga_p90": p90,
            "mmgd_p50": m50,
            "samples": samples,
        })
    return out


def clm_inputs(dec: Decomposition) -> dict:
    """Parametros agregados propostos como insumo a modelos equivalentes.

    Nao sao parametros do Composite Load Model prontos para simulacao: sao
    grandezas observadas que qualificam a parametrizacao feita pelos
    especialistas do ONS.
    """
    sup = dec.carga_supervisionada
    finite = sup[np.isfinite(sup)]
    if not len(finite):
        return {}
    mn, _ = dec.min_supervised()
    mx, _ = dec.max_supervised()
    ramp, _ = dec.max_ramp()
    share, _ = dec.peak_share()
    cz_night = dec.mmgd_estimada == 0.0
    night_anchor = float(np.nanmean(sup[cz_night])) if cz_night.any() else float("nan")
    return {
        "load_factor": round(float(np.nanmean(finite) / mx), 4) if mx else None,
        "solar_penetration_peak": round(share, 4),
        "night_anchor_mw": None if np.isnan(night_anchor) else round(night_anchor, 1),
        "min_supervised_mw": round(mn, 1),
        "max_supervised_mw": round(mx, 1),
        "ramp_max_mw_h": round(ramp, 1),
        "amplitude_mw": round(mx - mn, 1),
        "samples": int(len(finite)),
    }
