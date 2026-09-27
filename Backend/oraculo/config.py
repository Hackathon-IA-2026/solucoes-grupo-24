# -*- coding: utf-8 -*-
"""Configuracao central do O.R.A.C.U.L.O.

Tudo que e premissa de negocio vive aqui, versionado, para que possa ser
discutido com a operacao em vez de ficar escondido no meio do codigo.
"""
from __future__ import annotations

import os
from pathlib import Path

VERSION = "0.1.0"
APP_NAME = "O.R.A.C.U.L.O."
APP_SUBTITLE = (
    "Observabilidade de Redes e Análise de Curtailment "
    "em Usinas e Limites Operacionais"
)
TEAM = "Equipe 24 — LINKFY"

# ---------------------------------------------------------------- caminhos
# ROOT = Backend/ do repositorio (raiz de import). O pacote veio do prototipo
# 02-PROTOTIPO; o cache de trabalho mora em Backend/data/oraculo_cache (fora do
# git) e a interface antiga, em HTML/JS puro, fica em oraculo/web_legado,
# servida em /legado. A interface principal e o dashboard React.
ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = ROOT.parent
CACHE_DIR = Path(os.environ.get("ORACULO_CACHE", ROOT / "data" / "oraculo_cache"))
WEB_DIR = Path(__file__).resolve().parent / "web_legado"

#: Documentacao Sphinx construida, servida pela propria aplicacao (tecla F1).
#: Fica fora de `ROOT` de proposito: e um diretorio irmao do prototipo, com
#: ciclo de vida proprio -- pode nao ter sido construida ainda, e a aplicacao
#: precisa continuar funcionando nesse caso.
DOCS_DIR = Path(os.environ.get("ORACULO_DOCS",
                               REPO_ROOT / "docs" / "oraculo" / "documentacao_sphinx"
                               / "build" / "html"))
DOCS_URL_PREFIX = "/docs"

# ---------------------------------------------------------------- rede
ONS_CKAN_BASE = "https://dados.ons.org.br/api/3/action"
HTTP_TIMEOUT = float(os.environ.get("ORACULO_HTTP_TIMEOUT", "30"))
# Permite rodar apresentacao sem rede: ORACULO_OFFLINE=1
FORCE_OFFLINE = os.environ.get("ORACULO_OFFLINE", "") == "1"
CACHE_TTL_SECONDS = int(os.environ.get("ORACULO_CACHE_TTL", str(24 * 3600)))

# ---------------------------------------------------------------- areas
# Subsistemas do balanco de energia. lat/lon sao centroides aproximados de
# carga, usados apenas na geometria solar do estimador de MMGD.
SUBSYSTEMS: dict[str, dict] = {
    "SIN": {"name": "Sistema Interligado Nacional", "lat": -15.8, "lon": -47.9},
    "SE": {"name": "Sudeste/Centro-Oeste", "lat": -21.5, "lon": -45.5},
    "S": {"name": "Sul", "lat": -28.5, "lon": -51.5},
    "NE": {"name": "Nordeste", "lat": -9.5, "lon": -39.5},
    "N": {"name": "Norte", "lat": -4.0, "lon": -50.0},
}
DEFAULT_AREA = "SIN"

# Pontos de tempo (temperatura e ponto de orvalho, Open-Meteo/ERA5) por
# subsistema: as capitais que concentram a carga de cada um. Decisao: o
# centroide geografico do subsistema (SUBSYSTEMS acima) cai no interior e
# nao representa onde o consumo esta -- a temperatura que move o ar
# condicionado e a das metropoles. Peso = populacao da regiao metropolitana
# (IBGE, estimativa 2024, milhoes), so para ponderar a media entre pontos.
WEATHER_POINTS: dict[str, list[dict]] = {
    "SE": [{"nome": "São Paulo", "lat": -23.55, "lon": -46.63, "peso": 21.5},
           {"nome": "Rio de Janeiro", "lat": -22.91, "lon": -43.17, "peso": 13.3},
           {"nome": "Belo Horizonte", "lat": -19.92, "lon": -43.94, "peso": 6.0},
           {"nome": "Brasília", "lat": -15.79, "lon": -47.88, "peso": 4.8},
           {"nome": "Goiânia", "lat": -16.68, "lon": -49.25, "peso": 2.7}],
    "S": [{"nome": "Porto Alegre", "lat": -30.03, "lon": -51.23, "peso": 4.3},
          {"nome": "Curitiba", "lat": -25.43, "lon": -49.27, "peso": 3.7},
          {"nome": "Florianópolis", "lat": -27.59, "lon": -48.55, "peso": 1.3}],
    "NE": [{"nome": "Salvador", "lat": -12.97, "lon": -38.51, "peso": 4.0},
           {"nome": "Recife", "lat": -8.05, "lon": -34.88, "peso": 4.1},
           {"nome": "Fortaleza", "lat": -3.72, "lon": -38.54, "peso": 4.1}],
    "N": [{"nome": "Belém", "lat": -1.46, "lon": -48.49, "peso": 2.5},
          {"nome": "Manaus", "lat": -3.12, "lon": -60.02, "peso": 2.3},
          {"nome": "São Luís", "lat": -2.53, "lon": -44.30, "peso": 1.6}],
}
WEATHER_POINTS["SIN"] = [p for ss in ("SE", "S", "NE", "N") for p in WEATHER_POINTS[ss]]
TZ_OFFSET_HOURS = -3.0  # horario de Brasilia

# ---------------------------------------------------------------- MMGD
# Capacidade instalada de MMGD por subsistema, em MWp.
# Ancora: 43,5 GW verificados em 2025 (ONS, PAR/PEL 2025), rateados pela
# participacao regional historica da micro e minigeracao distribuida.
MMGD_CAPACITY_MWP: dict[str, float] = {
    "SE": 21_600.0,
    "S": 9_900.0,
    "NE": 8_300.0,
    "N": 3_700.0,
}
MMGD_CAPACITY_MWP["SIN"] = float(sum(MMGD_CAPACITY_MWP.values()))

# Performance ratio agregado: perdas, orientacao, sombreamento,
# indisponibilidade e envelhecimento do parque distribuido.
MMGD_PERFORMANCE_RATIO = 0.78
# Limites do fator de nebulosidade estimado por residuo.
MMGD_CLOUD_FACTOR_MIN = 0.15
MMGD_CLOUD_FACTOR_MAX = 1.00

# ---------------------------------------------------------------- patamares
# Faixas horarias usadas na perda assimetrica e no relatorio de metricas.
PATAMARES: dict[str, tuple[int, int]] = {
    "minima_diurna": (9, 15),
    "rampa": (16, 19),
    "ponta_noturna": (18, 22),
}

# Pesos da perda assimetrica: (peso_subestimacao, peso_superestimacao).
# Subestimar a ponta noturna pode significar acionamento emergencial;
# superestimar a minima diurna significa termica cara ligada a toa.
ASYMMETRIC_WEIGHTS: dict[str, tuple[float, float]] = {
    "minima_diurna": (1.0, 2.2),
    "rampa": (2.0, 1.2),
    "ponta_noturna": (2.8, 1.0),
    "base": (1.0, 1.0),
}

QUANTILES = (0.10, 0.50, 0.90)
HORIZONS: dict[str, int] = {"30min": 1, "3h": 3, "d1": 24}  # em passos horarios

# ---------------------------------------------------------------- risco
# Limiar de corte para rotular ocorrencia de restricao, como fracao da
# capacidade agregada observada na area.
RISK_LABEL_THRESHOLD_FRACTION = 0.10
# O risco so e uma pergunta interessante DENTRO da janela solar: fora dela a
# resposta e trivialmente "nao". Treinar e avaliar so no dia forca o modelo a
# discriminar entre horas de sol com e sem restricao.
RISK_DAYLIGHT_ONLY = True
RISK_DAYLIGHT_GHI_MIN = 0.05
RISK_SEVERITY_WEIGHTS = {"probability": 0.45, "expected_mw": 0.35, "criticality": 0.20}
# Criticidade por area: fronteiras ja sinalizadas em fluxo reverso pesam mais.
AREA_CRITICALITY: dict[str, float] = {
    "MT": 1.00, "MS": 0.92, "GO": 0.88, "MG": 0.85, "BA": 0.80,
    "PI": 0.78, "RN": 0.74, "CE": 0.72, "PE": 0.70, "PB": 0.66,
    "SE": 0.60, "S": 0.55, "NE": 0.80, "N": 0.62,
}
DEFAULT_CRITICALITY = 0.50

# ---------------------------------------------------------------- fronteira T-D
# Correlacao entre subestacoes de distribuicao (SED, reconstruidas da BDGD da
# ANEEL) e subestacoes de fronteira da rede basica (ONS). Premissas de
# negocio, versionadas aqui para que a operacao possa discuti-las.
ANEEL_CKAN_BASE = "https://dadosabertos.aneel.gov.br/api/3/action"
IBGE_SIDRA_BASE = "https://apisidra.ibge.gov.br/values"
IBGE_MALHAS_BASE = "https://servicodados.ibge.gov.br/api/v3/malhas"
# Base agregada e cadastral: muda pouco, e a reconstrucao custa ~1 min.
FRONTEIRA_TTL_SECONDS = int(os.environ.get("ORACULO_FRONTEIRA_TTL",
                                           str(7 * 24 * 3600)))
FRONTEIRA = {
    # Raio maximo de busca de SE de fronteira candidata, a partir da SED.
    "raio_max_km": 150.0,
    # Escala de decaimento da atratividade com a distancia, e expoente da
    # capacidade: a(s,f) = MVA^alfa * exp(-d/lambda). Escolhidos pela
    # varredura exposta no painel de qualidade (`correlacao.sensitivity`):
    # sem verdade de campo, o criterio e a coerencia fisica -- menor
    # dispersao do carregamento implicito, nenhuma SE acima de 100% e o
    # menor numero de SEs sem carga. alfa=1 deixava 103 SEs vazias (a SE
    # grande "atrai demais"); alfa=0 (so distancia) sobrecarregava SEs em
    # ate 330%. alfa=0,5 e lambda=20 km: CV 0,62, maximo 84%, 44 vazias.
    "lambda_km": 20.0,
    "expoente_mva": 0.5,
    # A distribuidora da SED e o agente principal da SE no ONS sao do mesmo
    # grupo economico (CPFL T x CPFL Paulista, EDP Goias x EDP). O agente no
    # ONS e quase sempre a transmissora, nao a distribuidora: a coincidencia
    # e de GRUPO, evidencia moderada -- dai o bonus contido.
    "bonus_agente": 1.5,
    # Concessao de distribuicao e, quase sempre, intraestadual.
    "bonus_uf": 1.5,
    # Minimo de UCs para uma SED entrar na correlacao. A posicao que importa
    # e a da CARGA, nao a do barramento da SED: uma UC de alta tensao com
    # subestacao propria tem posicao exata. Com 3, 1.330 SEDs -- quase todas
    # consumidores industriais de AT -- sumiam da conta.
    "min_ucs": 1,
    # Abaixo desta probabilidade, a associacao e declarada ambigua.
    "limiar_ambiguo": 0.50,
    # Carregamento medio implicito fora desta faixa e sinalizado.
    "carregamento_faixa": (0.05, 1.00),
    # SAMP: somente mercados "Regular". As linhas de "Sistema de
    # Compensacao GD" registram energia COMPENSADA, e soma-las ao Regular
    # conta o mesmo consumo duas vezes (verificado: Regular residencial
    # 2025 = 160 TWh, a ordem de grandeza do residencial nacional).
    "samp_ano": 2025,
    "samp_mercados": ("Regular", "Refaturamento - Regular",
                      "Sistema Isolado - Regular",
                      "Sistema Individual - Regular"),
    "samp_subgrupos_bt": ("B", "B1", "B2", "B3", "B4"),
}
# Classes de consumo da ANEEL -> classes do Modelo de Carga Composta. Poder
# publico, servico publico, iluminacao e consumo proprio vao para "comercial":
# perfil diurno de servicos, sem motor de processo. Premissa declarada.
CLASSE_CLM = {
    "RE": "residencial", "CO": "comercial", "IN": "industrial", "RU": "rural",
    "PP": "comercial", "SP": "comercial", "IP": "comercial", "CP": "comercial",
    "CS": "comercial",
}

# ---------------------------------------------------------------- BESS
# Apoio a decisao de investimento em armazenamento: onde um BESS recupera
# mais energia cortada, com peso para a penetracao de MMGD. Premissas de
# negocio, versionadas; os pesos podem ser ajustados na tela.
BESS = {
    # Janela: os ultimos N meses COMPLETOS de constrained-off (FV + eolica).
    "meses": 12,
    # Eficiencia de ida e volta tipica de ion-litio no ponto de conexao.
    "eficiencia": 0.88,
    # BESS de referencia para comparar sitios em pe de igualdade (MW, h),
    # limitado a disponibilidade maxima do sitio.
    "referencia": (100.0, 4.0),
    # Grade do dimensionamento.
    "potencias_mw": (25.0, 50.0, 100.0, 200.0, 300.0, 500.0),
    "duracoes_h": (2.0, 4.0, 6.0),
    # Abaixo disto o ativo cicla pouco para se pagar com arbitragem de corte:
    # e o limiar que separa "utilizacao adequada" de "baixa" no dimensionamento.
    "ciclos_min_ano": 200.0,
    # Raio para listar a MMGD vizinha de uma SE de fronteira (tese BESS
    # junto a carga). NAO entra na pontuacao do sitio de geracao.
    "raio_mmgd_km": 100.0,
    # Pesos da pontuacao (normalizados). "mmgd" e a FRACAO do corte do sitio
    # atribuivel ao excedente sistemico que a MMGD cria (ENE + SIS dentro da
    # curva do pato) -- nao a MMGD instalada perto da usina. "local" e o seu
    # quase complemento: corte de restricao na rede do ponto. Os dois
    # expressam teses diferentes; os pesos padrao nao escolhem uma delas.
    "pesos": {"energia": 0.45, "mmgd": 0.20, "recorrencia": 0.20, "local": 0.15},
}

# ---------------------------------------------------------------- projecao ENE
# Projecao do corte por razao energetica e do BESS que ele justifica. As taxas
# dos cenarios NAO sao projecao oficial: sao derivadas das series observadas
# (balanco de energia do ONS e cadastro de MMGD da ANEEL) e ficam editaveis.
ENE = {
    # Calibracao: so a partir de 04/2024, quando o corte FV passa a ser
    # publicado; antes disso a serie do SIN esta incompleta.
    "inicio_calibracao": "2024-04",
    # Backtest: ajusta antes deste mes, testa a partir dele.
    "corte_backtest": "2025-09",
    # Horizonte, em anos, a partir do ano de referencia (12 ultimos meses).
    "anos": 4,
    # Grade do BESS no SIN (GW x h) e criterio de ciclo marginal (config.BESS).
    "potencias_gw": (1.0, 2.0, 3.0, 5.0, 8.0, 12.0, 16.0, 20.0, 25.0, 30.0, 40.0,
                     50.0, 60.0),
    # Acima desta fracao da geracao eolica + solar POTENCIAL cortada, o cenario
    # e economicamente inconsistente: o modelo nao tem realimentacao (ninguem
    # segue construindo usinas nesse ritmo com esse corte). Sinalizado, nao
    # escondido.
    "corte_max_plausivel": 0.25,
    "duracoes_h": (2.0, 4.0, 6.0),
    # Defasagem de cadastro da MMGD: os ultimos meses sao sub-registrados.
    "defasagem_cadastro_meses": 3,
    # Trajetoria OFICIAL: PAR/PEL 2025 (ONS), Sumario Executivo. Valores
    # transcritos do documento; as taxas anuais sao calculadas deles. Aplica-se
    # a TAXA, nao o nivel: o cadastro da ANEEL (53,7 GW FV em 08/2026) e o
    # PAR/PEL (46,2 GW em dez/2025) contabilizam bases diferentes.
    "parpel": {
        "fonte": "ONS · PAR/PEL 2025 — Sumário Executivo",
        "url": "https://www.ons.org.br/Paginas/energia-no-futuro/"
               "suprimento-eletrico/parpel2025/sumario-executivo/index.aspx",
        "mmgd_dez2025_gw": 46.2,
        "mmgd_2029_gw": 65.3,             # fim de 2029, base do PMO
        "mmgd_2030_dist_gw": 60.9,        # 2030, base das distribuidoras
        "vre_dez2025_gw": 55.1,           # eolica + solar centralizadas
        "vre_2029_gw": 60.3,
        "carga_max_2030_crescimento": 0.17,   # sobre a maxima de 2025
    },
    # Trajetoria OFICIAL de carga global e MMGD: ONS/EPE/CCEE, "Previsoes de
    # Carga Global para o Planejamento Anual da Operacao Energetica — 2a
    # Revisao Quadrimestral do PLAN 2026-2030", 07/08/2026. Valores do SIN
    # transcritos das tabelas do documento (MWmed; capacidade em GW).
    "plan": {
        "fonte": "ONS/EPE/CCEE · 2ª Revisão Quadrimestral do PLAN 2026-2030 "
                 "(07/08/2026)",
        "url": "https://www.ccee.org.br/o/ccee/documentos/CCEE_1363305",
        "carga_global_mwmed": {2025: 81630, 2026: 84989, 2027: 88785, 2028: 92634,
                               2029: 97153, 2030: 101947},
        "mmgd_mwmed": {2026: 8536, 2027: 9343, 2028: 9974, 2029: 10610, 2030: 11240},
        "mmgd_gw": {2025: 48.2, 2026: 55.6, 2027: 59.8, 2028: 64.0, 2029: 68.3,
                    2030: 72.5},
        # ano do PLAN que representa o ano de referencia (set/25-ago/26: 8 dos
        # 12 meses em 2026)
        "ano_base": 2026,
    },
}

# ---------------------------------------------------------------- tempo x MMGD
# Previsao da curva do pato pelo tempo. MMGD media por subsistema em 2026 da
# 2a RQ do PLAN 2026-2030 (ONS/EPE/CCEE, tabela "Total (Base + Expansao)").
TEMPO = {
    "mmgd_mwmed_ss": {"SE": 4406, "S": 1616, "NE": 1786, "N": 727},
    "era5_lag_dias": 6,          # o ERA5 do Open-Meteo chega com ~5 dias de atraso
    "backtest_dias": 63,
    "dias_previsao": 7,
}

# ---------------------------------------------------------------- modelos
L2_PENALTY = 1e-3
RANDOM_SEED = 20260913
FOURIER_ORDERS = {"daily": 4, "weekly": 2, "yearly": 2}
LAG_HOURS = (1, 2, 24, 168)
BACKTEST_TRAIN_FRACTION = 0.70

# ---------------------------------------------------------------- textos
DEMO_BANNER = "DADOS DEMONSTRATIVOS"
DISCLAIMER = (
    "Valores de MMGD são estimados, não medidos. O produto apoia a decisão "
    "humana e não automatiza despacho."
)

SOURCES = [
    {
        "label": "ONS · PAR/PEL 2025 — Sumário Executivo",
        "url": "https://www.ons.org.br/Paginas/energia-no-futuro/"
               "suprimento-eletrico/parpel2025/sumario-executivo/index.aspx",
    },
    {"label": "ONS · Portal de Dados Abertos", "url": "https://dados.ons.org.br/"},
    {
        "label": "ONS · FAQ Curtailment",
        "url": "https://www.ons.org.br/Paginas/faq_curtailment.aspx",
    },
    {
        "label": "WECC · Composite Load Model Specification",
        "url": "https://www.wecc.org/sites/default/files/documents/meeting/2024/"
               "WECC%20Comp%20Load%20Model%20Specification_final.pdf",
    },
]


def patamar_of_hour(hour: int) -> str:
    """Classifica a hora do dia no patamar operativo correspondente."""
    for name, (a, b) in PATAMARES.items():
        if a <= hour <= b:
            return name
    return "base"


def criticality_of(area: str) -> float:
    return AREA_CRITICALITY.get(area, DEFAULT_CRITICALITY)


def capacity_of(area: str) -> float:
    return MMGD_CAPACITY_MWP.get(area, MMGD_CAPACITY_MWP["SIN"] * 0.1)
