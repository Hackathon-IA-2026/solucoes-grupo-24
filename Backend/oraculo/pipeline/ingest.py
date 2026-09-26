# -*- coding: utf-8 -*-
"""Ingestao: do Portal de Dados Abertos ao Frame canonico.

Orquestra ckan -> csvio -> Frame, com degradacao graciosa para o modo
demonstrativo e proveniencia registrada em cada etapa.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import numpy as np

from ..core.frame import Frame, Provenance
from ..core.timeutils import reindex_hourly
from ..demo import synthetic
from ..ons import catalog, ckan, csvio

# Limite de download dos recursos mensais de constrained-off (~15 MB cada).
COFF_MAX_BYTES = 6_000_000


@dataclass
class IngestReport:
    dataset: str
    resource: str
    mode: str
    rows: int = 0
    bytes_read: int = 0
    discarded_bad_time: int = 0
    discarded_short_line: int = 0
    duplicates: int = 0
    gaps: int = 0
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "dataset": self.dataset,
            "resource": self.resource,
            "mode": self.mode,
            "rows": self.rows,
            "bytes_read": self.bytes_read,
            "discarded_bad_time": self.discarded_bad_time,
            "discarded_short_line": self.discarded_short_line,
            "duplicates": self.duplicates,
            "gaps": self.gaps,
            "error": self.error,
        }


@dataclass
class Bundle:
    """Conjunto de dados carregado, pronto para o dominio."""

    balanco: Frame
    coff: Frame
    mode: str
    reports: list[IngestReport] = field(default_factory=list)

    def provenance(self) -> list[dict]:
        seen: set[tuple] = set()
        out: list[dict] = []
        for p in list(self.balanco.provenance) + list(self.coff.provenance):
            key = (p.dataset, p.resource, p.mode)
            if key in seen:
                continue
            seen.add(key)
            out.append(p.to_dict())
        return out

    def reports_dicts(self) -> list[dict]:
        return [r.to_dict() for r in self.reports]


def _default_year() -> int:
    return date.today().year


def _load_balanco_year(year: int, spec: dict, *, refresh: bool
                       ) -> tuple[Frame | None, IngestReport]:
    url = catalog.resource_url("balanco", year)
    name = catalog.resource_name("balanco", year)
    res = ckan.fetch_resource(url, dataset=spec["package"], resource=name,
                              refresh=refresh)
    if not res.ok:
        return None, IngestReport(spec["package"], name, "demo", error=res.error)
    prov = Provenance(spec["package"], name, url, res.fetched_at, 0,
                      res.bytes_read, res.mode, spec["lag_note"])
    frame, r = csvio.read_csv(res.payload, schema=spec["schema"],
                              provenance=prov, truncated=False)
    if len(frame) == 0:
        return None, IngestReport(spec["package"], name, res.mode,
                                  error="sem registros utilizáveis")
    frame.provenance[0] = Provenance(
        spec["package"], name, url, res.fetched_at, len(frame),
        res.bytes_read, res.mode, spec["lag_note"]
    )
    rep = IngestReport(spec["package"], name, res.mode, len(frame),
                       res.bytes_read, r.discarded_bad_time,
                       r.discarded_short_line)
    return frame, rep


def load_balanco(year: int | None = None, *, refresh: bool = False,
                 years_back: int = 1) -> tuple[Frame, list[IngestReport]]:
    """Balanco de energia nos subsistemas, horario.

    Carrega o ano corrente e `years_back` anteriores. Um ano completo de
    historico e necessario para IDENTIFICAR os harmonicos anuais da matriz de
    projeto: treinar com serie parcial deixa a sazonalidade nao identificada e
    produz vies sistematico na ponta quando o teste cai em outra estacao.
    """
    year = year or _default_year()
    spec = catalog.CURATED["balanco"]
    frames: list[Frame] = []
    reports: list[IngestReport] = []
    for y in range(year - years_back, year + 1):
        f, rep = _load_balanco_year(y, spec, refresh=refresh)
        reports.append(rep)
        if f is not None:
            frames.append(f)

    if not frames:
        f = synthetic.balanco_frame()
        reports.append(IngestReport(spec["package"], "gerador determinístico",
                                    "demo", rows=len(f)))
        return f, reports

    frame = _concat(frames)
    frame, dup = frame.dedupe_last(["id_subsistema", "din_instante"])
    if dup and reports:
        reports[-1].duplicates = dup
    return frame, reports


def load_coff(year: int | None = None, months: list[int] | None = None, *,
              source: str = "coff_fv", refresh: bool = False
              ) -> tuple[Frame, list[IngestReport]]:
    """Constrained-off por usina, semi-horario. Concatena varios meses."""
    year = year or _default_year()
    months = months or [8, 7]
    spec = catalog.CURATED[source]
    frames: list[Frame] = []
    reports: list[IngestReport] = []

    for pos, m in enumerate(months):
        url = catalog.resource_url(source, year, m)
        name = catalog.resource_name(source, year, m)
        # O recurso esta ordenado por usina: truncar por Range enviesaria a
        # amostra para as primeiras areas do alfabeto. O mes mais recente vem
        # completo; os anteriores podem ser truncados.
        limit = None if pos == 0 else COFF_MAX_BYTES
        res = ckan.fetch_resource(url, dataset=spec["package"], resource=name,
                                  max_bytes=limit, refresh=refresh)
        if not res.ok:
            reports.append(IngestReport(spec["package"], name, "demo",
                                        error=res.error))
            continue
        prov = Provenance(spec["package"], name, url, res.fetched_at, 0,
                          res.bytes_read, res.mode, spec["lag_note"])
        f, r = csvio.read_csv(res.payload, schema=spec["schema"],
                              provenance=prov, truncated=(limit is not None))
        if len(f) == 0:
            reports.append(IngestReport(spec["package"], name, res.mode,
                                        error="sem registros utilizáveis"))
            continue
        f.provenance[0] = Provenance(
            spec["package"], name, url, res.fetched_at, len(f),
            res.bytes_read, res.mode, spec["lag_note"]
        )
        frames.append(f)
        reports.append(IngestReport(spec["package"], name, res.mode, len(f),
                                    res.bytes_read, r.discarded_bad_time,
                                    r.discarded_short_line))

    if not frames:
        f = synthetic.coff_frame()
        reports.append(IngestReport(spec["package"], "gerador determinístico",
                                    "demo", rows=len(f)))
        return f, reports
    return _concat(frames), reports


def _concat(frames: list[Frame]) -> Frame:
    if len(frames) == 1:
        return frames[0]
    names = frames[0].names
    cols: dict[str, np.ndarray] = {}
    for n in names:
        cols[n] = np.concatenate([f[n] for f in frames])
    prov: list[Provenance] = []
    for f in frames:
        prov.extend(f.provenance)
    out = Frame(cols, prov)
    out.quality["rows"] = len(out)
    return out


def load_bundle(*, year: int | None = None, months: list[int] | None = None,
                refresh: bool = False, force_demo: bool = False) -> Bundle:
    """Carrega tudo o que o dominio precisa, num unico objeto."""
    if force_demo:
        b = synthetic.balanco_frame()
        c = synthetic.coff_frame()
        return Bundle(b, c, "demo", [
            IngestReport("balanco-energia-subsistema", "gerador determinístico",
                         "demo", rows=len(b)),
            IngestReport("restricao_coff_fotovoltaica", "gerador determinístico",
                         "demo", rows=len(c)),
        ])

    bal, rb = load_balanco(year, refresh=refresh)
    coff, rc = load_coff(year, months, refresh=refresh)
    modes = {r.mode for r in rb} | {r.mode for r in rc}
    mode = "live" if "live" in modes else ("cache" if "cache" in modes else "demo")
    return Bundle(bal, coff, mode, list(rb) + list(rc))


# ------------------------------------------------------------- series
def area_series(balanco: Frame, area: str) -> dict[str, np.ndarray]:
    """Extrai as series canonicas da area, numa grade horaria completa."""
    sub = balanco.eq("id_subsistema", area).sort_by("din_instante")
    if len(sub) == 0:
        return {}
    ts, carga, gaps = reindex_hourly(sub["din_instante"], sub["val_carga"])
    out: dict[str, np.ndarray] = {"index": ts, "carga_supervisionada": carga}
    for src, dst in (("val_gereolica", "ger_eolica"),
                     ("val_gersolar", "ger_solar_centralizada"),
                     ("val_gerhidraulica", "ger_hidraulica"),
                     ("val_gertermica", "ger_termica"),
                     ("val_intercambio", "intercambio")):
        if src in sub:
            _, v, _ = reindex_hourly(sub["din_instante"], sub[src])
            out[dst] = v
    if "ger_hidraulica" in out and "ger_termica" in out:
        out["margem_controlavel"] = out["ger_hidraulica"] + out["ger_termica"]
    out["_gaps"] = np.array([gaps])
    return out
