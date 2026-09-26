# -*- coding: utf-8 -*-
"""Base agregada da correlacao fronteira T-D: construcao, cache e demo.

A base guarda somente AGREGADOS (por SED, por municipio, por distribuidora).
A associacao SED -> SE de fronteira nao e guardada: e recalculada a cada carga,
em milissegundos, sobre o registro do ONS -- assim uma mudanca de premissa em
`config.FRONTEIRA` vale na hora, sem reconstruir nada.

Modos, como no resto da aplicacao:

    live   baixa da ANEEL e do IBGE, agrega, grava o agregado no cache
    cache  le o agregado ja gravado (padrao quando fresco)
    demo   gerador deterministico em torno do registro demonstrativo

Arquivos baixados manualmente (quando o proxy bloquear o download) podem ser
postos em `ORACULO_FRONTEIRA_RAW`: `ucmt_pj.csv`, `ucat_pj.csv` e
`empreendimento-geracao-distribuida.zip` sao lidos de la em vez da rede.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import numpy as np

from .. import config
from ..ons import cache
from . import fontes as F
from .correlacao import dist_identity

BASE_VERSION = 1
BASE_NAME = "fronteira_base.json"
RAW_DIR = os.environ.get("ORACULO_FRONTEIRA_RAW", "")

STAGES = [
    ("ucmt", "BDGD · unidades de média tensão (UCMT)"),
    ("ucat", "BDGD · unidades de alta tensão (UCAT)"),
    ("gd", "ANEEL · cadastro de micro e minigeração distribuída"),
    ("samp", "ANEEL · SAMP, energia de baixa tensão por distribuidora"),
    ("ibge", "IBGE · população e malha municipal"),
    ("grava", "agregação e gravação no cache"),
]


def base_path() -> Path:
    return cache.cache_dir() / BASE_NAME


def load_cached() -> dict | None:
    p = base_path()
    if not p.exists():
        return None
    try:
        b = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if b.get("version") != BASE_VERSION:
        return None
    return b


def is_fresh(b: dict | None) -> bool:
    if not b:
        return False
    return (time.time() - float(b.get("built_ts", 0))) < config.FRONTEIRA_TTL_SECONDS


# ------------------------------------------------------------ construcao
def build(progress=None) -> dict:
    """Constroi a base a partir das fontes reais. Levanta excecao em falha."""
    def step(key: str, frac: float = 0.0) -> None:
        if progress:
            progress(key, frac)

    t0 = time.time()
    tmp = F.temp_dir()
    prov: list[dict] = []
    try:
        def get(res_name: str, pkg: str, key: str):
            if RAW_DIR and (Path(RAW_DIR) / res_name).exists():
                p = Path(RAW_DIR) / res_name
                return F.Download(p, "arquivo local: %s" % p, "",
                                  p.stat().st_size, F._now()), True
            url = F.resolve_url(pkg, res_name)
            return F.download(url, tmp, lambda f: step(key, 0.8 * f)), False

        step("ucmt")
        d_mt, local_mt = get(F.RES_UCMT, F.PKG_BDGD, "ucmt")
        step("ucmt", 0.85)
        mt = F.aggregate_uc(d_mt.path, tensao="MT")
        prov.append(_prov(d_mt, local_mt, "bdgd · UCMT_PJ", F.RES_UCMT,
                          mt["report"]["rows"],
                          "Unidades consumidoras de média tensão, pessoa "
                          "jurídica. Pessoa física não é publicada."))
        step("ucat")
        d_at, local_at = get(F.RES_UCAT, F.PKG_BDGD, "ucat")
        at = F.aggregate_uc(d_at.path, tensao="AT")
        prov.append(_prov(d_at, local_at, "bdgd · UCAT_PJ", F.RES_UCAT,
                          at["report"]["rows"],
                          "Unidades consumidoras de alta tensão."))
        seds = F.finalize_seds(F.merge_uc(mt, at))
        ceg_to_sed = {c: s["key"] for s in seds for c in s["ceg"]}
        for s in seds:
            s["n_ceg"] = len(s.pop("ceg"))

        step("gd")
        d_gd, local_gd = get(F.RES_GD, F.PKG_GD, "gd")
        step("gd", 0.85)
        gd = F.aggregate_gd(d_gd.path, ceg_to_sed)
        prov.append(_prov(d_gd, local_gd,
                          "relacao-de-empreendimentos-de-geracao-distribuida",
                          F.RES_GD, gd["report"]["rows"],
                          "Cadastro de MMGD. CPF/CNPJ e nome do titular não "
                          "são lidos; só o agregado é guardado."))
        F.cleanup(tmp)            # o bruto nao sobrevive a agregacao

        step("samp")
        samp = F.fetch_samp(progress=lambda f: step("samp", f))
        prov.append({"dataset": "samp", "resource": samp["resource"],
                     "url": samp["url"], "fetched_at": F._now(),
                     "rows": samp["rows"], "bytes_read": 0, "mode": "live",
                     "lag_note": "Consulta filtrada: Energia TUSD, baixa "
                                 "tensão, mercados Regular."})
        step("ibge")
        pop = F.fetch_population()
        cen = F.fetch_centroids()
        prov.append({"dataset": "ibge · sidra 6579", "resource": pop["ano"],
                     "url": pop["url"], "fetched_at": F._now(),
                     "rows": pop["rows"], "bytes_read": 0, "mode": "live",
                     "lag_note": "Estimativa populacional por município."})
        prov.append({"dataset": "ibge · malha municipal", "resource": "BR",
                     "url": cen["url"], "fetched_at": F._now(),
                     "rows": cen["rows"], "bytes_read": 0, "mode": "live",
                     "lag_note": "Centroide calculado da malha simplificada."})

        step("grava")
        base = {
            "version": BASE_VERSION, "mode": "live",
            "built_at": F._now(), "built_ts": time.time(),
            "build_seconds": round(time.time() - t0, 1),
            "seds": seds, "sed_gd": gd["sed"], "mun": gd["mun"],
            "samp": samp["dist"], "pop": pop["pop"],
            "centroid": {k: list(v) for k, v in cen["centroid"].items()},
            "provenance": prov,
            "report": {"ucmt": mt["report"], "ucat": at["report"],
                       "gd": gd["report"], "samp_rows": samp["rows"],
                       "pop_rows": pop["rows"], "centroids": cen["rows"]},
        }
        base["dist"] = dist_identity(seds, base["mun"])
        base_path().write_text(json.dumps(base, ensure_ascii=False),
                               encoding="utf-8")
        step("grava", 1.0)
        return base
    finally:
        F.cleanup(tmp)


def _prov(d: F.Download, local: bool, dataset: str, resource: str, rows: int,
          note: str) -> dict:
    p = d.provenance(dataset, resource, rows, note)
    if local:
        p["mode"] = "cache"
        p["lag_note"] = note + " Lido de arquivo local (ORACULO_FRONTEIRA_RAW)."
    return p


# ------------------------------------------------------------ demo
def demo_base(frontier: list) -> dict:
    """Base sintetica e deterministica em torno das SEs de fronteira dadas.

    Serve a suite de testes e a apresentacao sem rede. Os numeros NAO tem
    correspondencia com a rede real: o selo de modo demonstrativo acompanha.
    """
    rng = np.random.default_rng(config.RANDOM_SEED)
    seds: list[dict] = []
    mun: dict[str, dict] = {}
    pop: dict[str, int] = {}
    cent: dict[str, list] = {}
    sed_gd: dict[str, dict] = {}
    samp: dict[str, dict] = {}
    uf_code = {v: k for k, v in F.UF_IBGE.items()}
    season = 1.0 + 0.12 * np.cos(2 * np.pi * (np.arange(12) - 1) / 12.0)
    for j, f in enumerate(frontier):
        cnpj = "%014d" % (10_000_000_000_000 + j)
        sig = "DEMO-%s" % f.uf
        uf2 = uf_code.get(f.uf, "35")
        n_sed = 3 + int(rng.integers(0, 6))
        for k in range(n_sed):
            ang = rng.uniform(0, 2 * np.pi)
            r = rng.uniform(3, 45)
            la = f.lat + (r * np.cos(ang)) / 111.0
            lo = f.lon + (r * np.sin(ang)) / (111.0 * np.cos(np.deg2rad(f.lat)))
            m = "%s%05d" % (uf2, (j * 10 + k) % 99999)
            mix = rng.dirichlet([2.0, 3.0, 2.0, 1.0])
            e = float(rng.uniform(20, 400)) * 1e6
            n_uc = int(rng.integers(8, 120))
            key = "D%03d|S%02d" % (j, k)
            seds.append({
                "key": key, "dist": "D%03d" % j, "sub": "S%02d" % k,
                "n_mt": n_uc, "n_at": int(rng.integers(0, 3)),
                "lat": round(la, 5), "lon": round(lo, 5),
                "spread_km": round(float(rng.uniform(1, 6)), 2),
                "spread_p90_km": round(float(rng.uniform(6, 14)), 2),
                "uf": f.uf,
                "e_class": {c: round(e * w, 1) for c, w in zip(F.CLASSES, mix)},
                "n_class": {c: max(1, int(n_uc * w)) for c, w in zip(F.CLASSES, mix)},
                "e_month": [round(e / 12 * s / season.mean(), 1) for s in season],
                "dem_kw": round(e / 8760 / 0.55, 1),
                "car_kw": round(e / 8760 / 0.35, 1),
                "mun": {m: n_uc}, "n_ceg": int(rng.integers(0, 6)),
            })
            pop[m] = int(rng.integers(8_000, 400_000))
            cent[m] = [round(la, 5), round(lo, 5)]
            kw = float(pop[m]) * float(rng.uniform(0.05, 0.35))
            mix_gd = rng.dirichlet([6.0, 2.0, 0.6, 1.2])
            direct = kw * float(rng.uniform(0.05, 0.2))
            mun[m] = {"n": int(kw / 6), "kw": round(kw, 2),
                      "kw_ufv": round(kw * 0.98, 2), "kw_direct": round(direct, 2),
                      "kw_class": {c: round(kw * w, 2)
                                   for c, w in zip(F.CLASSES, mix_gd)},
                      "dist": {"%s|%s|Distribuidora demonstrativa %s"
                               % (cnpj, sig, f.uf): int(kw / 6)}}
            sed_gd[key] = {"n": int(direct / 60) + 1, "kw": round(direct, 2),
                           "kw_ufv": round(direct, 2),
                           "kw_class": {"comercial": round(direct * 0.7, 2),
                                        "industrial": round(direct * 0.3, 2)}}
        e_bt = float(rng.uniform(300, 3000)) * 1e6
        samp[cnpj] = {"sigla": sig, "nome": "Distribuidora demonstrativa %s" % f.uf,
                      "kwh_class": {"residencial": round(e_bt * 0.72, 1),
                                    "comercial": round(e_bt * 0.20, 1),
                                    "rural": round(e_bt * 0.06, 1),
                                    "industrial": round(e_bt * 0.02, 1)},
                      "kwh_month": [round(e_bt / 12 * s / season.mean(), 1)
                                    for s in season]}
    base = {"version": BASE_VERSION, "mode": "demo", "built_at": F._now(),
            "built_ts": time.time(), "build_seconds": 0.0,
            "seds": seds, "sed_gd": sed_gd, "mun": mun, "samp": samp,
            "pop": pop, "centroid": cent,
            "provenance": [{"dataset": "fronteira · gerador determinístico",
                            "resource": "demo", "url": "", "fetched_at": F._now(),
                            "rows": len(seds), "bytes_read": 0, "mode": "demo",
                            "lag_note": "Dados demonstrativos: sem "
                                        "correspondência com a rede real."}],
            "report": {"demo": True}}
    base["dist"] = dist_identity(seds, mun)
    return base
