# -*- coding: utf-8 -*-
"""Fontes externas da correlacao fronteira T-D: ANEEL e IBGE.

O ONS publica a rede basica. A subestacao de DISTRIBUICAO (SED) nao esta no
Portal do ONS: esta na BDGD da ANEEL. A camada geografica da BDGD (ArcGIS) e
bloqueada pelo proxy corporativo, mas o pacote BDGD no CKAN da ANEEL publica
as unidades consumidoras de media e alta tensao, e cada uma traz o codigo da
SED que a atende (`SUB`), o alimentador, a classe, 12 meses de energia e de
demanda, o vinculo com a GD (`CEG_GD`) e a coordenada. A SED e reconstruida
a partir das cargas que ela atende::

    UCMT_PJ.csv / UCAT_PJ.csv  (BDGD)   -> SED: posicao, energia e demanda
                                           por classe, municipios atendidos
    empreendimento-geracao-distribuida  -> MMGD por municipio e por SED
    SAMP                                -> baixa tensao por distribuidora
    IBGE SIDRA 6579 + malha municipal   -> populacao e centroide

PRIVACIDADE. O cadastro de GD traz CPF/CNPJ e nome do titular; a BDGD traz
endereco. Nenhum desses campos e lido para alem do necessario, e nada
granular e persistido: o arquivo bruto vai para um diretorio temporario e e
apagado depois da agregacao. So o agregado entra no cache.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import tempfile
import unicodedata
import zipfile
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .. import config

try:
    import httpx
except ImportError:  # pragma: no cover
    httpx = None  # type: ignore

# ------------------------------------------------------------ recursos
# Identificadores estaveis do CKAN da ANEEL. A URL de download e resolvida por
# `package_show` na hora (muda quando a ANEEL republica); estes sao o recuo.
PKG_BDGD = "base-de-dados-geografica-da-distribuidora-bdgd"
PKG_GD = "relacao-de-empreendimentos-de-geracao-distribuida"
PKG_SAMP = "samp"
RES_UCMT = "ucmt_pj.csv"
RES_UCAT = "ucat_pj.csv"
RES_GD = "empreendimento-geracao-distribuida.zip"

FALLBACK_URLS = {
    RES_UCMT: "https://dadosabertos.aneel.gov.br/dataset/4459e483-451f-4444-"
              "8022-bd8b5eac05c5/resource/f6671cba-f269-42ef-8eb3-62cb3bfa0b98/"
              "download/ucmt_pj.csv",
    RES_UCAT: "https://dadosabertos.aneel.gov.br/dataset/4459e483-451f-4444-"
              "8022-bd8b5eac05c5/resource/4318d38a-0bcd-421d-afb1-fb88b0c92a87/"
              "download/ucat_pj.csv",
    RES_GD: "https://dadosabertos.aneel.gov.br/dataset/5e0fafd2-21b9-4d5b-"
            "b622-40438d40aba2/resource/b1bd71e7-d0ad-4214-9053-cbd58e9564a7/"
            "download/empreendimento-geracao-distribuida.zip",
}

# Codigo IBGE da UF (dois primeiros digitos do municipio) -> sigla.
UF_IBGE = {
    "11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP",
    "17": "TO", "21": "MA", "22": "PI", "23": "CE", "24": "RN", "25": "PB",
    "26": "PE", "27": "AL", "28": "SE", "29": "BA", "31": "MG", "32": "ES",
    "33": "RJ", "35": "SP", "41": "PR", "42": "SC", "43": "RS", "50": "MS",
    "51": "MT", "52": "GO", "53": "DF",
}

CLASSES = ("residencial", "comercial", "industrial", "rural")


def uf_of_mun(mun: str) -> str:
    return UF_IBGE.get(str(mun)[:2], "")


def norm(s: str) -> str:
    """Maiusculas sem acento, espacos colapsados."""
    s = unicodedata.normalize("NFKD", str(s or ""))
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return " ".join(s.upper().split())


def classe_clm(codigo_ou_nome: str) -> str:
    """Classe ANEEL (codigo BDGD ou descricao do cadastro/SAMP) -> classe CLM."""
    n = norm(codigo_ou_nome)
    if n.startswith("REBR"):
        return "residencial"          # residencial baixa renda
    for pref, alvo in (("RESID", "residencial"), ("COMERC", "comercial"),
                       ("INDUST", "industrial"), ("RURAL", "rural")):
        if n.startswith(pref):
            return alvo
    return config.CLASSE_CLM.get(n[:2], "comercial")


def _f(v: str) -> float:
    """Numero em ponto ou virgula decimal; vazio e lixo viram 0."""
    if not v:
        return 0.0
    try:
        return float(v.replace(",", ".")) if "," in v else float(v)
    except ValueError:
        return 0.0


# ------------------------------------------------------------ rede
@dataclass
class Download:
    path: Path
    url: str
    sha256: str
    bytes_read: int
    fetched_at: str

    def provenance(self, dataset: str, resource: str, rows: int,
                   note: str) -> dict:
        return {"dataset": dataset, "resource": resource, "url": self.url,
                "fetched_at": self.fetched_at, "rows": int(rows),
                "bytes_read": int(self.bytes_read), "mode": "live",
                "lag_note": note, "sha256": self.sha256}


def _client(timeout: float | None = None):
    if httpx is None or config.FORCE_OFFLINE:
        raise ConnectionError("rede indisponível (offline ou sem httpx)")
    return httpx.Client(timeout=timeout or max(config.HTTP_TIMEOUT, 120.0),
                        follow_redirects=True)


def _now() -> str:
    from ..core.frame import Provenance
    return Provenance.now_iso()


def resolve_url(package: str, resource_name: str) -> str:
    """URL atual do recurso pelo CKAN da ANEEL, com recuo para a conhecida."""
    try:
        with _client(60.0) as c:
            r = c.get(config.ANEEL_CKAN_BASE + "/package_show",
                      params={"id": package})
            r.raise_for_status()
            for res in r.json()["result"]["resources"]:
                url = res.get("url") or ""
                if url.rsplit("/", 1)[-1].lower() == resource_name.lower():
                    return url
    except Exception:
        pass
    return FALLBACK_URLS.get(resource_name, "")


def download(url: str, tmpdir: Path, progress=None) -> Download:
    """Baixa em streaming para arquivo temporario, com hash."""
    dest = tmpdir / url.rsplit("/", 1)[-1]
    h = hashlib.sha256()
    n = 0
    with _client() as c, c.stream("GET", url) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length") or 0)
        with open(dest, "wb") as fh:
            for chunk in r.iter_bytes(1 << 20):
                fh.write(chunk)
                h.update(chunk)
                n += len(chunk)
                if progress and total:
                    progress(n / total)
    return Download(dest, url, h.hexdigest(), n, _now())


TEMP_PREFIX = "oraculo-fronteira-"


def temp_dir() -> Path:
    """Diretorio para os brutos, varrendo antes os restos de execucoes mortas.

    Se o processo cai no meio do download, o `finally` de `build` nao roda e
    ~160 MB de dado granular ficariam no disco. Resto com mais de uma hora e
    de construcao que nao terminou: e apagado.
    """
    root = Path(tempfile.gettempdir())
    import time as _t
    for old in root.glob(TEMP_PREFIX + "*"):
        try:
            if old.is_dir() and _t.time() - old.stat().st_mtime > 3600:
                cleanup(old)
        except OSError:
            pass
    return Path(tempfile.mkdtemp(prefix=TEMP_PREFIX))


# ------------------------------------------------------------ BDGD
def aggregate_uc(path: Path, *, tensao: str) -> dict:
    """Agrega UCMT/UCAT por SED. Le so as colunas necessarias.

    Chave da SED: `DIST|SUB` -- o codigo `SUB` e unico dentro da
    distribuidora, nao no pais. Somente UCs ativas (`SIT_ATIV == AT`).
    Energia em kWh/ano (soma dos 12 meses); demanda em kW (maximo mensal da
    UC, somado entre UCs: demanda NAO coincidente).
    """
    seds: dict[str, dict] = {}
    rep = {"rows": 0, "inactive": 0, "no_sub": 0, "no_point": 0, "used": 0}
    # A BDGD mistura codificacoes no mesmo arquivo; os campos usados sao ASCII.
    with open(path, encoding="utf-8", errors="replace", newline="") as fh:
        rd = csv.reader(fh, delimiter=";")
        head = next(rd)
        ix = {k: i for i, k in enumerate(head)}
        at = tensao == "AT"
        ene = ([("ENE_P_%02d" % m, "ENE_F_%02d" % m) for m in range(1, 13)]
               if at else [("ENE_%02d" % m, None) for m in range(1, 13)])
        dem = ([("DEM_P_%02d" % m, "DEM_F_%02d" % m) for m in range(1, 13)]
               if at else [("DEM_%02d" % m, None) for m in range(1, 13)])
        ene = [(ix[a], ix[b] if b else None) for a, b in ene]
        dem = [(ix[a], ix[b] if b else None) for a, b in dem]
        i_d, i_s, i_m = ix["DIST"], ix["SUB"], ix["MUN"]
        i_c, i_g, i_a = ix["CLAS_SUB"], ix["CEG_GD"], ix["SIT_ATIV"]
        i_x, i_y, i_ci = ix["POINT_X"], ix["POINT_Y"], ix["CAR_INST"]
        for r in rd:
            rep["rows"] += 1
            if len(r) < len(head):
                continue
            if r[i_a].strip() != "AT":
                rep["inactive"] += 1
                continue
            sub = r[i_s].strip()
            if not sub:
                rep["no_sub"] += 1
                continue
            lon, lat = _f(r[i_x]), _f(r[i_y])
            if not (-34.5 <= lat <= 6.0 and -74.5 <= lon <= -28.0):
                rep["no_point"] += 1
                continue
            key = r[i_d].strip() + "|" + sub
            s = seds.get(key)
            if s is None:
                s = seds[key] = {
                    "dist": r[i_d].strip(), "sub": sub, "n_mt": 0, "n_at": 0,
                    "e_class": defaultdict(float), "n_class": defaultdict(int),
                    "e_month": np.zeros(12), "dem_kw": 0.0, "car_kw": 0.0,
                    "lat": [], "lon": [], "mun": defaultdict(int), "ceg": [],
                }
            s["n_at" if at else "n_mt"] += 1
            e = np.array([_f(r[a]) + (_f(r[b]) if b is not None else 0.0)
                          for a, b in ene])
            d = max((max(_f(r[a]), _f(r[b]) if b is not None else 0.0)
                     for a, b in dem), default=0.0)
            cls = classe_clm(r[i_c])
            s["e_class"][cls] += float(e.sum())
            s["n_class"][cls] += 1
            s["e_month"] += e
            s["dem_kw"] += d
            s["car_kw"] += _f(r[i_ci])
            s["lat"].append(lat)
            s["lon"].append(lon)
            s["mun"][r[i_m].strip()] += 1
            ceg = r[i_g].strip()
            if ceg:
                s["ceg"].append(ceg)
            rep["used"] += 1
    rep["seds"] = len(seds)
    return {"seds": seds, "report": rep}


def merge_uc(*parts: dict) -> dict:
    """Une os agregados de UCMT e UCAT numa unica tabela de SED."""
    out: dict[str, dict] = {}
    for p in parts:
        for k, s in p["seds"].items():
            t = out.get(k)
            if t is None:
                out[k] = s
                continue
            t["n_mt"] += s["n_mt"]
            t["n_at"] += s["n_at"]
            for c, v in s["e_class"].items():
                t["e_class"][c] += v
            for c, v in s["n_class"].items():
                t["n_class"][c] += v
            t["e_month"] = t["e_month"] + s["e_month"]
            t["dem_kw"] += s["dem_kw"]
            t["car_kw"] += s["car_kw"]
            t["lat"] += s["lat"]
            t["lon"] += s["lon"]
            for m, v in s["mun"].items():
                t["mun"][m] += v
            t["ceg"] += s["ceg"]
    return out


def finalize_seds(raw: dict[str, dict]) -> list[dict]:
    """Posicao robusta (mediana) e dispersao das UCs de cada SED."""
    out = []
    for key, s in sorted(raw.items()):
        lat = np.asarray(s["lat"])
        lon = np.asarray(s["lon"])
        la, lo = float(np.median(lat)), float(np.median(lon))
        dist = haversine_km(la, lo, lat, lon)
        muns = sorted(s["mun"].items(), key=lambda kv: -kv[1])
        ufs: dict[str, int] = defaultdict(int)
        for m, n in muns:
            ufs[uf_of_mun(m)] += n
        out.append({
            "key": key, "dist": s["dist"], "sub": s["sub"],
            "n_mt": s["n_mt"], "n_at": s["n_at"],
            "lat": round(la, 5), "lon": round(lo, 5),
            "spread_km": round(float(np.median(dist)), 2),
            "spread_p90_km": round(float(np.percentile(dist, 90)), 2),
            "uf": max(ufs.items(), key=lambda kv: kv[1])[0] if ufs else "",
            "e_class": {c: round(v, 1) for c, v in s["e_class"].items()},
            "n_class": dict(s["n_class"]),
            "e_month": [round(float(v), 1) for v in s["e_month"]],
            "dem_kw": round(s["dem_kw"], 1),
            "car_kw": round(s["car_kw"], 1),
            "mun": {m: n for m, n in muns},
            "ceg": s["ceg"],
        })
    return out


# ------------------------------------------------------------ cadastro de GD
def aggregate_gd(zip_path: Path, ceg_to_sed: dict[str, str]) -> dict:
    """Agrega o cadastro de MMGD por municipio e, quando houver, por SED.

    O vinculo direto vem do `CEG_GD` da UC de media tensao -- a GD
    esta instalada naquela UC, e a UC pertence aquela SED. O resto da GD
    (microgeracao em baixa tensao, a maioria) so tem municipio.
    """
    mun: dict[str, dict] = {}
    sed_gd: dict[str, dict] = {}
    rep = {"rows": 0, "kw_total": 0.0, "kw_direct": 0.0, "n_direct": 0}
    with zipfile.ZipFile(zip_path) as z:
        name = next(n for n in z.namelist() if n.lower().endswith(".csv"))
        with z.open(name) as raw:
            fh = io.TextIOWrapper(raw, encoding="utf-8", errors="replace",
                                  newline="")
            rd = csv.reader(fh, delimiter=";")
            head = next(rd)
            ix = {k: i for i, k in enumerate(head)}
            i_m, i_cl = ix["CodMunicipioIbge"], ix["DscClasseConsumo"]
            i_kw, i_cod = ix["MdaPotenciaInstaladaKW"], ix["CodEmpreendimento"]
            i_src, i_cnpj = ix["SigTipoGeracao"], ix["NumCNPJDistribuidora"]
            i_sig, i_nom = ix["SigAgente"], ix["NomAgente"]
            for r in rd:
                if len(r) < len(head):
                    continue
                rep["rows"] += 1
                kw = _f(r[i_kw])
                cls = classe_clm(r[i_cl])
                ufv = r[i_src].strip().upper() == "UFV"
                rep["kw_total"] += kw
                sed = ceg_to_sed.get(r[i_cod].strip())
                if sed is not None:
                    g = sed_gd.setdefault(sed, {"n": 0, "kw": 0.0,
                                                "kw_ufv": 0.0,
                                                "kw_class": defaultdict(float)})
                    g["n"] += 1
                    g["kw"] += kw
                    g["kw_ufv"] += kw if ufv else 0.0
                    g["kw_class"][cls] += kw
                    rep["kw_direct"] += kw
                    rep["n_direct"] += 1
                code = r[i_m].strip()
                m = mun.get(code)
                if m is None:
                    m = mun[code] = {"n": 0, "kw": 0.0, "kw_ufv": 0.0,
                                     "kw_direct": 0.0,
                                     "kw_class": defaultdict(float),
                                     "dist": defaultdict(int)}
                m["n"] += 1
                m["kw"] += kw
                m["kw_ufv"] += kw if ufv else 0.0
                m["kw_class"][cls] += kw
                if sed is not None:
                    m["kw_direct"] += kw
                # distribuidora -> apenas o identificador PUBLICO da empresa
                m["dist"]["%s|%s|%s" % (r[i_cnpj].strip(), r[i_sig].strip(),
                                        r[i_nom].strip())] += 1
    for g in list(mun.values()) + list(sed_gd.values()):
        g["kw_class"] = {c: round(v, 2) for c, v in g["kw_class"].items()}
        for k in ("kw", "kw_ufv", "kw_direct"):
            if k in g:
                g[k] = round(g[k], 2)
    for m in mun.values():
        m["dist"] = dict(m["dist"])
    rep["kw_total"] = round(rep["kw_total"], 1)
    rep["kw_direct"] = round(rep["kw_direct"], 1)
    rep["municipios"] = len(mun)
    return {"mun": mun, "sed": sed_gd, "report": rep}


# ------------------------------------------------------------ SAMP
def fetch_samp(ano: int | None = None, progress=None) -> dict:
    """Energia de baixa tensao por distribuidora e classe (kWh/ano).

    Consulta filtrada pela API `datastore_search` do CKAN da ANEEL -- o CSV
    anual tem ~390 MB, a consulta traz ~70 mil linhas.
    """
    ano = ano or config.FRONTEIRA["samp_ano"]
    with _client() as c:
        r = c.get(config.ANEEL_CKAN_BASE + "/package_show",
                  params={"id": PKG_SAMP})
        r.raise_for_status()
        res = next(x for x in r.json()["result"]["resources"]
                   if x.get("name") == "samp-%d.csv" % ano)
        flt = {"DscDetalheMercado": "Energia TUSD (kWh)",
               "DscSubGrupoTarifario": list(config.FRONTEIRA["samp_subgrupos_bt"]),
               "NomTipoMercado": list(config.FRONTEIRA["samp_mercados"])}
        fields = ("NumCNPJAgenteDistribuidora,SigAgenteDistribuidora,"
                  "NomAgenteDistribuidora,DscClasseConsumoMercado,"
                  "DatCompetencia,VlrMercado")
        recs: list[dict] = []
        off, total = 0, None
        while total is None or off < total:
            q = c.get(config.ANEEL_CKAN_BASE + "/datastore_search", params={
                "resource_id": res["id"], "filters": json.dumps(flt),
                "fields": fields, "limit": 32000, "offset": off})
            q.raise_for_status()
            body = q.json()["result"]
            total = int(body["total"])
            recs += body["records"]
            off += 32000
            if progress and total:
                progress(min(1.0, off / total))
    out: dict[str, dict] = {}
    for x in recs:
        cnpj = str(x["NumCNPJAgenteDistribuidora"]).zfill(14)
        d = out.setdefault(cnpj, {"sigla": x["SigAgenteDistribuidora"],
                                  "nome": x["NomAgenteDistribuidora"],
                                  "kwh_class": defaultdict(float),
                                  "kwh_month": np.zeros(12)})
        v = _f(str(x["VlrMercado"]))
        d["kwh_class"][classe_clm(x["DscClasseConsumoMercado"])] += v
        mes = int(str(x["DatCompetencia"])[5:7])
        d["kwh_month"][mes - 1] += v
    for d in out.values():
        d["kwh_class"] = {c: round(v, 1) for c, v in d["kwh_class"].items()}
        d["kwh_month"] = [round(float(v), 1) for v in d["kwh_month"]]
    return {"dist": out, "resource": res["name"], "url": res.get("url", ""),
            "rows": len(recs)}


# ------------------------------------------------------------ IBGE
def fetch_population() -> dict:
    """Populacao estimada por municipio (SIDRA, tabela 6579, ultimo ano)."""
    url = config.IBGE_SIDRA_BASE + "/t/6579/n6/all/v/9324/p/last"
    with _client() as c:
        r = c.get(url)
        r.raise_for_status()
        rows = r.json()
    pop, ano = {}, ""
    for x in rows[1:]:
        try:
            pop[str(x["D1C"])] = int(x["V"])
            ano = x.get("D3N", ano)
        except (KeyError, ValueError):
            continue
    return {"pop": pop, "url": url, "ano": ano, "rows": len(pop)}


def fetch_centroids() -> dict:
    """Centroide de cada municipio, da malha oficial do IBGE (qualidade minima)."""
    url = (config.IBGE_MALHAS_BASE + "/paises/BR?formato=application/"
           "vnd.geo+json&intrarregiao=municipio&qualidade=minima")
    with _client() as c:
        r = c.get(url)
        r.raise_for_status()
        gj = r.json()
    out = {}
    for f in gj.get("features", []):
        code = str((f.get("properties") or {}).get("codarea", ""))
        c = polygon_centroid(f.get("geometry") or {})
        if code and c:
            out[code] = c
    return {"centroid": out, "url": url, "rows": len(out)}


def polygon_centroid(geom: dict) -> tuple[float, float] | None:
    """Centroide ponderado por area dos aneis externos (lat, lon)."""
    t = geom.get("type")
    polys = ([geom["coordinates"]] if t == "Polygon"
             else geom.get("coordinates", []) if t == "MultiPolygon" else [])
    A = cx = cy = 0.0
    for poly in polys:
        if not poly:
            continue
        ring = np.asarray(poly[0], dtype=float)
        if len(ring) < 3:
            continue
        x, y = ring[:, 0], ring[:, 1]
        x1, y1 = np.roll(x, -1), np.roll(y, -1)
        cr = x * y1 - x1 * y
        a = cr.sum() / 2.0
        if a == 0:
            continue
        A += a
        cx += ((x + x1) * cr).sum() / 6.0
        cy += ((y + y1) * cr).sum() / 6.0
    if A == 0:
        return None
    return (round(cy / A, 5), round(cx / A, 5))


# ------------------------------------------------------------ geometria
def haversine_km(lat1, lon1, lat2, lon2):
    """Distancia em km; aceita escalares ou arrays (com broadcast)."""
    la1, lo1 = np.deg2rad(lat1), np.deg2rad(lon1)
    la2, lo2 = np.deg2rad(lat2), np.deg2rad(lon2)
    a = (np.sin((la2 - la1) / 2) ** 2 +
         np.cos(la1) * np.cos(la2) * np.sin((lo2 - lo1) / 2) ** 2)
    return 6371.0 * 2.0 * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))


def cleanup(tmpdir: Path) -> None:
    """Apaga os brutos: o dado granular nao sobrevive a agregacao."""
    for p in tmpdir.glob("*"):
        try:
            p.unlink()
        except OSError:
            pass
    try:
        os.rmdir(tmpdir)
    except OSError:
        pass
