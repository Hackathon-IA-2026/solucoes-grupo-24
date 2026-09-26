# -*- coding: utf-8 -*-
"""Curva do pato prevista: radiacao prevista x onde esta a MMGD.

    MMGD por municipio (cadastro ANEEL)  -> celulas de ~2,5 graus, por subsistema
    radiacao + temperatura previstas     -> geracao da MMGD por hora e celula
    (ECMWF AIFS / IFS, GFS)
    PR calibrado com ERA5                -> nivel = MMGD media oficial do PLAN
    dia-tipo + sensibilidades            -> carga supervisionada prevista:

        sup(d) = sup_tipo(d) - beta * [MMGD(d) - MMGD_tipo] + gama * [T(d) - T_tipo]

beta e gama sao estimados por subsistema, com dados do ONS, numa janela de
TREINO anterior ao teste. A temperatura entra porque o tempo mexe nos dois
lados: dia de sol aumenta a MMGD, mas tambem aquece e aumenta a carga de
refrigeracao. Sem controlar a temperatura, a sensibilidade estimada a MMGD
cai para perto de zero (fator de confusao); com ela, beta volta a ~0,8 no
Sudeste e a temperatura responde por ~940 MW por grau.

A carga supervisionada e a que o ONS enxerga; a barriga da curva do pato e o
seu minimo do meio-dia. A MMGD e a parcela da curva mais sensivel ao tempo:
um dia nublado no Sudeste "devolve" gigawatts de carga a rede ao meio-dia.

Modelo fotovoltaico, por celula:

    P = C * PR * G/1000 * (1 - 0,004 * (T + 0,03 G - 25))

G e a radiacao global horizontal (W/m2), T a temperatura do ar; o termo
0,03 G aproxima a temperatura de celula. PR (performance ratio efetivo) e
calibrado por subsistema para que a MMGD reconstruida com ERA5 na janela de
referencia reproduza a MMGD media oficial do PLAN 2026-2030.

Alinhamento temporal: a radiacao do Open-Meteo e a media da hora ANTERIOR ao
rotulo; o balanco do ONS rotula a hora pelo inicio. A hora h do ONS recebe o
valor rotulado h+1 (verificado no backtest).
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date

import numpy as np

from .. import config
from ..core import calendar_br
from ..fronteira.fontes import uf_of_mun

UF_SS = {
    **{u: "SE" for u in ("SP", "RJ", "MG", "ES", "GO", "DF", "MT", "MS", "AC", "RO")},
    **{u: "S" for u in ("PR", "SC", "RS")},
    **{u: "NE" for u in ("BA", "SE", "AL", "PE", "PB", "RN", "CE", "PI")},
    **{u: "N" for u in ("PA", "TO", "MA", "AP", "AM", "RR")},
}
SUBS = ("SE", "S", "NE", "N")
GAMMA = -0.004
SHIFT = 1


# ------------------------------------------------------------ espaco
def clusters(mun: dict, centroid: dict, cell_deg: float = 2.5,
             min_mw: float = 20.0) -> list[dict]:
    """Celulas de MMGD por subsistema, com centroide ponderado pela potencia."""
    cells: dict[tuple, dict] = {}
    for code, g in mun.items():
        c = centroid.get(code)
        ss = UF_SS.get(uf_of_mun(code))
        if not c or not ss or g.get("kw", 0) <= 0:
            continue
        la, lo = c
        key = (ss, int(np.floor(la / cell_deg)), int(np.floor(lo / cell_deg)))
        a = cells.setdefault(key, {"ss": ss, "kw": 0.0, "wla": 0.0, "wlo": 0.0, "n": 0})
        a["kw"] += g["kw"]
        a["wla"] += la * g["kw"]
        a["wlo"] += lo * g["kw"]
        a["n"] += 1
    pts = [{"ss": a["ss"], "mw": a["kw"] / 1000.0, "lat": a["wla"] / a["kw"],
            "lon": a["wlo"] / a["kw"], "mun": a["n"]} for a in cells.values()]
    keep = [p for p in pts if p["mw"] >= min_mw]
    for p in pts:                                    # celulas pequenas -> vizinha
        if p["mw"] >= min_mw:
            continue
        same = [q for q in keep if q["ss"] == p["ss"]] or keep
        q = min(same, key=lambda q: (q["lat"] - p["lat"]) ** 2 + (q["lon"] - p["lon"]) ** 2)
        q["mw"] += p["mw"]
        q["mun"] += p["mun"]
    return sorted(keep, key=lambda p: (p["ss"], -p["mw"]))


# ------------------------------------------------------------ fotovoltaico
def pv_mw(ghi: np.ndarray, temp: np.ndarray, cap_mw: np.ndarray,
          pr: np.ndarray) -> np.ndarray:
    """ghi, temp: [pontos x horas]; cap, pr: [pontos]. Devolve MW [pontos x horas]."""
    g = np.nan_to_num(np.asarray(ghi, float))
    t = np.nan_to_num(np.asarray(temp, float), nan=25.0)
    derate = 1.0 + GAMMA * (t + 0.03 * g - 25.0)
    return cap_mw[:, None] * pr[:, None] * g / 1000.0 * np.clip(derate, 0.5, 1.2)


def to_daily(times: list[str], series: np.ndarray, shift: int = SHIFT) -> dict:
    """Serie horaria (rotulo Open-Meteo) -> {dia: array(24)} no rotulo do ONS."""
    out: dict[str, np.ndarray] = {}
    for i, ts in enumerate(times):
        j = i + shift
        if j >= len(times) or j < 0:
            continue
        d, h = ts[:10], int(ts[11:13])
        out.setdefault(d, np.full(24, np.nan))[h] = series[j]
    return out


def mmgd_by_ss(weather: dict, model: str, pts: list[dict], pr_ss: dict,
               shift: int = SHIFT) -> dict[str, dict]:
    """{ss: {dia: array(24) MW}} a partir do tempo de um modelo."""
    w = weather[model]
    ghi = np.array([[np.nan if v is None else v for v in row]
                    for row in w["shortwave_radiation"]], float)
    tmp = np.array([[np.nan if v is None else v for v in row]
                    for row in w["temperature_2m"]], float)
    cap = np.array([p["mw"] for p in pts])
    pr = np.array([pr_ss.get(p["ss"], 0.75) for p in pts])
    mw = pv_mw(ghi, tmp, cap, pr)
    out = {}
    for ss in SUBS:
        sel = np.array([p["ss"] == ss for p in pts])
        if sel.any():
            out[ss] = to_daily(weather["time"], mw[sel].sum(axis=0), shift)
    return out


def calibrate_pr(era: dict, pts: list[dict], target_mwmed: dict,
                 days: set[str]) -> dict:
    """PR por subsistema: MMGD(ERA5, PR=1) media na janela -> alvo oficial."""
    raw = mmgd_by_ss(era, "_", pts, {ss: 1.0 for ss in SUBS})
    pr = {}
    for ss in SUBS:
        vals = [a for d, a in raw.get(ss, {}).items() if d in days]
        mean = float(np.nanmean(np.array(vals))) if vals else 0.0
        pr[ss] = round(target_mwmed[ss] / mean, 4) if mean > 0 and target_mwmed.get(ss) else 0.75
    return pr


# ------------------------------------------------------------ carga
def temp_by_ss(weather: dict, model: str, pts: list[dict], shift: int = SHIFT) -> dict:
    """Temperatura media ponderada pela MMGD (proxy de onde esta a carga urbana)."""
    T = np.array([[np.nan if v is None else v for v in row]
                  for row in weather[model]["temperature_2m"]], float)
    out = {}
    for ss in SUBS:
        sel = np.array([p["ss"] == ss for p in pts])
        if not sel.any():
            continue
        w = np.array([p["mw"] for p in pts])[sel]
        out[ss] = to_daily(weather["time"], (T[sel] * w[:, None]).sum(axis=0) / w.sum(),
                           shift)
    return out


def fit_sensitivity(sup: dict, mm: dict, temp: dict, train: list[str],
                    hours=range(6, 21)) -> dict:
    """beta (MW de carga por MW de MMGD) e gama (MW por grau), por subsistema."""
    out = {}
    for ss in SUBS:
        rows = []
        for d in train:
            ok = (_is_regular(d) and d in sup.get(ss, {}) and d in mm.get(ss, {})
                  and d in temp.get(ss, {}))
            if not ok:
                continue
            last = _prev(d)
            ps = same_weekday_mean(sup[ss], d, last)
            pm = same_weekday_mean(mm[ss], d, last)
            pt = same_weekday_mean(temp[ss], d, last)
            if ps is None or pm is None or pt is None:
                continue
            for h in hours:
                r = (sup[ss][d][h] - ps[h], mm[ss][d][h] - pm[h], temp[ss][d][h] - pt[h])
                if np.isfinite(r).all():
                    rows.append(r)
        if len(rows) < 50:
            out[ss] = {"beta": 1.0, "gamma": 0.0, "r2": None, "r2_mmgd_only": None, "n": 0}
            continue
        A = np.array(rows)
        y, X = A[:, 0], A[:, 1:]
        coef, *_ = np.linalg.lstsq(X, y, rcond=None)
        r2 = 1 - ((y - X @ coef) ** 2).sum() / ((y - y.mean()) ** 2).sum()
        c1, *_ = np.linalg.lstsq(X[:, :1], y, rcond=None)
        r2m = 1 - ((y - X[:, :1] @ c1) ** 2).sum() / ((y - y.mean()) ** 2).sum()
        out[ss] = {"beta": round(float(-coef[0]), 4), "gamma": round(float(coef[1]), 1),
                   "r2": round(float(r2), 4), "r2_mmgd_only": round(float(r2m), 4),
                   "n": len(y)}
    return out


def forecast_sup(sup_ss: dict, mm_hist: dict, t_hist: dict, mm_d: np.ndarray,
                 t_d: np.ndarray, d: str, last_obs: str, sens: dict) -> np.ndarray | None:
    """Carga supervisionada prevista para o dia d."""
    ps = same_weekday_mean(sup_ss, d, last_obs)
    pm = same_weekday_mean(mm_hist, d, last_obs)
    pt = same_weekday_mean(t_hist, d, last_obs)
    if ps is None or pm is None or pt is None:
        return None
    return ps - sens["beta"] * (mm_d - pm) + sens["gamma"] * (t_d - pt)


def _prev(d: str) -> str:
    return str(np.datetime64(d) - np.timedelta64(1, "D"))


def _is_regular(d: str) -> bool:
    y, m, dd = int(d[:4]), int(d[5:7]), int(d[8:10])
    return not calendar_br.is_holiday(date(y, m, dd))


def same_weekday_mean(series: dict, d: str, last_obs: str, n: int = 2) -> np.ndarray | None:
    """Media das `n` ultimas ocorrencias do mesmo dia da semana ja observadas."""
    base = np.datetime64(d)
    got = []
    k = 1
    while len(got) < n and k <= 8:
        prev = str(base - np.timedelta64(7 * k, "D"))
        if prev <= last_obs and prev in series and _is_regular(prev):
            got.append(series[prev])
        k += 1
    if not got:
        return None
    return np.nanmean(np.array(got), axis=0)


# ------------------------------------------------------------ metricas
BELLY = slice(10, 16)        # a barriga do pato: 10h a 15h


def day_metrics(fc: np.ndarray, obs: np.ndarray) -> dict:
    mid = slice(9, 17)
    err = fc - obs
    fmin, omin = float(np.nanmin(fc[BELLY])), float(np.nanmin(obs[BELLY]))
    framp = float(np.nanmax(fc[17:22]) - fmin)
    oramp = float(np.nanmax(obs[17:22]) - omin)
    return {"mae_mid": float(np.nanmean(np.abs(err[mid]))),
            "mae_day": float(np.nanmean(np.abs(err))),
            "err_min": fmin - omin, "err_ramp": framp - oramp,
            "obs_min": omin, "obs_ramp": oramp}


def summarize(rows: list[dict]) -> dict:
    if not rows:
        return {}
    a = lambda k: np.array([r[k] for r in rows], float)  # noqa: E731
    return {"days": len(rows),
            "mae_mid_mw": round(float(np.mean(a("mae_mid"))), 0),
            "mae_day_mw": round(float(np.mean(a("mae_day"))), 0),
            "mae_min_mw": round(float(np.mean(np.abs(a("err_min")))), 0),
            "bias_min_mw": round(float(np.mean(a("err_min"))), 0),
            "mae_ramp_mw": round(float(np.mean(np.abs(a("err_ramp")))), 0),
            "mape_mid": round(float(np.mean(a("mae_mid") / np.maximum(a("obs_min"), 1))), 4)}


def backtest(sup: dict, mm_era: dict, t_era: dict, methods: dict, sens: dict,
             days: list[str]) -> dict:
    """Carga supervisionada prevista x observada, por subsistema e SIN.

    `methods`: {nome: (mmgd {ss: {dia: array}}, temperatura {ss: {dia: array}})}.
    O historico do dia-tipo usa sempre ERA5 (o passado ja aconteceu); o dia
    previsto usa o tempo de cada metodo. A persistencia nao usa tempo nenhum.
    "ERA5 (tempo perfeito)" e o teto: o erro que sobra nao e do tempo.
    """
    allm = dict(methods)
    allm["ERA5 (tempo perfeito)"] = (mm_era, t_era)
    out: dict[str, dict] = {}
    series: dict[str, dict] = defaultdict(dict)
    for ss in list(SUBS) + ["SIN"]:
        per: dict[str, list] = defaultdict(list)
        subs = SUBS if ss == "SIN" else (ss,)
        for d in days:
            if not _is_regular(d) or any(d not in sup[s] for s in subs):
                continue
            last = _prev(d)
            obs = sum(sup[s][d] for s in subs)
            pers = [same_weekday_mean(sup[s], d, last) for s in subs]
            if any(x is None for x in pers) or not np.isfinite(obs).all():
                continue
            pers = sum(pers)
            per["persistência"].append(day_metrics(pers, obs))
            if ss == "SIN":
                series["observado"][d] = obs
                series["persistência"][d] = pers
            for name, (mm, tt) in allm.items():
                fcs = []
                for s in subs:
                    f = None
                    if d in mm.get(s, {}) and d in tt.get(s, {}):
                        f = forecast_sup(sup[s], mm_era[s], t_era[s], mm[s][d], tt[s][d],
                                         d, last, sens[s])
                    if f is None:
                        fcs = []
                        break
                    fcs.append(f)
                if not fcs:
                    continue
                fc = sum(fcs)
                if not np.isfinite(fc).all():
                    continue
                per[name].append(day_metrics(fc, obs))
                if ss == "SIN":
                    series[name][d] = fc
        out[ss] = {m: summarize(v) for m, v in per.items() if v}
    return {"metrics": out, "series_sin": series}
