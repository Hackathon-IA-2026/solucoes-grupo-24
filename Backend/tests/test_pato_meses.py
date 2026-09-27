"""Testes da MMGD e da curva do pato de meses (src/models/pato_meses.py): vazamento temporal.

Séries sintéticas de teste (fixtures), sem rede; nada disso entra em saída do projeto.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.models import pato_meses as pm


def _capd() -> pd.DataFrame:
    idx = pd.date_range("2019-01-01", "2026-09-25", freq="D")
    base = np.linspace(1000, 20000, len(idx))
    return pd.DataFrame({s: base * (i + 1) for i, s in enumerate(pm.SUBS)}, index=idx)


def test_membros_so_com_tempo_anterior_a_emissao():
    em = pd.Timestamp("2025-07-01")
    alvos = pd.date_range(em, periods=24 * 180, freq="h")
    ks = pm.deslocamentos(em, alvos, pd.Timestamp("2019-01-01"), 2019)
    assert ks and ks[0] == 1
    for k in ks:
        assert (alvos - pd.DateOffset(years=k)).max() < em  # o membro inteiro é passado
        assert (alvos - pd.DateOffset(years=k)).min() >= pd.Timestamp("2019-01-01")


def test_capacidade_projetada_ignora_cadastro_futuro():
    em = pd.Timestamp("2025-07-01")
    alvos = pd.date_range(em, periods=24 * 30, freq="h")
    a = pm.cap_projetada(_capd(), em, alvos, "historico")
    c2 = _capd()
    c2.loc[c2.index > em - pd.DateOffset(months=3)] *= 10  # depois do ponto de partida (E − defasagem)
    b = pm.cap_projetada(c2, em, alvos, "historico")
    pd.testing.assert_frame_equal(a, b)
    assert (a.diff().dropna() >= 0).all().all()  # cadastro não encolhe


def test_pr_so_com_janela_anterior():
    em = pd.Timestamp("2025-07-01")
    idx = pd.date_range("2024-01-01", "2025-12-31 23:00", freq="h")
    U = pd.DataFrame({s: np.clip(np.sin(np.pi * (idx.hour - 6) / 12), 0, None) for s in pm.SUBS}, index=idx)
    capd = _capd()
    ons = U * capd.reindex(idx.normalize()).to_numpy() * 0.8
    a = pm.calibrar_pr(U, capd, ons, em)
    ons2 = ons.copy()
    ons2.loc[ons2.index >= em] *= 5
    b = pm.calibrar_pr(U, capd, ons2, em)
    pd.testing.assert_series_equal(a, b)
    assert np.allclose(a.to_numpy(), 0.8)


def test_barriga_e_ponta_diarias():
    ts = pd.date_range("2026-01-01", periods=48, freq="h")
    v = np.arange(48, dtype="f8")[None, :]
    bar = pm._dias(ts, v, (9, 16), "min")
    pon = pm._dias(ts, v, (19, 22), "max")
    assert list(bar.iloc[0]) == [9.0, 33.0]
    assert list(pon.iloc[0]) == [21.0, 45.0]
