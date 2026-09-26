# -*- coding: utf-8 -*-
"""Cache em disco com manifesto de proveniencia.

Garante ingestao idempotente e auditavel: cada recurso baixado registra URL,
instante de extracao, tamanho e hash. E a base da regra "nenhum alerta sem
evidencia rastreavel".
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

from ..config import CACHE_DIR, CACHE_TTL_SECONDS

MANIFEST_NAME = "manifest.json"


def _key(url: str, suffix: str = "") -> str:
    h = hashlib.sha256((url + suffix).encode("utf-8")).hexdigest()[:24]
    return h


def cache_dir() -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR


def manifest_path() -> Path:
    return cache_dir() / MANIFEST_NAME


def load_manifest() -> dict:
    p = manifest_path()
    if not p.exists():
        return {"entries": {}}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return {"entries": {}}


def save_manifest(man: dict) -> None:
    manifest_path().write_text(
        json.dumps(man, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def path_for(url: str, suffix: str = "") -> Path:
    ext = ".json" if url.endswith(".json") or "api/3/action" in url else ".csv"
    return cache_dir() / (_key(url, suffix) + ext)


def is_fresh(url: str, suffix: str = "", ttl: int | None = None) -> bool:
    p = path_for(url, suffix)
    if not p.exists():
        return False
    ttl = CACHE_TTL_SECONDS if ttl is None else ttl
    if ttl <= 0:
        return True
    return (time.time() - p.stat().st_mtime) < ttl


def read(url: str, suffix: str = "") -> bytes | None:
    p = path_for(url, suffix)
    if not p.exists():
        return None
    try:
        return p.read_bytes()
    except OSError:
        return None


def write(url: str, payload: bytes, *, dataset: str = "", resource: str = "",
          suffix: str = "", note: str = "") -> dict:
    """Grava no cache e atualiza o manifesto. Devolve a entrada criada."""
    p = path_for(url, suffix)
    p.write_bytes(payload)
    entry = {
        "dataset": dataset,
        "resource": resource,
        "url": url,
        "file": p.name,
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "note": note,
    }
    man = load_manifest()
    man.setdefault("entries", {})[p.name] = entry
    save_manifest(man)
    return entry


def entry_for(url: str, suffix: str = "") -> dict | None:
    return load_manifest().get("entries", {}).get(path_for(url, suffix).name)


def stats() -> dict:
    man = load_manifest()
    entries = man.get("entries", {})
    total = 0
    for e in entries.values():
        try:
            total += int(e.get("bytes", 0))
        except (TypeError, ValueError):
            pass
    return {"entries": len(entries), "bytes": total, "dir": str(cache_dir())}


def all_entries() -> list[dict]:
    entries = list(load_manifest().get("entries", {}).values())
    entries.sort(key=lambda e: e.get("fetched_at", ""), reverse=True)
    return entries


def clear() -> int:
    """Remove arquivos de cache. Devolve quantos foram apagados."""
    n = 0
    d = cache_dir()
    for f in d.glob("*"):
        if f.name == MANIFEST_NAME:
            continue
        try:
            os.remove(f)
            n += 1
        except OSError:
            pass
    save_manifest({"entries": {}})
    return n
