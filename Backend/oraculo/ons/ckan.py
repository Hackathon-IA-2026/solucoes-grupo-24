# -*- coding: utf-8 -*-
"""Cliente do Portal de Dados Abertos do ONS (CKAN + recursos em S3).

Degradacao graciosa e requisito, nao cortesia: falha de rede nunca derruba a
aplicacao. Toda funcao devolve tambem o modo efetivo ("live", "cache", "demo").
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

from ..config import FORCE_OFFLINE, HTTP_TIMEOUT, ONS_CKAN_BASE
from . import cache

try:  # httpx esta presente no ambiente-alvo; a ausencia nao deve quebrar import
    import httpx
except ImportError:  # pragma: no cover
    httpx = None  # type: ignore


@dataclass
class FetchResult:
    payload: bytes
    mode: str          # live | cache | demo
    url: str
    bytes_read: int
    fetched_at: str
    error: str = ""

    @property
    def ok(self) -> bool:
        return bool(self.payload)


def network_available() -> bool:
    """Checagem barata de conectividade com o Portal."""
    if FORCE_OFFLINE or httpx is None:
        return False
    try:
        with httpx.Client(timeout=8.0, follow_redirects=True) as c:
            r = c.get(ONS_CKAN_BASE + "/package_list")
            return r.status_code == 200
    except Exception:
        return False


# ------------------------------------------------------------------ CKAN
def _ckan(action: str, params: dict | None = None, *, refresh: bool = False) -> FetchResult:
    url = "%s/%s" % (ONS_CKAN_BASE, action)
    if params:
        url += "?" + "&".join("%s=%s" % (k, v) for k, v in sorted(params.items()))
    if not refresh:
        blob = cache.read(url)
        if blob is not None and cache.is_fresh(url):
            ent = cache.entry_for(url) or {}
            return FetchResult(blob, "cache", url, len(blob),
                               ent.get("fetched_at", ""))
    if FORCE_OFFLINE or httpx is None:
        blob = cache.read(url)
        if blob is not None:
            ent = cache.entry_for(url) or {}
            return FetchResult(blob, "cache", url, len(blob), ent.get("fetched_at", ""))
        return FetchResult(b"", "demo", url, 0, "", "offline e sem cache")
    try:
        with httpx.Client(timeout=HTTP_TIMEOUT, follow_redirects=True) as c:
            r = c.get(url)
            r.raise_for_status()
            payload = r.content
        ent = cache.write(url, payload, dataset="ckan", resource=action,
                          note="API CKAN do Portal de Dados Abertos do ONS")
        return FetchResult(payload, "live", url, len(payload), ent["fetched_at"])
    except Exception as exc:  # rede instavel, proxy, DNS
        blob = cache.read(url)
        if blob is not None:
            ent = cache.entry_for(url) or {}
            return FetchResult(blob, "cache", url, len(blob),
                               ent.get("fetched_at", ""), str(exc)[:160])
        return FetchResult(b"", "demo", url, 0, "", str(exc)[:160])


def package_list(refresh: bool = False) -> tuple[list[str], str]:
    res = _ckan("package_list", refresh=refresh)
    if not res.ok:
        return [], res.mode
    try:
        return list(json.loads(res.payload)["result"]), res.mode
    except (ValueError, KeyError):
        return [], res.mode


def package_show(pkg_id: str, refresh: bool = False) -> tuple[dict, str]:
    res = _ckan("package_show", {"id": pkg_id}, refresh=refresh)
    if not res.ok:
        return {}, res.mode
    try:
        return json.loads(res.payload)["result"], res.mode
    except (ValueError, KeyError):
        return {}, res.mode


# ------------------------------------------------------------ recursos CSV
_YEAR_RE = re.compile(r"(20\d\d)(?:[_-](\d{2}))?")


def resource_period(name_or_url: str) -> tuple[int | None, int | None]:
    """Extrai (ano, mes) do nome do recurso, quando existirem."""
    m = _YEAR_RE.search(name_or_url)
    if not m:
        return None, None
    year = int(m.group(1))
    month = int(m.group(2)) if m.group(2) else None
    return year, month


def fetch_resource(url: str, *, dataset: str = "", resource: str = "",
                   max_bytes: int | None = None, refresh: bool = False) -> FetchResult:
    """Baixa um recurso, opcionalmente truncado por `Range` para agilizar.

    `max_bytes` limita o download dos recursos mensais de constrained-off
    (cerca de 15 MB cada). A ultima linha parcial e descartada pelo leitor CSV.
    """
    suffix = "" if max_bytes is None else "#%d" % max_bytes
    if not refresh:
        blob = cache.read(url, suffix)
        if blob is not None and cache.is_fresh(url, suffix):
            ent = cache.entry_for(url, suffix) or {}
            return FetchResult(blob, "cache", url, len(blob), ent.get("fetched_at", ""))
    if FORCE_OFFLINE or httpx is None:
        blob = cache.read(url, suffix)
        if blob is not None:
            ent = cache.entry_for(url, suffix) or {}
            return FetchResult(blob, "cache", url, len(blob), ent.get("fetched_at", ""))
        return FetchResult(b"", "demo", url, 0, "", "offline e sem cache")
    headers = {}
    if max_bytes:
        headers["Range"] = "bytes=0-%d" % (max_bytes - 1)
    try:
        with httpx.Client(timeout=HTTP_TIMEOUT, follow_redirects=True) as c:
            r = c.get(url, headers=headers)
            if r.status_code not in (200, 206):
                r.raise_for_status()
            payload = r.content
        ent = cache.write(url, payload, dataset=dataset, resource=resource,
                          suffix=suffix,
                          note="truncado em %s bytes" % max_bytes if max_bytes else "")
        return FetchResult(payload, "live", url, len(payload), ent["fetched_at"])
    except Exception as exc:
        blob = cache.read(url, suffix)
        if blob is not None:
            ent = cache.entry_for(url, suffix) or {}
            return FetchResult(blob, "cache", url, len(blob),
                               ent.get("fetched_at", ""), str(exc)[:160])
        return FetchResult(b"", "demo", url, 0, "", str(exc)[:160])
