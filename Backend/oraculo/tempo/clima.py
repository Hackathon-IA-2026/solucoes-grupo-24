# -*- coding: utf-8 -*-
"""Previsao do tempo para a MMGD: modelos de IA e fisicos via Open-Meteo.

Provedores::

    ecmwf_aifs025_single   ECMWF AIFS -- modelo de IA (mesma familia do
                           FourCastNet do NVIDIA Earth-2 e do GraphCast)
    ecmwf_ifs025           ECMWF IFS -- modelo fisico de referencia
    gfs_seamless           NOAA GFS -- modelo fisico
    era5                   reanalise ERA5 -- a "verdade" para calibrar e validar

O NVIDIA Earth-2 (FourCastNet, CorrDiff) exige GPU + `earth2studio` (PyTorch)
ou um NIM com chave de API da NVIDIA. Nenhum dos dois esta disponivel neste
ambiente: o provedor existe como contrato, e `providers_status` diz por que
nao roda -- como o YOLO na secao de visao computacional. GraphCast esta no
Open-Meteo, mas nao produz radiacao, que e a variavel que importa aqui.

TLS. A rede corporativa intercepta HTTPS com uma CA propria, instalada no
repositorio do Windows. O cliente valida contra esse repositorio (o mesmo que
o navegador usa). A CA do proxy nao declara a extensao keyUsage, que o modo
ESTRITO do OpenSSL (padrao desde o Python 3.13) exige; so esse modo e
desligado. Cadeia e nome do servidor continuam verificados.
"""
from __future__ import annotations

import hashlib
import json
import ssl
import time

from .. import config
from ..bess import fontes as BF

try:
    import httpx
except ImportError:  # pragma: no cover
    httpx = None  # type: ignore

FORECAST = "https://api.open-meteo.com/v1/forecast"
HISTORICAL = "https://historical-forecast-api.open-meteo.com/v1/forecast"
ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"
HOURLY = "shortwave_radiation,temperature_2m"
TZ = "America/Sao_Paulo"

MODELS = {
    "ecmwf_aifs025_single": {"label": "ECMWF AIFS", "kind": "IA",
                             "note": "modelo de previsão por IA do ECMWF"},
    "ecmwf_ifs025": {"label": "ECMWF IFS", "kind": "físico",
                     "note": "modelo numérico de referência do ECMWF"},
    "gfs_seamless": {"label": "NOAA GFS", "kind": "físico",
                     "note": "modelo numérico global da NOAA"},
}


def ssl_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()          # no Windows: repositorios ROOT/CA
    if hasattr(ssl, "VERIFY_X509_STRICT"):
        ctx.verify_flags &= ~ssl.VERIFY_X509_STRICT
    return ctx


def providers_status() -> list[dict]:
    out = [dict(k=k, available=True, **v) for k, v in MODELS.items()]
    out.append({"k": "earth2", "label": "NVIDIA Earth-2 (FourCastNet / CorrDiff)",
                "kind": "IA", "available": False,
                "note": "requer GPU e earth2studio (PyTorch) ou NIM com chave de API "
                        "da NVIDIA; o proxy bloqueia o PyPI e não há GPU aqui. O "
                        "contrato do provedor é o mesmo: trocar é uma função."})
    out.append({"k": "gfs_graphcast025", "label": "GraphCast (DeepMind)", "kind": "IA",
                "available": False,
                "note": "disponível no Open-Meteo, mas não produz radiação solar."})
    return out


# ------------------------------------------------------------ cache
def _cache_path(url: str, params: dict):
    key = hashlib.sha256((url + json.dumps(params, sort_keys=True)).encode()).hexdigest()[:24]
    return BF.bess_dir().parent / "tempo" / (key + ".json")


def _get(url: str, params: dict, ttl: float) -> dict:
    p = _cache_path(url, params)
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists() and time.time() - p.stat().st_mtime < ttl:
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
    if httpx is None or config.FORCE_OFFLINE:
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
        raise ConnectionError("offline e sem previsão em cache")
    body = None
    with httpx.Client(timeout=180, follow_redirects=True, verify=ssl_context()) as c:
        for attempt in range(4):
            r = c.get(url, params=params)
            if r.status_code in (429, 500, 502, 503, 504) and attempt < 3:
                time.sleep(4 * (attempt + 1))        # servico gratuito: recua e tenta
                continue
            r.raise_for_status()
            body = r.json()
            break
    p.write_text(json.dumps(body), encoding="utf-8")
    return body


def _points_params(points: list[dict]) -> dict:
    return {"latitude": ",".join("%.3f" % p["lat"] for p in points),
            "longitude": ",".join("%.3f" % p["lon"] for p in points),
            "hourly": HOURLY, "timezone": TZ}


def _unpack(body, points: list[dict], models: list[str] | None) -> dict:
    """Resposta multi-local -> {modelo: {var: [n_pontos][n_horas]}, 'time': [...]}"""
    items = body if isinstance(body, list) else [body]
    out: dict = {"time": items[0]["hourly"]["time"]}
    keys = models or ["_"]
    for m in keys:
        out[m] = {}
        for var in HOURLY.split(","):
            col = var if models is None or len(keys) == 1 else "%s_%s" % (var, m)
            if col not in items[0]["hourly"]:
                col = var
            out[m][var] = [it["hourly"].get(col) for it in items]
    return out


CHUNK = 30


def _chunked(url: str, points: list[dict], extra: dict, ttl: float,
             models: list[str] | None) -> dict:
    """Divide os pontos em lotes (o servico recusa requisicoes grandes) e junta."""
    merged: dict | None = None
    for i in range(0, len(points), CHUNK):
        part = points[i:i + CHUNK]
        body = _get(url, dict(_points_params(part), **extra), ttl)
        u = _unpack(body, part, models)
        if merged is None:
            merged = u
            continue
        for m in (models or ["_"]):
            for var in merged[m]:
                merged[m][var] += u[m][var]
    return merged or {}


def forecast(points: list[dict], models: list[str], days: int = 7) -> dict:
    extra = {"models": ",".join(models), "forecast_days": days}
    return _chunked(FORECAST, points, extra, 3 * 3600, models)


def historical_forecast(points: list[dict], models: list[str], start: str,
                        end: str) -> dict:
    """Previsoes ARQUIVADAS: o que cada modelo previu para aqueles dias."""
    extra = {"models": ",".join(models), "start_date": start, "end_date": end}
    return _chunked(HISTORICAL, points, extra, 30 * 86400, models)


def era5(points: list[dict], start: str, end: str) -> dict:
    extra = {"start_date": start, "end_date": end}
    return _chunked(ARCHIVE, points, extra, 30 * 86400, None)
