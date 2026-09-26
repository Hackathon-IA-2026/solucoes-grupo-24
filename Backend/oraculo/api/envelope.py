# -*- coding: utf-8 -*-
"""Envelope de proveniencia obrigatorio (RNF-04).

A ausencia de `provenance` em qualquer resposta e falha de contrato, verificada
por teste. E a materializacao da regra "nenhum alerta sem evidencia
rastreavel".
"""
from __future__ import annotations

import json
import math
from typing import Any

from ..core.timeutils import now_iso

ERROR_CODES = ("BAD_REQUEST", "NOT_FOUND", "UPSTREAM_UNAVAILABLE",
               "INSUFFICIENT_DATA", "INTERNAL")


def ok(data: Any, *, mode: str, provenance: list[dict],
       notes: list[str] | None = None) -> dict:
    return {
        "ok": True,
        "mode": mode,
        "generated_at": now_iso(),
        "data": data,
        "provenance": provenance or [],
        "notes": notes or [],
    }


def error(code: str, message: str, hint: str = "") -> dict:
    if code not in ERROR_CODES:
        code = "INTERNAL"
    return {
        "ok": False,
        "generated_at": now_iso(),
        "error": {"code": code, "message": message, "hint": hint},
    }


def status_for(code: str) -> int:
    return {
        "BAD_REQUEST": 400,
        "NOT_FOUND": 404,
        "INSUFFICIENT_DATA": 422,
        "UPSTREAM_UNAVAILABLE": 503,
        "INTERNAL": 500,
    }.get(code, 500)


def sanitize(obj: Any) -> Any:
    """Torna o payload serializavel: NaN e Infinity viram null.

    `json.dumps` aceita NaN por padrao, mas `JSON.parse` do navegador nao.
    Sanitizar aqui evita uma classe inteira de falha silenciosa na interface.
    """
    if isinstance(obj, dict):
        return {str(k): sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [sanitize(v) for v in obj]
    if isinstance(obj, float):
        return None if (math.isnan(obj) or math.isinf(obj)) else obj
    if isinstance(obj, (str, int, bool)) or obj is None:
        return obj
    # numpy e outros escalares
    for attr in ("item",):
        if hasattr(obj, attr):
            try:
                return sanitize(getattr(obj, attr)())
            except Exception:
                break
    return str(obj)


def dumps(obj: Any) -> bytes:
    return json.dumps(sanitize(obj), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")
