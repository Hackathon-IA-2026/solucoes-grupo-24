"""Etapa de espacialização (Fase 6): BDGD -> áreas de influência -> MMGD por área de influência -> pesos de carga.

Chamada pela etapa "espacializacao" do Backend/run_heavywork.py via `construir()`. Linha de
comando para depuração:
    python -m src.spatial.construir

Saídas:
    output/areas_influencia_rj.geojson              áreas de influência (polígonos) + atributos de MMGD (Mapa Híbrido;
                                           fora do contrato até combinar o schema com o Luiz)
    data/processed/mmgd_area_influencia.csv         uma linha por área de influência: rede, capacidade por categoria,
                                           fonte, fator de correção, pontos (subestação e interno)
    data/processed/mmgd_fronteira_diaria.csv  subestação de fronteira × data: capacidade de MMGD
                                           cadastrada no dia e acumulada (base dos excedentes)
    data/processed/carga_area_influencia_mensal.csv subestação de fronteira × mês: energia bruta (BDGD) e
                                           peso na carga da área
    docs/reports/desempate_mmgd.md         BDGD × cadastro ANEEL por distribuidora
    docs/reports/alimentadores_fluxo_reverso.csv  alimentadores com energia líquida negativa
"""
from __future__ import annotations

import geopandas as gpd
import pandas as pd

from src.spatial import bdgd, excedentes, areas_influencia, mmgd
from src.utils.config import arquivo_direto
from src.spatial.saidas import (SAIDA_CARGA_AREA_INFLUENCIA, SAIDA_EXPORTADORES, SAIDA_MMGD_EMPREENDIMENTOS, SAIDA_AREAS_INFLUENCIA_GEOJSON,
                                SAIDA_MMGD_DIARIA, SAIDA_MMGD_AREA_INFLUENCIA, SAIDA_RELATORIO)
from src.utils.paths import DATA_PROCESSED, DOCS_REPORTS, OUTPUT, ensure

APELIDO_MALHA_UF = "ibge_malha_rj"


def _entradas_carga() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Alimentadores e consumidores AT de todas as distribuidoras (a carga da área é uma só)."""
    cts, ucs = [], []
    for d in bdgd.distribuidoras():
        cts.append(bdgd.circuitos(d))
        ucs.append(bdgd.consumidores_at(d))
    return pd.concat(cts, ignore_index=True), pd.concat(ucs, ignore_index=True)


def relatorio(unidades: pd.DataFrame, geo: gpd.GeoDataFrame, exportadores: pd.DataFrame) -> str:
    """Markdown do desempate BDGD × ANEEL e da qualidade das áreas de influência."""
    u = unidades.drop_duplicates(["distribuidora", "ceg"])
    linhas = ["# Desempate da MMGD: BDGD × cadastro da ANEEL (área piloto RJ)", "",
              "Gerado por `python -m src.spatial.construir` (etapa `espacializacao` do run_heavywork).",
              "Método em `docs/metodo_espacial.md`. Potências em MW.", "",
              "| distribuidora | BDGD (data) | categoria | empreendimentos | potência ANEEL | potência BDGD |",
              "|---|---|---|---:|---:|---:|"]
    for (dist, cat), g in u.groupby(["distribuidora", "categoria"]):
        data_bdgd = g["data_bdgd"].iloc[0].date()
        pa = g["pot_aneel_kw"].sum() / 1000
        pb = g["pot_bdgd_kw"].sum() / 1000
        linhas.append(f"| {dist} | {data_bdgd} | {cat} | {len(g):,} | {pa:,.1f} | {pb:,.1f} |")
    linhas += ["", "## Leitura", ""]
    for dist, g in u.groupby("distribuidora"):
        amb = g[g["categoria"] == "bdgd_e_aneel"]
        razao = (amb["pot_bdgd_kw"] / amb["pot_aneel_kw"]).median()
        lag = g[g["categoria"] == "lag_sistema"]
        antes = (lag["data"] <= lag["data_bdgd"]).sum()
        sem_area = unidades[(unidades["distribuidora"] == dist) & (unidades["categoria"] == "lag_sistema")
                              & unidades["area_id"].isna()]
        linhas.append(f"- **{dist}**: potência BDGD ÷ ANEEL (mediana, mesmo CEG) = {razao:.2f}. "
                      f"Lag de sistema: {len(lag):,} empreendimentos ({lag['pot_aneel_kw'].sum() / 1000:,.1f} MW), "
                      f"dos quais {antes:,} cadastrados na ANEEL até a data da BDGD (ausentes da BDGD, não só atrasados). "
                      f"Lag sem rede da distribuidora no município (sem área de influência): {sem_area['ceg'].nunique():,} "
                      f"({sem_area['pot_aneel_kw'].sum() / 1000:,.2f} MW).")
    vazias = geo[geo["geometria_vazia"]]
    linhas += ["", "## Áreas de influência", "",
               f"- {len(geo)} áreas de influência (uma por subestação), {int((geo['origem'] == 'semente').sum())} "
               f"sem transformadores suficientes para o fecho (semente + Voronoi).",
               f"- Geometria vazia depois dos recortes: {len(vazias)} "
               f"({', '.join(vazias['area_id']) or 'nenhuma'}); a MMGD delas continua contada.",
               f"- Recorte pelo limite do IBGE ignorado (apagaria a área de influência): {int(geo['recorte_ignorado'].sum())}.",
               f"- Classificação: " + "; ".join(f"{k}: {v}" for k, v in geo["classificacao"].value_counts().items()) + ".",
               "", "## Fluxo reverso medido (BDGD)", "",
               f"{len(exportadores)} alimentadores têm energia líquida negativa em pelo menos um mês "
               f"(exportam para a subestação; lista em `docs/reports/alimentadores_fluxo_reverso.csv`), "
               f"com origem em {exportadores['area_id'].nunique()} áreas de influência: "
               f"{', '.join(geo.set_index('area_id').reindex(exportadores['area_id'].unique())['nome'].fillna('?'))}. "
               "É a evidência medida pela distribuidora com que os excedentes previstos devem bater.", ""]
    return "\n".join(linhas)


def construir() -> str:
    """Roda a espacialização inteira e grava as saídas. Devolve o resumo da etapa."""
    limite = gpd.read_file(arquivo_direto(APELIDO_MALHA_UF))
    geo = areas_influencia.construir_areas(limite)
    rep = geo.to_crs(bdgd.cfg()["geometria"]["crs_metrico"]).representative_point().to_crs("EPSG:4326")
    # Área de influência vazia: o ponto interno é o da própria subestação.
    geo["lat_rep"] = rep.y.where(~geo["geometria_vazia"], geo["lat_sub"]).round(6)
    geo["lon_rep"] = rep.x.where(~geo["geometria_vazia"], geo["lon_sub"]).round(6)

    fator = mmgd.fator_correcao_satelite()
    m = mmgd.construir(fator)
    resumo = mmgd.resumo_por_area(m["unidades"], fator)
    geo = geo.merge(resumo, on="area_id", how="left")
    num = resumo.columns.drop(["area_id", "fonte", "fator_correcao"])
    geo[num] = geo[num].fillna(0.0)
    orfas = set(resumo["area_id"]) - set(geo["area_id"])
    if orfas:  # MMGD numa subestação que não existe na camada SUB: nunca descartar calado
        raise ValueError(f"MMGD em subestações fora da camada SUB da BDGD: {sorted(orfas)[:10]}")

    circuitos, consumidores_at = _entradas_carga()
    pesos = excedentes.pesos_carga(circuitos, consumidores_at, m["energia_mensal"])
    fora = set(pesos["area_id"]) - set(geo["area_id"])
    if fora:  # carga numa "área de influência" que não existe na camada SUB: id quebrado, nunca publicar
        raise ValueError(f"pesos de carga com área de influência fora da camada SUB: {sorted(fora)[:10]}")
    exportadores = excedentes.alimentadores_exportadores(circuitos)

    ensure(OUTPUT), ensure(DATA_PROCESSED), ensure(DOCS_REPORTS)
    geo.to_file(SAIDA_AREAS_INFLUENCIA_GEOJSON, driver="GeoJSON")
    geo.drop(columns="geometry").to_csv(SAIDA_MMGD_AREA_INFLUENCIA, index=False)
    m["diaria_fronteira"].to_csv(SAIDA_MMGD_DIARIA, index=False)
    pesos.to_csv(SAIDA_CARGA_AREA_INFLUENCIA, index=False)
    exportadores.to_csv(SAIDA_EXPORTADORES, index=False)
    mmgd.por_empreendimento(m["unidades"]).to_parquet(SAIDA_MMGD_EMPREENDIMENTOS, index=False)
    SAIDA_RELATORIO.write_text(relatorio(m["unidades"], geo, exportadores), encoding="utf-8")
    cap = geo["capacidade_mmgd_kw"].sum() / 1000
    return (f"{len(geo)} áreas de influência, MMGD {cap:,.1f} MW "
            f"({geo['capacidade_lag_kw'].sum() / 1000:,.1f} MW de lag de sistema rateado)")


if __name__ == "__main__":
    print(construir())
