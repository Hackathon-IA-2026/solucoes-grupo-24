# -*- coding: utf-8 -*-
"""Frame colunar, tempo e calendario brasileiro."""
from __future__ import annotations

from datetime import date

import numpy as np
import pytest

from oraculo.core import calendar_br as cal
from oraculo.core import timeutils as T
from oraculo.core.frame import Frame, Provenance, _to_float, nan_to_none


# --------------------------------------------------------------- Frame
def test_frame_rejeita_colunas_de_tamanhos_diferentes():
    with pytest.raises(ValueError):
        Frame({"a": np.arange(3), "b": np.arange(4)})


def test_frame_operacoes_basicas():
    f = Frame({
        "area": np.array(["SE", "NE", "SE", "S"], dtype=object),
        "v": np.array([10.0, 20.0, 30.0, np.nan]),
    })
    assert len(f) == 4
    assert "area" in f
    assert f.eq("area", "SE")["v"].tolist() == [10.0, 30.0]
    assert sorted(f.unique("area").tolist()) == ["NE", "S", "SE"]
    assert f.select(["v"]).names == ["v"]
    with pytest.raises(KeyError):
        f.select(["inexistente"])


def test_frame_group_sum_ignora_nan():
    f = Frame({
        "area": np.array(["A", "A", "B"], dtype=object),
        "v": np.array([1.0, np.nan, 5.0]),
    })
    g = f.group_sum(["area"], ["v"])
    d = {r["area"]: r["v"] for r in g.to_records()}
    assert d["A"] == pytest.approx(1.0)
    assert d["B"] == pytest.approx(5.0)
    assert g["n"].tolist() == [2, 1]


def test_frame_dedupe_last_mantem_ultima_ocorrencia():
    f = Frame({
        "k": np.array(["x", "x", "y"], dtype=object),
        "v": np.array([1.0, 2.0, 3.0]),
    })
    out, dup = f.dedupe_last(["k"])
    assert dup == 1
    assert sorted(out["v"].tolist()) == [2.0, 3.0]


def test_frame_sort_e_join():
    a = Frame({"k": np.array(["b", "a"], dtype=object), "v": np.array([2.0, 1.0])})
    b = Frame({"k": np.array(["a", "b"], dtype=object), "w": np.array([10.0, 20.0])})
    s = a.sort_by("k")
    assert s["k"].tolist() == ["a", "b"]
    j = s.join_on(b, "k", ["w"])
    assert j["w"].tolist() == [10.0, 20.0]


def test_frame_to_records_serializa_nan_como_none():
    f = Frame({"v": np.array([1.5, np.nan])})
    recs = f.to_records()
    assert recs[0]["v"] == 1.5
    assert recs[1]["v"] is None


# --------------------- regra de qualidade: vazio vira NaN, nunca zero
@pytest.mark.parametrize("raw", ["", "  ", "-", "NA", "null", None])
def test_campo_vazio_vira_nan_nunca_zero(raw):
    v = _to_float(raw)
    assert np.isnan(v), "vazio virou %r; zerar inventaria informacao" % v


def test_to_float_aceita_decimal_com_ponto_e_virgula():
    assert _to_float("1234.5") == pytest.approx(1234.5)
    assert _to_float("1234,5") == pytest.approx(1234.5)


def test_nan_to_none():
    assert nan_to_none([1.0, float("nan")]) == [1.0, None]


# --------------------------------------------------------------- Provenance
def test_provenance_serializa_campos_obrigatorios():
    p = Provenance("ds", "res", "http://x", Provenance.now_iso(), 10, 20, "live", "nota")
    d = p.to_dict()
    for k in ("dataset", "resource", "url", "fetched_at", "rows", "bytes_read",
              "mode", "lag_note"):
        assert k in d


# --------------------------------------------------------------- tempo
def test_parse_instante_formato_do_ons():
    ts = T.parse_instante("2025-08-01 13:30:00")
    assert str(ts) == "2025-08-01T13:30:00"


@pytest.mark.parametrize("bad", ["", "xx", "2025-99-99 00:00:00"])
def test_parse_instante_invalido_vira_nat(bad):
    assert np.isnat(T.parse_instante(bad))


def test_hour_of_day_e_day_of_week():
    ts = np.array(["2026-09-14T00:00:00", "2026-09-14T13:00:00"], dtype="datetime64[s]")
    assert T.hour_of_day(ts).tolist() == [0, 13]
    # 14/09/2026 e uma segunda-feira
    assert T.day_of_week(ts).tolist() == [0, 0]


def test_reindex_hourly_preenche_lacuna_com_nan():
    ts = np.array(["2026-01-01T00:00:00", "2026-01-01T02:00:00"], dtype="datetime64[s]")
    grid, vals, gaps = T.reindex_hourly(ts, np.array([1.0, 3.0]))
    assert len(grid) == 3
    assert gaps == 1
    assert np.isnan(vals[1])


# --------------------------------------------------------------- calendario
def test_pascoa_datas_conhecidas():
    assert cal.easter(2024) == date(2024, 3, 31)
    assert cal.easter(2025) == date(2025, 4, 20)
    assert cal.easter(2026) == date(2026, 4, 5)


def test_feriados_moveis_derivados_da_pascoa():
    h = cal.holidays(2026)
    assert date(2026, 2, 16) in h            # Carnaval (segunda)
    assert date(2026, 4, 3) in h             # Sexta-feira Santa
    assert date(2026, 6, 4) in h             # Corpus Christi


def test_feriados_fixos():
    h = cal.holidays(2026)
    for d in (date(2026, 1, 1), date(2026, 9, 7), date(2026, 12, 25),
              date(2026, 11, 20)):
        assert d in h


def test_typeday_classifica_domingo_sabado_e_util():
    assert cal.typeday(date(2026, 9, 13)) == cal.TYPEDAY_SUNHOL   # domingo
    assert cal.typeday(date(2026, 9, 12)) == cal.TYPEDAY_SATURDAY
    assert cal.typeday(date(2026, 9, 14)) == cal.TYPEDAY_UTIL


def test_feriado_em_dia_util_conta_como_domingo_feriado():
    assert cal.typeday(date(2026, 9, 7)) == cal.TYPEDAY_SUNHOL
