"""Leitura ÚNICA da carga verificada do ONS (API de carga) em data/raw.

Usada pela carga supervisionada por subsistema (tabelas.construir_carga) e pela carga por área
de carga (cadastro.construir_carga_areas). Antes, a consulta vivia dentro de construir_carga;
com duas tabelas lendo a mesma base, a deduplicação e a conversão de tempo precisam ser as
mesmas — uma função só (DRY).

- Janelas rebaixadas podem repetir um instante: fica a publicação mais recente (din_atualizacao).
- Carga global <= 0 é fisicamente impossível (falha de medição, ex.: N em 2024-02-08 10:00 =
  -187,6 MW; o ONS publica 8.019 MW na versão consistida): vira NaN com a flag
  `carga_global_invalida`, em vez de entrar como verdade no treino. Regra aqui, e não em cada
  tabela, para que subsistema, área piloto e áreas de carga tratem a falha do mesmo jeito.
- `din_referenciautc` marca o FIM da semi-hora em UTC: vira início da semi-hora no fuso do
  projeto (src/utils/tempo.py), a convenção de todas as tabelas.
"""
from __future__ import annotations

import pandas as pd

from src.utils.banco_analitico import conectar
from src.utils.paths import RAW_ONS
from src.utils.tempo import de_utc, fim_para_inicio

COLUNAS = ("val_cargaglobal", "val_cargaglobalcons", "val_cargammgd", "val_cargaglobalsmmgd")


def ler_carga_verificada(areas: list[str]) -> pd.DataFrame:
    """Linhas da carga verificada das áreas pedidas: cod_areacarga, timestamp, as grandezas e a
    flag carga_global_invalida (val_cargaglobal <= 0, já trocado por NaN)."""
    if not areas:
        raise ValueError("nenhuma área de carga pedida")
    lista = ", ".join(f"'{a}'" for a in areas)
    fonte = (RAW_ONS / "carga_verificada").as_posix()
    con = conectar()
    df = con.sql(f"""
        SELECT cod_areacarga, din_referenciautc, din_atualizacao, {', '.join(COLUNAS)}
        FROM read_parquet('{fonte}/**/*.parquet', hive_partitioning=false, union_by_name=true)
        WHERE cod_areacarga IN ({lista})
    """).df()
    con.close()
    df = (df.sort_values("din_atualizacao")
            .drop_duplicates(["cod_areacarga", "din_referenciautc"], keep="last"))
    df = df.reset_index(drop=True)
    df["timestamp"] = fim_para_inicio(de_utc(df["din_referenciautc"]))
    df["carga_global_invalida"] = df["val_cargaglobal"] <= 0
    df.loc[df["carga_global_invalida"], "val_cargaglobal"] = float("nan")
    return df
