"""Único ponto de padronização de tempo (fuso e convenção de intervalo).

Toda base do ONS passa por aqui antes de entrar numa tabela processada. Assim nenhuma
tabela consegue ficar num fuso diferente das outras: não existe outro caminho de conversão.
"""
import pandas as pd

from src.utils.config import carregar

_CFG = carregar("processamento")["tempo"]
FUSO: str = _CFG["fuso"]
RESOLUCAO: str = _CFG["resolucao"]
PASSO = pd.Timedelta(RESOLUCAO)


def de_utc(serie: pd.Series) -> pd.Series:
    """Timestamps em UTC (texto ou datetime) -> horário local do projeto, sem tz (naive)."""
    return pd.to_datetime(serie, utc=True).dt.tz_convert(FUSO).dt.tz_localize(None)


def para_utc(serie: pd.Series) -> pd.Series:
    """Horário local do projeto (naive, UTC-3 fixo) -> UTC com tz. Inverso de `de_utc`.

    Usado na publicação: o contrato com o dashboard trafega em UTC (sufixo Z) e a conversão
    para Brasília é só na tela.
    """
    return pd.to_datetime(serie).dt.tz_localize(FUSO).dt.tz_convert("UTC")


def de_local_ons(serie: pd.Series) -> pd.Series:
    """Timestamps do ONS já em horário de Brasília (sem tz).

    As bases do portal (tm/detail, balanço, térmicas) publicam `din_instante` em horário
    de Brasília. Depois de 2019 não há horário de verão, então coincide com UTC-3 fixo.
    Antes disso (fora da janela das bases de curtailment, que começam em 2021) haveria
    ambiguidade; por isso esta função recusa datas anteriores a 2019-03-01.
    """
    s = pd.to_datetime(serie)
    if (s < pd.Timestamp("2019-03-01")).any():
        raise ValueError("de_local_ons: há datas com horário de verão; trate a base em UTC")
    return s


def fim_para_inicio(serie: pd.Series) -> pd.Series:
    """Dados "integralizados no final do intervalo" -> marca de início do intervalo."""
    return serie - PASSO
