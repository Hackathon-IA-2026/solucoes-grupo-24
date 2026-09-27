"""Caminhos das saídas da espacialização (Fase 6), num módulo sem lógica.

Separado de src/spatial/construir.py de propósito: quem só LÊ as saídas (publicação, etapas do
run_heavywork) importa daqui. Assim a impressão digital do código de quem lê (codigo_de segue os
imports) não inclui o código de quem constrói, e mexer no desenho das áreas de influência não refaz a
publicação por "código mudou" (as saídas em si, se mudarem, já entram como dado).
"""
from src.utils.paths import DATA_PROCESSED, DOCS_REPORTS, OUTPUT

SAIDA_AREAS_INFLUENCIA_GEOJSON = OUTPUT / "areas_influencia_rj.geojson"
SAIDA_MMGD_AREA_INFLUENCIA = DATA_PROCESSED / "mmgd_area_influencia.csv"
SAIDA_MMGD_DIARIA = DATA_PROCESSED / "mmgd_fronteira_diaria.csv"
SAIDA_CARGA_AREA_INFLUENCIA = DATA_PROCESSED / "carga_area_influencia_mensal.csv"
SAIDA_RELATORIO = DOCS_REPORTS / "desempate_mmgd.md"
SAIDA_EXPORTADORES = DOCS_REPORTS / "alimentadores_fluxo_reverso.csv"
# Uma linha por empreendimento de MMGD com a categoria do desempate BDGD × ANEEL (sem dado pessoal):
# é o que a aba Triangulação do protótipo (oraculo/triangulation) lê para as camadas 2 e 3.
SAIDA_MMGD_EMPREENDIMENTOS = DATA_PROCESSED / "mmgd_empreendimentos.parquet"
SAIDAS = (SAIDA_AREAS_INFLUENCIA_GEOJSON, SAIDA_MMGD_AREA_INFLUENCIA, SAIDA_MMGD_DIARIA, SAIDA_CARGA_AREA_INFLUENCIA, SAIDA_RELATORIO,
          SAIDA_EXPORTADORES, SAIDA_MMGD_EMPREENDIMENTOS)
