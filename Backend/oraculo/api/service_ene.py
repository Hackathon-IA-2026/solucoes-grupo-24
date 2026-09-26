# -*- coding: utf-8 -*-
"""Fachada da projecao do corte por razao energetica (ENE) e do BESS futuro.

Mixin proprio (decisao D7). Reaproveita o cache mensal do constrained-off da
secao de BESS e estende a janela ao historico publicado inteiro (eolica desde
10/2021, fotovoltaica desde 04/2024). A construcao do historico roda em
segundo plano; o modelo, uma vez com os dados, responde em segundos.
"""
from __future__ import annotations

import threading
import time

import numpy as np

from .. import config
from ..bess import fontes as BF
from ..ene import modelo as M
from ..ene import series as S

_LOCK = threading.Lock()
REF = "PLAN 2026-2030 (2ª RQ)"
MES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


class EneMixin:
    """Estado da secao Projecao do corte ENE."""

    _ene_data: dict | None = None
    _ene_cache: dict = {}
    _ene_job: dict = {"state": "idle", "stage": "", "done": 0, "total": 0,
                      "error": "", "started": 0.0}

    def _ene_window(self) -> list:
        last = BF.months_window(1)[-1]
        return S.history_months(last)

    def ene_status(self) -> dict:
        self._ene_ensure_started()
        j = dict(type(self)._ene_job)
        ready = type(self)._ene_data is not None
        return {"state": "ready" if ready and j["state"] != "building" else j["state"],
                "stage": j["stage"], "done": j["done"], "total": j["total"],
                "overall": round(j["done"] / j["total"], 3) if j["total"] else
                           (1.0 if ready else 0.0),
                "error": j["error"],
                "elapsed_s": round(time.time() - j["started"], 1)
                             if j["state"] == "building" else None,
                "mode": self.ene_mode()}

    def ene_mode(self) -> str:
        d = type(self)._ene_data
        return (d or {}).get("mode") or ("demo" if self._bs_demo() else "cache")

    def _ene_ensure_started(self) -> None:
        cls = type(self)
        with _LOCK:
            if cls._ene_job["state"] == "building" or cls._ene_data is not None:
                return
            if self._bs_demo():
                cls._ene_data = _demo_data()
                return
            window = self._ene_window()
            if cls._ene_job["state"] == "error":
                return
            cls._ene_job = {"state": "building", "stage": "", "done": 0,
                            "total": len(window) + 2, "error": "",
                            "started": time.time()}
        threading.Thread(target=self._ene_build, args=(window,), daemon=True,
                         name="ene-build").start()

    def _ene_build(self, window) -> None:
        cls = type(self)
        try:
            months, prov = [], []
            for i, (src, y, m) in enumerate(window):
                cls._ene_job.update(done=i, stage="%s %04d-%02d" % (
                    BF.SOURCES[src]["label"], y, m))
                agg = BF.load_month(src, y, m)
                agg.setdefault("year", y)
                agg.setdefault("month", m)
                months.append(agg)
                if agg.get("provenance"):
                    prov.append(dict(agg["provenance"], mode="cache"))
            cls._ene_job.update(done=len(window), stage="balanço de energia horário")
            cut = S.cut_series(months)
            years = sorted({int(d[:4]) for d in cut["hour_es"]} |
                           {int(y) for _, y, _ in window})
            bal = S.balanco_hourly(years)
            cls._ene_job.update(done=len(window) + 1, stage="MMGD conectada (ANEEL)")
            mmgd = S.mmgd_history()
            data = {"mode": "cache", "cut": cut, "bal": bal["days"], "mmgd": mmgd,
                    "provenance": prov[-6:] + bal["provenance"] + [{
                        "dataset": "2ª RQ do PLAN 2026-2030 (ONS/EPE/CCEE)",
                        "resource": "carga global e MMGD do SIN, 2025–2030",
                        "url": config.ENE["plan"]["url"], "fetched_at": "",
                        "rows": 0, "bytes_read": 0, "mode": "live",
                        "lag_note": "Publicado em 07/08/2026; valores transcritos "
                                    "das tabelas."}, {
                        "dataset": "PAR/PEL 2025 — Sumário Executivo",
                        "resource": "capacidade instalada dez/2025 e 2029–2030",
                        "url": config.ENE["parpel"]["url"], "fetched_at": "",
                        "rows": 0, "bytes_read": 0, "mode": "live",
                        "lag_note": "Valores transcritos do documento; aplicam-se "
                                    "as taxas anuais."}, {
                        "dataset": "empreendimento-gd-informacoes-tecnicas-fotovoltaica",
                        "resource": S.RES_GD_FV, "url": mmgd.get("url", ""),
                        "fetched_at": mmgd.get("fetched_at", ""),
                        "rows": mmgd.get("units", 0), "bytes_read": 0, "mode": "cache",
                        "lag_note": "Potência por data de conexão; últimos meses "
                                    "sub-registrados pela defasagem de cadastro."}],
                    "months_loaded": len(months)}
            with _LOCK:
                cls._ene_data = data
                cls._ene_cache = {}
                cls._ene_job = {"state": "ready", "stage": "", "done": len(window) + 2,
                                "total": len(window) + 2, "error": "", "started": 0.0}
        except Exception as exc:
            with _LOCK:
                cls._ene_job = {"state": "error", "stage": cls._ene_job.get("stage", ""),
                                "done": cls._ene_job.get("done", 0),
                                "total": cls._ene_job.get("total", 0),
                                "error": str(exc)[:300], "started": 0.0}

    def ene_provenance(self) -> list[dict]:
        return list((type(self)._ene_data or {}).get("provenance") or [])

    def ene_notes(self) -> list[str]:
        n = ["Projeção por modelo físico da carga líquida, calibrado nas séries "
             "horárias do ONS. Referência: carga global e MMGD da 2ª Revisão "
             "Quadrimestral do PLAN 2026-2030 (ONS/EPE/CCEE), ano a ano; eólica + "
             "solar centralizadas do PAR/PEL 2025.",
             "Sem nova transmissão nem flexibilidade no cenário base: o corte "
             "projetado é o que rede, armazenamento e flexibilidade precisariam "
             "resolver."]
        if self.ene_mode() == "demo":
            n.insert(0, "%s — séries sintéticas." % config.DEMO_BANNER)
        return n

    # ------------------------------------------------------------ base
    def _ene_base(self) -> dict:
        """Matrizes, taxas observadas, ajuste e backtest (independe do cenario)."""
        self._ene_ensure_started()
        cls = type(self)
        d = cls._ene_data
        if d is None:
            from .service_fronteira import BaseNotReady
            j = cls._ene_job
            if j["state"] == "error":
                raise BaseNotReady("falha ao montar o histórico: %s" % j["error"])
            raise BaseNotReady("histórico de constrained-off em construção")
        if "base" in cls._ene_cache:
            return cls._ene_cache["base"]
        cut, bal = d["cut"], d["bal"]
        start = config.ENE["inicio_calibracao"]
        days = sorted(x for x in cut["hour_es"].keys() | bal.keys()
                      if x[:7] >= start and x in bal)
        # so dias com corte publicado nas duas fontes (a partir de 04/2024)
        last_cut = max(cut["hour_all"]) if cut["hour_all"] else ""
        days = [x for x in days if x <= last_cut]
        X = M.assemble(days, bal, cut["hour_es"], cut["hour_all"])
        bt = M.backtest(X, config.ENE["corte_backtest"])
        params = M.fit(X)                                   # todo o periodo
        # ano de referencia: os ultimos 12 meses completos, com MMGD horaria
        ref_days = [x for x in X["days"] if x >= _minus_months(last_cut[:7], 11) + "-01"]
        mm = self._ene_mmgd_hourly(ref_days)
        Xref = M.assemble(ref_days, bal, cut["hour_es"], cut["hour_all"], mm)
        # O envelope estima um PISO. O nivel passa a ser o oficial do PLAN
        # (MWmed do ano base); o perfil horario e o da estimativa.
        plan = config.ENE["plan"]
        target = plan["mmgd_mwmed"].get(plan["ano_base"])
        est_mean = float(np.nanmean(Xref["mmgd"])) if Xref["mmgd"] is not None else 0.0
        mmgd_scale = target / est_mean if target and est_mean > 0 else 1.0
        if Xref["mmgd"] is not None:
            Xref["mmgd"] = Xref["mmgd"] * mmgd_scale
        rates = self._ene_rates(d, X)
        base = {"X": X, "Xref": Xref, "params": params, "backtest": bt, "rates": rates,
                "ref": {"from": ref_days[0] if ref_days else None,
                        "to": ref_days[-1] if ref_days else None,
                        "days": len(ref_days),
                        "mmgd_est_mwmed": round(est_mean, 0),
                        "mmgd_plan_mwmed": target,
                        "mmgd_scale": round(mmgd_scale, 3)}}
        cls._ene_cache["base"] = base
        return base

    def _ene_mmgd_hourly(self, days: list[str]) -> dict:
        """MMGD estimada do SIN por hora (soma dos subsistemas), nos dias pedidos."""
        try:
            self.ensure()
        except Exception:
            return {}
        want = set(days)
        out: dict[str, np.ndarray] = {}
        for ss in ("SE", "S", "NE", "N"):
            st = self.areas.get(ss)
            if st is None:
                continue
            ix = st.index
            ds = np.datetime_as_string(ix.astype("datetime64[D]"))
            hr = (ix.astype("datetime64[h]") - ix.astype("datetime64[D]")).astype(int)
            mm = np.nan_to_num(st.mmgd_est.mmgd_mw)
            for dd, h, v in zip(ds, hr, mm):
                if dd in want:
                    out.setdefault(str(dd), np.zeros(24))[h] += v
        return out

    def _ene_rates(self, d: dict, X: dict) -> dict:
        """Taxas observadas: VRE, carga (balanco) e MMGD (cadastro ANEEL)."""
        bal = d["bal"]
        years: dict[int, dict] = {}
        for day, rec in bal.items():
            y = int(day[:4])
            a = years.setdefault(y, {"sup": 0.0, "vre": 0.0, "h": 0})
            a["sup"] += float(np.nansum(rec["sup"]))
            a["vre"] += float(np.nansum(rec["eol"]) + np.nansum(rec["sol"]))
            a["h"] += int(np.isfinite(rec["sup"]).sum())
        full = sorted(y for y, a in years.items() if a["h"] >= 8700)

        def g(key, a, b):
            if a is None or b is None or b <= a or a not in years or b not in years                     or years[a][key] <= 0:
                return None
            return (years[b][key] / years[a][key]) ** (1.0 / (b - a)) - 1.0

        last = full[-1] if full else None
        mm = d["mmgd"]
        lag = config.ENE["defasagem_cadastro_meses"]
        until = mm["months"][-1 - lag] if len(mm.get("months", [])) > lag else None
        mm_12 = S.growth_rate(mm["months"], mm["cumulative_gw"], until) if until else None
        mm_24 = None
        if until:
            i = mm["months"].index(until)
            if i >= 24 and mm["cumulative_gw"][i - 24] > 0:
                mm_24 = (mm["cumulative_gw"][i] / mm["cumulative_gw"][i - 24]) ** 0.5 - 1
        return {
            "years": {y: {"carga_twh": round(a["sup"] / 1e6, 1),
                          "vre_twh": round(a["vre"] / 1e6, 1)} for y, a in years.items()
                      if y in full},
            "vre_last": g("vre", last - 1, last) if last else None,
            "vre_2y": g("vre", last - 2, last) if last else None,
            "vre_6y": g("vre", full[0], last) if full else None,
            "load_last": g("sup", last - 1, last) if last else None,
            "load_6y": g("sup", full[0], last) if full else None,
            "mmgd_12m": mm_12, "mmgd_24m": mm_24, "mmgd_until": until,
            "mmgd_gw": mm["cumulative_gw"][mm["months"].index(until)] if until else None,
            "last_full_year": last,
        }

    def ene_default_scenarios(self) -> dict:
        """Cenario OFICIAL do PAR/PEL 2025 e, para comparacao, a tendencia.

        PAR/PEL 2025: MMGD de 46,2 GW (dez/2025) a 65,3 GW (fim de 2029, base
        do PMO) ou 60,9 GW (2030, base das distribuidoras); eolica + solar
        centralizadas de 55,1 a 60,3 GW; carga maxima de 2030 17% acima da de
        2025. "Tendencia observada" extrapola as series e so serve de contraste.
        """
        r = self._ene_base()["rates"]
        pp = config.ENE["parpel"]
        mm_pmo = (pp["mmgd_2029_gw"] / pp["mmgd_dez2025_gw"]) ** (1 / 4) - 1
        mm_dist = (pp["mmgd_2030_dist_gw"] / pp["mmgd_dez2025_gw"]) ** (1 / 5) - 1
        vre_pp = (pp["vre_2029_gw"] / pp["vre_dez2025_gw"]) ** (1 / 4) - 1
        load_pp = (1 + pp["carga_max_2030_crescimento"]) ** (1 / 5) - 1

        def v(x, dflt):
            return round(float(x), 4) if x is not None else dflt

        plan = config.ENE["plan"]
        b0 = plan["ano_base"]
        yrs = [b0 + k for k in range(1, config.ENE["anos"] + 1)]
        g, mw = plan["carga_global_mwmed"], plan["mmgd_mwmed"]
        traj_load = [g[y] / g[b0] for y in yrs]
        traj_mmgd = [mw[y] / mw[b0] for y in yrs]
        traj_vre = [(1 + vre_pp) ** k for k in range(1, len(yrs) + 1)]

        def cagr(t):
            return round(t[-1] ** (1 / len(t)) - 1, 4)

        return {
            REF: {"g_vre": round(vre_pp, 4), "g_mmgd": cagr(traj_mmgd),
                  "g_load": cagr(traj_load), "flex_gw": 0.0,
                  "traj": {"vre": traj_vre, "mmgd": traj_mmgd, "load": traj_load},
                  "source": "carga global e MMGD: 2ª RQ do PLAN 2026-2030 (ONS/EPE/"
                            "CCEE, ano a ano); eólica + solar: PAR/PEL 2025"},
            "PAR/PEL 2025": {"g_vre": round(vre_pp, 4), "g_mmgd": round(mm_pmo, 4),
                             "g_load": round(load_pp, 4), "flex_gw": 0.0,
                             "source": "PAR/PEL 2025: MMGD 46,2 → 65,3 GW (2029); "
                                       "carga máxima +17% até 2030"},
            "tendência observada": {"g_vre": v(r["vre_last"], 0.10),
                                    "g_mmgd": v(r["mmgd_12m"], 0.15),
                                    "g_load": v(r["load_6y"], 0.03), "flex_gw": 0.0,
                                    "source": "extrapolação das séries — só contraste"},
        }

    # ------------------------------------------------------------ payloads
    def ene_payload(self, custom: dict | None = None) -> dict:
        base = self._ene_base()
        scen = self.ene_default_scenarios()
        if custom:
            scen["personalizado"] = dict({k: v for k, v in scen[REF].items()
                                          if k != "traj"}, **custom,
                                         source="taxas informadas na tela")
        key = str(sorted((k, str(v)) for k, v in scen.items()))
        cls = type(self)
        if cls._ene_cache.get("scen_key") != key:
            cls._ene_cache["scen"] = M.scenarios_payload(
                base["Xref"], base["params"], scen, config.ENE["anos"])
            cls._ene_cache["scen_key"] = key
        proj = cls._ene_cache["scen"]
        d = cls._ene_data
        mon = d["cut"]["monthly"]
        hist = [{"month": k, "label": "%s/%s" % (MES[int(k[5:]) - 1], k[2:4]),
                 "es_eol_twh": round(v["es_eol"] / 1e6, 3),
                 "es_fv_twh": round(v["es_fv"] / 1e6, 3),
                 "total_twh": round((v["fv"] + v["eol"]) / 1e6, 3),
                 "ene_twh": round(v["reason"].get("ENE", 0.0) / 1e6, 3)}
                for k, v in mon.items()]
        X = base["Xref"]
        ref_year = int(base["ref"]["to"][:4]) if base["ref"]["to"] else 2026
        nl = (X["sup"] - X["vre_pot"]).mean(axis=0)
        es_ref = float(X["es"].sum()) / 1e6
        ref_bess = M.bess_potential(X["es"])
        th = base["params"]["theta"]
        last12 = hist[-12:]
        prev12 = hist[-24:-12]
        g_obs = (sum(h["es_eol_twh"] + h["es_fv_twh"] for h in last12) /
                 sum(h["es_eol_twh"] + h["es_fv_twh"] for h in prev12) - 1) \
            if len(prev12) == 12 and sum(h["es_eol_twh"] + h["es_fv_twh"] for h in prev12) else None
        mm = d["mmgd"]
        return {
            "history": hist,
            "fv_start": "%04d-%02d" % S.HISTORY_START["fv"],
            "reference": dict(base["ref"], ene_twh=round(es_ref, 2),
                              bess=ref_bess, year=ref_year),
            "observed_growth": round(g_obs, 4) if g_obs is not None else None,
            "params": {"alpha": base["params"]["alpha"],
                       "theta_gw": [round(th[m] / 1000, 2) for m in range(1, 13)]},
            "backtest": base["backtest"],
            "rates": base["rates"],
            "scenarios": proj,
            "years": [ref_year + k for k in range(1, config.ENE["anos"] + 1)],
            "duck_ref": {"nl_mw": [round(float(v), 0) for v in nl],
                         "es_mw": [round(float(v), 0) for v in X["es"].mean(axis=0)],
                         "theta_mean_mw": round(float(np.mean(list(th.values()))), 0)},
            "mmgd_series": {"months": mm["months"][-72:],
                            "cumulative_gw": mm["cumulative_gw"][-72:]},
            "allocation": self._ene_allocation(proj),
            "premises": _premises(),
            "parpel": dict(config.ENE["parpel"]),
            "plan": {k: v for k, v in config.ENE["plan"].items()},
            "reference_scenario": REF,
        }

    def _ene_allocation(self, proj: list[dict]) -> list[dict]:
        """Rateio indicativo do BESS de referencia no ultimo ano pelos sitios."""
        ref = next((p for p in proj if p["name"] == REF), None)
        if not ref:
            return []
        gw = (ref["years"][-1]["bess"] or {}).get("p_gw") or 0.0
        try:
            rows = self._bs()
        except Exception:
            return []
        tot = sum(getattr(r["site"], "es_mwh", 0.0) for r in rows) or 1.0
        rows = sorted(rows, key=lambda r: -getattr(r["site"], "es_mwh", 0.0))[:10]
        return [{"code": r["site"].code, "name": r["site"].name, "uf": r["site"].uf,
                 "share": round(getattr(r["site"], "es_mwh", 0.0) / tot, 4),
                 "gw": round(gw * getattr(r["site"], "es_mwh", 0.0) / tot, 2)}
                for r in rows]


def _minus_months(ym: str, n: int) -> str:
    y, m = int(ym[:4]), int(ym[5:7])
    m -= n
    while m <= 0:
        y, m = y - 1, m + 12
    return "%04d-%02d" % (y, m)


def _premises() -> list[dict]:
    E = config.ENE
    return [
        {"k": "Modelo", "v": "corte = α · máx(0, θ_mês − carga líquida)"},
        {"k": "Carga líquida", "v": "supervisionada − (eólica + solar) POTENCIAIS"},
        {"k": "Calibração", "v": "desde %s (FV publicada)" % E["inicio_calibracao"]},
        {"k": "Backtest", "v": "ajuste antes de %s, teste depois" % E["corte_backtest"]},
        {"k": "Ano de referência", "v": "últimos 12 meses observados (clima e perfil)"},
        {"k": "BESS no SIN", "v": "ciclo marginal ≥ %d/ano · %s GW × %s h" % (
            config.BESS["ciclos_min_ano"],
            "–".join(("%g" % E["potencias_gw"][0], "%g" % E["potencias_gw"][-1])),
            "/".join("%g" % h for h in E["duracoes_h"]))},
        {"k": "Transmissão e flexibilidade", "v": "constantes no cenário base (flex = 0)"},
        {"k": "Nível da MMGD", "v": "perfil do envelope escalado para a MMGD média "
                                    "oficial do ano base (PLAN)"},
    ]


def _demo_data() -> dict:
    """Series sinteticas deterministicas: uma curva do pato que se aprofunda."""
    rng = np.random.default_rng(config.RANDOM_SEED + 11)
    hours = np.arange(24)
    solar = np.clip(np.sin(np.pi * (hours - 6) / 12), 0, None)
    bal, hes, hall, monthly = {}, {}, {}, {}
    day = np.datetime64("2024-04-01")
    for i in range(760):
        d = str(day + i)
        m = int(d[5:7])
        growth = 1 + 0.0006 * i
        sup = 70000 + 8000 * np.sin(np.pi * (hours - 4) / 16) + rng.normal(0, 800, 24)
        eol = (14000 + 4000 * np.cos(np.pi * (hours - 3) / 12)) * growth
        sol = 22000 * solar * growth * (0.8 + 0.4 * rng.random())
        theta = 42000 + 3000 * np.cos(2 * np.pi * (m - 3) / 12)
        es = 0.8 * np.maximum(0, theta - (sup - eol - sol))
        bal[d] = {"sup": sup, "eol": eol - 0.3 * es, "sol": sol - 0.7 * es}
        hes[d] = es
        hall[d] = es * 1.3
        ym = d[:7]
        mo = monthly.setdefault(ym, {"fv": 0.0, "eol": 0.0, "es_fv": 0.0, "es_eol": 0.0,
                                     "reason": {"ENE": 0.0}})
        mo["es_fv"] += float(es.sum()) * 0.7
        mo["es_eol"] += float(es.sum()) * 0.3
        mo["fv"] += float(es.sum()) * 0.9
        mo["eol"] += float(es.sum()) * 0.4
        mo["reason"]["ENE"] += float(es.sum())
    months = ["%04d-%02d" % (2019 + k // 12, k % 12 + 1) for k in range(90)]
    cum = [round(2.0 * 1.03 ** k, 3) for k in range(90)]
    return {"mode": "demo", "cut": {"hour_es": hes, "hour_all": hall, "monthly": monthly},
            "bal": bal, "mmgd": {"months": months, "cumulative_gw": cum,
                                 "added_mw": [0.0] * 90, "units": 0},
            "provenance": [{"dataset": "ene · gerador determinístico", "resource": "demo",
                            "url": "", "fetched_at": "", "rows": 0, "bytes_read": 0,
                            "mode": "demo", "lag_note": "Séries sintéticas."}],
            "months_loaded": 0}
