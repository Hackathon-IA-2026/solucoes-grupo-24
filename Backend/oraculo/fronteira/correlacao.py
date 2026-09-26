# -*- coding: utf-8 -*-
"""Correlacao SED (distribuicao) -> SE de fronteira (rede basica).

Nenhuma base publica diz de qual SE da rede basica cada subestacao de
distribuicao recebe energia: essa topologia de subtransmissao esta no cadastro
interno da distribuidora. O que existe em dado aberto e a posicao das duas
pontas e a capacidade da transformacao de fronteira. A associacao e, portanto,
INFERIDA, e o modulo trata isso como tal: cada vinculo sai com probabilidade,
alternativas e a evidencia que o sustenta.

Modelo gravitacional (Huff), por SED s e SE de fronteira f candidata::

    a(s, f) = MVA_fronteira(f)^alfa * exp(-d(s, f) / lambda)
              * bonus_uf     [mesma UF]
              * bonus_agente [mesmo grupo economico]
    p(s, f) = a(s, f) / sum_f a(s, f),     d(s, f) <= raio_max

A SE de maior p e o vinculo primario. A associacao e ambigua quando p < limiar.

A baixa tensao e a GD sem vinculo direto nao tem SED: tem municipio. Elas
descem ao municipio (SAMP rateado por populacao; cadastro de GD ja municipal)
e sobem as SEDs na proporcao das UCs de media tensao que cada SED atende
naquele municipio. Municipio sem nenhuma SED cai direto na SE de fronteira
pelo seu centroide, pelo mesmo modelo gravitacional.
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field

import numpy as np

from .. import config
from .fontes import CLASSES, haversine_km, norm, uf_of_mun

HOURS_YEAR = 8760.0
POWER_FACTOR = 0.92      # para converter MVA de fronteira em MW


# ------------------------------------------------------------ distribuidora
def dist_identity(seds: list[dict], mun_gd: dict[str, dict]) -> dict[str, dict]:
    """Codigo `DIST` da BDGD -> CNPJ, sigla e nome da distribuidora.

    A BDGD identifica a distribuidora por um codigo interno; SAMP e cadastro
    de GD, por CNPJ. A ponte e o municipio: vota-se, ponderando pelas UCs da
    SED em cada municipio, na distribuidora que mais registra GD ali.
    """
    votes: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for s in seds:
        for m, n in s["mun"].items():
            dd = (mun_gd.get(m) or {}).get("dist") or {}
            tot = float(sum(dd.values()))
            for k, c in dd.items():
                votes[s["dist"]][k] += n * c / tot
    out = {}
    for code, v in votes.items():
        tot = sum(v.values())
        k, best = max(v.items(), key=lambda kv: kv[1])
        cnpj, sigla, nome = (k.split("|") + ["", "", ""])[:3]
        out[code] = {"cnpj": cnpj.zfill(14), "sigla": sigla, "nome": nome,
                     "confianca": round(best / tot, 4) if tot else 0.0}
    return out


_GENERIC = {"DISTRIBUIDORA", "DISTRIBUICAO", "ENERGIA", "ELETRICA", "COMPANHIA",
            "CIA", "SA", "S/A", "LTDA", "DE", "DO", "DA", "DOS", "ESTADO",
            "SUL", "NORTE", "NORDESTE", "SERVICOS", "ELETRICIDADE"}


def group_token(sigla: str, nome: str = "") -> str:
    """Token do grupo economico: CPFL, ENEL, ENERGISA, EDP, CEMIG..."""
    for src in (sigla, nome):
        for tok in re.split(r"[^A-Z0-9]+", norm(src)):
            if len(tok) >= 3 and tok not in _GENERIC:
                return tok
    return ""


# ------------------------------------------------------------ associacao
@dataclass
class Link:
    idx: int                   # indice da SE de fronteira primaria (-1 = nenhuma)
    p: float                   # probabilidade do vinculo primario
    d_km: float
    alternatives: list[tuple[int, float, float]] = field(default_factory=list)
    same_uf: bool = False
    agent_match: bool = False
    candidates: int = 0

    limiar: float = 0.5

    @property
    def ambiguous(self) -> bool:
        return self.idx >= 0 and self.p < self.limiar


class Gravity:
    """Atratividade das SEs de fronteira, vetorizada."""

    def __init__(self, frontier: list, params: dict | None = None) -> None:
        P = dict(config.FRONTEIRA, **(params or {}))
        self.f = frontier
        self.lat = np.array([s.lat for s in frontier], dtype=float)
        self.lon = np.array([s.lon for s in frontier], dtype=float)
        mva = np.array([s.frontier_mva if s.frontier_mva > 0
                        else s.capacity_mva for s in frontier], dtype=float)
        self.mva = np.where(mva > 0, mva, 1.0) ** float(P["expoente_mva"])
        self.uf = np.array([s.uf for s in frontier])
        self.agent = [norm(s.agent) for s in frontier]
        self.lam = float(P["lambda_km"])
        self.rmax = float(P["raio_max_km"])
        self.b_uf = float(P["bonus_uf"])
        self.b_ag = float(P["bonus_agente"])
        self.limiar = float(P["limiar_ambiguo"])

    def link(self, lat: float, lon: float, uf: str, token: str) -> Link:
        if not len(self.f):
            return Link(-1, 0.0, float("nan"))
        d = haversine_km(lat, lon, self.lat, self.lon)
        ok = d <= self.rmax
        if not ok.any():
            j = int(np.argmin(d))
            return Link(-1, 0.0, float(d[j]))
        same = self.uf == uf
        ag = np.array([bool(token) and token in a for a in self.agent])
        a = self.mva * np.exp(-d / self.lam)
        a = a * np.where(same, self.b_uf, 1.0) * np.where(ag, self.b_ag, 1.0)
        a = np.where(ok, a, 0.0)
        tot = a.sum()
        if tot <= 0:
            return Link(-1, 0.0, float(d.min()))
        p = a / tot
        order = np.argsort(-p)
        j = int(order[0])
        alts = [(int(k), float(p[k]), float(d[k])) for k in order[1:4] if p[k] > 0]
        return Link(j, float(p[j]), float(d[j]), alts, bool(same[j]),
                    bool(ag[j]), int(ok.sum()), self.limiar)


# ------------------------------------------------------------ resultado
@dataclass
class Resultado:
    frontier: list                       # Substation (registro do ONS)
    seds: list[dict]
    links: list[Link]
    dist: dict[str, dict]
    per_frontier: list[dict]
    mun_links: dict[str, Link]
    report: dict


def correlate(base: dict, frontier: list, params: dict | None = None) -> Resultado:
    """Executa a correlacao completa sobre a base agregada.

    `params` sobrepoe premissas de `config.FRONTEIRA` -- usado pela
    varredura de sensibilidade, sem tocar na configuracao global.
    """
    P = dict(config.FRONTEIRA, **(params or {}))
    seds_all = base["seds"]
    mun = base.get("mun") or {}
    samp = base.get("samp") or {}
    pop = base.get("pop") or {}
    cent = base.get("centroid") or {}
    sed_gd = base.get("sed_gd") or {}

    ident = base.get("dist") or dist_identity(seds_all, mun)
    seds = [s for s in seds_all if (s["n_mt"] + s["n_at"]) >= P["min_ucs"]]
    grav = Gravity(frontier, params)

    links: list[Link] = []
    for s in seds:
        di = ident.get(s["dist"]) or {}
        links.append(grav.link(s["lat"], s["lon"], s["uf"],
                               group_token(di.get("sigla", ""),
                                           di.get("nome", ""))))

    nF = len(frontier)
    acc = [_empty_acc() for _ in range(nF)]

    # ---- 1. media e alta tensao: medidas, por SED
    for i, (s, lk) in enumerate(zip(seds, links)):
        if lk.idx < 0:
            continue
        a = acc[lk.idx]
        a["seds"].append(i)
        for c, v in s["e_class"].items():
            a["e_mtat"][c] += v
        a["e_month_mtat"] += np.asarray(s["e_month"])
        a["dem_mtat_kw"] += s["dem_kw"]
        a["n_uc"] += s["n_mt"] + s["n_at"]
        if lk.ambiguous:
            a["e_ambig"] += sum(s["e_class"].values())
        g = sed_gd.get(s["key"])
        if g:
            a["gd_kw_direct"] += g["kw"]
            a["gd_n_direct"] += g["n"]
            for c, v in g["kw_class"].items():
                a["gd_kw_class"][c] += v

    # ---- 2. municipio -> SEs de fronteira, via SEDs (ou centroide)
    mun_sed: dict[str, list[tuple[int, float]]] = defaultdict(list)
    for i, (s, lk) in enumerate(zip(seds, links)):
        if lk.idx < 0:
            continue
        for m, n in s["mun"].items():
            mun_sed[m].append((lk.idx, float(n)))
    mun_w: dict[str, dict[int, float]] = {}
    mun_links: dict[str, Link] = {}
    for m, lst in mun_sed.items():
        w: dict[int, float] = defaultdict(float)
        tot = sum(n for _, n in lst)
        for j, n in lst:
            w[j] += n / tot
        mun_w[m] = dict(w)
    for m in set(mun) | set(pop):
        if m in mun_w or m not in cent:
            continue
        la, lo = cent[m]
        dd = (mun.get(m) or {}).get("dist") or {}
        top = max(dd.items(), key=lambda kv: kv[1])[0] if dd else "||"
        _, sig, nom = (top.split("|") + ["", "", ""])[:3]
        lk = grav.link(la, lo, uf_of_mun(m), group_token(sig, nom))
        mun_links[m] = lk
        if lk.idx >= 0:
            mun_w[m] = {lk.idx: 1.0}

    # ---- 3. baixa tensao: SAMP da distribuidora -> municipios por populacao
    mun_share: dict[str, dict[str, float]] = defaultdict(dict)
    for m, g in mun.items():
        tot = float(sum(g.get("dist", {}).values()))
        for k, c in g.get("dist", {}).items():
            mun_share[k.split("|")[0].zfill(14)][m] = c / tot
    bt_alloc = bt_unalloc = 0.0
    for cnpj, d in samp.items():
        ms = mun_share.get(cnpj) or {}
        wts = {m: pop.get(m, 0) * sh for m, sh in ms.items()}
        tot = sum(wts.values())
        e_tot = sum(d["kwh_class"].values())
        if tot <= 0:
            bt_unalloc += e_tot
            continue
        month = np.asarray(d.get("kwh_month") or np.zeros(12), dtype=float)
        for m, wm in wts.items():
            if wm <= 0:
                continue
            f_m = wm / tot
            wf = mun_w.get(m)
            if not wf:
                bt_unalloc += e_tot * f_m
                continue
            for j, fj in wf.items():
                a = acc[j]
                for c, v in d["kwh_class"].items():
                    a["e_bt"][c] += v * f_m * fj
                a["e_month_bt"] += month * f_m * fj
                a["pop"] += pop.get(m, 0) * ms.get(m, 0) * fj
            bt_alloc += e_tot * f_m

    # ---- 4. MMGD sem vinculo direto: municipio -> SEs
    gd_alloc = gd_unalloc = 0.0
    for m, g in mun.items():
        resto = max(0.0, g["kw"] - g.get("kw_direct", 0.0))
        wf = mun_w.get(m)
        if not wf:
            gd_unalloc += resto
            continue
        frac = resto / g["kw"] if g["kw"] > 0 else 0.0
        n_resto = g["n"] * frac
        for j, fj in wf.items():
            a = acc[j]
            a["gd_kw_mun"] += resto * fj
            a["gd_n_mun"] += n_resto * fj
            a["gd_kw_ufv"] += g.get("kw_ufv", 0.0) * frac * fj
            for c, v in g["kw_class"].items():
                a["gd_kw_class"][c] += v * frac * fj
        gd_alloc += resto

    per = [_finish(acc[j], frontier[j], j, P) for j in range(nF)]
    rep = _report(seds_all, seds, links, frontier, per, base,
                  bt_alloc, bt_unalloc, gd_alloc, gd_unalloc, mun_links)
    return Resultado(frontier, seds, links, ident, per, mun_links, rep)


def _empty_acc() -> dict:
    return {"seds": [], "e_mtat": defaultdict(float), "e_bt": defaultdict(float),
            "e_month_mtat": np.zeros(12), "e_month_bt": np.zeros(12),
            "dem_mtat_kw": 0.0, "n_uc": 0, "e_ambig": 0.0, "pop": 0.0,
            "gd_kw_direct": 0.0, "gd_n_direct": 0, "gd_kw_mun": 0.0,
            "gd_n_mun": 0.0, "gd_kw_ufv": 0.0, "gd_kw_class": defaultdict(float)}


def _finish(a: dict, sub, j: int, P: dict) -> dict:
    """Consolida o que chegou a uma SE de fronteira."""
    e_cls = {c: a["e_mtat"].get(c, 0.0) + a["e_bt"].get(c, 0.0) for c in CLASSES}
    e_tot = sum(e_cls.values())
    e_mtat = sum(a["e_mtat"].values())
    e_bt = sum(a["e_bt"].values())
    mw_avg = e_tot / HOURS_YEAR / 1000.0
    mva = sub.frontier_mva if sub.frontier_mva > 0 else sub.capacity_mva
    gd_kw = a["gd_kw_direct"] + a["gd_kw_mun"]
    month = a["e_month_mtat"] + a["e_month_bt"]
    lo, hi = P["carregamento_faixa"]
    load = mw_avg / (mva * POWER_FACTOR) if mva > 0 else None
    flag = ("sem carga associada" if e_tot <= 0 else
            "sem capacidade de fronteira" if load is None else
            "acima da faixa" if load > hi else
            "abaixo da faixa" if load < lo else "")
    return {
        "idx": j, "sub_id": sub.sub_id, "name": sub.name, "uf": sub.uf,
        "subsystem": sub.subsystem, "agent": sub.agent,
        "lat": round(sub.lat, 5), "lon": round(sub.lon, 5),
        "voltage_kv": sub.voltage_kv, "secondary_kv": sub.secondary_kv_min,
        "frontier_mva": round(mva, 1),
        "n_sed": len(a["seds"]), "sed_idx": a["seds"], "n_uc": a["n_uc"],
        "e_class_kwh": {c: round(v, 0) for c, v in e_cls.items()},
        "e_mtat_class_kwh": {c: round(a["e_mtat"].get(c, 0.0), 0) for c in CLASSES},
        "e_bt_class_kwh": {c: round(a["e_bt"].get(c, 0.0), 0) for c in CLASSES},
        "e_total_gwh": round(e_tot / 1e6, 3),
        "e_mtat_gwh": round(e_mtat / 1e6, 3),
        "e_bt_gwh": round(e_bt / 1e6, 3),
        "measured_share": round(e_mtat / e_tot, 4) if e_tot else None,
        "weights": {c: round(v / e_tot, 4) for c, v in e_cls.items()} if e_tot
                   else {c: 0.0 for c in CLASSES},
        "dominant": max(e_cls.items(), key=lambda kv: kv[1])[0] if e_tot else "",
        "e_month_gwh": [round(float(v) / 1e6, 4) for v in month],
        "e_month_mtat_gwh": [round(float(v) / 1e6, 4) for v in a["e_month_mtat"]],
        "e_month_bt_gwh": [round(float(v) / 1e6, 4) for v in a["e_month_bt"]],
        "mw_avg": round(mw_avg, 2),
        "dem_mtat_mw": round(a["dem_mtat_kw"] / 1000.0, 2),
        "loading": round(load, 4) if load is not None else None,
        "loading_flag": flag,
        "ambiguous_share": round(a["e_ambig"] / e_mtat, 4) if e_mtat else 0.0,
        "pop_served": int(round(a["pop"])),
        "gd_kw": round(gd_kw, 1),
        "gd_kw_direct": round(a["gd_kw_direct"], 1),
        "gd_kw_mun": round(a["gd_kw_mun"], 1),
        "gd_kw_ufv": round(a["gd_kw_ufv"] + 0.0, 1),
        "gd_n": int(round(a["gd_n_direct"] + a["gd_n_mun"])),
        "gd_direct_share": round(a["gd_kw_direct"] / gd_kw, 4) if gd_kw else None,
        "gd_kw_class": {c: round(a["gd_kw_class"].get(c, 0.0), 1) for c in CLASSES},
        # MW de GD instalada por MW medio de carga: o indicador que interessa
        # ao modelo -- quanto da carga pode "sumir" ao meio-dia.
        "gd_penetration": round(gd_kw / 1000.0 / mw_avg, 4) if mw_avg > 0 else None,
    }


def _report(seds_all, seds, links, frontier, per, base, bt_alloc, bt_unalloc,
            gd_alloc, gd_unalloc, mun_links) -> dict:
    assoc = [lk for lk in links if lk.idx >= 0]
    d = np.array([lk.d_km for lk in assoc]) if assoc else np.array([np.nan])
    p = np.array([lk.p for lk in assoc]) if assoc else np.array([np.nan])
    e_sed = np.array([sum(s["e_class"].values()) for s in seds])
    e_assoc = sum(e for e, lk in zip(e_sed, links) if lk.idx >= 0)
    gd_total = sum(g["kw"] for g in (base.get("mun") or {}).values())
    gd_direct = sum(g["kw"] for g in (base.get("sed_gd") or {}).values())
    covered = [f for f in per if f["n_sed"] > 0]
    loads = np.array([f["loading"] for f in per
                      if f["loading"] is not None and f["e_total_gwh"] > 0])
    return {
        "seds_total": len(seds_all),
        "seds_used": len(seds),
        "seds_discarded_few_ucs": len(seds_all) - len(seds),
        "seds_associated": len(assoc),
        "seds_unassociated": len(seds) - len(assoc),
        "seds_ambiguous": sum(1 for lk in assoc if lk.ambiguous),
        "frontier_total": len(frontier),
        "frontier_with_sed": len(covered),
        "distance_km": _quant(d),
        "probability": _quant(p),
        "same_uf_rate": round(float(np.mean([lk.same_uf for lk in assoc])), 4)
                        if assoc else None,
        "agent_match_rate": round(float(np.mean([lk.agent_match for lk in assoc])), 4)
                            if assoc else None,
        "energy_mtat_associated_share": round(float(e_assoc / e_sed.sum()), 4)
                                        if e_sed.sum() else None,
        "bt_allocated_twh": round(bt_alloc / 1e9, 2),
        "bt_unallocated_twh": round(bt_unalloc / 1e9, 2),
        "gd_total_mw": round(gd_total / 1000.0, 1),
        "gd_direct_mw": round(gd_direct / 1000.0, 1),
        "gd_municipal_allocated_mw": round(gd_alloc / 1000.0, 1),
        "gd_unallocated_mw": round(gd_unalloc / 1000.0, 1),
        "municipios_por_centroide": sum(1 for lk in mun_links.values() if lk.idx >= 0),
        "loading": _quant(loads),
        "loading_flags": _count(f["loading_flag"] for f in per if f["loading_flag"]),
    }


def _quant(x: np.ndarray) -> dict:
    x = x[np.isfinite(x)]
    if not len(x):
        return {}
    q = np.percentile(x, [10, 25, 50, 75, 90])
    return {"n": int(len(x)), "mean": round(float(x.mean()), 4),
            "p10": round(float(q[0]), 4), "p25": round(float(q[1]), 4),
            "p50": round(float(q[2]), 4), "p75": round(float(q[3]), 4),
            "p90": round(float(q[4]), 4)}


def _count(items) -> dict:
    out: dict[str, int] = defaultdict(int)
    for it in items:
        out[it] += 1
    return dict(out)


def histogram(values, edges) -> list[dict]:
    v = np.asarray([x for x in values if x is not None and np.isfinite(x)])
    counts, _ = np.histogram(v, bins=edges)
    return [{"from": float(edges[i]), "to": float(edges[i + 1]),
             "count": int(counts[i])} for i in range(len(counts))]


# ------------------------------------------------------------ sensibilidade
SWEEP_ALPHA = (1.0, 0.5, 0.0)
SWEEP_LAMBDA = (30.0, 20.0, 12.0)


def sensitivity(base: dict, frontier: list) -> list[dict]:
    """Varredura das duas premissas que mais mexem na associacao.

    Nao ha verdade de campo para a topologia de subtransmissao. O criterio e
    coerencia fisica: uma associacao boa distribui a carga de modo que o
    carregamento implicito das SEs seja homogeneo (CV baixo), nenhuma passe
    de 100% e poucas fiquem sem carga nenhuma.
    """
    out = []
    cur = (float(config.FRONTEIRA["expoente_mva"]),
           float(config.FRONTEIRA["lambda_km"]))
    for a in SWEEP_ALPHA:
        for lam in SWEEP_LAMBDA:
            r = correlate(base, frontier, {"expoente_mva": a, "lambda_km": lam})
            L = np.array([f["loading"] for f in r.per_frontier
                          if f["e_total_gwh"] > 0 and f["loading"] is not None])
            assoc = [lk for lk in r.links if lk.idx >= 0]
            nearest = np.mean([lk.d_km <= min([lk.d_km] + [x[2] for x in
                                                             lk.alternatives]) + 1e-9
                               for lk in assoc]) if assoc else float("nan")
            out.append({
                "alpha": a, "lambda_km": lam, "current": (a, lam) == cur,
                "ambiguous_rate": round(len([lk for lk in assoc if lk.ambiguous])
                                        / len(assoc), 4) if assoc else None,
                "nearest_rate": round(float(nearest), 4),
                "frontier_no_load": sum(1 for f in r.per_frontier
                                        if f["e_total_gwh"] <= 0),
                "loading_cv": round(float(L.std() / L.mean()), 4) if len(L) else None,
                "loading_max": round(float(L.max()), 4) if len(L) else None,
                "over_100": int((L > 1.0).sum()),
                "distance_p50_km": (r.report["distance_km"] or {}).get("p50"),
            })
    return out
