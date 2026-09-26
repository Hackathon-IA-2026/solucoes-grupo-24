"""Caminhos das tabelas processadas (etapa 2 do run_heavywork), num módulo sem lógica.

Separado de src/processing/tabelas.py de propósito (mesmo padrão de src/spatial/saidas.py):
quem só LÊ as tabelas (modelos de carga e curtailment, publicação, testes) importa daqui.
A impressão digital do código de cada etapa (codigo_de, em src/utils/impressao.py) segue os
imports; enquanto os modelos importavam tabelas.py só por causa destes caminhos, qualquer
mudança no processamento (ex.: tabela nova carga_area) retreinava carga e curtailment
(~50 min) mesmo com as tabelas idênticas. Se o processamento mudar os DADOS, os arquivos
abaixo mudam e já entram na impressão das etapas seguintes como dado.
tests/test_heavywork.py garante que os modelos não voltem a depender do código do processamento.
"""
from src.utils.paths import DATA_PROCESSED

SAIDA_CALENDARIO = DATA_PROCESSED / "calendario.csv"
SAIDA_CARGA = DATA_PROCESSED / "carga_supervisionada.csv"
SAIDA_ROTULOS = DATA_PROCESSED / "rotulos_curtailment.parquet"
SAIDA_CAPACIDADE_MMGD = DATA_PROCESSED / "capacidade_mmgd.csv"
SAIDA_CARGA_AREA = DATA_PROCESSED / "carga_area.csv"
# Arquivos que a etapa de processamento precisa deixar prontos (o run_heavywork.py refaz a
# etapa se algum sumir, mesmo que as entradas não tenham mudado).
SAIDAS = (SAIDA_CALENDARIO, SAIDA_CARGA, SAIDA_ROTULOS, SAIDA_CAPACIDADE_MMGD, SAIDA_CARGA_AREA)

# Apelido (config/fontes_ons.yaml) do cadastro de MMGD da ANEEL, lido pelo processamento
# (capacidade_mmgd) e pela espacialização (src/spatial/mmgd.py). Fica aqui, e não em tabelas.py,
# pelo mesmo motivo dos caminhos: a espacialização não deve depender do código do processamento.
APELIDO_ANEEL_MMGD = "aneel_mmgd_empreendimentos"
