"""Testes das tabelas processadas [NUNCA CORTAR].

Rodam sobre as saídas reais de `python -m src.processing.tabelas`. Se uma tabela ainda não
foi gerada, o teste é pulado com o motivo (não passa em silêncio).
"""
import pandas as pd
import pytest

from src.features.calendario import dia_dos_pais, faixa_curtailment, patamar
from src.processing.saidas import SAIDA_CALENDARIO, SAIDA_CARGA, SAIDA_ROTULOS
from src.utils.banco_analitico import conectar
from src.utils.config import razoes_curtailment


def _exige(arq):
    if not arq.exists():
        pytest.skip(f"{arq.name} não gerado: rode python -m src.processing.tabelas")


# ------------------------------------------------------------------ calendário (unitários)
def test_dia_dos_pais_segundo_domingo_de_agosto():
    assert dia_dos_pais(2024).isoformat() == "2024-08-11"
    assert dia_dos_pais(2025).isoformat() == "2025-08-10"
    assert dia_dos_pais(2026).isoformat() == "2026-08-09"


def test_patamares_e_faixas_nas_fronteiras():
    h = pd.Series([0, 6.5, 7, 8.5, 9, 15.5, 16, 17.5, 18, 18.5, 19, 21.5, 22, 23.5])
    assert list(patamar(h)) == ["outro"] * 4 + ["minima_diurna"] * 2 + ["rampa_vespertina"] * 4 + \
        ["ponta_noturna"] * 2 + ["outro"] * 2
    assert list(faixa_curtailment(h)) == ["00-07"] * 2 + ["07-09|16-18"] * 2 + ["09-16"] * 2 + \
        ["07-09|16-18"] * 2 + ["18-24"] * 6


# ------------------------------------------------------------------ calendário (tabela)
def test_calendario_sem_duplicata_e_sem_buraco():
    _exige(SAIDA_CALENDARIO)
    cal = pd.read_csv(SAIDA_CALENDARIO, parse_dates=["timestamp"])
    assert cal["timestamp"].is_unique
    assert (cal["timestamp"].diff().dropna() == pd.Timedelta("30min")).all()


def test_feriado_tratado_como_domingo():
    _exige(SAIDA_CALENDARIO)
    cal = pd.read_csv(SAIDA_CALENDARIO, parse_dates=["timestamp"])
    assert cal.loc[cal["eh_feriado"], "tratar_como_domingo"].all()
    natal = cal[cal["timestamp"] == "2025-12-25 12:00"].iloc[0]
    assert natal["eh_feriado"] and natal["dia_semana_efetivo"] == 6


# ------------------------------------------------------------------ carga supervisionada
def test_carga_unica_por_subsistema_e_instante():
    _exige(SAIDA_CARGA)
    c = pd.read_csv(SAIDA_CARGA, parse_dates=["timestamp"])
    assert not c.duplicated(["subsistema", "timestamp"]).any()
    assert set(c["subsistema"]) == {"SE", "S", "NE", "N"}


def test_carga_sem_negativos_inesperados_e_subtracao_confere():
    _exige(SAIDA_CARGA)
    c = pd.read_csv(SAIDA_CARGA, parse_dates=["timestamp"])
    assert (c["carga_global"].dropna() > 0).all()
    assert (c["mmgd_estimada"].dropna() >= 0).all()
    ok = c.dropna(subset=["carga_supervisionada"])
    # tolerância de float: o CSV arredonda na ida e volta
    dif = (ok["carga_supervisionada"] - (ok["carga_global"] - ok["mmgd_estimada"])).abs()
    assert (dif < 1e-6).all()
    # onde o ONS publica a carga líquida de MMGD, a nossa subtração tem que bater com ela
    assert ok["confere_ons"].mean() > 0.99


# ------------------------------------------------------------------ rótulos de curtailment
def test_rotulos_chave_composta_fonte_mais_id():
    _exige(SAIDA_ROTULOS)
    con = conectar()
    arq = SAIDA_ROTULOS.as_posix()
    dups = con.sql(f"SELECT count(*) - count(DISTINCT (chave, timestamp)) FROM '{arq}'").fetchone()[0]
    assert dups == 0
    # a chave determina fonte e id_ons (mesmo id em fontes diferentes = chaves diferentes)
    ruins = con.sql(f"""SELECT count(*) FROM (SELECT chave FROM '{arq}' GROUP BY chave
        HAVING count(DISTINCT fonte) > 1 OR count(DISTINCT id_ons) > 1)""").fetchone()[0]
    assert ruins == 0
    formato = con.sql(f"SELECT bool_and(chave = fonte || ':' || id_ons) FROM '{arq}'").fetchone()[0]
    assert formato


def test_rotulos_sem_negativos_nem_nan_e_colunas_por_config():
    _exige(SAIDA_ROTULOS)
    con = conectar()
    arq = SAIDA_ROTULOS.as_posix()
    cols = {r[0] for r in con.sql(f"DESCRIBE SELECT * FROM '{arq}'").fetchall()}
    for r in ("ENE", "CNF", "REL"):
        assert (f"flag_{r}" in cols) == (r in razoes_curtailment())
    for r in razoes_curtailment():
        neg, nan = con.sql(f"""SELECT sum((corte_MW_{r} < 0)::INT), sum((corte_MW_{r} IS NULL)::INT)
                               FROM '{arq}'""").fetchone()
        assert neg == 0
        assert nan == 0
        # evento marcado sem nenhum corte medido é permitido (restrição sem perda),
        # mas corte > 0 sem evento marcado não é
        sem_flag = con.sql(f"SELECT count(*) FROM '{arq}' WHERE corte_MW_{r} > 0 AND NOT flag_{r}").fetchone()[0]
        assert sem_flag == 0


def test_rotulos_timestamps_em_grade_de_30_min():
    _exige(SAIDA_ROTULOS)
    fora = conectar().sql(f"""SELECT count(*) FROM '{SAIDA_ROTULOS.as_posix()}'
        WHERE minute(timestamp) NOT IN (0, 30) OR second(timestamp) <> 0""").fetchone()[0]
    assert fora == 0
