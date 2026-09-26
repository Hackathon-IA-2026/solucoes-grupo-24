"""Constrói as tabelas processadas do Prompt 1 [NUNCA CORTAR].

Chamado pela etapa 2 do Backend/run_heavywork.py via `construir()`. Linha de comando para
depuração:
    python -m src.processing.tabelas                 # as três
    python -m src.processing.tabelas calendario carga rotulos

Saídas (data/processed/):
    calendario.csv               30 min, feriados, patamar, faixa de curtailment
    carga_supervisionada.csv     subsistema × 30 min: carga_global, mmgd_estimada, carga_supervisionada
    rotulos_curtailment.parquet  fonte+id_ons × 30 min: corte por razão e flags (>1M linhas -> Parquet)
    capacidade_mmgd.csv          UF × data: potência de MMGD cadastrada na ANEEL (diária e acumulada)
    carga_area.csv               área de carga da área piloto (config/espacial.yaml) × 30 min:
                                 carga_global e mmgd_estimada (base dos excedentes por mancha)

Um resumo de cobertura de cada tabela vai para docs/reports/cobertura_tabelas.csv.
"""
import argparse

import pandas as pd

from src.features.calendario import montar_calendario
from src.utils.banco_analitico import conectar
from src.utils.config import arquivo_direto, carregar, razoes_curtailment
from src.utils.joins import cruzar_subsistema_area
from src.processing.saidas import (SAIDA_CALENDARIO, SAIDA_CAPACIDADE_MMGD, SAIDA_CARGA, SAIDA_CARGA_AREA,
                                   SAIDA_ROTULOS)
from src.utils.paths import DATA_PROCESSED, DOCS_REPORTS, RAW_ONS, ensure
from src.utils.tempo import de_local_ons, de_utc, fim_para_inicio

CFG = carregar("processamento")
# Caminhos das saídas (SAIDA_*, SAIDAS) ficam em src/processing/saidas.py: quem só lê as
# tabelas importa de lá, sem puxar este módulo para a impressão digital do próprio código.


# Leitura das bases brutas: sempre hive_partitioning=false. As pastas ano=/area= são só
# organização; se viessem como coluna, "ano" colidiria com colunas homônimas do ONS.


# --------------------------------------------------------------------------- calendário
def construir_calendario() -> pd.DataFrame:
    cal = montar_calendario()
    cal.to_csv(SAIDA_CALENDARIO, index=False)
    return cal


# --------------------------------------------------------------------------- carga
def _ler_carga_verificada(areas: list[str]) -> pd.DataFrame:
    """Carga verificada bruta das áreas pedidas, sem duplicatas e com `timestamp` no padrão.

    Único leitor da API de carga verificada (DRY): a tabela por subsistema e a da área piloto
    saem daqui, então as duas têm o mesmo fuso, a mesma convenção de intervalo e a mesma regra
    de duplicata. Carga global <= 0 vira NaN com flag `carga_global_invalida` (falha de medição,
    ex.: N em 2024-02-08 10:00 = -187,6 MW; o ONS publica 8.019 MW na versão consistida).
    """
    lista = ", ".join(f"'{s}'" for s in areas)
    fonte = (RAW_ONS / "carga_verificada").as_posix()
    df = conectar().sql(f"""
        SELECT cod_areacarga, din_referenciautc, din_atualizacao, val_cargaglobal,
               val_cargaglobalcons, val_cargammgd, val_cargaglobalsmmgd
        FROM read_parquet('{fonte}/**/*.parquet', hive_partitioning=false, union_by_name=true)
        WHERE cod_areacarga IN ({lista})
    """).df()
    # Janelas rebaixadas podem repetir um instante: fica a publicação mais recente.
    df = (df.sort_values("din_atualizacao")
            .drop_duplicates(["cod_areacarga", "din_referenciautc"], keep="last")
            .reset_index(drop=True))
    df["timestamp"] = fim_para_inicio(de_utc(df["din_referenciautc"]))
    df["carga_global_invalida"] = df["val_cargaglobal"] <= 0
    df.loc[df["carga_global_invalida"], "val_cargaglobal"] = float("nan")
    return df


def construir_carga_area() -> pd.DataFrame:
    """Carga global e MMGD estimada (ONS) da área de carga da área piloto, 30 min.

    É a base dos excedentes por mancha (src/spatial/excedentes.py): a carga global da área é
    repartida entre as manchas e a MMGD estimada, dividida pela capacidade cadastrada, dá o
    fator de geração da MMGD em cada semi-hora. Área em config/processamento.yaml
    (carga.area_piloto_ons).
    """
    area = CFG["carga"]["area_piloto_ons"]
    df = _ler_carga_verificada([area])
    if df.empty:
        raise LookupError(f"carga verificada sem a área '{area}': rode a ingestão")
    out = pd.DataFrame({"area": df["cod_areacarga"], "timestamp": df["timestamp"],
                        "carga_global": df["val_cargaglobal"], "mmgd_estimada": df["val_cargammgd"],
                        "carga_global_invalida": df["carga_global_invalida"]})
    out = out.sort_values(["area", "timestamp"]).reset_index(drop=True)
    out.to_csv(SAIDA_CARGA_AREA, index=False)
    return out


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
    df = _ler_carga_verificada(CFG["carga"]["subsistemas_api"])
    df = cruzar_subsistema_area(df, "cod_areacarga", de="cod_areacarga", para="id_subsistema")

    out = pd.DataFrame({
        "subsistema": df["id_subsistema"],
        "timestamp": df["timestamp"],
        "carga_global": df["val_cargaglobal"],
        "mmgd_estimada": df["val_cargammgd"],
    })
    # Carga global <= 0 já veio NaN de _ler_carga_verificada, com flag, em vez de entrar como
    # verdade no treino. A versão consistida continua em outra coluna.
    out["carga_global_invalida"] = df["carga_global_invalida"].to_numpy()
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


# --------------------------------------------------------------------------- capacidade MMGD
APELIDO_ANEEL_MMGD = "aneel_mmgd_empreendimentos"


def construir_capacidade_mmgd() -> pd.DataFrame:
    """Potência de MMGD cadastrada na ANEEL por UF e data, diária e acumulada (MW).

    Usada para "MMGD ÷ capacidade instalada" (tela Visão Geral): a capacidade vale NA DATA do
    instante consultado (acumulada até ela), para o modo replay não enxergar cadastros futuros.

    Decisões:
    - Data = DthAtualizaCadastralEmpreend. O cadastro não publica data de conexão; a data de
      atualização cadastral é a aproximação disponível. Limitação: se um empreendimento teve o
      cadastro atualizado depois de conectar, ele "entra" mais tarde do que entrou de fato
      (a capacidade no passado fica subestimada). Registrado em docs/real_vs_mock.md.
    - kW -> MW (/1000). Linhas sem data, UF ou potência ficam de fora e são contadas no log.
    - A ANEEL usa 1900-01-01 como data sentinela (0,74 MW no cadastro de 2026-08): mantido,
      conta como "antigo" em qualquer consulta; impacto desprezível frente a ~54 GW.
    - PRIVACIDADE: o arquivo tem CPF/CNPJ e nome do titular. Este SELECT lê SÓ três colunas
      (UF, data, potência); nenhuma coluna pessoal sai de data/raw.
    """
    fonte = arquivo_direto(APELIDO_ANEEL_MMGD).as_posix()
    con = conectar()
    fora = con.execute(f"""SELECT count(*) FROM read_parquet('{fonte}')
        WHERE SigUF IS NULL OR DthAtualizaCadastralEmpreend IS NULL OR MdaPotenciaInstaladaKW IS NULL""").fetchone()[0]
    df = con.sql(f"""
        SELECT uf, data, potencia_mw_dia,
               sum(potencia_mw_dia) OVER (PARTITION BY uf ORDER BY data) AS potencia_acumulada_mw
        FROM (SELECT SigUF AS uf, DthAtualizaCadastralEmpreend AS data,
                     sum(MdaPotenciaInstaladaKW) / 1000.0 AS potencia_mw_dia
              FROM read_parquet('{fonte}')
              WHERE SigUF IS NOT NULL AND DthAtualizaCadastralEmpreend IS NOT NULL
                AND MdaPotenciaInstaladaKW IS NOT NULL
              GROUP BY 1, 2)
        ORDER BY uf, data""").df()
    con.close()
    print(f"capacidade_mmgd: {fora} linhas do cadastro sem UF, data ou potência (fora da tabela); "
          f"total cadastrado {df.groupby('uf')['potencia_acumulada_mw'].last().sum() / 1000:.2f} GW")
    df.to_csv(SAIDA_CAPACIDADE_MMGD, index=False)
    return df


# --------------------------------------------------------------------------- cobertura
def cobertura(nome: str, df: pd.DataFrame, grupo: str | None) -> pd.DataFrame:
    g = df.groupby(grupo) if grupo else [("todos", df)]
    linhas = []
    for k, d in g:
        linhas.append({"tabela": nome, "grupo": k, "linhas": len(d),
                       "inicio": d["timestamp"].min(), "fim": d["timestamp"].max()})
    return pd.DataFrame(linhas)


TABELAS = ("calendario", "carga", "rotulos", "capacidade_mmgd", "carga_area")


def construir(tabelas=TABELAS) -> pd.DataFrame:
    """Reconstrói as tabelas pedidas e atualiza docs/reports/cobertura_tabelas.csv."""
    desconhecidas = set(tabelas) - set(TABELAS)
    if desconhecidas:
        raise ValueError(f"tabelas desconhecidas: {sorted(desconhecidas)}; opções: {TABELAS}")
    ensure(DATA_PROCESSED)
    ensure(DOCS_REPORTS)
    cob = []
    if "calendario" in tabelas:
        cob.append(cobertura("calendario", construir_calendario(), None))
    if "carga" in tabelas:
        cob.append(cobertura("carga_supervisionada", construir_carga(), "subsistema"))
    if "rotulos" in tabelas:
        cob.append(construir_rotulos())  # já devolve a cobertura calculada em SQL
    if "capacidade_mmgd" in tabelas:
        cap = construir_capacidade_mmgd()
        cob.append(cobertura("capacidade_mmgd", cap.rename(columns={"data": "timestamp"}), None))
    if "carga_area" in tabelas:
        cob.append(cobertura("carga_area", construir_carga_area(), "area"))
    cob = pd.concat(cob)
    arq = DOCS_REPORTS / "cobertura_tabelas.csv"
    if arq.exists():  # atualiza só as tabelas reconstruídas
        ant = pd.read_csv(arq)
        cob = pd.concat([ant[~ant["tabela"].isin(cob["tabela"])], cob])
    cob.to_csv(arq, index=False)
    return cob


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("tabelas", nargs="*", default=list(TABELAS))
    print(construir(ap.parse_args().tabelas).to_string(index=False))


if __name__ == "__main__":
    main()
