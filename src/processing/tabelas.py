"""Constrói as tabelas processadas do Prompt 1 [NUNCA CORTAR].

Uso:
    python -m src.processing.tabelas                 # as três
    python -m src.processing.tabelas calendario carga rotulos

Saídas (data/processed/):
    calendario.csv               30 min, feriados, patamar, faixa de curtailment
    carga_supervisionada.csv     subsistema × 30 min: carga_global, mmgd_estimada, carga_supervisionada
    rotulos_curtailment.parquet  fonte+id_ons × 30 min: corte por razão e flags (>1M linhas -> Parquet)

Um resumo de cobertura de cada tabela vai para docs/reports/cobertura_tabelas.csv.
"""
import argparse

import pandas as pd

from src.features.calendario import montar_calendario
from src.utils.banco_analitico import conectar
from src.utils.config import carregar, razoes_curtailment
from src.utils.joins import cruzar_subsistema_area
from src.utils.paths import DATA_PROCESSED, DOCS_REPORTS, RAW_ONS, ensure
from src.utils.tempo import de_local_ons, de_utc, fim_para_inicio

CFG = carregar("processamento")
SAIDA_CALENDARIO = DATA_PROCESSED / "calendario.csv"
SAIDA_CARGA = DATA_PROCESSED / "carga_supervisionada.csv"
SAIDA_ROTULOS = DATA_PROCESSED / "rotulos_curtailment.parquet"


# Leitura das bases brutas: sempre hive_partitioning=false. As pastas ano=/area= são só
# organização; se viessem como coluna, "ano" colidiria com colunas homônimas do ONS.


# --------------------------------------------------------------------------- calendário
def construir_calendario() -> pd.DataFrame:
    cal = montar_calendario()
    cal.to_csv(SAIDA_CALENDARIO, index=False)
    return cal


# --------------------------------------------------------------------------- carga
def construir_carga() -> pd.DataFrame:
    """Carga supervisionada = carga global − MMGD estimada, por subsistema, 30 min.

    Unidades: as três grandezas vêm da MESMA base (API de carga verificada) em MWmed
    integralizado na semi-hora (dicionário DicionarioDados_Carga_Verificada). Mesma unidade
    e mesma resolução de 30 min: nenhuma reamostragem é necessária, e a subtração é direta.
    (Se um dia vier outra fonte em MWh ou horária: potência -> interpolação linear;
    energia -> redistribuição uniforme. Não se aplica aqui.)

    Decisões:
    - carga_global = val_cargaglobal (verificada). A versão consistida pelo ONS para os
      modelos dele (val_cargaglobalcons) vai junto em carga_global_consistida.
    - MMGD ausente (anos em que o ONS não estimava) fica NaN e carga_supervisionada NaN:
      não assumimos zero. A coluna mmgd_disponivel marca isso.
    - Checagem: carga_global − mmgd deve bater com val_cargaglobalsmmgd publicado pelo ONS.
    """
    subs = CFG["carga"]["subsistemas_api"]
    lista = ", ".join(f"'{s}'" for s in subs)
    fonte = (RAW_ONS / "carga_verificada").as_posix()
    df = conectar().sql(f"""
        SELECT cod_areacarga, din_referenciautc, din_atualizacao, val_cargaglobal,
               val_cargaglobalcons, val_cargammgd, val_cargaglobalsmmgd
        FROM read_parquet('{fonte}/**/*.parquet', hive_partitioning=false, union_by_name=true)
        WHERE cod_areacarga IN ({lista})
    """).df()
    # Janelas rebaixadas podem repetir um instante: fica a publicação mais recente.
    df = (df.sort_values("din_atualizacao")
            .drop_duplicates(["cod_areacarga", "din_referenciautc"], keep="last"))
    df["timestamp"] = fim_para_inicio(de_utc(df["din_referenciautc"]))
    df = cruzar_subsistema_area(df, "cod_areacarga", de="cod_areacarga", para="id_subsistema")

    out = pd.DataFrame({
        "subsistema": df["id_subsistema"],
        "timestamp": df["timestamp"],
        "carga_global": df["val_cargaglobal"],
        "mmgd_estimada": df["val_cargammgd"],
    })
    out["carga_supervisionada"] = out["carga_global"] - out["mmgd_estimada"]
    out["mmgd_disponivel"] = out["mmgd_estimada"].notna()
    out["carga_global_consistida"] = df["val_cargaglobalcons"].to_numpy()

    tol = CFG["carga"]["tolerancia_checagem_mw"]
    dif = (out["carga_supervisionada"] - df["val_cargaglobalsmmgd"].to_numpy()).abs()
    out["confere_ons"] = dif <= tol  # NaN em qualquer lado -> False (sem como conferir)
    out = out.sort_values(["subsistema", "timestamp"]).reset_index(drop=True)
    out.to_csv(SAIDA_CARGA, index=False)
    return out


# --------------------------------------------------------------------------- rótulos
def _sql_rotulos_fonte(apelido: str, fonte: str) -> str:
    """SELECT dos rótulos de uma base tm (eólica ou solar).

    Regras (decididas olhando os dados, ver docs/STATUS.md → Decisões):
    - Códigos vazios ('' ou espaços) viram NULL NA LEITURA. A base solar de mai–dez/2024
      usa '' para "sem restrição"; tratar isso aqui, uma vez, impede que '' seja lido
      como "tem razão" em qualquer regra abaixo.
    - corte total = GNRa (val_geracaonaorealizadaapurada, MWmed), a medida oficial.
      Quando a GNRa não foi publicada (solar mai–dez/2024) mas há restrição, usa-se
      max(referência − geração, 0): nas linhas que têm as duas, GNRa é EXATAMENTE isso
      (diferença mediana 0, correlação 1,0 nas duas bases). `corte_origem` registra a fonte.
    - corte por razão = corte total × minutos da razão / minutos totais (ENE+CNF+REL).
      ~51 mil semi-horas têm mais de uma razão. Sem minutos mas com razão declarada:
      tudo nela.
    - flag_X = num_minutos_X > 0, ou razão declarada = X quando não há minutos publicados.
    - sem nenhuma restrição -> corte 0 (zero de fato). Restrição sem como medir -> NaN
      (desconhecido: nunca vira zero).
    - Linhas repetidas (mesmo id_ons e instante; ex.: CJU_RNSDMA em nov/2021 vem duplicado
      pelo ONS) são reduzidas a uma, preferindo a mais completa. A contagem vai para o log.
    - din_instante já está em horário de Brasília e marca o INÍCIO da semi-hora (cada mês
      vai de 00:00 do dia 1 a 23:30 do último dia), igual à convenção do projeto.
    """
    src = (RAW_ONS / apelido).as_posix()
    partes = []
    for r in ("ENE", "CNF", "REL"):
        m = f"coalesce(num_minutos_{r.lower()}, 0)"
        partes.append(f"""
            CASE WHEN NOT restrito THEN 0.0
                 WHEN tot > 0 THEN corte * {m} / tot
                 ELSE corte * (razao = '{r}')::DOUBLE END AS corte_MW_{r},
            ({m} > 0 OR (tot = 0 AND coalesce(razao = '{r}', false))) AS flag_{r}""")
    return f"""
        SELECT '{fonte}' || ':' || id_ons AS chave, '{fonte}' AS fonte, id_ons, nom_usina,
               id_subsistema AS subsistema, id_estado AS uf, din_instante AS timestamp,
               origem AS origem_restricao, corte_origem, {','.join(partes)}
        FROM (
          SELECT *,
                 coalesce(gnra, CASE WHEN restrito THEN greatest(val_geracaoreferencia - val_geracao, 0) END) AS corte,
                 CASE WHEN NOT restrito THEN 'sem_restricao'
                      WHEN gnra IS NOT NULL THEN 'gnra'
                      WHEN val_geracaoreferencia IS NOT NULL AND val_geracao IS NOT NULL THEN 'ref_menos_ger'
                      ELSE 'desconhecido' END AS corte_origem
          FROM (
            SELECT *, (tot > 0 OR razao IS NOT NULL) AS restrito
            FROM (
              SELECT *, val_geracaonaorealizadaapurada AS gnra,
                     nullif(trim(cod_razaorestricao), '') AS razao,
                     nullif(trim(cod_origemrestricao), '') AS origem,
                     coalesce(num_minutos_ene,0)+coalesce(num_minutos_cnf,0)+coalesce(num_minutos_rel,0) AS tot
              FROM ({_sql_minutos_validos(src)})
            )
          )
          QUALIFY row_number() OVER (PARTITION BY id_ons, din_instante
                                     ORDER BY (gnra IS NULL), (razao IS NULL), tot DESC) = 1
        )
    """


def _sql_minutos_validos(src: str) -> str:
    """Base tm com minutos fora de [0, 30] anulados (NULL = inválido, não zero).

    A base traz erros como num_minutos_ene = -30 (RNESF4, 2022-12-25 12:00). Corrigir o
    sinal seria supor; anulamos e a razão declarada decide flag e destino do corte.
    """
    cols = ", ".join(
        f"CASE WHEN num_minutos_{r} BETWEEN 0 AND 30 THEN num_minutos_{r} END AS num_minutos_{r}"
        for r in ("ene", "cnf", "rel"))
    return (f"SELECT * REPLACE ({cols}) FROM read_parquet('{src}/**/*.parquet', "
            f"hive_partitioning=false, union_by_name=true)")


def contar_minutos_invalidos(apelido: str) -> int:
    src = (RAW_ONS / apelido).as_posix()
    cond = " OR ".join(f"NOT (num_minutos_{r} BETWEEN 0 AND 30)" for r in ("ene", "cnf", "rel"))
    return conectar().sql(f"""SELECT count(*) FROM read_parquet('{src}/**/*.parquet',
        hive_partitioning=false, union_by_name=true) WHERE {cond}""").fetchone()[0]


def contar_duplicatas_brutas(apelido: str) -> int:
    """Linhas a mais por (id_ons, din_instante) na base bruta — vão para o log/relatório."""
    src = (RAW_ONS / apelido).as_posix()
    return conectar().sql(f"""SELECT count(*) - count(DISTINCT (id_ons, din_instante))
        FROM read_parquet('{src}/**/*.parquet', hive_partitioning=false, union_by_name=true)""").fetchone()[0]


def construir_rotulos() -> pd.DataFrame:
    """Grava rotulos_curtailment.parquet via DuckDB (15M+ linhas: fora da memória do pandas)."""
    inicio = CFG["curtailment"]["inicio_rotulos"]
    razoes = razoes_curtailment()  # REL só entra se incluir_rel=true
    fora = [r for r in ("ENE", "CNF", "REL") if r not in razoes]
    excluir = ", ".join(c for r in fora for c in (f"corte_MW_{r}", f"flag_{r}"))
    con = conectar()
    uniao = (f"{_sql_rotulos_fonte('coff_eolica_tm', 'eolica')} UNION ALL BY NAME "
             f"{_sql_rotulos_fonte('coff_solar_tm', 'solar')}")
    # Mesma trava de de_local_ons (src/utils/tempo.py): antes de 2019-03 havia horário de verão.
    minimo = con.execute(f"SELECT min(timestamp) FROM ({uniao})").fetchone()[0]
    de_local_ons(pd.Series([minimo]))
    sel = f"* EXCLUDE ({excluir})" if excluir else "*"
    con.execute(f"""COPY (SELECT {sel} FROM ({uniao}) WHERE timestamp >= '{inicio}'
                         ORDER BY chave, timestamp)
                    TO '{SAIDA_ROTULOS.as_posix()}' (FORMAT parquet, COMPRESSION zstd)""")
    resumo = con.execute(f"""SELECT 'rotulos_curtailment' AS tabela, fonte AS grupo,
        count(*) AS linhas, min(timestamp) AS inicio, max(timestamp) AS fim
        FROM '{SAIDA_ROTULOS.as_posix()}' GROUP BY fonte""").df()
    con.close()
    for apelido in ("coff_eolica_tm", "coff_solar_tm"):
        print(f"{apelido}: {contar_duplicatas_brutas(apelido)} linhas duplicadas removidas, "
              f"{contar_minutos_invalidos(apelido)} linhas com minutos fora de [0, 30] anulados")
    return resumo


# --------------------------------------------------------------------------- cobertura
def cobertura(nome: str, df: pd.DataFrame, grupo: str | None) -> pd.DataFrame:
    g = df.groupby(grupo) if grupo else [("todos", df)]
    linhas = []
    for k, d in g:
        linhas.append({"tabela": nome, "grupo": k, "linhas": len(d),
                       "inicio": d["timestamp"].min(), "fim": d["timestamp"].max()})
    return pd.DataFrame(linhas)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("tabelas", nargs="*", default=["calendario", "carga", "rotulos"])
    args = ap.parse_args()
    ensure(DATA_PROCESSED)
    ensure(DOCS_REPORTS)
    cob = []
    if "calendario" in args.tabelas:
        cob.append(cobertura("calendario", construir_calendario(), None))
    if "carga" in args.tabelas:
        cob.append(cobertura("carga_supervisionada", construir_carga(), "subsistema"))
    if "rotulos" in args.tabelas:
        cob.append(construir_rotulos())  # já devolve a cobertura calculada em SQL
    cob = pd.concat(cob)
    arq = DOCS_REPORTS / "cobertura_tabelas.csv"
    if arq.exists():  # atualiza só as tabelas reconstruídas
        ant = pd.read_csv(arq)
        cob = pd.concat([ant[~ant["tabela"].isin(cob["tabela"])], cob])
    cob.to_csv(arq, index=False)
    print(cob.to_string(index=False))


if __name__ == "__main__":
    main()
