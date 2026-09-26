# -*- coding: utf-8 -*-
"""Projecao do corte por razao energetica e do BESS que ele justifica.

Por que um modelo fisico e nao uma extrapolacao da serie. O corte ENE cresceu
em saltos nos ultimos dois anos; uma tendencia ajustada a isso projeta o
proprio salto para sempre. O que o gera, porem, e mensuravel hora a hora: a
carga liquida que sobra para a geracao controlavel.

    carga liquida  NL(t) = carga supervisionada(t) - [eolica + solar](t) POTENCIAIS

(potencial = verificada + cortada; sem somar o corte de volta, o modelo seria
circular -- o corte reduz a geracao verificada e "eleva" a carga liquida).
Quando NL cai abaixo do piso que o sistema absorve -- inflexibilidade
hidraulica e termica, limites de exportacao --, a sobra vira corte:

    corte_ENE+SIS(t) = alfa * max(0, teta_mes - NL(t))

teta tem um valor por mes do ano (a inflexibilidade hidraulica e sazonal) e
alfa mede quanto do excedente vira corte apurado (o resto e acomodado de outra
forma). Ajuste por minimos quadrados em grade; backtest fora da amostra.

Projecao: sobre o ano de referencia observado (mesmo clima, mesmo perfil),
cresce-se a geracao centralizada, a MMGD e a carga:

    NL_k(t) = [(sup + mmgd)(1+g_carga)^k - mmgd (1+g_mmgd)^k] - VRE (1+g_vre)^k
    teta_k  = teta - flex * k

O corte ENE+SIS e SISTEMICO: um armazenamento em qualquer ponto do SIN o
absorve. Por isso o BESS justificavel e dimensionado no nivel do SIN, pelo
mesmo criterio de ciclo marginal da secao de alocacao.
"""
from __future__ import annotations

import numpy as np

from .. import config
from ..bess import analise as BA

E = config.ENE


# ------------------------------------------------------------ dados
def assemble(days: list[str], bal: dict, hour_es: dict, hour_all: dict,
             mmgd: dict | None = None) -> dict:
    """Matrizes dia x 24 alinhadas: carga, VRE potencial, corte, MMGD."""
    keep = [d for d in days if d in bal]
    sup = np.array([bal[d]["sup"] for d in keep])
    vre_obs = np.array([np.nan_to_num(bal[d]["eol"]) + np.nan_to_num(bal[d]["sol"])
                        for d in keep])
    cut_all = np.array([hour_all.get(d, np.zeros(24)) for d in keep])
    es = np.array([hour_es.get(d, np.zeros(24)) for d in keep])
    mm = np.array([(mmgd or {}).get(d, np.zeros(24)) for d in keep]) if mmgd else None
    vre_pot = vre_obs + cut_all
    month = np.array([int(d[5:7]) for d in keep])
    ok = np.isfinite(sup).all(axis=1)
    return {"days": [d for d, o in zip(keep, ok) if o], "sup": sup[ok],
            "vre_pot": vre_pot[ok], "vre_obs": vre_obs[ok], "cut_all": cut_all[ok],
            "es": es[ok], "month": month[ok],
            "mmgd": mm[ok] if mm is not None else None}


# ------------------------------------------------------------ ajuste
def fit(X: dict, mask: np.ndarray | None = None) -> dict:
    """alfa e teta_mes por minimos quadrados em grade."""
    m = np.ones(len(X["days"]), bool) if mask is None else mask
    NL = (X["sup"] - X["vre_pot"])[m]
    y = X["es"][m]
    mon = X["month"][m]
    lo, hi = np.nanpercentile(NL, 0.5), np.nanpercentile(NL, 60)
    thetas = np.linspace(lo, hi, 160)
    best = None
    for a in np.arange(0.2, 1.21, 0.05):
        th, sse = {}, 0.0
        for mm in range(1, 13):
            sel = mon == mm
            if not sel.any():
                continue
            nl, yy = NL[sel].ravel(), y[sel].ravel()
            pred = a * np.maximum(0.0, thetas[:, None] - nl[None, :])
            err = ((pred - yy[None, :]) ** 2).sum(axis=1)
            k = int(err.argmin())
            th[mm] = float(thetas[k])
            sse += float(err[k])
        if best is None or sse < best["sse"]:
            best = {"alpha": round(float(a), 3), "theta": th, "sse": sse}
    # meses sem dado no ajuste: media dos vizinhos (nao deveria ocorrer na janela)
    for mm in range(1, 13):
        if mm not in best["theta"]:
            vals = [best["theta"][k] for k in best["theta"]]
            best["theta"][mm] = float(np.mean(vals)) if vals else 0.0
    return best


def predict(params: dict, NL: np.ndarray, month: np.ndarray,
            flex_mw: float = 0.0) -> np.ndarray:
    th = np.array([params["theta"][int(m)] for m in month])[:, None] - flex_mw
    return params["alpha"] * np.maximum(0.0, th - NL)


def monthly_totals(days: list[str], hourly: np.ndarray) -> dict[str, float]:
    out: dict[str, float] = {}
    for d, row in zip(days, hourly):
        out[d[:7]] = out.get(d[:7], 0.0) + float(np.nansum(row))
    return {k: v / 1e6 for k, v in sorted(out.items())}            # TWh


def backtest(X: dict, split: str) -> dict:
    """Ajuste antes de `split` (AAAA-MM), teste depois; compara com ingenuo."""
    ym = np.array([d[:7] for d in X["days"]])
    tr, te = ym < split, ym >= split
    params = fit(X, tr)
    NL = X["sup"] - X["vre_pot"]
    pred = predict(params, NL, X["month"])
    obs_m = monthly_totals(X["days"], X["es"])
    pre_m = monthly_totals(X["days"], pred)
    test_months = sorted({m for m in ym[te]})
    o = np.array([obs_m[m] for m in test_months])
    p = np.array([pre_m[m] for m in test_months])
    # ingenuo: mesmo mes do ano anterior, quando existe
    naive = np.array([obs_m.get("%04d-%s" % (int(m[:4]) - 1, m[5:]), np.nan)
                      for m in test_months])
    ok = np.isfinite(naive)

    def mape(a, b):
        return float(np.mean(np.abs(a - b) / np.maximum(a, 1e-9)))

    hourly_corr = float(np.corrcoef(X["es"][te].ravel(), pred[te].ravel())[0, 1])
    return {
        "split": split, "train_months": int(len({m for m in ym[tr]})),
        "test_months": len(test_months), "params": params,
        "monthly": [{"month": m, "observed_twh": round(obs_m[m], 3),
                     "model_twh": round(pre_m[m], 3), "test": m >= split}
                    for m in sorted(obs_m)],
        "test_total_obs_twh": round(float(o.sum()), 2),
        "test_total_model_twh": round(float(p.sum()), 2),
        "test_bias": round(float(p.sum() / o.sum() - 1), 4) if o.sum() else None,
        "mape_model": round(mape(o, p), 4),
        "mape_naive": round(mape(o[ok], naive[ok]), 4) if ok.any() else None,
        "naive_months": int(ok.sum()),
        "hourly_corr": round(hourly_corr, 4),
    }


# ------------------------------------------------------------ projecao
def project(X: dict, params: dict, m_vre: float, m_mmgd: float, m_load: float,
            flex_gw: float, k: int) -> np.ndarray:
    """Corte ENE+SIS horario no ano k a frente, sobre o ano de referencia.

    `m_*` sao MULTIPLICADORES sobre o ano de referencia (1,0 = igual): vem de
    trajetorias ano a ano (PLAN) ou de taxas compostas (1+g)^k.
    """
    mm = X["mmgd"] if X["mmgd"] is not None else np.zeros_like(X["sup"])
    sup_k = (X["sup"] + mm) * m_load - mm * m_mmgd
    vre_k = X["vre_pot"] * m_vre
    return predict(params, sup_k - vre_k, X["month"], flex_mw=flex_gw * 1000.0 * k)


def multipliers(s: dict, k: int) -> tuple[float, float, float]:
    """Multiplicadores do ano k: trajetoria explicita ou taxa composta."""
    def one(key):
        traj = (s.get("traj") or {}).get(key)
        if traj:
            return float(traj[k - 1])
        return (1.0 + float(s["g_" + key])) ** k
    return one("vre"), one("mmgd"), one("load")


def bess_potential(hourly: np.ndarray) -> dict:
    """BESS no SIN justificavel pelo ciclo marginal, sobre o corte horario."""
    if not len(hourly):
        return {}
    mat = np.repeat(hourly, 2, axis=1)                 # meia hora, como na secao BESS
    annual = 365.0 / len(hourly)
    grid = []
    for p_gw in E["potencias_gw"]:
        for h in E["duracoes_h"]:
            p = p_gw * 1000.0
            r = BA.simulate(mat, p, p * h, annual=annual)
            r.update({"p_mw": p, "hours": h, "e_mwh": p * h})
            grid.append(r)
    g = BA.suggest(grid) or {}
    total = float(mat.sum()) * 0.5 * annual
    return {"p_gw": round(g.get("p_mw", 0) / 1000, 1), "hours": g.get("hours"),
            "e_gwh": round(g.get("e_mwh", 0) / 1000, 1),
            "delivered_twh": round(g.get("delivered_mwh", 0) / 1e6, 2),
            "capture": g.get("capture"), "cycles": g.get("cycles"),
            "marginal_cycles": g.get("marginal_cycles"),
            "utilization": g.get("utilization"), "at_grid_limit": g.get("at_grid_limit"),
            "ene_twh": round(total / 1e6, 2),
            "grid": [{"p_gw": x["p_mw"] / 1000, "hours": x["hours"],
                      "delivered_twh": round(x["delivered_mwh"] / 1e6, 3),
                      "cycles": x["cycles"]} for x in grid]}


def scenarios_payload(X: dict, params: dict, scen: dict, years: int) -> list[dict]:
    out = []
    for name, s in scen.items():
        rows = []
        for k in range(1, years + 1):
            mv, mm, ml = multipliers(s, k)
            h = project(X, params, mv, mm, ml, s["flex_gw"], k)
            h0 = project(X, params, mv, 1.0, ml, s["flex_gw"], k)
            b = bess_potential(h)
            vre_twh = float((X["vre_pot"] * mv).sum()) / 1e6
            share = float(h.sum()) / 1e6 / vre_twh if vre_twh > 0 else None
            rows.append({"k": k, "ene_twh": round(float(h.sum()) / 1e6, 2),
                         "vre_pot_twh": round(vre_twh, 1),
                         "cut_share": round(share, 4) if share is not None else None,
                         "implausible": bool(share is not None and
                                             share > E["corte_max_plausivel"]),
                         "ene_sem_mmgd_twh": round(float(h0.sum()) / 1e6, 2),
                         "bess": {x: b.get(x) for x in ("p_gw", "hours", "e_gwh",
                                                       "delivered_twh", "capture",
                                                       "cycles", "marginal_cycles",
                                                       "utilization", "at_grid_limit")},
                         "mult": {"vre": round(mv, 4), "mmgd": round(mm, 4),
                                  "load": round(ml, 4)},
                         "profile_mw": [round(float(v), 0) for v in h.mean(axis=0)]})
        out.append({"name": name, "params": {k: v for k, v in s.items() if k != "traj"},
                    "source": s.get("source", ""), "years": rows})
    return out
