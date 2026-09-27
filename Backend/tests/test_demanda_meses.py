"""Testes da demanda de meses (src/models/demanda_meses.py).

O principal é o de vazamento temporal (regra do CLAUDE.md): perturbar TUDO que vem depois da
emissão não pode mudar a previsão. Os dados são uma série sintética de teste (fixture), não
entram em nenhuma saída do projeto.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.models import demanda_meses as dm


@pytest.fixture(scope="module")
def cal() -> pd.DataFrame:
    """Calendário horário sintético de 2019 a 2027 (dia-tipo pelo dia da semana)."""
    ts = pd.date_range("2019-01-01", "2027-12-31 23:00", freq="h")
    dow = ts.dayofweek
    return pd.DataFrame({"timestamp": ts, "dia_tipo": pd.Series(dow).map(dm.DIA_TIPO).to_numpy(),
                         "patamar": np.where((ts.hour >= 9) & (ts.hour < 16), "minima_diurna", "outro"),
                         "mes": ts.month, "hora": ts.hour})


@pytest.fixture(scope="module")
def serie(cal) -> pd.DataFrame:
    """Demanda de teste: tendência + sazonalidade anual + ciclo diário + ruído, até 2026-09."""
    c = cal[cal["timestamp"] < "2026-09-26"].copy()
    rng = np.random.default_rng(0)
    anos = (c["timestamp"] - pd.Timestamp("2019-01-01")) / dm.ANO
    c["y"] = (60000 * 1.03 ** anos + 3000 * np.sin(2 * np.pi * c["mes"] / 12)
              + 8000 * np.sin(2 * np.pi * (c["hora"] - 6) / 24) + rng.normal(0, 500, len(c)))
    return c[["timestamp", "y", "mes", "hora", "dia_tipo"]].reset_index(drop=True)


@pytest.fixture(scope="module")
def temp(cal) -> pd.Series:
    ts = cal["timestamp"]
    return pd.Series(22 + 5 * np.sin(2 * np.pi * (ts.dt.hour - 9) / 24).to_numpy(), index=ts.to_numpy())


def test_sem_vazamento_temporal(serie, temp, cal):
    """Mudar demanda e temperatura depois da emissão não muda a variante clim nem o nível."""
    em = pd.Timestamp("2025-07-01")
    a = dm.prever_emissao(serie, em, 6, temp, cal)
    s2 = serie.copy()
    s2.loc[s2["timestamp"] >= em, "y"] *= 3.0          # futuro absurdo
    t2 = temp.copy()
    t2[t2.index >= em] += 15.0
    b = dm.prever_emissao(s2, em, 6, t2, cal)
    pd.testing.assert_series_equal(a["p50_clim"], b["p50_clim"])
    # A era5 só pode mudar pela temperatura dos ALVOS (tempo perfeito, declarado), nunca pela
    # demanda futura: com a temperatura original, a demanda futura perturbada não muda nada.
    c = dm.prever_emissao(s2, em, 6, temp, cal)
    pd.testing.assert_series_equal(a["p50_era5"], c["p50_era5"])


def test_horizontes_e_media_mensal(serie, cal):
    em = pd.Timestamp("2025-07-01")
    f = dm.prever_emissao(serie, em, 6, None, cal)
    assert f["timestamp"].min() == em
    assert sorted(f["horizonte"].unique()) == [1, 2, 3, 4, 5, 6]
    assert "p50_era5" not in f  # sem temperatura, a variante era5 não existe (nunca inventa)
    assert f["p50_clim"].notna().all()


def test_baselines_so_passado(serie):
    em = pd.Timestamp("2025-07-01")
    alvos = pd.Series(pd.date_range(em, periods=24 * 180, freq="h"))
    b = dm.baselines(serie, em, alvos, 12)
    assert b.notna().all().all()
    with pytest.raises(ValueError):
        dm.baselines(serie, em, pd.Series(pd.date_range(em + pd.Timedelta(days=370), periods=2, freq="h")), 12)


def test_banda_so_com_erro_ja_conhecido():
    """Os fatores da banda de uma emissão ignoram alvos que ainda não aconteceram nela."""
    em = pd.Timestamp("2025-07-01")
    bt = pd.DataFrame({
        "serie": "SIN", "horizonte": 1, "hora": 0,
        "emissao": [pd.Timestamp("2025-06-01"), pd.Timestamp("2025-06-01")],
        "timestamp": [pd.Timestamp("2025-06-10"), pd.Timestamp("2025-07-10")],
        "y": [100.0, 1e9], "p50_clim": [100.0, 100.0]})
    f = dm.fatores_banda(bt, "clim", em)
    assert f["n"].iloc[0] == 1 and f["f_hi"].iloc[0] == pytest.approx(1.0)


def test_fator_plan_cresce():
    alvos = pd.Series(pd.to_datetime(["2026-07-02", "2027-07-02"]))
    f = dm.fator_plan(pd.Timestamp("2026-07-02"), alvos)
    assert f[0] == pytest.approx(1.0)
    assert f[1] == pytest.approx(88785 / 84989)
