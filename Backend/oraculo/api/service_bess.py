# -*- coding: utf-8 -*-
"""Fachada da secao de investimento: alocacao de BESS pelo corte observado.

Mixin proprio (decisao D7). A base sao 12 meses x 2 fontes de constrained-off
(~800 MB de CSV). Cada mes e agregado uma vez e guardado: a primeira carga
leva alguns minutos, em segundo plano e com progresso; as seguintes so baixam
o mes novo.
"""
from __future__ import annotations

import threading
import time

import numpy as np

from .. import config
from ..bess import analise as A
from ..bess import fontes as F

_LOCK = threading.Lock()
MONTHS_PT = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set",
             "out", "nov", "dez"]


class BessMixin:
    """Estado da secao Alocacao de BESS."""

    _bs_months: list | None = None
    _bs_sites: list | None = None
    _bs_rows: list | None = None
    _bs_key: tuple | None = None
    _bs_meta: dict = {}
    _bs_job: dict = {"state": "idle", "stage": "", "done": 0, "total": 0,
                     "error": "", "started": 0.0}

    # ------------------------------------------------------------ base
    def _bs_demo(self) -> bool:
        self.ensure()
        return self.mode() == "demo" or config.FORCE_OFFLINE

    def _bs_window(self) -> list[tuple[str, int, int]]:
        return [(src, y, m) for (y, m) in F.months_window(config.BESS["meses"])
                for src in F.SOURCES]

    def bess_status(self) -> dict:
        self._bs_ensure_started()
        job = dict(type(self)._bs_job)
        ready = type(self)._bs_months is not None
        return {
            "state": "ready" if ready and job["state"] != "building" else job["state"],
            "stage": job["stage"], "done": job["done"], "total": job["total"],
            "overall": round(job["done"] / job["total"], 3) if job["total"] else
                       (1.0 if ready else 0.0),
            "error": job["error"],
            "elapsed_s": round(time.time() - job["started"], 1)
                         if job["state"] == "building" else None,
            "mode": self.bess_mode(),
            "months": type(self)._bs_meta.get("months", []),
        }

    def _bs_ensure_started(self, *, force: bool = False) -> None:
        cls = type(self)
        with _LOCK:
            if cls._bs_job["state"] == "building":
                return
            if self._bs_demo():
                if cls._bs_months is None or cls._bs_meta.get("mode") != "demo":
                    frontier = self.registry_ensure().frontier()
                    cls._bs_months = _demo_months(frontier)
                    cls._bs_meta = {"mode": "demo", "months": ["demo"],
                                    "provenance": [{
                                        "dataset": "bess · gerador determinístico",
                                        "resource": "demo", "url": "",
                                        "fetched_at": "", "rows": 0, "bytes_read": 0,
                                        "mode": "demo",
                                        "lag_note": "Corte sintético, sem "
                                                    "correspondência com a rede."}]}
                    cls._bs_sites = cls._bs_rows = None
                return
            window = self._bs_window()
            cached = all(F.month_is_current(s, y, m) for s, y, m in window)
            if cls._bs_months is not None and cls._bs_meta.get("mode") != "demo" \
                    and not force and cls._bs_meta.get("window") == window:
                return
            if cached and not force:
                self._bs_load(window)
                return
            if cls._bs_job["state"] == "error" and not force:
                return
            cls._bs_job = {"state": "building", "stage": "", "done": 0,
                           "total": len(window), "error": "", "started": time.time()}
        threading.Thread(target=self._bs_build, args=(window, force), daemon=True,
                         name="bess-build").start()

    def _bs_load(self, window, *, refresh: bool = False, progress=None) -> None:
        cls = type(self)
        months, prov = [], []
        for i, (src, y, m) in enumerate(window):
            if progress:
                progress(i, "%s %04d-%02d" % (F.SOURCES[src]["label"], y, m))
            agg = F.load_month(src, y, m, refresh=refresh)
            agg.setdefault("year", y)
            agg.setdefault("month", m)
            months.append(agg)
            if agg.get("provenance"):
                pv = dict(agg["provenance"])
                if pv.get("mode") == "live" and not refresh:
                    pv["mode"] = "cache"
                prov.append(pv)
        cls._bs_months = months
        cls._bs_meta = {"mode": "cache" if not refresh else "live",
                        "months": sorted({"%04d-%02d" % (y, m) for _, y, m in window}),
                        "window": window, "provenance": prov}
        cls._bs_sites = cls._bs_rows = None

    def _bs_build(self, window, force) -> None:
        cls = type(self)

        def prog(i, stage):
            cls._bs_job["done"] = i
            cls._bs_job["stage"] = stage

        try:
            self._bs_load(window, progress=prog)
            with _LOCK:
                cls._bs_meta["mode"] = "live"
                cls._bs_job = {"state": "ready", "stage": "", "done": len(window),
                               "total": len(window), "error": "", "started": 0.0}
        except Exception as exc:
            with _LOCK:
                cls._bs_job = {"state": "error", "stage": cls._bs_job.get("stage", ""),
                               "done": cls._bs_job.get("done", 0),
                               "total": len(window), "error": str(exc)[:300],
                               "started": 0.0}

    def bess_rebuild(self) -> dict:
        if self._bs_demo():
            raise ValueError("modo demonstrativo: não há o que reconstruir")
        type(self)._bs_job["state"] = "idle"
        self._bs_ensure_started(force=False)
        return self.bess_status()

    def bess_mode(self) -> str:
        return type(self)._bs_meta.get("mode") or ("demo" if self._bs_demo() else "cache")

    def bess_provenance(self) -> list[dict]:
        out = list(type(self)._bs_meta.get("provenance") or [])
        try:
            out += self.fronteira_provenance()[:2]
        except Exception:
            pass
        return out

    def bess_notes(self) -> list[str]:
        n = ["Corte = geração não realizada APURADA pelo ONS "
             "(val_geracaonaorealizadaapurada), 12 meses, FV e eólica "
             "CENTRALIZADAS. A MMGD não é cortada: ela reduz a carga líquida e "
             "cria o excedente que vira corte ENE+SIS.",
             "BESS simulado: carrega no corte e descarrega uma vez por dia; "
             "eficiência de ida e volta %.0f%%. Não modela receita nem rede."
             % (100 * config.BESS["eficiencia"])]
        if self.bess_mode() == "demo":
            n.insert(0, "%s — corte sintético." % config.DEMO_BANNER)
        return n

    def _bs(self) -> list[dict]:
        """Sitios analisados (sem a pontuacao, que depende dos pesos)."""
        self._bs_ensure_started()
        cls = type(self)
        if cls._bs_months is None:
            job = cls._bs_job
            from .service_fronteira import BaseNotReady
            if job["state"] == "error":
                raise BaseNotReady("falha ao montar a base de corte: %s" % job["error"])
            raise BaseNotReady("base de constrained-off em construção")
        fr_key = type(self)._fr_key if hasattr(type(self), "_fr_key") else None
        key = (id(cls._bs_months), fr_key, str(config.BESS))
        if cls._bs_rows is None or cls._bs_key != key:
            months = cls._bs_months
            pts: dict = {}
            for m in months:
                pts.update(m["points"])
            if self.bess_mode() == "demo":
                locs = {pid: {"lat": p["lat"], "lon": p["lon"], "method": "SE do ONS",
                              "se_name": p["nom"], "se_code": p["code"]}
                        for pid, p in pts.items()}
            else:
                locs = F.locate(pts, F.ons_substations(), F.modalidade_cegs(),
                                _safe(F.siga_coordinates, {}))
            sites = A.build_sites(months, locs)
            mmgd_sin, duck = self._bs_mmgd_series(sites)
            cls._bs_meta["attribution"] = A.mmgd_induced(sites, mmgd_sin)
            cls._bs_meta["duck"] = duck
            days = _window_days(months)
            cls._bs_sites = sites
            cls._bs_rows = A.analyse(sites, days)
            cls._bs_meta["days"] = days
            cls._bs_key = key
        return cls._bs_rows

    def _bs_mmgd_series(self, sites) -> tuple[dict, dict]:
        """MMGD do SIN por meia hora e a curva do pato de cada subsistema.

        A MMGD e a estimativa horaria do O.R.A.C.U.L.O. por subsistema (metodo
        do envelope, um PISO), somada no SIN. A curva do pato e o perfil medio
        horario, nos dias da janela do corte, de: carga com MMGD
        (supervisionada + MMGD estimada), supervisionada (carga verificada do
        ONS) e liquida (supervisionada - eolica - solar centralizada).
        """
        self.ensure()
        days = sorted({d for s in sites for d in s.days})
        dayset = set(days)
        sin: dict = {}
        duck: dict = {}
        cut_by_ss: dict = {}
        for s in sites:
            acc = cut_by_ss.setdefault(s.subsystem, np.zeros(F.HALF_HOURS))
            for a in s.days.values():
                acc += a
        n_days = max(1, len(days))
        for ss in ("SE", "S", "NE", "N"):
            st = self.areas.get(ss)
            if st is None:
                continue
            ix = st.index
            dstr = np.datetime_as_string(ix.astype("datetime64[D]"))
            hour = (ix.astype("datetime64[h]") - ix.astype("datetime64[D]")).astype(int)
            mm = np.nan_to_num(st.mmgd_est.mmgd_mw)
            sup = st.series["carga_supervisionada"]
            eol = st.series.get("ger_eolica", np.zeros(len(ix)))
            sol = st.series.get("ger_solar_centralizada", np.zeros(len(ix)))
            sel = np.array([d in dayset for d in dstr])
            for d, h, v in zip(dstr[sel], hour[sel], mm[sel]):
                arr = sin.setdefault(str(d), np.zeros(F.HALF_HOURS))
                arr[2 * h] += v
                arr[2 * h + 1] += v
            prof = {}
            for name, ser in (("supervisionada", sup), ("mmgd", mm),
                              ("eolica", eol), ("solar", sol)):
                x = np.where(sel, ser, np.nan)
                vals = []
                for h in range(24):
                    xh = x[hour == h]
                    vals.append(round(float(np.nanmean(xh)), 1)
                                if np.isfinite(xh).any() else None)
                prof[name] = vals
            glob_ = [None if a is None or b is None else round(a + b, 1)
                     for a, b in zip(prof["supervisionada"], prof["mmgd"])]
            liq = [None if None in (a, b, c) else round(a - b - c, 1)
                   for a, b, c in zip(prof["supervisionada"], prof["eolica"],
                                      prof["solar"])]
            cut = cut_by_ss.get(ss, np.zeros(F.HALF_HOURS)) / n_days
            duck[ss] = {
                "subsystem": ss, "name": config.SUBSYSTEMS[ss]["name"],
                "carga_global": glob_, "supervisionada": prof["supervisionada"],
                "liquida": liq, "mmgd": prof["mmgd"],
                "corte": [round(float(cut[2 * h:2 * h + 2].mean()), 1)
                          for h in range(24)],
            }
        return sin, duck

    def _bs_load_side(self) -> list:
        """Tese 2: BESS junto a carga, onde a MMGD mais aprofunda a curva do pato."""
        try:
            per = self._fr().per_frontier
        except Exception:
            return []
        rows = [f for f in per if (f.get("mw_avg") or 0) >= 30 and f.get("gd_kw")]
        rows.sort(key=lambda f: -(f.get("gd_penetration") or 0))
        return [{"sub_id": f["sub_id"], "name": f["name"], "uf": f["uf"],
                 "subsystem": f["subsystem"], "gd_mw": round(f["gd_kw"] / 1000, 1),
                 "load_mw": f["mw_avg"], "penetration": f["gd_penetration"],
                 "energy_gwh": f["e_total_gwh"]} for f in rows[:15]]

    # ------------------------------------------------------------ ranking
    def bess_ranking_payload(self, *, weights: dict | None = None, uf: str = "",
                             source: str = "", limit: int = 60) -> dict:
        base = self._bs()
        rows = A.score([dict(r) for r in base], weights)
        if uf:
            rows = [r for r in rows if r["site"].uf == uf]
        if source:
            rows = [r for r in rows if source in r["site"].sources]
        tot_cut = sum(r["site"].e_cut for r in base)
        ann = 365.0 / max(1, type(self)._bs_meta.get("days", 365))
        top = rows[: max(1, limit)]
        rec = sum((r["suggested"] or {}).get("delivered_mwh", 0.0) for r in rows[:10])
        att = type(self)._bs_meta.get("attribution") or {}
        return {
            "filters": {"uf": uf, "source": source},
            "weights": (rows[0]["weights"] if rows else A.score([], weights)) or {},
            "default_weights": config.BESS["pesos"],
            "ufs": sorted({r["site"].uf for r in base if r["site"].uf}),
            "kpis": {
                "sites": len(base),
                "cut_twh_year": round(tot_cut * ann / 1e6, 2),
                "cut_top10_share": round(sum(r["site"].e_cut for r in sorted(
                    base, key=lambda x: -x["site"].e_cut)[:10]) / tot_cut, 4) if tot_cut else None,
                "recoverable_top10_twh": round(rec / 1e6, 2),
                "ene_share": round(sum(r["site"].e_reason.get("ENE", 0.0) for r in base)
                                   / tot_cut, 4) if tot_cut else None,
                "located_share": round(sum(r["site"].e_cut for r in base
                                           if r["site"].lat is not None) / tot_cut, 4)
                                 if tot_cut else None,
                "mmgd_induced_twh": round(att.get("induced_mwh", 0.0) * ann / 1e6, 2),
                "mmgd_induced_share": round(att.get("induced_mwh", 0.0) / tot_cut, 4)
                                      if tot_cut else None,
                "es_share": round(att.get("es_mwh", 0.0) / tot_cut, 4) if tot_cut else None,
            },
            "duck": type(self)._bs_meta.get("duck") or {},
            "load_side": self._bs_load_side(),
            "rows": [_row(r, ann) for r in top],
            "map": [{"code": r["site"].code, "name": r["site"].name,
                     "lat": r["site"].lat, "lon": r["site"].lon,
                     "cut_gwh": round(r["site"].e_cut * ann / 1e3, 1),
                     "score": r["score"], "rank": r["rank"],
                     "induced": round(getattr(r["site"], "induced_share", 0.0), 3)}
                    for r in rows if r["site"].lat is not None],
            "stability": A.stability([dict(r) for r in base]),
            "months": type(self)._bs_meta.get("months", []),
            "premises": _premises(),
            "pipeline": [
                "constrained-off FV e eólico do ONS, 12 meses, por ponto de "
                "conexão (geração não realizada apurada)",
                "ponto → SE: código da SE (6 caracteres) no cadastro do ONS; "
                "recuo por usinas → CEG → coordenada no SIGA/ANEEL",
                "BESS simulado por dia: carrega no corte (limite P e E), um ciclo, "
                "eficiência declarada",
                "dimensionamento pelo ciclo MARGINAL: o MWh adicional precisa "
                "ciclar ≥ %d vezes/ano" % config.BESS["ciclos_min_ano"],
                "corte induzido pela MMGD: em cada meia hora, mín(corte ENE+SIS "
                "do SIN, MMGD estimada do SIN), rateado pelos sítios (limite superior)",
                "pontuação por postos percentuais, pesos ajustáveis, teste de "
                "estabilidade do top 10",
            ],
        }

    def bess_site_payload(self, code: str, *, weights: dict | None = None) -> dict:
        base = self._bs()
        rows = A.score([dict(r) for r in base], weights)
        r = next((x for x in rows if x["site"].code == code), None)
        if r is None:
            raise LookupError("sítio não encontrado: %s" % code)
        s = r["site"]
        ann = 365.0 / max(1, type(self)._bs_meta.get("days", 365))
        mat = s.matrix()
        days = sorted(s.days)
        # mapa de calor mes x meia-hora (MW medio de corte nos dias do mes)
        heat_rows = []
        for ym in sorted(s.e_month):
            idx = [i for i, d in enumerate(days) if d.startswith(ym)]
            n_days = _days_in(ym)
            v = mat[idx].sum(axis=0) / n_days if idx else np.zeros(F.HALF_HOURS)
            heat_rows.append({"label": MONTHS_PT[int(ym[5:7]) - 1] + "/" + ym[2:4],
                              "values": [round(float(x), 1) for x in v]})
        out = _row(r, ann)
        out.update({
            "points": s.points,
            "usinas": sorted(s.usinas.values())[:60],
            "n_usinas": len(s.usinas),
            "agentes": sorted(s.agentes)[:20],
            "grid": r["grid"],
            "profile_mwh": r["profile_mwh"],
            "heat": heat_rows,
            "months": [{"month": ym, "gwh": round(v / 1e3, 2)} for ym, v in
                       sorted(s.e_month.items())],
            "e_reason_gwh": {k: round(v * ann / 1e3, 1) for k, v in s.e_reason.items()},
            "e_origin_gwh": {k: round(v * ann / 1e3, 1) for k, v in s.e_origin.items()},
            "e_source_gwh": {F.SOURCES[k]["label"]: round(v * ann / 1e3, 1)
                             for k, v in s.e_source.items()},
            "daily_p50_mwh": r["daily_p50_mwh"], "daily_p90_mwh": r["daily_p90_mwh"],
            "peak_cut_mw": r["peak_cut_mw"],
            "location_method": s.method,
            "reference": r["reference"],
            "reference_size": config.BESS["referencia"],
            "reasoning": _reasoning(r),
        })
        return out

    def bess_method_payload(self) -> dict:
        base = self._bs()
        tot = sum(r["site"].e_cut for r in base) or 1.0
        by_method: dict[str, float] = {}
        for r in base:
            k = r["site"].method.split(" (")[0]
            by_method[k] = by_method.get(k, 0.0) + r["site"].e_cut
        reasons: dict[str, float] = {}
        origins: dict[str, float] = {}
        for r in base:
            for k, v in r["site"].e_reason.items():
                reasons[k] = reasons.get(k, 0.0) + v
            for k, v in r["site"].e_origin.items():
                origins[k] = origins.get(k, 0.0) + v
        return {
            "location": {k: round(v / tot, 4) for k, v in by_method.items()},
            "unlocated": [{"code": r["site"].code, "name": r["site"].name,
                           "uf": r["site"].uf,
                           "cut_gwh": round(r["site"].e_cut / 1e3, 1)}
                          for r in base if r["site"].lat is None][:30],
            "reasons": {k: round(v / tot, 4) for k, v in reasons.items()},
            "origins": {k: round(v / tot, 4) for k, v in origins.items()},
            "stability": A.stability([dict(r) for r in base]),
            "months": type(self)._bs_meta.get("months", []),
            "days": type(self)._bs_meta.get("days"),
            "premises": _premises(),
            "limits": [
                "O corte apurado é a decisão operativa observada, não o potencial "
                "físico: parte do corte futuro depende de obras de transmissão já "
                "previstas, que podem torná-lo desnecessário.",
                "BESS simulado com um ciclo por dia e sem restrição de rede na "
                "descarga. A viabilidade depende de receita (PLD, serviços "
                "ancilares, capacidade) e do marco regulatório de armazenamento.",
                "Corte sistêmico (origem SIS) é aliviado por armazenamento em "
                "qualquer ponto do subsistema; o local (LOC), só no ponto.",
                "O corte induzido pela MMGD é um LIMITE SUPERIOR contrafactual: "
                "supõe que a carga que a MMGD atende seria suprida pela geração "
                "cortada. A MMGD vem da estimativa do envelope (um piso).",
                "A MMGD não é cortada e não escolhe o sítio de geração: MMGD alta ao "
                "lado de uma usina não a torna mais cortada. Ela aparece na tese de "
                "BESS junto à carga.",
            ],
        }


# ------------------------------------------------------------ utilitarios
def _safe(fn, default):
    try:
        return fn()
    except Exception:
        return default


def _days_in(ym: str) -> int:
    import calendar
    return calendar.monthrange(int(ym[:4]), int(ym[5:7]))[1]


def _window_days(months: list[dict]) -> int:
    yms = sorted({(m["year"], m["month"]) for m in months
                  if isinstance(m.get("year"), int)})
    if not yms:
        return 365
    return sum(_days_in("%04d-%02d" % ym) for ym in yms)


def _row(r: dict, ann: float) -> dict:
    s = r["site"]
    g = r["suggested"] or {}
    return {
        "code": s.code, "name": s.name, "uf": s.uf, "subsystem": s.subsystem,
        "lat": s.lat, "lon": s.lon, "method": s.method,
        "sources": sorted(F.SOURCES[x]["label"] for x in s.sources),
        "rank": r.get("rank"), "score": r.get("score"),
        "components": r.get("components"),
        "cut_gwh_year": round(s.e_cut * ann / 1e3, 1),
        "cut_rate": r["cut_rate"],
        "recurrence": r["recurrence"], "days_cut": r["days_cut"],
        "local_share": r["local_share"],
        "ene_share": round(s.e_reason.get("ENE", 0.0) / s.e_cut, 4) if s.e_cut else None,
        "disp_max_mw": round(s.disp_max, 1),
        "suggested": {k: g.get(k) for k in ("p_mw", "hours", "e_mwh", "cycles",
                                            "marginal_cycles", "delivered_mwh",
                                            "capture", "utilization", "at_grid_limit")},
        "induced_share": round(getattr(s, "induced_share", 0.0), 4),
        "induced_gwh_year": round(getattr(s, "induced_mwh", 0.0) * ann / 1e3, 1),
        "es_share": round(getattr(s, "es_mwh", 0.0) / s.e_cut, 4) if s.e_cut else None,
    }


def _reasoning(r: dict) -> list[str]:
    """Por que este sitio esta onde esta -- em frases, para quem decide."""
    s, c = r["site"], r.get("components") or {}
    g = r["suggested"] or {}
    out = []
    out.append("Corte em %d dias da janela (%.0f%%): %s." % (
        r["days_cut"], 100 * r["recurrence"],
        "recorrente — o ativo cicla quase todo dia" if r["recurrence"] >= 0.6
        else "intermitente — o ativo fica ocioso parte do ano"))
    if g:
        out.append("BESS de %.0f MW / %.0f h: o MWh adicional ainda cicla %.0f "
                   "vezes/ano; entrega %.0f GWh/ano (%s)." % (
                       g["p_mw"], g["hours"], g.get("marginal_cycles") or 0,
                       (g.get("delivered_mwh") or 0) / 1e3,
                       "no limite da grade ou da capacidade do sítio"
                       if g.get("at_grid_limit") else "utilização " + g["utilization"]))
    ls = r["local_share"]
    out.append("%.0f%% do corte tem origem LOCAL: %s." % (
        100 * ls, "restrição na rede do ponto — o BESS ali resolve o que "
                  "outro local não resolve" if ls >= 0.5 else
                  "predominantemente sistêmico — o armazenamento ajuda, mas "
                  "poderia estar em outro ponto do subsistema"))
    ind = getattr(s, "induced_share", 0.0)
    out.append("Até %.0f%% do corte deste sítio é excedente sistêmico que a MMGD "
               "explica (ENE+SIS na barriga da curva do pato). %s" % (
                   100 * ind,
                   "O BESS aqui absorve o que a MMGD empurra para fora do sistema e "
                   "devolve na rampa do fim da tarde." if ind >= 0.5 else
                   "O resto é restrição de rede ou de confiabilidade, que a MMGD "
                   "não causa."))
    return out


def _premises() -> list[dict]:
    B = config.BESS
    return [
        {"k": "Janela", "v": "%d meses completos · FV + eólica" % B["meses"]},
        {"k": "Eficiência de ida e volta", "v": "%.0f%%" % (100 * B["eficiencia"])},
        {"k": "Ciclo", "v": "um por dia (carga no corte, descarga no fim da tarde)"},
        {"k": "Grade de potência", "v": " · ".join("%.0f" % p for p in B["potencias_mw"]) + " MW"},
        {"k": "Grade de duração", "v": " · ".join("%.0f" % h for h in B["duracoes_h"]) + " h"},
        {"k": "Ciclo marginal mínimo", "v": "%.0f por ano" % B["ciclos_min_ano"]},
        {"k": "Atribuição à MMGD", "v": "mín(corte ENE+SIS, MMGD) no SIN, por meia hora"},
        {"k": "Pesos padrão", "v": " · ".join("%s %.0f%%" % (k, 100 * v)
                                              for k, v in B["pesos"].items())},
    ]


# ------------------------------------------------------------ demo
def _demo_months(frontier: list) -> list[dict]:
    """Dois meses sinteticos e deterministicos em torno das SEs demonstrativas."""
    rng = np.random.default_rng(config.RANDOM_SEED + 7)
    solar = np.clip(np.sin(np.pi * (np.arange(48) / 2.0 - 6.0) / 12.0), 0, None)
    months = []
    for (y, mth) in ((2026, 7), (2026, 8)):
        for src in ("fv", "eol"):
            pts = {}
            for j, f in enumerate(frontier):
                if (j + (src == "eol")) % 2:
                    continue
                pid = "%s-%s-A" % (f.sub_id[:6], "230")
                scale = float(rng.uniform(20, 400))
                prob = float(rng.uniform(0.2, 0.95))
                days = {}
                e = 0.0
                for d in range(1, 29):
                    if rng.random() > prob:
                        continue
                    shape = solar if src == "fv" else np.clip(
                        0.6 + 0.4 * np.cos(np.pi * (np.arange(48) / 2.0 - 3.0) / 12.0), 0, None)
                    v = scale * shape * float(rng.uniform(0.3, 1.0))
                    days["%04d-%02d-%02d" % (y, mth, d)] = [round(float(x), 2) for x in v]
                    e += float(v.sum()) * 0.5
                days_es = {k: [round(x * 0.6, 2) for x in a] for k, a in days.items()}
                loc = float(rng.uniform(0, 1))
                pts[pid] = {"id": pid, "nom": f.name, "uf": f.uf,
                            "subsystem": f.subsystem, "agentes": ["Agente demo"],
                            "usinas": {"U%s%d" % (src, j): "Usina demo %s %d" % (src, j)},
                            "cegs": [], "e_cut": round(e, 2), "e_gen": round(e * 4, 2),
                            "e_reason": {"ENE": round(e * 0.7, 2), "CNF": round(e * 0.3, 2)},
                            "e_origin": {"LOC": round(e * loc, 2), "SIS": round(e * (1 - loc), 2)},
                            "disp_max": round(scale * 1.6, 1), "days": days,
                            "days_es": days_es,
                            "source": src, "lat": f.lat, "lon": f.lon,
                            "code": f.sub_id[:6]}
            months.append({"points": pts, "year": y, "month": mth,
                           "report": {"demo": True}})
    return months
