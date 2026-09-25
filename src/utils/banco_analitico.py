"""Único ponto de criação de conexões DuckDB para processamento pesado.

A máquina tem ~8 GB de RAM e pouco disco. Sem limites o DuckDB assume até 80% da RAM e
até 90% do disco livre em temporários — já estourou memória e quase encheu o disco.
Toda conexão sai daqui com limites de config/fontes_ons.yaml (seção duckdb) e com
temporários numa pasta conhecida, então "DuckDB sem limite" não tem como acontecer.
"""
import duckdb

from src.utils.config import carregar
from src.utils.paths import DATA_RAW, ensure


def conectar() -> duckdb.DuckDBPyConnection:
    lim = carregar("fontes_ons")["duckdb"]
    con = duckdb.connect()
    con.execute(f"SET memory_limit='{lim['memory_limit']}'")
    con.execute(f"SET threads={lim['threads']}")
    con.execute(f"SET max_temp_directory_size='{lim['max_temp_directory_size']}'")
    con.execute(f"SET temp_directory='{ensure(DATA_RAW / '_duckdb_tmp').as_posix()}'")
    con.execute(f"SET partitioned_write_max_open_files={lim['partitioned_write_max_open_files']}")
    con.execute(f"SET partitioned_write_flush_threshold={lim['partitioned_write_flush_threshold']}")
    # Ordem de inserção só importa quando há ORDER BY explícito; desligar libera memória.
    con.execute("SET preserve_insertion_order=false")
    con.execute("SET enable_progress_bar=false")  # não polui logs de processos em background
    return con
