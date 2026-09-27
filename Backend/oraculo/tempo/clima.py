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

import numpy as np

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


def _points_params(points: list[dict], hourly: str = HOURLY) -> dict:
    return {"latitude": ",".join("%.3f" % p["lat"] for p in points),
            "longitude": ",".join("%.3f" % p["lon"] for p in points),
            "hourly": hourly, "timezone": TZ}


def _unpack(body, points: list[dict], models: list[str] | None,
            hourly: str = HOURLY) -> dict:
    """Resposta multi-local -> {modelo: {var: [n_pontos][n_horas]}, 'time': [...]}"""
    items = body if isinstance(body, list) else [body]
    out: dict = {"time": items[0]["hourly"]["time"]}
    keys = models or ["_"]
    for m in keys:
        out[m] = {}
        for var in hourly.split(","):
            col = var if models is None or len(keys) == 1 else "%s_%s" % (var, m)
            if col not in items[0]["hourly"]:
                col = var
            out[m][var] = [it["hourly"].get(col) for it in items]
    return out


CHUNK = 30


def _chunked(url: str, points: list[dict], extra: dict, ttl: float,
             models: list[str] | None, hourly: str = HOURLY) -> dict:
    """Divide os pontos em lotes (o servico recusa requisicoes grandes) e junta."""
    merged: dict | None = None
    for i in range(0, len(points), CHUNK):
        part = points[i:i + CHUNK]
        body = _get(url, dict(_points_params(part, hourly), **extra), ttl)
        u = _unpack(body, part, models, hourly)
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


def era5(points: list[dict], start: str, end: str, hourly: str = HOURLY,
         ttl: float = 30 * 86400, tz: str | None = None) -> dict:
    """ERA5 horario. `tz` troca o fuso da resposta (padrao TZ); o preditivo de meses usa
    "America/Bahia" (UTC-3 fixo, sem o horario de verao que o Brasil teve ate 2019)."""
    extra = {"start_date": start, "end_date": end}
    if tz:
        extra["timezone"] = tz
    return _chunked(ARCHIVE, points, extra, ttl, None, hourly)


# ------------------------------------------------- clima dos modelos de carga
# Variaveis que entram na matriz de projeto (grupo "clima" de
# features/builder.py): temperatura e ponto de orvalho, que dao o indice de
# desconforto (ar condicionado).
HOURLY_CARGA = "temperature_2m,dew_point_2m"
# Dias finais re-baixados com validade curta: o arquivo do Open-Meteo completa
# os dias recentes com a analise operacional do ECMWF e troca pelo ERA5 quando
# ele sai (~5 dias depois). O bloco antigo nao muda mais e fica 30 dias em cache.
RECENT_DAYS = 10


def weather_for_area(index: np.ndarray, area: str) -> tuple[dict | None, dict]:
    """Temperatura e ponto de orvalho REAIS na grade horaria `index` da area.

    Media ponderada (populacao) das capitais de config.WEATHER_POINTS, da
    reanalise ERA5 pelo arquivo do Open-Meteo (dias recentes: analise
    operacional do ECMWF, mesma rota). Substitui o proxy sintetico que o
    builder usava: o grupo "clima" dos modelos passa a ser observado.

    Devolve (tempo, proveniencia). Sem rede e sem cache -> (None, prov com o
    erro): o builder entao deixa o grupo clima de FORA em vez de inventar.
    """
    index = np.asarray(index, dtype="datetime64[s]")
    pts = config.WEATHER_POINTS.get(area) or config.WEATHER_POINTS["SIN"]
    prov = {"dataset": "Open-Meteo · ERA5 (reanálise) · temperatura e ponto de orvalho",
            "resource": "%s: %s" % (area, ", ".join(p["nome"] for p in pts)),
            "mode": "live", "rows": 0, "url": ARCHIVE}
    if len(index) == 0:
        return None, dict(prov, mode="demo", lag_note="série vazia")
    start = index.min().astype("datetime64[D]")
    end = index.max().astype("datetime64[D]")
    today = np.datetime64(time.strftime("%Y-%m-%d"), "D")
    # Corte ancorado no fim do mes anterior a (hoje - RECENT_DAYS): a chave do
    # cache do bloco antigo so muda uma vez por mes, em vez de todo dia.
    month0 = (today - np.timedelta64(RECENT_DAYS, "D")).astype("datetime64[M]")
    cut = min(end, month0.astype("datetime64[D]") - np.timedelta64(1, "D"))
    blocks = []
    try:
        if cut >= start:
            blocks.append(era5(pts, str(start), str(cut), HOURLY_CARGA))
        if end > cut:
            blocks.append(era5(pts, str(max(start, cut + np.timedelta64(1, "D"))),
                               str(end), HOURLY_CARGA, ttl=3 * 3600))
    except Exception as exc:  # rede/servico: sem tempo real, sem grupo clima
        return None, dict(prov, mode="demo", lag_note="sem tempo real: %s" % str(exc)[:160])

    w = np.array([p["peso"] for p in pts], dtype="f8")
    w = w / w.sum()
    times, temp, dew = [], [], []
    for b in blocks:
        times += b["time"]
        # [n_pontos][n_horas] -> media ponderada por hora (None -> NaN)
        t = np.array(b["_"]["temperature_2m"], dtype="f8")
        d = np.array(b["_"]["dew_point_2m"], dtype="f8")
        temp.append(np.nansum(t * w[:, None], axis=0) / np.sum(np.isfinite(t) * w[:, None], axis=0))
        dew.append(np.nansum(d * w[:, None], axis=0) / np.sum(np.isfinite(d) * w[:, None], axis=0))
    tt = np.array(times, dtype="datetime64[s]")
    temp_all, dew_all = np.concatenate(temp), np.concatenate(dew)
    # Alinha a grade horaria da serie (horario de Brasilia, mesmo fuso pedido
    # ao servico); hora ausente fica NaN e o builder a trata como invalida.
    pos = {int(v): i for i, v in enumerate(tt.astype("i8"))}
    idx = np.array([pos.get(int(v), -1) for v in index.astype("i8")])
    ok = idx >= 0
    out_t = np.full(len(index), np.nan)
    out_d = np.full(len(index), np.nan)
    out_t[ok] = temp_all[idx[ok]]
    out_d[ok] = dew_all[idx[ok]]
    prov["rows"] = int(ok.sum())
    prov["lag_note"] = ("ERA5 até %s; dias seguintes pela análise operacional "
                        "do ECMWF (mesma rota do Open-Meteo)." % cut)
    return {"temperature": out_t, "dewpoint": out_d}, prov
