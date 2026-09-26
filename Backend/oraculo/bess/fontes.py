# -*- coding: utf-8 -*-
"""Fontes da secao de alocacao de BESS: constrained-off do ONS e SIGA/ANEEL::

    restricao_coff_fotovoltaica / restricao_coff_eolica_usi  (ONS, mensal)
        -> por PONTO DE CONEXAO: corte apurado semi-horario, razao, origem,
           geracao e disponibilidade
    subestacao (ONS)                 -> coordenada do ponto, pelo codigo da SE
    modalidade-usina (ONS) + SIGA    -> coordenada, quando a SE e coletora
                                        privada e nao esta no cadastro do ONS

O corte e o campo oficial `val_geracaonaorealizadaapurada` (MW medio no
intervalo de 30 min), nao a diferenca referencia - geracao recalculada aqui.

Cada mes e agregado uma vez e guardado; a reconstrucao so baixa os meses que
faltam. O bruto (~70 MB por mes) nao e guardado.
"""
from __future__ import annotations

import csv
import io
import json
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

from .. import config
from ..fronteira import fontes as FF
from ..ons import cache, catalog, ckan

SOURCES = {
    "fv": {"key": "coff_fv", "package": "restricao_coff_fotovoltaica",
           "label": "fotovoltaica"},
    "eol": {"key": "coff_eol", "package": "restricao_coff_eolica_usi",
            "label": "eólica"},
}
PKG_SIGA = "siga-sistema-de-informacoes-de-geracao-da-aneel"
RES_SIGA = "siga-empreendimentos-geracao.csv"
HALF_HOURS = 48
# Versao do agregado mensal. v2 separa a serie do corte ENE+SIS (excedente
# energetico sistemico), a parte do corte que a MMGD pode explicar.
AGG_VERSION = 2


def bess_dir() -> Path:
    d = cache.cache_dir() / "bess"
    d.mkdir(parents=True, exist_ok=True)
    return d


def se_code(id_ponto: str) -> str:
    """Codigo da SE no ponto de conexao, de largura fixa (6 caracteres).

    `RNACT-500-A` -> RNACT; `MGJBA3500-A` -> MGJBA3 (Janauba 3, 500 kV).
    Separar pelo primeiro hifen erra justamente os codigos de 6 letras.
    """
    return str(id_ponto or "")[:6].rstrip("-").strip().upper()


def ponto_name(nom: str) -> str:
    """Nome da SE sem prefixo, tensao e barra.

    O ONS grafa o mesmo ponto de formas diferentes em cada conjunto:
    `PARACATU 4 - 500 kV (A)` no constrained-off, `SE Paracatu 4 500 kV` e
    `SE PARACATU 4 138,0 kV` em modalidade-usina, `ACU III500kVA` colado.
    """
    import re
    n = FF.norm(nom)
    n = re.sub(r"^(SE|UFV|UEE|SUBESTACAO)\s+", "", n)
    n = re.sub(r"\s*-?\s*\d{2,3}([.,]\d+)?\s*KV.*$", "", n)
    return n.strip(" -")


def _f(v: str) -> float:
    v = (v or "").strip()
    if not v:
        return 0.0
    try:
        return float(v.replace(",", ".")) if "," in v else float(v)
    except ValueError:
        return 0.0


# ------------------------------------------------------------ meses
def months_window(n: int, *, today: tuple[int, int] | None = None) -> list[tuple[int, int]]:
    """Os `n` ultimos meses COMPLETOS (o mes corrente esta parcial)."""
    if today is None:
        t = time.gmtime()
        today = (t.tm_year, t.tm_mon)
    y, m = today
    out = []
    for _ in range(n):
        m -= 1
        if m == 0:
            y, m = y - 1, 12
        out.append((y, m))
    return sorted(out)


def month_url(src: str, year: int, month: int) -> str:
    return catalog.resource_url(SOURCES[src]["key"], year, month)


# ------------------------------------------------------------ agregacao
def aggregate_month(payload: bytes | str | Path, src: str) -> dict:
    """Agrega um mes de constrained-off por ponto de conexao.

    Por ponto: energia cortada por razao e por origem, geracao verificada,
    disponibilidade maxima simultanea, usinas, e a serie semi-horaria do
    corte (MW medio) somente nos dias em que houve corte.
    """
    if isinstance(payload, (str, Path)):
        fh = open(payload, encoding="utf-8", errors="replace", newline="")
    else:
        fh = io.StringIO(payload.decode("utf-8", errors="replace"), newline="")
    points: dict[str, dict] = {}
    disp_ts: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    rep = {"rows": 0, "rows_cut": 0, "bad_time": 0}
    with fh:
        rd = csv.reader(fh, delimiter=";")
        head = next(rd)
        ix = {k: i for i, k in enumerate(head)}
        g = lambda r, k: r[ix[k]] if k in ix and ix[k] < len(r) else ""  # noqa: E731
        for r in rd:
            if len(r) < len(head) - 2:
                continue
            rep["rows"] += 1
            pid = g(r, "id_pontoconexao").strip()
            if not pid:
                continue
            ts = g(r, "din_instante").strip()
            if len(ts) < 16:
                rep["bad_time"] += 1
                continue
            day, hh, mm = ts[:10], int(ts[11:13]), int(ts[14:16])
            slot = hh * 2 + (1 if mm >= 30 else 0)
            p = points.get(pid)
            if p is None:
                p = points[pid] = {
                    "id": pid, "nom": g(r, "nom_pontoconexao").strip(),
                    "uf": g(r, "id_estado").strip(),
                    "subsystem": g(r, "id_subsistema").strip(),
                    "agentes": set(), "usinas": {}, "cegs": set(),
                    "e_cut": 0.0, "e_gen": 0.0,
                    "e_reason": defaultdict(float), "e_origin": defaultdict(float),
                    "days": {}, "days_es": {},
                }
            p["agentes"].add(g(r, "nom_agenteoperador").strip())
            p["usinas"][g(r, "id_ons").strip()] = g(r, "nom_usina").strip()
            ceg = g(r, "ceg").strip()
            if ceg and ceg != "-":
                p["cegs"].add(ceg)
            gen = _f(g(r, "val_geracao"))
            p["e_gen"] += gen * 0.5
            disp_ts[pid][ts] += _f(g(r, "val_disponibilidade"))
            cut = _f(g(r, "val_geracaonaorealizadaapurada"))
            if cut <= 0:
                continue
            rep["rows_cut"] += 1
            e = cut * 0.5
            p["e_cut"] += e
            p["e_reason"][g(r, "cod_razaorestricao").strip() or "?"] += e
            p["e_origin"][g(r, "cod_origemrestricao").strip() or "?"] += e
            arr = p["days"].get(day)
            if arr is None:
                arr = p["days"][day] = [0.0] * HALF_HOURS
            arr[slot] += cut
            # excedente energetico sistemico: o unico corte que a reducao de
            # carga liquida pela MMGD pode explicar
            if (g(r, "cod_razaorestricao").strip() == "ENE"
                    and g(r, "cod_origemrestricao").strip() == "SIS"):
                es = p["days_es"].get(day)
                if es is None:
                    es = p["days_es"][day] = [0.0] * HALF_HOURS
                es[slot] += cut
    out = {}
    for pid, p in points.items():
        dts = disp_ts.get(pid) or {}
        out[pid] = {
            "id": pid, "nom": p["nom"], "uf": p["uf"], "subsystem": p["subsystem"],
            "agentes": sorted(a for a in p["agentes"] if a),
            "usinas": p["usinas"], "cegs": sorted(p["cegs"]),
            "e_cut": round(p["e_cut"], 2), "e_gen": round(p["e_gen"], 2),
            "e_reason": {k: round(v, 2) for k, v in p["e_reason"].items()},
            "e_origin": {k: round(v, 2) for k, v in p["e_origin"].items()},
            "disp_max": round(max(dts.values()), 2) if dts else 0.0,
            "days": {d: [round(x, 2) for x in a] for d, a in p["days"].items()},
            "days_es": {d: [round(x, 2) for x in a] for d, a in p["days_es"].items()},
            "source": src,
        }
    return {"points": out, "report": rep, "v": AGG_VERSION}


def month_cache_path(src: str, year: int, month: int) -> Path:
    return bess_dir() / ("%s_%04d_%02d.json" % (src, year, month))


def month_is_current(src: str, year: int, month: int) -> bool:
    """O agregado do mes existe e esta na versao atual?"""
    p = month_cache_path(src, year, month)
    if not p.exists():
        return False
    try:
        return json.loads(p.read_text(encoding="utf-8")).get("v", 1) >= AGG_VERSION
    except (OSError, ValueError):
        return False


def load_month(src: str, year: int, month: int, *, refresh: bool = False,
               progress=None) -> dict:
    """Agregado do mes, do cache ou baixado e agregado agora."""
    p = month_cache_path(src, year, month)
    if p.exists() and not refresh:
        try:
            agg = json.loads(p.read_text(encoding="utf-8"))
            if agg.get("v", 1) >= AGG_VERSION:
                return agg
        except (OSError, ValueError):
            pass
    if config.FORCE_OFFLINE:
        raise ConnectionError("offline e sem agregado do mes %04d-%02d" % (year, month))
    url = month_url(src, year, month)
    tmp = FF.temp_dir()
    try:
        d = FF.download(url, tmp, progress)
        agg = aggregate_month(d.path, src)
    finally:
        FF.cleanup(tmp)
    agg["provenance"] = {
        "dataset": SOURCES[src]["package"], "resource": url.rsplit("/", 1)[-1],
        "url": url, "fetched_at": d.fetched_at, "rows": agg["report"]["rows"],
        "bytes_read": d.bytes_read, "mode": "live", "sha256": d.sha256,
        "lag_note": "Corte = val_geracaonaorealizadaapurada (MW médio, 30 min).",
    }
    agg["year"], agg["month"] = year, month
    p.write_text(json.dumps(agg, ensure_ascii=False), encoding="utf-8")
    return agg


# ------------------------------------------------------------ localizacao
def ons_substations() -> dict[str, dict]:
    """Todas as SEs do cadastro do ONS por codigo (sem a deduplicacao do registro)."""
    res = ckan.fetch_resource(catalog.resource_url("subestacao"),
                              dataset="subestacao", resource="SUBESTACAO.csv")
    if not res.ok:
        return {}
    rd = csv.reader(io.StringIO(res.payload.decode("utf-8", "replace")), delimiter=";")
    head = next(rd)
    ix = {k: i for i, k in enumerate(head)}
    out = {}
    for r in rd:
        if len(r) < len(head):
            continue
        la, lo = _f(r[ix["val_latitude"]]), _f(r[ix["val_longitude"]])
        if not (-34.5 <= la <= 6.0 and -74.5 <= lo <= -28.0):
            continue
        code = r[ix["id_subestacao"]].strip().upper()
        kv = _f(r[ix["val_niveltensao"]])
        prev = out.get(code)
        if prev is None or kv > prev["kv"]:
            out[code] = {"code": code, "name": r[ix["nom_subestacao"]].strip(),
                         "uf": r[ix["id_estado"]].strip(), "lat": la, "lon": lo,
                         "kv": kv, "agent": r[ix["nom_agente_principal"]].strip()}
    return out


def modalidade_cegs() -> dict[str, list[str]]:
    """Nome do ponto de conexao -> CEGs das usinas ligadas nele (ONS)."""
    res = ckan.fetch_resource(catalog.resource_url("modalidade"),
                              dataset="modalidade-usina",
                              resource="MODALIDADE_USINA.csv")
    if not res.ok:
        return {}
    rd = csv.reader(io.StringIO(res.payload.decode("utf-8", "replace")), delimiter=";")
    head = next(rd)
    ix = {k: i for i, k in enumerate(head)}
    out: dict[str, list[str]] = defaultdict(list)
    for r in rd:
        if len(r) < len(head):
            continue
        ceg = r[ix["ceg"]].strip()
        pc = ponto_name(r[ix["nom_pontoconexao"]])
        if ceg and pc:
            out[pc].append(ceg)
    return dict(out)


def siga_coordinates() -> dict[str, list[float]]:
    """CEG -> [lat, lon] (SIGA/ANEEL). Guardado agregado no cache."""
    p = bess_dir() / "siga_coords.json"
    if p.exists() and time.time() - p.stat().st_mtime < config.FRONTEIRA_TTL_SECONDS:
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
    url = FF.resolve_url(PKG_SIGA, RES_SIGA) or ""
    if not url:
        return {}
    tmp = FF.temp_dir()
    try:
        d = FF.download(url, tmp)
        raw = d.path.read_bytes()
    finally:
        FF.cleanup(tmp)
    txt = raw.decode("utf-8", errors="replace")
    if txt.count("�") > 50:
        txt = raw.decode("latin-1")
    rd = csv.reader(io.StringIO(txt), delimiter=";")
    head = [h.strip().strip('"') for h in next(rd)]
    ix = {k: i for i, k in enumerate(head)}
    out = {}
    for r in rd:
        if len(r) < len(head):
            continue
        la = _f(r[ix["NumCoordNEmpreendimento"]])
        lo = _f(r[ix["NumCoordEEmpreendimento"]])
        if not (-34.5 <= la <= 6.0 and -74.5 <= lo <= -28.0):
            continue
        out[r[ix["CodCEG"]].strip()] = [round(la, 5), round(lo, 5)]
    p.write_text(json.dumps(out), encoding="utf-8")
    return out


def ceg_key(ceg: str) -> str:
    """CEG sem o digito de versao final: UFV.RS.BA.034153-3.01 -> UFV.RS.BA.034153-3."""
    parts = str(ceg).strip().split(".")
    return ".".join(parts[:4]) if len(parts) >= 4 else str(ceg).strip()


def locate(points: dict[str, dict], ses: dict[str, dict],
           mod: dict[str, list[str]], siga: dict[str, list[float]]) -> dict[str, dict]:
    """Coordenada de cada ponto, com o metodo declarado.

    1. codigo da SE no cadastro do ONS (a SE da rede de operacao);
    2. usinas do ponto pelo nome em `modalidade-usina` -> CEG -> SIGA;
    3. CEG das proprias usinas no constrained-off -> SIGA.
    """
    siga_k = {ceg_key(k): v for k, v in siga.items()}
    out = {}
    for pid, p in points.items():
        se = ses.get(se_code(pid))
        if se is not None:
            out[pid] = {"lat": se["lat"], "lon": se["lon"], "method": "SE do ONS",
                        "se_name": se["name"], "se_code": se["code"]}
            continue
        cegs = list(mod.get(ponto_name(p.get("nom", ""))) or []) + list(p.get("cegs") or [])
        pts = [siga_k.get(ceg_key(c)) for c in cegs]
        pts = [x for x in pts if x]
        if pts:
            a = np.asarray(pts)
            out[pid] = {"lat": float(np.median(a[:, 0])), "lon": float(np.median(a[:, 1])),
                        "method": "usinas no SIGA (%d)" % len(pts),
                        "se_name": ponto_name(p.get("nom", "")), "se_code": se_code(pid)}
        else:
            out[pid] = {"lat": None, "lon": None, "method": "não localizado",
                        "se_name": ponto_name(p.get("nom", "")), "se_code": se_code(pid)}
    return out
