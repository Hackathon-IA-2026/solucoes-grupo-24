# -*- coding: utf-8 -*-
"""Onde um BESS recupera mais energia cortada -- e onde a MMGD agrava o corte.

Unidade de decisao: o SITIO, isto e, a subestacao onde as usinas se conectam
(pontos de conexao de tensoes diferentes na mesma SE sao somados). E ali que
um armazenamento absorve o corte sem depender de rede adicional.

Para cada sitio, com 12 meses de constrained-off apurado do ONS:

  1. Energia recuperavel. Simula-se um BESS de potencia P e energia E que
     carrega durante o corte e descarrega uma vez por dia -- no fim da tarde,
     quando a MMGD some e a carga liquida sobe:

         absorvido(dia) = min( E,  sum_t min(corte_t, P) * 0,5 h )
         entregue       = absorvido * eficiencia_ida_e_volta

     Varre-se uma grade de P x duracao; o dimensionamento sugerido e o de
     maior energia entregue que ainda cicla o suficiente para se pagar.

  2. Corte induzido pela MMGD. O corte acontece nas usinas CENTRALIZADAS; a
     MMGD nao e cortada. O que ela faz e reduzir a carga liquida do sistema
     ao meio-dia (a barriga da curva do pato), criando excedente que vira
     corte por razao energetica de origem sistemica (ENE + SIS) em qualquer
     usina do SIN. A atribuicao e contrafactual, em cada meia hora t:

         induzido_SIN(t) = min( corte_ENE+SIS_SIN(t), MMGD_SIN(t) )

     -- sem a MMGD, a carga liquida seria maior nessa quantidade. O volume e
     rateado entre os sitios pelo corte ENE+SIS de cada um. E um LIMITE
     SUPERIOR: supoe que toda a carga adicional seria atendida pela geracao
     cortada. Corte por confiabilidade ou indisponibilidade (CNF, REL) e
     restricao LOCAL nao sao atribuidos a MMGD.

     A penetracao de MMGD na vizinhanca NAO entra na escolha do sitio de
     geracao: MMGD alta ao lado de uma usina nao faz aquela usina ser mais
     cortada. Ela aparece na outra tese de investimento, BESS junto a carga.

  3. Pontuacao. Soma ponderada de postos percentuais (0 a 1) de quatro
     componentes, com pesos declarados e ajustaveis na tela. O postos, e nao
     o valor bruto, impedem que um sitio gigante esmague todos os outros.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

import numpy as np

from .. import config
from .fontes import HALF_HOURS, se_code

P = config.BESS


# ------------------------------------------------------------ sitios
@dataclass
class Site:
    code: str
    name: str
    uf: str
    subsystem: str
    lat: float | None
    lon: float | None
    method: str
    points: list[str] = field(default_factory=list)
    sources: set = field(default_factory=set)
    usinas: dict = field(default_factory=dict)
    agentes: set = field(default_factory=set)
    e_cut: float = 0.0
    e_gen: float = 0.0
    e_reason: dict = field(default_factory=lambda: defaultdict(float))
    e_origin: dict = field(default_factory=lambda: defaultdict(float))
    e_source: dict = field(default_factory=lambda: defaultdict(float))
    e_month: dict = field(default_factory=lambda: defaultdict(float))
    disp_max: float = 0.0
    disp_by: dict = field(default_factory=dict)   # ponto -> disponibilidade max
    days: dict = field(default_factory=dict)      # dia -> np.array(48) MW
    days_es: dict = field(default_factory=dict)   # idem, so ENE + SIS

    def matrix(self) -> np.ndarray:
        if not self.days:
            return np.zeros((0, HALF_HOURS))
        return np.vstack([self.days[d] for d in sorted(self.days)])


def build_sites(months: list[dict], locations: dict[str, dict]) -> list[Site]:
    """Agrega pontos de conexao por SE ao longo dos meses."""
    sites: dict[str, Site] = {}
    for m in months:
        ym = "%04d-%02d" % (m["year"], m["month"])
        for pid, p in m["points"].items():
            loc = locations.get(pid) or {}
            code = loc.get("se_code") or se_code(pid)
            s = sites.get(code)
            if s is None:
                s = sites[code] = Site(code=code, name=loc.get("se_name") or p["nom"],
                                       uf=p["uf"], subsystem=p["subsystem"],
                                       lat=loc.get("lat"), lon=loc.get("lon"),
                                       method=loc.get("method", "não localizado"))
            if pid not in s.points:
                s.points.append(pid)
            s.sources.add(p["source"])
            s.usinas.update(p["usinas"])
            s.agentes.update(p["agentes"])
            s.e_cut += p["e_cut"]
            s.e_gen += p["e_gen"]
            for k, v in p["e_reason"].items():
                s.e_reason[k] += v
            for k, v in p["e_origin"].items():
                s.e_origin[k] += v
            s.e_source[p["source"]] += p["e_cut"]
            s.e_month[ym] += p["e_cut"]
            # capacidade do sitio: max no tempo por ponto, somada entre pontos
            s.disp_by[pid] = max(s.disp_by.get(pid, 0.0), p["disp_max"])
            for key, store in (("days", s.days), ("days_es", s.days_es)):
                for d, arr in (p.get(key) or {}).items():
                    a = np.asarray(arr, dtype=float)
                    store[d] = store[d] + a if d in store else a
    for s in sites.values():
        s.disp_max = float(sum(s.disp_by.values()))
    return sorted(sites.values(), key=lambda x: -x.e_cut)


# ------------------------------------------------------------ BESS
def simulate(mat: np.ndarray, p_mw: float, e_mwh: float,
             eff: float | None = None, annual: float = 1.0) -> dict:
    """Um ciclo por dia: carrega no corte, limitado por P e por E.

    `annual` = 365 / dias da janela: energia e ciclos saem POR ANO. Sem isso,
    uma janela curta nunca atinge o limiar de ciclos e todo sitio parece
    subutilizado.
    """
    eff = P["eficiencia"] if eff is None else eff
    if not len(mat) or p_mw <= 0 or e_mwh <= 0:
        return {"absorbed_mwh": 0.0, "delivered_mwh": 0.0, "cycles": 0.0,
                "capture": 0.0, "days_full": 0}
    charge = np.minimum(mat, p_mw).sum(axis=1) * 0.5
    absorbed = np.minimum(charge, e_mwh)
    total = mat.sum() * 0.5
    return {
        "absorbed_mwh": round(float(absorbed.sum()) * annual, 1),
        "delivered_mwh": round(float(absorbed.sum() * eff) * annual, 1),
        "cycles": round(float(absorbed.sum() / e_mwh) * annual, 1),
        "capture": round(float(absorbed.sum() / total), 4) if total > 0 else 0.0,
        "days_full": int((charge >= e_mwh).sum()),
    }


def sizing_grid(mat: np.ndarray, disp_max: float, annual: float = 1.0) -> list[dict]:
    """Curva de captura na grade de potencia x duracao."""
    out = []
    cap = disp_max if disp_max > 0 else max(P["potencias_mw"])
    for p_mw in P["potencias_mw"]:
        if p_mw > cap * 1.0001 and p_mw != min(P["potencias_mw"]):
            continue
        for h in P["duracoes_h"]:
            r = simulate(mat, p_mw, p_mw * h, annual=annual)
            r.update({"p_mw": p_mw, "hours": h, "e_mwh": p_mw * h,
                      "delivered_per_mwh": round(r["delivered_mwh"] / (p_mw * h), 1)})
            out.append(r)
    return out


def suggest(grid: list[dict]) -> dict | None:
    """Dimensionamento pelo criterio MARGINAL.

    "Maior BESS que ainda cicla o bastante" escolhe sempre o topo da grade num
    sitio de corte grande: o ativo inteiro cicla bem mesmo quando os ultimos
    MWh quase nao sao usados. O que decide investimento e o incremento: sobe-
    se na fronteira eficiente (maior energia absorvida para cada tamanho) e
    para-se quando o MWh ADICIONAL cicla menos que o limiar por ano.
    """
    if not grid:
        return None
    thr = P["ciclos_min_ano"]
    # fronteira eficiente: por energia instalada, a melhor absorcao
    best_by_e: dict[float, dict] = {}
    for g in grid:
        b = best_by_e.get(g["e_mwh"])
        if b is None or g["absorbed_mwh"] > b["absorbed_mwh"]:
            best_by_e[g["e_mwh"]] = g
    front, top = [], -1.0
    for e in sorted(best_by_e):
        g = best_by_e[e]
        if g["absorbed_mwh"] > top:
            front.append(g)
            top = g["absorbed_mwh"]
    chosen, prev = None, {"e_mwh": 0.0, "absorbed_mwh": 0.0}
    for g in front:
        de = g["e_mwh"] - prev["e_mwh"]
        marginal = (g["absorbed_mwh"] - prev["absorbed_mwh"]) / de if de > 0 else 0.0
        if marginal < thr:
            break
        chosen = dict(g, marginal_cycles=round(marginal, 1))
        prev = g
    if chosen is None:
        g = max(grid, key=lambda x: x["cycles"])
        return dict(g, utilization="baixa", marginal_cycles=g["cycles"],
                    at_grid_limit=False)
    chosen["utilization"] = "adequada"
    chosen["at_grid_limit"] = chosen["e_mwh"] == front[-1]["e_mwh"] and         chosen["e_mwh"] == max(x["e_mwh"] for x in grid)
    return chosen


# ------------------------------------------------------------ MMGD -> corte
def mmgd_induced(sites: list[Site], mmgd_sin: dict[str, np.ndarray]) -> dict:
    """Corte ENE+SIS atribuivel a MMGD, por sitio (limite superior).

    `mmgd_sin`: dia -> array(48) com a MMGD estimada do SIN em MW medio
    (a estimativa horaria repetida nas duas meias horas).
    """
    days = sorted({d for s in sites for d in s.days_es})
    tot_es = {d: sum((s.days_es[d] for s in sites if d in s.days_es),
                     np.zeros(HALF_HOURS)) for d in days}
    frac = {}
    for d in days:
        m = mmgd_sin.get(d)
        c = tot_es[d]
        if m is None:
            frac[d] = np.zeros(HALF_HOURS)
            continue
        with np.errstate(divide="ignore", invalid="ignore"):
            frac[d] = np.where(c > 0, np.minimum(c, m) / c, 0.0)
    total_es = total_ind = 0.0
    for s in sites:
        ind = sum(float((s.days_es[d] * frac[d]).sum()) for d in s.days_es) * 0.5
        es = sum(float(a.sum()) for a in s.days_es.values()) * 0.5
        s.induced_mwh = ind
        s.es_mwh = es
        s.induced_share = ind / s.e_cut if s.e_cut else 0.0
        total_es += es
        total_ind += ind
    return {"es_mwh": total_es, "induced_mwh": total_ind,
            "coverage_days": sum(1 for d in days if d in mmgd_sin),
            "days": len(days)}


# ------------------------------------------------------------ pontuacao
COMPONENTS = ("energia", "mmgd", "recorrencia", "local")


def _rank01(x: np.ndarray) -> np.ndarray:
    """Posto percentual em [0, 1], com empate pelo posto medio; ausente vira 0.

    Posto medio importa: sitios empatados (ex.: todos saturam o mesmo BESS)
    precisam receber a mesma nota, nao uma ordem arbitraria do argsort.
    """
    from scipy.stats import rankdata
    ok = np.isfinite(x)
    out = np.zeros(len(x))
    if ok.sum() == 1:
        out[ok] = 1.0
    elif ok.sum() > 1:
        r = rankdata(x[ok], method="average")
        out[ok] = (r - 1) / (ok.sum() - 1)
    return out


def analyse(sites: list[Site], n_days: int) -> list[dict]:
    """Metricas por sitio, antes da pontuacao."""
    ref_p, ref_h = P["referencia"]
    annual = 365.0 / max(1, n_days)
    out = []
    for s in sites:
        mat = s.matrix()
        grid = sizing_grid(mat, s.disp_max, annual)
        rp = min(ref_p, s.disp_max) if s.disp_max > 0 else ref_p
        ref = simulate(mat, rp, rp * ref_h, annual=annual)
        daily = mat.sum(axis=1) * 0.5 if len(mat) else np.zeros(0)
        prof = mat.sum(axis=0) * 0.5 / max(1, n_days) if len(mat) else np.zeros(HALF_HOURS)
        loc_share = s.e_origin.get("LOC", 0.0) / s.e_cut if s.e_cut else 0.0
        out.append({
            "site": s,
            "grid": grid,
            "suggested": suggest(grid),
            "reference": ref,
            "days_cut": int((daily >= 1.0).sum()),
            "recurrence": round(float((daily >= 1.0).sum()) / max(1, n_days), 4),
            "daily_p50_mwh": round(float(np.median(daily)), 1) if len(daily) else 0.0,
            "daily_p90_mwh": round(float(np.percentile(daily, 90)), 1) if len(daily) else 0.0,
            "peak_cut_mw": round(float(mat.max()), 1) if len(mat) else 0.0,
            "profile_mwh": [round(float(v), 2) for v in prof],
            "local_share": round(loc_share, 4),
            "cut_rate": round(s.e_cut / (s.e_cut + s.e_gen), 4) if (s.e_cut + s.e_gen) else None,
        })
    return out


def score(rows: list[dict], weights: dict | None = None) -> list[dict]:
    """Pontuacao ponderada por postos percentuais. Devolve ordenado."""
    w = dict(P["pesos"], **(weights or {}))
    tot = sum(max(0.0, float(w.get(c, 0.0))) for c in COMPONENTS) or 1.0
    w = {c: max(0.0, float(w.get(c, 0.0))) / tot for c in COMPONENTS}
    if not rows:
        return []
    comp = {
        # energia que o BESS DIMENSIONADO para o sitio entrega por ano: o de
        # referencia (100 MW/4 h) satura em quase todo sitio grande e empata.
        "energia": _rank01(np.array([(r["suggested"] or {}).get("delivered_mwh", 0.0)
                                     for r in rows], float)),
        # fracao do corte do sitio que o excedente criado pela MMGD explica
        "mmgd": _rank01(np.array([getattr(r["site"], "induced_share", np.nan)
                                  for r in rows], float)),
        "recorrencia": _rank01(np.array([r["recurrence"] for r in rows], float)),
        "local": _rank01(np.array([r["local_share"] for r in rows], float)),
    }
    for i, r in enumerate(rows):
        r["components"] = {c: round(float(comp[c][i]), 4) for c in COMPONENTS}
        r["score"] = round(float(sum(w[c] * comp[c][i] for c in COMPONENTS)), 4)
        r["weights"] = w
    rows = sorted(rows, key=lambda r: -r["score"])
    for k, r in enumerate(rows, 1):
        r["rank"] = k
    return rows


WEIGHT_SCENARIOS = {
    "padrão": None,
    "só energia": {"energia": 1, "mmgd": 0, "recorrencia": 0, "local": 0},
    "curva do pato": {"energia": 0.3, "mmgd": 0.5, "recorrencia": 0.2, "local": 0.0},
    "restrição local": {"energia": 0.3, "mmgd": 0.0, "recorrencia": 0.2, "local": 0.5},
    "pesos iguais": {"energia": 1, "mmgd": 1, "recorrencia": 1, "local": 1},
    "sem MMGD": {"energia": 0.55, "mmgd": 0, "recorrencia": 0.225, "local": 0.225},
}


def stability(rows: list[dict], top: int = 10) -> list[dict]:
    """Quanto do top-N sobrevive a cenarios de peso diferentes."""
    base = [r["site"].code for r in score([dict(r) for r in rows])[:top]]
    out = []
    for name, w in WEIGHT_SCENARIOS.items():
        ranked = score([dict(r) for r in rows], w)[:top]
        alt = [r["site"].code for r in ranked]
        out.append({"scenario": name, "weights": w,
                    "overlap": len(set(base) & set(alt)),
                    "top": top, "top3": alt[:3],
                    "top3_names": ["%s (%s)" % (r["site"].name, r["site"].uf)
                                   for r in ranked[:3]]})
    return out
