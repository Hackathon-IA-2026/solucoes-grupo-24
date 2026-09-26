# -*- coding: utf-8 -*-
"""Leitor de CSV do ONS (delimitador ';', decimal '.').

Regras de qualidade aplicadas aqui, uma unica vez, para todo o sistema:
  - campo numerico vazio vira NaN, nunca zero;
  - registro com instante invalido e descartado e contabilizado;
  - ultima linha e descartada quando o download foi truncado por Range.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..core.frame import Frame, Provenance, _to_float
from ..core.timeutils import parse_instante


@dataclass
class ReadReport:
    rows: int = 0
    discarded_bad_time: int = 0
    discarded_short_line: int = 0
    duplicates: int = 0
    truncated_tail: bool = False
    columns: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "rows": self.rows,
            "discarded_bad_time": self.discarded_bad_time,
            "discarded_short_line": self.discarded_short_line,
            "duplicates": self.duplicates,
            "truncated_tail": self.truncated_tail,
            "columns": self.columns,
        }


def sniff_header(payload: bytes) -> list[str]:
    first = payload.split(b"\n", 1)[0]
    return [c.strip() for c in first.decode("utf-8", "replace").split(";")]


def read_csv(
    payload: bytes,
    *,
    schema: dict[str, str],
    time_column: str | None = "din_instante",
    provenance: Provenance | None = None,
    truncated: bool = False,
    filter_fn=None,
) -> tuple[Frame, ReadReport]:
    """Le o CSV em fluxo e devolve apenas as colunas do `schema`.

    `schema` mapeia nome_da_coluna -> tipo ("f8", "i8", "U", "M8[s]").
    `filter_fn(dict) -> bool` permite descartar linhas antes da materializacao,
    o que mantem o uso de memoria baixo em recursos de 15 MB.
    """
    rep = ReadReport(truncated_tail=truncated)
    if not payload:
        return Frame.empty(schema), rep

    text = payload.decode("utf-8", "replace")
    lines = text.split("\n")
    if not lines:
        return Frame.empty(schema), rep

    header = [c.strip() for c in lines[0].split(";")]
    rep.columns = header
    index = {name: i for i, name in enumerate(header)}
    wanted = [(name, index[name], kind) for name, kind in schema.items()
              if name in index]
    if not wanted:
        return Frame.empty(schema), rep

    body = lines[1:]
    if truncated and body:
        body = body[:-1]          # linha possivelmente cortada pelo Range
        rep.truncated_tail = True

    ncols = len(header)
    buckets: dict[str, list] = {name: [] for name, _, _ in wanted}
    t_idx = index.get(time_column) if time_column else None

    for raw in body:
        if not raw or raw.isspace():
            continue
        parts = raw.rstrip("\r").split(";")
        if len(parts) < ncols:
            rep.discarded_short_line += 1
            continue
        if t_idx is not None:
            ts = parse_instante(parts[t_idx])
            if np.isnat(ts):
                rep.discarded_bad_time += 1
                continue
        if filter_fn is not None:
            row = {name: parts[i] for name, i, _ in wanted}
            if not filter_fn(row):
                continue
        for name, i, _ in wanted:
            buckets[name].append(parts[i])
        rep.rows += 1

    cols: dict[str, np.ndarray] = {}
    for name, _, kind in wanted:
        vals = buckets[name]
        if kind.startswith("M8"):
            cols[name] = np.array([parse_instante(v) for v in vals],
                                  dtype="datetime64[s]")
        elif kind.startswith("f"):
            arr = np.empty(len(vals), dtype="f8")
            for i, v in enumerate(vals):
                arr[i] = _to_float(v)
            cols[name] = arr
        elif kind.startswith("i"):
            arr = np.zeros(len(vals), dtype="i8")
            for i, v in enumerate(vals):
                try:
                    arr[i] = int(v)
                except (TypeError, ValueError):
                    arr[i] = 0
            cols[name] = arr
        else:
            cols[name] = np.array([v.strip() for v in vals], dtype=object)

    frame = Frame(cols, [provenance] if provenance else [])
    frame.quality.update(rep.to_dict())
    return frame, rep
