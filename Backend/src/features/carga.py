"""Features da previsão de carga supervisionada (Fase 3).

Uma linha por ALVO (semi-hora prevista), para uma série (subsistema ou SIN) e um horizonte h:
- defasagens da própria carga supervisionada e da MMGD estimada (src/features/defasagens.py:
  só valores até a emissão t − h);
- calendário do ALVO (conhecido no futuro: hora, dia da semana com feriado = domingo,
  patamar...), vindo de data/processed/calendario.csv (src/features/calendario.py);
- referência do horizonte (persistência ou mesmo horário do dia anterior): o LightGBM
  aprende o desvio em relação a ela.

Sem meteorologia por decisão do Tiago (2026-09-25): baseline só com calendário e defasagens.
"""
from __future__ import annotations

import pandas as pd

from src.features import defasagens
from src.utils.config import carregar
from src.utils.tempo import PASSO

SUBSISTEMAS = ("SE", "S", "NE", "N")

# Código numérico de cada patamar, derivado da MESMA config que o calendário usa (patamar novo
# no processamento.yaml ganha código sozinho; "outro" = 0).
_PATAMARES = {"outro": 0, **{nome: i + 1 for i, nome in
                             enumerate(carregar("processamento")["calendario"]["patamares"])}}


def series_largas(carga: pd.DataFrame, coluna: str, passos_futuros: int) -> pd.DataFrame:
    """Tabela larga (timestamp × SE, S, NE, N, SIN) em grade regular de 30 min.

    - Grade do primeiro ao último instante + `passos_futuros` (linhas de alvo ainda sem
      valor, para previsões além do último dado). Buraco de dado vira NaN, nunca some.
    - SIN = soma dos 4 subsistemas só quando os 4 existem (min_count=4).
    """
    c = carga[carga["subsistema"].isin(SUBSISTEMAS)]
    larga = c.pivot_table(index=pd.to_datetime(c["timestamp"]), columns="subsistema",
                          values=coluna, aggfunc="first")
    larga = larga.reindex(columns=list(SUBSISTEMAS))
    grade = pd.date_range(larga.index.min(), larga.index.max() + passos_futuros * PASSO, freq=PASSO)
    larga = larga.reindex(grade)
    larga["SIN"] = larga[list(SUBSISTEMAS)].sum(axis=1, min_count=len(SUBSISTEMAS))
    larga.index.name = "timestamp"
    return larga


def calendario(cal: pd.DataFrame) -> pd.DataFrame:
    """Features numéricas de calendário, indexadas pelo timestamp (tabela processada)."""
    ts = pd.to_datetime(cal["timestamp"])
    return pd.DataFrame({
        "hora_decimal": (cal["hora"] + cal["minuto"] / 60).to_numpy(),
        "dia_semana_efetivo": cal["dia_semana_efetivo"].to_numpy(),  # feriado = domingo
        "eh_feriado": cal["eh_feriado"].astype(int).to_numpy(),
        "dia_dos_pais": cal["dia_dos_pais"].astype(int).to_numpy(),
        "mes": cal["mes"].to_numpy(),
        "dia_do_ano": ts.dt.dayofyear.to_numpy(),
        "patamar": cal["patamar"].map(_PATAMARES).to_numpy(),
    }, index=pd.DatetimeIndex(ts, name="timestamp"))


def referencia(y: pd.Series, horizonte: int, tipo: str) -> pd.Series:
    """Previsão ingênua que serve de base ao modelo e de baseline (config: referencia)."""
    if tipo == "persistencia":
        return defasagens.defasagem(y, horizonte, horizonte)
    if tipo == "sazonal_dia":
        return defasagens.defasagem(y, defasagens.mesmo_horario_disponivel(horizonte), horizonte)
    if tipo == "sazonal_semana":
        return defasagens.defasagem(y, 7 * defasagens.PASSOS_POR_DIA, horizonte)
    raise ValueError(f"referência desconhecida: {tipo}")


def matriz(y: pd.Series, mmgd: pd.Series, cal: pd.DataFrame, horizonte: int,
           cfg_features: dict) -> pd.DataFrame:
    """Matriz de features de uma série num horizonte (índice = timestamp do alvo)."""
    blocos = [
        defasagens.montar(y, horizonte, "carga", cfg_features["defasagens_recentes"],
                          cfg_features["defasagens_sazonais"], cfg_features["janelas_media"]),
        # MMGD: só o nível recente e o mesmo horário (perfil solar), mesmas regras de defasagem
        defasagens.montar(mmgd, horizonte, "mmgd", [0], [], [48]),
        cal.reindex(y.index),
    ]
    x = pd.concat(blocos, axis=1)
    x["horizonte"] = horizonte
    return x
