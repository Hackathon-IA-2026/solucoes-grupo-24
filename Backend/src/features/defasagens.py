"""Features de defasagem sem vazamento temporal, para qualquer série em grade regular de 30 min.

Módulo COMPARTILHADO (carga e curtailment usam o mesmo). A ideia central:

    Toda feature de uma linha com alvo em t e horizonte h é calculada SÓ com valores em
    instantes <= t − h (a "emissão" da previsão).

Não existe outra forma de montar defasagem no projeto: quem precisa de lag chama daqui. As
funções recebem o horizonte e RECUSAM defasagem menor que ele (seria olhar o futuro), então a
classe de bug "feature com informação posterior à emissão" não tem como ser escrita.
`tests/test_features_carga.py` prova isso perturbando todo o futuro e conferindo que as
features não mudam.

Convenção: série indexada pelo timestamp do ALVO, em grade regular (sem buracos no índice;
buraco de dado = NaN). `shift(k)` numa grade regular = valor de k passos antes.
"""
from __future__ import annotations

import math

import pandas as pd

PASSOS_POR_DIA = 48


def _exige_grade_regular(serie: pd.Series) -> None:
    """Defasagem por shift só é defasagem de tempo se a grade não tiver buracos."""
    idx = serie.index
    if not isinstance(idx, pd.DatetimeIndex) or not idx.is_monotonic_increasing:
        raise ValueError("série precisa de DatetimeIndex crescente")
    if len(idx) > 1 and (idx[1:] - idx[:-1] != idx[1] - idx[0]).any():
        raise ValueError("série fora de grade regular: reindexe (buraco = NaN) antes das defasagens")


def defasagem(serie: pd.Series, passos: int, horizonte: int) -> pd.Series:
    """Valor de `passos` antes do alvo. Recusa passos < horizonte (seria futuro na emissão)."""
    if passos < horizonte:
        raise ValueError(f"defasagem {passos} < horizonte {horizonte}: usaria dado posterior à emissão")
    _exige_grade_regular(serie)
    return serie.shift(passos)


def mesmo_horario_disponivel(horizonte: int) -> int:
    """Passos até o mesmo horário do dia mais recente que já é passado na emissão.

    h=1 ou 6 -> 48 (ontem, mesmo horário); h=48 -> 48; h=49..96 -> 96.
    """
    return PASSOS_POR_DIA * math.ceil(horizonte / PASSOS_POR_DIA)


def montar(serie: pd.Series, horizonte: int, prefixo: str, recentes: list[int],
           sazonais: list[int], janelas: list[int]) -> pd.DataFrame:
    """Bloco de defasagens de uma série para um horizonte.

    - recentes: k passos antes da EMISSÃO -> defasagem h + k
    - sazonais: s passos antes do ALVO (48 = dia, 336 = semana); s < h é descartado
    - janelas: médias móveis de w passos terminando na emissão
    - mesmo horário do dia mais recente disponível (sempre existe)
    """
    cols: dict[str, pd.Series] = {}
    for k in recentes:
        cols[f"{prefixo}_emissao_menos_{k}"] = defasagem(serie, horizonte + k, horizonte)
    for s in sazonais:
        if s >= horizonte:
            cols[f"{prefixo}_alvo_menos_{s}"] = defasagem(serie, s, horizonte)
    na_emissao = defasagem(serie, horizonte, horizonte)
    for w in janelas:
        # rolling olha para trás a partir da emissão: nada depois de t − h entra na média
        cols[f"{prefixo}_media_{w}"] = na_emissao.rolling(w, min_periods=max(1, w // 2)).mean()
    cols[f"{prefixo}_mesmo_horario"] = defasagem(serie, mesmo_horario_disponivel(horizonte), horizonte)
    return pd.DataFrame(cols, index=serie.index)
