"""Tabelas de cadastro e de recorte espacial que tiram os mocks do dashboard (MVP real, 2026-09-26).

Chamado pela etapa 2 do run_heavywork.py (via tabelas.construir). Hoje só `construir_usinas`
está ligada (tabela "usinas"); MMGD por município e carga por área de carga ficam disponíveis
para quando uma tela precisar (a densidade de MMGD do mapa já sai de src/spatial). Saídas em
data/processed/:

    usinas_cadastro.csv   usina/conjunto (chave fonte:id_ons): ponto de conexão, agente operador
                          e COORDENADA real (SIGA/ANEEL) — Lista de Riscos e Mapa Híbrido
    mmgd_municipio.csv    capacidade de MMGD por município (ANEEL) no centro do município (IBGE)
                          — camada de densidade do Mapa Híbrido
    carga_areas.csv       carga global e MMGD por ÁREA DE CARGA do ONS, 30 min — Excedentes TSO-DSO

Decisões (conferidas no dado em 2026-09-26):
- As bases tm do ONS estão por CONJUNTO de usinas: o `ceg` vem "-" em quase todas as linhas.
  O cadastro `usina_conjunto` do ONS liga cada conjunto às usinas e ao CEG de cada uma; a
  coordenada do conjunto é a média das coordenadas das usinas no SIGA, ponderada pela potência
  outorgada. CEG do ONS ("…-0.01") e do SIGA ("…-0.1") só diferem na versão: o casamento é pelo
  código antes do "-" (99,8% dos CEGs de usinas eólicas/solares do ONS casam).
- Coordenada de subestação no cadastro de MMGD da ANEEL cobre só 0,09% da potência: não serve.
  O município (código IBGE) está em 100% dos registros, então a densidade é por município.
- PRIVACIDADE: o cadastro de MMGD tem CPF/CNPJ, nome do titular e CEP. Os SELECTs daqui leem só
  município, UF, distribuidora, potência e data — nenhuma coluna pessoal sai de data/raw.
- Carga por área: mesma leitura (e mesma deduplicação) da carga supervisionada por subsistema
  (carga_bruta.ler_carga_verificada): um jeito só de ler a API de carga.
"""
from __future__ import annotations

import pandas as pd

from src.processing.carga_bruta import ler_carga_verificada
from src.utils.banco_analitico import conectar
from src.processing.saidas import SAIDA_USINAS_CADASTRO as SAIDA_USINAS
from src.utils.config import arquivo_direto
from src.utils.joins import codigos_areacarga
from src.utils.paths import DATA_PROCESSED, RAW_ONS

# Caminho das usinas em src/processing/saidas.py (a publicação lê sem importar este módulo).
SAIDA_MMGD_MUNICIPIO = DATA_PROCESSED / "mmgd_municipio.csv"
SAIDA_CARGA_AREAS = DATA_PROCESSED / "carga_areas.csv"
SAIDAS_CADASTRO = (SAIDA_USINAS, SAIDA_MMGD_MUNICIPIO, SAIDA_CARGA_AREAS)

# bases tm (curtailment) por fonte: as mesmas dos rótulos
BASES_TM = {"eolica": "coff_eolica_tm", "solar": "coff_solar_tm"}


def _parquet_de(apelido: str) -> str:
    """Destino do arquivo direto já convertido para Parquet (CSV/GeoJSON viram .parquet na chegada)."""
    return arquivo_direto(apelido).with_suffix(".parquet").as_posix()


# --------------------------------------------------------------------------- usinas
def construir_usinas() -> pd.DataFrame:
    """Uma linha por usina/conjunto das bases tm, com ponto de conexão, agente e coordenada."""
    con = conectar()
    uniao = " UNION ALL BY NAME ".join(
        f"""SELECT '{fonte}' AS fonte, id_ons, nom_usina, id_estado AS uf, id_subsistema AS subsistema,
                   nullif(trim(ceg), '-') AS ceg, nullif(trim(nom_pontoconexao), '') AS ponto_conexao,
                   nullif(trim(nom_agenteoperador), '') AS agente_operador, din_instante
            FROM read_parquet('{(RAW_ONS / base).as_posix()}/**/*.parquet', hive_partitioning=false, union_by_name=true)"""
        for fonte, base in BASES_TM.items())
    # atributos do registro MAIS RECENTE de cada usina/conjunto (ponto de conexão e agente mudam)
    usinas = con.sql(f"""
        SELECT fonte || ':' || id_ons AS chave, fonte, id_ons,
               arg_max(nom_usina, din_instante) AS nom_usina,
               arg_max(uf, din_instante) AS uf,
               arg_max(subsistema, din_instante) AS subsistema,
               arg_max(ponto_conexao, din_instante) FILTER (WHERE ponto_conexao IS NOT NULL) AS ponto_conexao,
               arg_max(agente_operador, din_instante) FILTER (WHERE agente_operador IS NOT NULL) AS agente_operador,
               arg_max(ceg, din_instante) FILTER (WHERE ceg IS NOT NULL) AS ceg_proprio
        FROM ({uniao}) GROUP BY ALL""").df()

    # membros de cada conjunto (relacionamento vigente = sem data de fim, ou a mais recente)
    membros = con.sql(f"""
        SELECT id_ons_conjunto AS id_ons, nullif(trim(ceg), '') AS ceg
        FROM read_parquet('{(RAW_ONS / 'usina_conjunto').as_posix()}/*.parquet')
        QUALIFY row_number() OVER (PARTITION BY id_ons_conjunto, id_ons_usina
                                   ORDER BY dat_fimrelacionamento IS NULL DESC, dat_fimrelacionamento DESC) = 1
          AND dat_fimrelacionamento IS NULL""").df()

    # SIGA: coordenada e potência por CEG sem a versão (uma linha por código: a de maior potência)
    siga = con.sql(f"""
        SELECT split_part(CodCEG, '-', 1) AS ceg_base,
               arg_max(replace(NumCoordNEmpreendimento, ',', '.')::DOUBLE, try_cast(replace(MdaPotenciaOutorgadaKw, ',', '.') AS DOUBLE)) AS lat,
               arg_max(replace(NumCoordEEmpreendimento, ',', '.')::DOUBLE, try_cast(replace(MdaPotenciaOutorgadaKw, ',', '.') AS DOUBLE)) AS lon,
               max(try_cast(replace(MdaPotenciaOutorgadaKw, ',', '.') AS DOUBLE)) / 1000.0 AS potencia_mw
        FROM read_parquet('{_parquet_de('aneel_siga_empreendimentos')}')
        WHERE CodCEG IS NOT NULL AND NumCoordNEmpreendimento IS NOT NULL AND NumCoordEEmpreendimento IS NOT NULL
        GROUP BY 1""").df()
    con.close()

    # CEGs de cada chave: os membros (conjunto) ou o próprio CEG (usina avulsa)
    cegs = pd.concat([
        membros.dropna(subset=["ceg"]),
        usinas.loc[usinas["ceg_proprio"].notna(), ["id_ons", "ceg_proprio"]].rename(columns={"ceg_proprio": "ceg"}),
    ]).drop_duplicates()
    cegs["ceg_base"] = cegs["ceg"].str.split("-").str[0]
    pos = cegs.merge(siga, on="ceg_base", how="left")
    # coordenadas fora do Brasil (erro de cadastro, lat/lon trocados) não entram na média
    ok = pos["lat"].between(-34, 6) & pos["lon"].between(-74, -28)
    pos.loc[~ok, ["lat", "lon"]] = pd.NA
    pos["peso"] = pos["potencia_mw"].fillna(0).clip(lower=0) + 1e-9  # sem potência: peso quase nulo, mas conta
    agg = pos.groupby("id_ons").apply(
        lambda g: pd.Series({
            "n_usinas": len(g),
            "n_usinas_com_coord": int(g["lat"].notna().sum()),
            "lat": (g["lat"] * g["peso"]).sum() / g.loc[g["lat"].notna(), "peso"].sum() if g["lat"].notna().any() else pd.NA,
            "lon": (g["lon"] * g["peso"]).sum() / g.loc[g["lon"].notna(), "peso"].sum() if g["lon"].notna().any() else pd.NA,
            "potencia_siga_mw": g["potencia_mw"].sum(min_count=1),
        }), include_groups=False).reset_index()

    out = usinas.drop(columns=["ceg_proprio"]).merge(agg, on="id_ons", how="left")
    out["coord_origem"] = out["lat"].notna().map({True: "siga", False: None})
    out = out.sort_values("chave").reset_index(drop=True)
    print(f"usinas_cadastro: {len(out)} usinas/conjuntos; {out['lat'].notna().mean():.1%} com coordenada do SIGA; "
          f"{out['ponto_conexao'].notna().mean():.1%} com ponto de conexão")
    out.to_csv(SAIDA_USINAS, index=False)
    return out


# --------------------------------------------------------------------------- MMGD por município
def construir_mmgd_municipio() -> pd.DataFrame:
    """Capacidade de MMGD por município (ANEEL) no ponto representativo do município (IBGE).

    Ponto representativo = `representative_point` do polígono (sempre DENTRO do município, ao
    contrário do centroide, que cai fora em municípios côncavos).
    """
    import geopandas as gpd

    con = conectar()
    fonte = arquivo_direto("aneel_mmgd_empreendimentos").as_posix()
    mmgd = con.sql(f"""
        SELECT lpad(CAST(CodMunicipioIbge AS VARCHAR), 7, '0') AS cod_municipio,
               any_value(NomMunicipio) AS municipio, any_value(SigUF) AS uf,
               arg_max(SigAgente, MdaPotenciaInstaladaKW) AS distribuidora,
               sum(MdaPotenciaInstaladaKW) / 1000.0 AS potencia_mw, count(*) AS n_empreendimentos,
               max(DatGeracaoConjuntoDados) AS data_base
        FROM read_parquet('{fonte}')
        WHERE CodMunicipioIbge IS NOT NULL AND MdaPotenciaInstaladaKW IS NOT NULL
        GROUP BY 1""").df()
    con.close()

    malha = gpd.read_parquet(_parquet_de("ibge_malha_municipios"))
    malha["cod_municipio"] = malha["codarea"].astype(str).str.zfill(7)
    pontos = malha.geometry.representative_point()
    malha["lat"], malha["lon"] = pontos.y, pontos.x
    out = mmgd.merge(malha[["cod_municipio", "lat", "lon"]], on="cod_municipio", how="left")
    sem = out["lat"].isna()
    print(f"mmgd_municipio: {len(out)} municípios, {out['potencia_mw'].sum() / 1000:.2f} GW; "
          f"{out.loc[sem, 'potencia_mw'].sum():.1f} MW em códigos sem malha do IBGE (fora da camada)")
    out = out.sort_values("cod_municipio").reset_index(drop=True)
    out.to_csv(SAIDA_MMGD_MUNICIPIO, index=False)
    return out


# --------------------------------------------------------------------------- carga por área
def construir_carga_areas() -> pd.DataFrame:
    """Carga global e MMGD por área de carga do ONS (tipo 'area' no mapeamento), 30 min."""
    # lista das áreas vem de joins.py (única leitura autorizada do mapeamento subsistema × área)
    areas = codigos_areacarga("area")
    df = ler_carga_verificada(areas)
    out = pd.DataFrame({
        "cod_areacarga": df["cod_areacarga"],
        "timestamp": df["timestamp"],
        "carga_global": df["val_cargaglobal"],  # ≤ 0 (falha de medição) já vem NaN de ler_carga_verificada
        "mmgd_estimada": df["val_cargammgd"],
    }).sort_values(["cod_areacarga", "timestamp"]).reset_index(drop=True)
    print(f"carga_areas: {out['cod_areacarga'].nunique()} áreas, {len(out)} linhas, "
          f"{out['timestamp'].min()} → {out['timestamp'].max()}")
    out.to_csv(SAIDA_CARGA_AREAS, index=False)
    return out
