"""Calendário semi-horário: feriados, patamares e faixas de curtailment.

Módulo de features COMPARTILHADO (regra DRY do contexto dos prompts): os modelos de carga
e de curtailment importam daqui; ninguém recalcula patamar ou feriado por conta própria.
"""
from datetime import date

import holidays
import pandas as pd

from src.utils.config import carregar
from src.utils.tempo import RESOLUCAO

_CFG = carregar("processamento")["calendario"]


def _no_intervalo(hora_decimal: pd.Series, intervalos: list[list[float]]) -> pd.Series:
    """True se a hora (início do intervalo de 30 min) cai em algum [ini, fim)."""
    m = pd.Series(False, index=hora_decimal.index)
    for ini, fim in intervalos:
        m |= (hora_decimal >= ini) & (hora_decimal < fim)
    return m


def patamar(hora_decimal: pd.Series) -> pd.Series:
    """'ponta_noturna' | 'minima_diurna' | 'outro' (config: calendario.patamares)."""
    out = pd.Series("outro", index=hora_decimal.index, dtype="object")
    for nome, (ini, fim) in _CFG["patamares"].items():
        out[_no_intervalo(hora_decimal, [[ini, fim]])] = nome
    return out


def faixa_curtailment(hora_decimal: pd.Series) -> pd.Series:
    """Faixa horária de curtailment (config: calendario.faixas_curtailment)."""
    out = pd.Series(pd.NA, index=hora_decimal.index, dtype="object")
    for rotulo, intervalos in _CFG["faixas_curtailment"].items():
        out[_no_intervalo(hora_decimal, intervalos)] = rotulo
    if out.isna().any():  # as faixas precisam cobrir as 24h; lacuna = config errada
        raise ValueError("faixas_curtailment não cobrem todas as horas do dia")
    return out


def dia_dos_pais(ano: int) -> date:
    """2º domingo de agosto."""
    primeiro = date(ano, 8, 1)
    ate_domingo = (6 - primeiro.weekday()) % 7
    return date(ano, 8, 1 + ate_domingo + 7)


def montar_calendario(inicio: str | None = None, fim: str | None = None) -> pd.DataFrame:
    """Uma linha por intervalo de 30 min (timestamp = início do intervalo, fuso do projeto)."""
    inicio = pd.Timestamp(inicio or _CFG["inicio"])
    fim = pd.Timestamp(fim or _CFG["fim"]) + pd.Timedelta(days=1) - pd.Timedelta(RESOLUCAO)
    ts = pd.date_range(inicio, fim, freq=RESOLUCAO)
    cal = pd.DataFrame({"timestamp": ts})
    cal["data"] = cal["timestamp"].dt.date
    cal["ano"] = cal["timestamp"].dt.year
    cal["mes"] = cal["timestamp"].dt.month
    cal["dia_semana"] = cal["timestamp"].dt.dayofweek  # 0=segunda ... 6=domingo
    cal["hora"] = cal["timestamp"].dt.hour
    cal["minuto"] = cal["timestamp"].dt.minute
    hora_dec = cal["hora"] + cal["minuto"] / 60

    # Feriados nacionais do Brasil (biblioteca holidays). Regra do CLAUDE.md: feriado = domingo.
    fer = holidays.Brazil(years=range(inicio.year, fim.year + 1))
    cal["nome_feriado"] = cal["data"].map(fer.get)
    cal["eh_feriado"] = cal["nome_feriado"].notna()
    cal["tratar_como_domingo"] = cal["eh_feriado"] | (cal["dia_semana"] == 6)
    pais = {dia_dos_pais(a) for a in range(inicio.year, fim.year + 1)}
    cal["dia_dos_pais"] = cal["data"].isin(pais)
    # dia_semana "efetivo" para os modelos: feriado vira domingo (6)
    cal["dia_semana_efetivo"] = cal["dia_semana"].where(~cal["eh_feriado"], 6)

    cal["patamar"] = patamar(hora_dec)
    cal["faixa_curtailment"] = faixa_curtailment(hora_dec)
    return cal
