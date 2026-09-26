# -*- coding: utf-8 -*-
"""Series temporais da projecao do corte por razao energetica::

    constrained-off (ONS, mensal)    -> corte ENE+SIS horario do SIN, e o corte
                                        total (para a geracao POTENCIAL)
    balanco de energia (ONS, horario) -> carga supervisionada, eolica e solar
                                        centralizadas verificadas, SIN
    cadastro tecnico FV da MMGD       -> potencia conectada por mes (DatConexao):
    (ANEEL)                              a serie historica de crescimento da MMGD

O corte do ONS comeca em 10/2021 para a eolica e em 04/2024 para a
fotovoltaica. Antes disso o corte FV existia, mas nao e publicado: a serie do
SIN so e completa a partir de 04/2024, e o modelo so e calibrado ali.
"""
from __future__ import annotations

import csv
import io
import json
import time
import zipfile
from collections import defaultdict

import numpy as np

from .. import config
from ..bess import fontes as BF
from ..fronteira import fontes as FF
from ..ons import catalog, ckan, csvio

HISTORY_START = {"eol": (2021, 10), "fv": (2024, 4)}
PKG_GD = "relacao-de-empreendimentos-de-geracao-distribuida"
RES_GD_FV = "empreendimento-gd-informacoes-tecnicas-fotovoltaica.zip"


def month_range(y0: int, m0: int, y1: int, m1: int):
    y, m = y0, m0
    while (y, m) <= (y1, m1):
        yield y, m
        m += 1
        if m == 13:
            y, m = y + 1, 1


def history_months(last: tuple[int, int]) -> list[tuple[str, int, int]]:
    out = []
    for src, (y0, m0) in HISTORY_START.items():
        out += [(src, y, m) for y, m in month_range(y0, m0, *last)]
    return out


# ------------------------------------------------------------ corte
def cut_series(months: list[dict]) -> dict:
    """Corte do SIN por hora (ENE+SIS e total) e totais mensais por fonte/razao."""
    hour_es: dict[str, np.ndarray] = {}
    hour_all: dict[str, np.ndarray] = {}
    monthly: dict[str, dict] = defaultdict(lambda: {"fv": 0.0, "eol": 0.0,
                                                   "es_fv": 0.0, "es_eol": 0.0,
                                                   "reason": defaultdict(float)})
    for mo in months:
        ym = "%04d-%02d" % (mo["year"], mo["month"])
        for p in mo["points"].values():
            src = p["source"]
            monthly[ym][src] += p["e_cut"]
            for k, v in p["e_reason"].items():
                monthly[ym]["reason"][k] += v
            for key, store in (("days", hour_all), ("days_es", hour_es)):
                for d, arr in (p.get(key) or {}).items():
                    a = np.asarray(arr, dtype=float)
                    h = a.reshape(24, 2).mean(axis=1)          # MW medio da hora
                    store[d] = store[d] + h if d in store else h
            for arr in (p.get("days_es") or {}).values():
                monthly[ym]["es_" + src] += float(np.sum(arr)) * 0.5
    mon = {ym: {"fv": v["fv"], "eol": v["eol"], "es_fv": v["es_fv"],
                "es_eol": v["es_eol"], "reason": dict(v["reason"])}
           for ym, v in sorted(monthly.items())}
    return {"hour_es": hour_es, "hour_all": hour_all, "monthly": mon}


# ------------------------------------------------------------ balanco
def balanco_hourly(years: list[int]) -> dict:
    """SIN horario: carga supervisionada, eolica e solar verificadas (MW medio)."""
    out: dict[str, dict] = {}
    prov = []
    spec = catalog.CURATED["balanco"]
    for y in years:
        url = catalog.resource_url("balanco", y)
        res = ckan.fetch_resource(url, dataset=spec["package"],
                                  resource=url.rsplit("/", 1)[-1])
        if not res.ok:
            continue
        f, _ = csvio.read_csv(res.payload, schema=spec["schema"])
        sub = np.array(f["id_subsistema"])
        m = sub == "SIN"
        if not m.any():
            continue
        ts = np.array(f["din_instante"])[m]
        car = np.array(f["val_carga"], float)[m]
        eol = np.array(f["val_gereolica"], float)[m]
        sol = np.array(f["val_gersolar"], float)[m]
        days = np.datetime_as_string(ts.astype("datetime64[D]"))
        hours = (ts.astype("datetime64[h]") - ts.astype("datetime64[D]")).astype(int)
        for d, h, c, e, s in zip(days, hours, car, eol, sol):
            rec = out.get(d)
            if rec is None:
                rec = out[d] = {"sup": np.full(24, np.nan), "eol": np.full(24, np.nan),
                                "sol": np.full(24, np.nan)}
            rec["sup"][h], rec["eol"][h], rec["sol"][h] = c, e, s
        prov.append({"dataset": spec["package"], "resource": url.rsplit("/", 1)[-1],
                     "url": url, "fetched_at": res.fetched_at, "rows": int(m.sum()),
                     "bytes_read": res.bytes_read, "mode": res.mode,
                     "lag_note": "SIN horário: carga, eólica e solar verificadas."})
    return {"days": out, "provenance": prov}


# ------------------------------------------------------------ MMGD
def mmgd_history(*, refresh: bool = False) -> dict:
    """Potencia de MMGD fotovoltaica conectada por mes (ANEEL, DatConexao).

    Guardado agregado; o cadastro tecnico (~105 MB) nao e mantido.
    """
    p = BF.bess_dir() / "mmgd_conexoes.json"
    if p.exists() and not refresh and \
            time.time() - p.stat().st_mtime < config.FRONTEIRA_TTL_SECONDS:
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
    url = FF.resolve_url(PKG_GD, RES_GD_FV)
    tmp = FF.temp_dir()
    try:
        d = FF.download(url, tmp)
        kw: dict[str, float] = defaultdict(float)
        n = 0
        with zipfile.ZipFile(d.path) as z:
            name = next(x for x in z.namelist() if x.lower().endswith(".csv"))
            with z.open(name) as raw:
                fh = io.TextIOWrapper(raw, encoding="utf-8", errors="replace", newline="")
                rd = csv.reader(fh, delimiter=";")
                head = next(rd)
                ix = {k: i for i, k in enumerate(head)}
                i_d, i_p = ix["DatConexao"], ix["MdaPotenciaInstalada"]
                for r in rd:
                    if len(r) <= max(i_d, i_p):
                        continue
                    dt = r[i_d].strip()
                    if len(dt) < 7:
                        continue
                    kw[dt[:7]] += FF._f(r[i_p])
                    n += 1
    finally:
        FF.cleanup(tmp)
    months = sorted(kw)
    cum, acc = [], 0.0
    for ym in months:
        acc += kw[ym]
        cum.append(round(acc / 1e6, 4))                    # GW acumulados
    out = {"months": months, "added_mw": [round(kw[m] / 1e3, 1) for m in months],
           "cumulative_gw": cum, "units": n, "url": url,
           "fetched_at": d.fetched_at, "sha256": d.sha256}
    p.write_text(json.dumps(out), encoding="utf-8")
    return out


def growth_rate(months: list[str], cum: list[float], until: str, span: int = 12) -> float | None:
    """Crescimento em `span` meses ate `until` (inclusive), da serie acumulada."""
    if until not in months:
        return None
    i = months.index(until)
    if i - span < 0 or cum[i - span] <= 0:
        return None
    return cum[i] / cum[i - span] - 1.0
