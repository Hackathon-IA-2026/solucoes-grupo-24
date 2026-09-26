# -*- coding: utf-8 -*-
"""Fachada da previsao da curva do pato pelo tempo (radiacao x MMGD).

Mixin proprio (decisao D7). Roda em segundo plano: ERA5 de 12 meses para
calibrar, previsoes ARQUIVADAS dos modelos para o backtest e a previsao
operacional dos proximos dias. As respostas do Open-Meteo ficam em cache.
"""
from __future__ import annotations

import threading
import time
from datetime import date

import numpy as np

from .. import config
from ..fronteira import base as FB
from ..tempo import clima as W
from ..tempo import pato as P

_LOCK = threading.Lock()
ENSEMBLE = "média dos modelos"


def _d(x) -> str:
    return str(x)[:10]


class TempoMixin:
    """Estado da secao Curva do pato pelo tempo."""

    _tp_data: dict | None = None
    _tp_job: dict = {"state": "idle", "stage": "", "error": "", "started": 0.0}

    def tempo_status(self) -> dict:
        self._tp_ensure_started()
        j = dict(type(self)._tp_job)
        ready = type(self)._tp_data is not None
        return {"state": "ready" if ready and j["state"] != "building" else j["state"],
                "stage": j["stage"], "error": j["error"],
                "elapsed_s": round(time.time() - j["started"], 1)
                             if j["state"] == "building" else None,
                "mode": self.tempo_mode()}

    def tempo_mode(self) -> str:
        d = type(self)._tp_data
        return (d or {}).get("mode") or ("demo" if self._bs_demo() else "live")

    def _tp_ensure_started(self, force: bool = False) -> None:
        cls = type(self)
        with _LOCK:
            if cls._tp_job["state"] == "building":
                return
            if cls._tp_data is not None and not force:
                age = time.time() - cls._tp_data.get("built_ts", 0)
                if age < 3 * 3600 or cls._tp_data.get("mode") == "demo":
                    return
            if self._bs_demo():
                cls._tp_data = _demo()
                return
            if cls._tp_job["state"] == "error" and not force:
                return
            cls._tp_job = {"state": "building", "stage": "", "error": "",
                           "started": time.time()}
        threading.Thread(target=self._tp_build, daemon=True, name="tempo-build").start()

    def tempo_rebuild(self) -> dict:
        if self._bs_demo():
            raise ValueError("modo demonstrativo: não há o que reconstruir")
        type(self)._tp_job["state"] = "idle"
        self._tp_ensure_started(force=True)
        return self.tempo_status()

    def tempo_provenance(self) -> list[dict]:
        return list((type(self)._tp_data or {}).get("provenance") or [])

    def tempo_notes(self) -> list[str]:
        n = ["Previsão de tempo pelo Open-Meteo: ECMWF AIFS (IA), ECMWF IFS e NOAA "
             "GFS. NVIDIA Earth-2 não roda aqui (exige GPU ou chave de API).",
             "Carga supervisionada prevista = dia-tipo − β·ΔMMGD + γ·Δtemperatura, com "
             "β e γ estimados em janela de treino anterior ao teste."]
        if self.tempo_mode() == "demo":
            n.insert(0, "%s — tempo sintético." % config.DEMO_BANNER)
        return n

    # ------------------------------------------------------------ construcao
    def _tp_sup(self) -> dict:
        self.ensure()
        sup = {}
        for ss in P.SUBS:
            st = self.areas.get(ss)
            if st is None:
                continue
            ix = st.index
            ds = np.datetime_as_string(ix.astype("datetime64[D]"))
            hr = (ix.astype("datetime64[h]") - ix.astype("datetime64[D]")).astype(int)
            d = {}
            for dd, h, v in zip(ds, hr, st.series["carga_supervisionada"]):
                d.setdefault(str(dd), np.full(24, np.nan))[h] = v
            sup[ss] = {k: v for k, v in d.items() if np.isfinite(v).all()}
        return sup

    def _tp_build(self) -> None:
        cls = type(self)
        job = cls._tp_job
        try:
            job["stage"] = "células de MMGD"
            fb = FB.load_cached()
            if fb is None:
                raise RuntimeError("requer a base da seção Fronteira T–D (MMGD por município)")
            pts = P.clusters(fb["mun"], fb["centroid"], min_mw=100)
            sup = self._tp_sup()
            last_obs = max(sup["SE"])
            today = _d(date.today())
            plan = config.ENE["plan"]
            target = {ss: v for ss, v in config.TEMPO["mmgd_mwmed_ss"].items()}
            ref_start = _d(np.datetime64(last_obs) - np.timedelta64(365, "D"))
            era_end = _d(np.datetime64(today) - np.timedelta64(config.TEMPO["era5_lag_dias"], "D"))
            job["stage"] = "ERA5: 12 meses para calibrar"
            era = W.era5(pts, ref_start, era_end)
            ref = {d for d in sup["SE"] if ref_start <= d <= era_end}
            pr = P.calibrate_pr(era, pts, target, ref)
            mm_era = P.mmgd_by_ss(era, "_", pts, pr)
            t_era = P.temp_by_ss(era, "_", pts)
            # dias recentes sem ERA5: completa com a previsao arquivada do IFS
            job["stage"] = "previsões arquivadas (AIFS, IFS, GFS)"
            models = list(W.MODELS)
            bt_start = _d(np.datetime64(last_obs) - np.timedelta64(config.TEMPO["backtest_dias"] + 21, "D"))
            hf = W.historical_forecast(pts, models, bt_start, last_obs)
            mm_hf = {m: P.mmgd_by_ss(hf, m, pts, pr) for m in models}
            t_hf = {m: P.temp_by_ss(hf, m, pts) for m in models}
            for ss in P.SUBS:
                for dd in mm_hf["ecmwf_ifs025"].get(ss, {}):
                    if dd not in mm_era[ss] and dd <= last_obs:
                        mm_era[ss][dd] = mm_hf["ecmwf_ifs025"][ss][dd]
                        t_era[ss][dd] = t_hf["ecmwf_ifs025"][ss][dd]
            job["stage"] = "sensibilidades β e γ (treino)"
            bt_first = _d(np.datetime64(last_obs) - np.timedelta64(config.TEMPO["backtest_dias"], "D"))
            train = [d for d in sorted(sup["SE"]) if ref_start < d < bt_first]
            sens = P.fit_sensitivity(sup, mm_era, t_era, train)
            methods = {W.MODELS[m]["label"]: (mm_hf[m], t_hf[m]) for m in models}
            methods[ENSEMBLE] = (_mean_ss([mm_hf[m] for m in models]),
                                 _mean_ss([t_hf[m] for m in models]))
            days = [d for d in sorted(sup["SE"]) if bt_first <= d <= last_obs]
            job["stage"] = "backtest"
            bt = P.backtest(sup, mm_era, t_era, methods, sens, days)
            job["stage"] = "previsão operacional (7 dias)"
            fc = W.forecast(pts, models, days=config.TEMPO["dias_previsao"])
            mm_fc = {m: P.mmgd_by_ss(fc, m, pts, pr) for m in models}
            t_fc = {m: P.temp_by_ss(fc, m, pts) for m in models}
            oper = self._tp_operational(sup, mm_era, t_era, mm_fc, t_fc, sens, last_obs,
                                        today)
            data = {
                "mode": "live", "built_ts": time.time(), "points": pts, "pr": pr,
                "sens": sens, "backtest": bt, "operational": oper,
                "last_obs": last_obs, "era_end": era_end, "ref_start": ref_start,
                "bt_days": [days[0], days[-1]] if days else [],
                "target_mwmed": target, "providers": W.providers_status(),
                "provenance": [
                    {"dataset": "Open-Meteo · ERA5 (reanálise)", "resource": "%s a %s" % (ref_start, era_end),
                     "url": W.ARCHIVE, "fetched_at": "", "rows": len(pts), "bytes_read": 0,
                     "mode": "live", "lag_note": "Calibração do PR e histórico do dia-tipo."},
                    {"dataset": "Open-Meteo · previsões arquivadas", "resource": "AIFS, IFS, GFS",
                     "url": W.HISTORICAL, "fetched_at": "", "rows": len(pts), "bytes_read": 0,
                     "mode": "live", "lag_note": "Backtest com o que cada modelo previu."},
                    {"dataset": "Open-Meteo · previsão", "resource": "AIFS, IFS, GFS · 7 dias",
                     "url": W.FORECAST, "fetched_at": "", "rows": len(pts), "bytes_read": 0,
                     "mode": "live", "lag_note": "Atualizada a cada 3 h."},
                    {"dataset": "2ª RQ do PLAN 2026-2030 (ONS/EPE/CCEE)",
                     "resource": "MMGD média por subsistema, 2026", "url": plan["url"],
                     "fetched_at": "", "rows": 4, "bytes_read": 0, "mode": "live",
                     "lag_note": "Nível oficial para calibrar o PR."},
                ],
            }
            with _LOCK:
                cls._tp_data = data
                cls._tp_job = {"state": "ready", "stage": "", "error": "", "started": 0.0}
        except Exception as exc:
            with _LOCK:
                cls._tp_job = {"state": "error", "stage": job.get("stage", ""),
                               "error": str(exc)[:300], "started": 0.0}

    def _tp_operational(self, sup, mm_era, t_era, mm_fc, t_fc, sens, last_obs,
                        today) -> dict:
        """Curva do pato prevista por dia, por subsistema e SIN, por modelo."""
        models = list(mm_fc)
        days = sorted(d for d in mm_fc[models[0]]["SE"] if d >= today)
        out = {}
        for ss in list(P.SUBS) + ["SIN"]:
            subs = P.SUBS if ss == "SIN" else (ss,)
            per_day = []
            for d in days:
                curves, mms = {}, {}
                for m in models:
                    fcs, mmv = [], []
                    for s in subs:
                        if d not in mm_fc[m].get(s, {}):
                            fcs = None
                            break
                        f = P.forecast_sup(sup[s], mm_era[s], t_era[s], mm_fc[m][s][d],
                                           t_fc[m][s][d], d, last_obs, sens[s])
                        if f is None:
                            fcs = None
                            break
                        fcs.append(f)
                        mmv.append(mm_fc[m][s][d])
                    if fcs:
                        curves[W.MODELS[m]["label"]] = sum(fcs)
                        mms[W.MODELS[m]["label"]] = sum(mmv)
                if not curves:
                    continue
                arr = np.array(list(curves.values()))
                ens = np.nanmean(arr, axis=0)
                mm_ens = np.nanmean(np.array(list(mms.values())), axis=0)
                imin = int(np.nanargmin(ens[P.BELLY])) + P.BELLY.start
                per_day.append({
                    "day": d,
                    "ensemble": [round(float(v), 0) for v in ens],
                    "low": [round(float(v), 0) for v in np.nanmin(arr, axis=0)],
                    "high": [round(float(v), 0) for v in np.nanmax(arr, axis=0)],
                    "models": {k: [round(float(x), 0) for x in v] for k, v in curves.items()},
                    "mmgd": [round(float(v), 0) for v in mm_ens],
                    "mmgd_models": {k: round(float(np.nanmax(v)), 0) for k, v in mms.items()},
                    "min_mw": round(float(ens[imin]), 0), "min_hour": imin,
                    "ramp_mw": round(float(np.nanmax(ens[17:22]) - ens[imin]), 0),
                    "mmgd_peak_mw": round(float(np.nanmax(mm_ens)), 0),
                    "spread_min_mw": round(float(np.nanmax(arr[:, imin]) - np.nanmin(arr[:, imin])), 0),
                })
            out[ss] = per_day
        return out

    # ------------------------------------------------------------ payload
    def tempo_payload(self) -> dict:
        self._tp_ensure_started()
        d = type(self)._tp_data
        if d is None:
            from .service_fronteira import BaseNotReady
            j = type(self)._tp_job
            if j["state"] == "error":
                raise BaseNotReady("falha ao montar a previsão: %s" % j["error"])
            raise BaseNotReady("previsão do tempo em construção")
        bt = d["backtest"]
        ser = bt.get("series_sin") or {}
        obs = ser.get("observado") or {}
        sample = sorted(obs)[-14:]
        return {
            "points": [{"ss": p["ss"], "lat": round(p["lat"], 3), "lon": round(p["lon"], 3),
                        "mw": round(p["mw"], 0), "mun": p["mun"]} for p in d["points"]],
            "pr": d["pr"], "sensitivity": d["sens"], "target_mwmed": d["target_mwmed"],
            "metrics": bt["metrics"],
            "backtest_window": d["bt_days"],
            "backtest_sample": {"days": sample,
                                "series": {k: [[round(float(x), 0) for x in v[day]]
                                               if day in v else None for day in sample]
                                           for k, v in ser.items()}},
            "operational": d["operational"],
            "last_obs": d["last_obs"], "era_end": d["era_end"],
            "providers": d["providers"],
            "premises": [
                {"k": "Modelo fotovoltaico", "v": "P = C·PR·G/1000·(1 − 0,004·(T + 0,03G − 25))"},
                {"k": "Células de MMGD", "v": "~2,5° por subsistema, ≥ 100 MW"},
                {"k": "Calibração do PR", "v": "ERA5 → MMGD média oficial do PLAN 2026"},
                {"k": "Carga prevista", "v": "dia-tipo − β·ΔMMGD + γ·ΔT"},
                {"k": "Dia-tipo", "v": "média das 2 últimas semanas, mesmo dia, sem feriado"},
                {"k": "Alinhamento", "v": "hora h do ONS ← rótulo h+1 do Open-Meteo"},
                {"k": "Backtest", "v": "%d dias com as previsões arquivadas" % config.TEMPO["backtest_dias"]},
            ],
        }


def _mean_ss(items: list[dict]) -> dict:
    out = {}
    for ss in P.SUBS:
        days = set.intersection(*[set(it.get(ss, {})) for it in items]) if items else set()
        out[ss] = {d: np.nanmean(np.array([it[ss][d] for it in items]), axis=0) for d in days}
    return out


def _demo() -> dict:
    """Previsao sintetica e deterministica para os testes e o modo offline."""
    rng = np.random.default_rng(config.RANDOM_SEED + 21)
    h = np.arange(24)
    solar = np.clip(np.sin(np.pi * (h - 6) / 12), 0, None)
    base = {"SE": 42000, "S": 13000, "NE": 12500, "N": 8500}
    mmx = {"SE": 12000, "S": 5000, "NE": 4500, "N": 1800}
    oper = {}
    for ss in list(P.SUBS) + ["SIN"]:
        rows = []
        for k in range(7):
            subs = P.SUBS if ss == "SIN" else (ss,)
            cloud = 0.5 + 0.5 * rng.random()
            load = sum(base[s] * (1 + 0.15 * np.sin(np.pi * (h - 4) / 16)) for s in subs)
            mm = sum(mmx[s] for s in subs) * solar * cloud
            ens = load - mm
            imin = int(np.argmin(ens[10:16])) + 10
            rows.append({"day": "2026-01-%02d" % (k + 1),
                         "ensemble": [round(float(v)) for v in ens],
                         "low": [round(float(v * 0.98)) for v in ens],
                         "high": [round(float(v * 1.02)) for v in ens],
                         "models": {"ECMWF AIFS": [round(float(v)) for v in ens]},
                         "mmgd": [round(float(v)) for v in mm],
                         "mmgd_models": {"ECMWF AIFS": round(float(mm.max()))},
                         "min_mw": round(float(ens[imin])), "min_hour": imin,
                         "ramp_mw": round(float(ens[17:22].max() - ens[imin])),
                         "mmgd_peak_mw": round(float(mm.max())), "spread_min_mw": 500})
        oper[ss] = rows
    met = {ss: {"persistência": {"days": 30, "mae_mid_mw": 2800, "mae_day_mw": 2000,
                                  "mae_min_mw": 2800, "bias_min_mw": -1200,
                                  "mae_ramp_mw": 2200, "mape_mid": 0.035},
                ENSEMBLE: {"days": 30, "mae_mid_mw": 2000, "mae_day_mw": 1500,
                           "mae_min_mw": 1800, "bias_min_mw": -500, "mae_ramp_mw": 1700,
                           "mape_mid": 0.025}}
           for ss in list(P.SUBS) + ["SIN"]}
    return {"mode": "demo", "built_ts": time.time(),
            "points": [{"ss": "SE", "lat": -23.5, "lon": -46.6, "mw": 5000.0, "mun": 40}],
            "pr": {ss: 0.8 for ss in P.SUBS},
            "sens": {ss: {"beta": 0.8, "gamma": 800.0, "r2": 0.3, "r2_mmgd_only": 0.02,
                          "n": 1000} for ss in P.SUBS},
            "backtest": {"metrics": met, "series_sin": {}}, "operational": oper,
            "last_obs": "2025-12-31", "era_end": "2025-12-31", "ref_start": "2025-01-01",
            "bt_days": ["2025-11-01", "2025-12-31"], "target_mwmed": {},
            "providers": W.providers_status(),
            "provenance": [{"dataset": "tempo · gerador determinístico", "resource": "demo",
                            "url": "", "fetched_at": "", "rows": 0, "bytes_read": 0,
                            "mode": "demo", "lag_note": "Tempo sintético."}]}
