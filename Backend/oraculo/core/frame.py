# -*- coding: utf-8 -*-
"""Tabela colunar minima sobre numpy.

Substitui pandas, que nao pode ser instalado no ambiente-alvo (proxy
corporativo com certificado proprio bloqueia o PyPI). O escopo e deliberadamente
pequeno: apenas as operacoes que os modulos de dominio realmente usam.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Any, Callable, Iterable, Sequence

import numpy as np


# --------------------------------------------------------------- proveniencia
@dataclass(frozen=True)
class Provenance:
    """Rastro de origem de uma serie. Acompanha o dado ate a tela."""

    dataset: str
    resource: str = ""
    url: str = ""
    fetched_at: str = ""
    rows: int = 0
    bytes_read: int = 0
    mode: str = "demo"  # live | cache | demo
    lag_note: str = ""

    @staticmethod
    def now_iso() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def to_dict(self) -> dict:
        return {
            "dataset": self.dataset,
            "resource": self.resource,
            "url": self.url,
            "fetched_at": self.fetched_at,
            "rows": int(self.rows),
            "bytes_read": int(self.bytes_read),
            "mode": self.mode,
            "lag_note": self.lag_note,
        }


@dataclass
class Frame:
    """Colunas de igual comprimento, com proveniencia e relatorio de qualidade."""

    columns: dict[str, np.ndarray]
    provenance: list[Provenance] = field(default_factory=list)
    quality: dict[str, int] = field(default_factory=dict)

    # ------------------------------------------------------------- fabrica
    def __post_init__(self) -> None:
        lengths = {len(v) for v in self.columns.values()}
        if len(lengths) > 1:
            raise ValueError(
                "colunas com comprimentos diferentes: %s"
                % {k: len(v) for k, v in self.columns.items()}
            )

    @classmethod
    def from_records(
        cls,
        records: Iterable[dict],
        schema: dict[str, str],
        provenance: Provenance | None = None,
    ) -> "Frame":
        """Constroi a partir de dicionarios, com esquema explicito.

        schema mapeia nome -> tipo ("f8", "i8", "U64", "M8[s]", "bool").
        """
        buckets: dict[str, list] = {k: [] for k in schema}
        n = 0
        for rec in records:
            for k in schema:
                buckets[k].append(rec.get(k))
            n += 1
        cols: dict[str, np.ndarray] = {}
        for k, kind in schema.items():
            cols[k] = _coerce(buckets[k], kind)
        f = cls(cols, [provenance] if provenance else [])
        f.quality.setdefault("rows", n)
        return f

    @classmethod
    def empty(cls, schema: dict[str, str]) -> "Frame":
        return cls({k: _coerce([], v) for k, v in schema.items()})

    # ------------------------------------------------------------- basico
    @property
    def names(self) -> list[str]:
        return list(self.columns.keys())

    def __len__(self) -> int:
        for v in self.columns.values():
            return int(len(v))
        return 0

    def __contains__(self, key: str) -> bool:
        return key in self.columns

    def __getitem__(self, key: str) -> np.ndarray:
        return self.columns[key]

    def get(self, key: str, default: np.ndarray | None = None) -> np.ndarray | None:
        return self.columns.get(key, default)

    def copy(self) -> "Frame":
        return Frame(
            {k: v.copy() for k, v in self.columns.items()},
            list(self.provenance),
            dict(self.quality),
        )

    # ------------------------------------------------------------- ops
    def select(self, names: Sequence[str]) -> "Frame":
        missing = [n for n in names if n not in self.columns]
        if missing:
            raise KeyError("colunas ausentes: %s" % missing)
        return Frame(
            {n: self.columns[n] for n in names}, list(self.provenance), dict(self.quality)
        )

    def add_column(self, name: str, values: np.ndarray) -> "Frame":
        values = np.asarray(values)
        if len(self) and len(values) != len(self):
            raise ValueError(
                "coluna %r tem %d linhas, frame tem %d" % (name, len(values), len(self))
            )
        cols = dict(self.columns)
        cols[name] = values
        return Frame(cols, list(self.provenance), dict(self.quality))

    def take(self, mask_or_idx: np.ndarray) -> "Frame":
        idx = np.asarray(mask_or_idx)
        if idx.dtype == bool:
            idx = np.flatnonzero(idx)
        return Frame(
            {k: v[idx] for k, v in self.columns.items()},
            list(self.provenance),
            dict(self.quality),
        )

    def where(self, predicate: Callable[["Frame"], np.ndarray]) -> "Frame":
        return self.take(predicate(self))

    def eq(self, column: str, value: Any) -> "Frame":
        return self.take(self.columns[column] == value)

    def between(self, column: str, lo: Any, hi: Any) -> "Frame":
        v = self.columns[column]
        return self.take((v >= lo) & (v <= hi))

    def sort_by(self, *columns: str, descending: bool = False) -> "Frame":
        keys = [self.columns[c] for c in reversed(columns)]
        order = np.lexsort(keys)
        if descending:
            order = order[::-1]
        return self.take(order)

    def unique(self, column: str) -> np.ndarray:
        return np.unique(self.columns[column])

    def group_sum(self, by: Sequence[str], value_cols: Sequence[str]) -> "Frame":
        """Soma value_cols agrupando por `by`, ignorando NaN."""
        return self._group(by, value_cols, np.nansum)

    def group_mean(self, by: Sequence[str], value_cols: Sequence[str]) -> "Frame":
        return self._group(by, value_cols, np.nanmean)

    def group_max(self, by: Sequence[str], value_cols: Sequence[str]) -> "Frame":
        return self._group(by, value_cols, np.nanmax)

    def _group(self, by, value_cols, fn) -> "Frame":
        by = list(by)
        keys = [self.columns[c] for c in by]
        composite = np.array(
            ["\x1f".join(str(k[i]) for k in keys) for i in range(len(self))],
            dtype=object,
        )
        uniq, inverse = np.unique(composite, return_inverse=True)
        out: dict[str, list] = {c: [] for c in by}
        aggs: dict[str, list] = {c: [] for c in value_cols}
        counts: list[int] = []
        for gi in range(len(uniq)):
            sel = inverse == gi
            first = int(np.flatnonzero(sel)[0])
            for c in by:
                out[c].append(self.columns[c][first])
            for c in value_cols:
                vals = self.columns[c][sel].astype("f8")
                if np.all(np.isnan(vals)):
                    aggs[c].append(np.nan)
                else:
                    aggs[c].append(float(fn(vals)))
            counts.append(int(sel.sum()))
        cols: dict[str, np.ndarray] = {}
        for c in by:
            cols[c] = np.asarray(out[c], dtype=self.columns[c].dtype)
        for c in value_cols:
            cols[c] = np.asarray(aggs[c], dtype="f8")
        cols["n"] = np.asarray(counts, dtype="i8")
        return Frame(cols, list(self.provenance), dict(self.quality))

    def join_on(self, other: "Frame", key: str, columns: Sequence[str]) -> "Frame":
        """Junta colunas de `other` alinhando por `key` (left join)."""
        lut = {k: i for i, k in enumerate(other.columns[key].tolist())}
        idx = np.array(
            [lut.get(k, -1) for k in self.columns[key].tolist()], dtype="i8"
        )
        cols = dict(self.columns)
        for c in columns:
            src = other.columns[c]
            if src.dtype.kind in "fi":
                dest = np.full(len(self), np.nan, dtype="f8")
                ok = idx >= 0
                dest[ok] = src[idx[ok]].astype("f8")
            else:
                dest = np.array(
                    [src[i] if i >= 0 else "" for i in idx], dtype=src.dtype
                )
            cols[c] = dest
        return Frame(cols, list(self.provenance) + list(other.provenance), dict(self.quality))

    def dedupe_last(self, by: Sequence[str]) -> tuple["Frame", int]:
        """Mantem a ultima ocorrencia por chave. Devolve (frame, colisoes)."""
        keys = [self.columns[c] for c in by]
        composite = np.array(
            ["\x1f".join(str(k[i]) for k in keys) for i in range(len(self))],
            dtype=object,
        )
        seen: dict[object, int] = {}
        for i, k in enumerate(composite):
            seen[k] = i
        keep = np.array(sorted(seen.values()), dtype="i8")
        return self.take(keep), int(len(self) - len(keep))

    # ------------------------------------------------------------- saida
    def to_records(self, limit: int | None = None) -> list[dict]:
        n = len(self) if limit is None else min(limit, len(self))
        out = []
        for i in range(n):
            rec = {}
            for k, v in self.columns.items():
                x = v[i]
                if isinstance(x, np.datetime64):
                    rec[k] = str(x)
                elif isinstance(x, (np.floating,)):
                    rec[k] = None if np.isnan(x) else float(x)
                elif isinstance(x, (np.integer,)):
                    rec[k] = int(x)
                elif isinstance(x, (np.bool_,)):
                    rec[k] = bool(x)
                else:
                    rec[k] = str(x)
            out.append(rec)
        return out

    def with_provenance(self, prov: Provenance) -> "Frame":
        return Frame(self.columns, list(self.provenance) + [prov], dict(self.quality))

    def provenance_dicts(self) -> list[dict]:
        return [p.to_dict() for p in self.provenance]


# --------------------------------------------------------------- helpers
def _coerce(values: list, kind: str) -> np.ndarray:
    if kind.startswith("M8"):
        return np.array(
            [np.datetime64(v, "s") if v is not None else np.datetime64("NaT")
             for v in values],
            dtype="datetime64[s]",
        )
    if kind.startswith("f"):
        out = np.empty(len(values), dtype="f8")
        for i, v in enumerate(values):
            out[i] = _to_float(v)
        return out
    if kind.startswith("i"):
        out = np.zeros(len(values), dtype="i8")
        for i, v in enumerate(values):
            try:
                out[i] = int(v)
            except (TypeError, ValueError):
                out[i] = 0
        return out
    if kind == "bool":
        return np.array([bool(v) for v in values], dtype=bool)
    return np.array(["" if v is None else str(v) for v in values], dtype=object)


def _to_float(v: Any) -> float:
    """Converte respeitando a regra: vazio vira NaN, nunca zero."""
    if v is None:
        return float("nan")
    if isinstance(v, (int, float, np.integer, np.floating)):
        return float(v)
    s = str(v).strip()
    if not s or s in {"-", "--", "NA", "N/A", "null", "None"}:
        return float("nan")
    s = s.replace(",", ".") if s.count(",") == 1 and s.count(".") == 0 else s
    try:
        return float(s)
    except ValueError:
        return float("nan")


def nan_to_none(seq: Iterable[float]) -> list:
    return [None if (x is None or np.isnan(x)) else round(float(x), 4) for x in seq]
