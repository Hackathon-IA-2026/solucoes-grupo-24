"""Features de carga: prova de ausência de vazamento temporal (regra do CLAUDE.md).

O teste central perturba TODO valor posterior à emissão (alvo − h) e exige que as features
do alvo não mudem. Qualquer feature nova que olhe o futuro faz este teste falhar.
"""
import numpy as np
import pandas as pd
import pytest

from src.features import carga as fc
from src.features import defasagens

FEATURES = {"defasagens_recentes": [0, 1, 2, 4, 6, 12], "defasagens_sazonais": [48, 96, 336, 672],
            "janelas_media": [6, 48, 336]}


def _grade(n=2000, inicio="2024-01-01"):
    return pd.date_range(inicio, periods=n, freq="30min", name="timestamp")


def _cal(idx):
    return pd.DataFrame({"hora_decimal": idx.hour + idx.minute / 60, "mes": idx.month}, index=idx)


@pytest.mark.parametrize("h", [1, 6, 48])
def test_features_nao_enxergam_nada_depois_da_emissao(h):
    rng = np.random.default_rng(0)
    idx = _grade()
    y = pd.Series(rng.normal(1000, 50, len(idx)), index=idx)
    mmgd = pd.Series(rng.normal(100, 5, len(idx)), index=idx)
    x = fc.matriz(y, mmgd, _cal(idx), h, FEATURES)
    for pos in (1500, 1700, 1999):
        emissao = pos - h
        y2, mmgd2 = y.copy(), mmgd.copy()
        y2.iloc[emissao + 1:] = 1e9      # o "futuro" da emissão vira lixo
        mmgd2.iloc[emissao + 1:] = -1e9
        x2 = fc.matriz(y2, mmgd2, _cal(idx), h, FEATURES)
        pd.testing.assert_series_equal(x.iloc[pos], x2.iloc[pos])
        # e a referência do horizonte também não muda
        for tipo in ("persistencia", "sazonal_dia", "sazonal_semana"):
            assert fc.referencia(y, h, tipo).iloc[pos] == fc.referencia(y2, h, tipo).iloc[pos]


def test_defasagem_menor_que_o_horizonte_e_recusada():
    y = pd.Series(1.0, index=_grade(100))
    with pytest.raises(ValueError, match="posterior à emissão"):
        defasagens.defasagem(y, 5, horizonte=6)


def test_grade_com_buraco_e_recusada():
    idx = _grade(10).delete(4)  # sem uma semi-hora: shift(1) deixaria de ser "30 min antes"
    with pytest.raises(ValueError, match="grade regular"):
        defasagens.defasagem(pd.Series(1.0, index=idx), 1, 1)


def test_mesmo_horario_disponivel():
    assert [defasagens.mesmo_horario_disponivel(h) for h in (1, 6, 48, 49, 96)] == [48, 48, 48, 96, 96]


def test_sin_so_existe_com_os_4_subsistemas_e_grade_vai_ao_futuro():
    linhas = [(s, "2026-01-01 00:00", 10.0) for s in ("SE", "S", "NE", "N")]
    linhas += [(s, "2026-01-01 01:00", 10.0) for s in ("SE", "S", "NE")]  # falta o N
    df = pd.DataFrame(linhas, columns=["subsistema", "timestamp", "carga_supervisionada"])
    larga = fc.series_largas(df, "carga_supervisionada", passos_futuros=2)
    assert larga.loc["2026-01-01 00:00", "SIN"] == 40
    assert np.isnan(larga.loc["2026-01-01 00:30", "SIN"])   # buraco vira NaN, não some
    assert np.isnan(larga.loc["2026-01-01 01:00", "SIN"])   # soma parcial não vira SIN
    assert larga.index.max() == pd.Timestamp("2026-01-01 02:00")  # 2 passos além do último dado
