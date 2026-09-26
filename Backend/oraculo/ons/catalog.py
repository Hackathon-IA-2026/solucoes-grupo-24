# -*- coding: utf-8 -*-
"""Catalogo curado dos conjuntos do Portal de Dados Abertos do ONS.

Esquemas verificados por inspecao direta dos recursos CSV. O catalogo curado
descreve o papel de cada conjunto na solucao; o catalogo completo (85 conjuntos)
vem da API CKAN e e navegavel na interface.
"""
from __future__ import annotations

S3 = "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset"

# ------------------------------------------------------------ esquemas reais
SCHEMA_BALANCO = {
    "id_subsistema": "U",
    "din_instante": "M8[s]",
    "val_carga": "f8",
    "val_gerhidraulica": "f8",
    "val_gertermica": "f8",
    "val_gereolica": "f8",
    "val_gersolar": "f8",
    "val_intercambio": "f8",
}

SCHEMA_CURVA_CARGA = {
    "id_subsistema": "U",
    "din_instante": "M8[s]",
    "val_cargaenergiahomwmed": "f8",
}

SCHEMA_COFF = {
    "id_subsistema": "U",
    "id_estado": "U",
    "nom_usina": "U",
    "id_ons": "U",
    "din_instante": "M8[s]",
    "val_geracao": "f8",
    "val_disponibilidade": "f8",
    "val_geracaoreferencia": "f8",
    "cod_razaorestricao": "U",
    "cod_origemrestricao": "U",
    "nom_pontoconexao": "U",
}

SCHEMA_SUBESTACAO = {
    "id_subsistema": "U",
    "id_estado": "U",
    "nom_estado": "U",
    "nom_agente_principal": "U",
    "id_subestacao": "U",
    "nom_subestacao": "U",
    "val_niveltensao": "f8",
    "val_latitude": "f8",
    "val_longitude": "f8",
}

SCHEMA_CAPACIDADE_TRAFO = {
    "id_estado": "U",
    "nom_subestacao": "U",
    "nom_transformador": "U",
    "dat_desativacao": "U",
    "val_tensaoprimario_kv": "f8",
    "val_tensaosecundario_kv": "f8",
    "val_potencianominal_mva": "f8",
    "nom_tipoderede": "U",
}

SCHEMA_MODALIDADE = {
    "nom_usina": "U",
    "ceg": "U",
    "nom_modalidadeoperacao": "U",
    "val_potenciaautorizada": "f8",
    "nom_pontoconexao": "U",
    "id_estado": "U",
}

RAZOES = {
    "REL": "Indisponibilidade externa / restrição elétrica fora da usina",
    "CNF": "Confiabilidade e segurança da operação",
    "ENE": "Razão energética — geração disponível supera a demanda",
    "PAR": "Parecer de acesso",
}
ORIGENS = {"LOC": "Local", "SIS": "Sistêmica"}


# ------------------------------------------------------------ conjuntos
CURATED: dict[str, dict] = {
    "balanco": {
        "package": "balanco-energia-subsistema",
        "title": "Balanço de Energia nos Subsistemas",
        "role": "Espinha dorsal: carga verificada e geração por fonte, horária.",
        "schema": SCHEMA_BALANCO,
        "pattern": S3 + "/balanco_energia_subsistema_ho/"
                        "BALANCO_ENERGIA_SUBSISTEMA_{year}.csv",
        "granularity": "horária · por subsistema",
        "period": "anual",
        "lag_note": "Publicação consolidada; verificar defasagem de fechamento.",
        "approx_bytes": 4_100_000,
    },
    "curva_carga": {
        "package": "curva-carga",
        "title": "Curva de Carga Horária",
        "role": "Conferência cruzada da carga e preenchimento de lacunas.",
        "schema": SCHEMA_CURVA_CARGA,
        "pattern": S3 + "/curva-carga-ho/CURVA_CARGA_{year}.csv",
        "granularity": "horária · por subsistema",
        "period": "anual",
        "lag_note": "Mesma cadência do balanço de energia.",
        "approx_bytes": 1_450_000,
    },
    "coff_fv": {
        "package": "restricao_coff_fotovoltaica",
        "title": "Constrained-off de Usinas Fotovoltaicas",
        "role": "Rótulo do Produto 2: montante, razão e origem da restrição.",
        "schema": SCHEMA_COFF,
        "pattern": S3 + "/restricao_coff_fotovoltaica_tm/"
                        "RESTRICAO_COFF_FOTOVOLTAICA_{year}_{month}.csv",
        "granularity": "semi-horária · por usina",
        "period": "mensal",
        "lag_note": "Nulos frequentes nos campos de caracterização da restrição.",
        "approx_bytes": 15_500_000,
        "since": "2024-04",
    },
    "coff_eol": {
        "package": "restricao_coff_eolica_usi",
        "title": "Constrained-off de Usinas Eólicas",
        "role": "Rótulo do Produto 2 para a fonte eólica.",
        "schema": SCHEMA_COFF,
        "pattern": S3 + "/restricao_coff_eolica_tm/"
                        "RESTRICAO_COFF_EOLICA_{year}_{month}.csv",
        "granularity": "semi-horária · por usina",
        "period": "mensal",
        "lag_note": "Cobertura desde 2021-10.",
        "approx_bytes": 20_000_000,
        "since": "2021-10",
    },
}


CURATED["subestacao"] = {
    "package": "subestacao",
    "title": "Subestação da Rede de Operação",
    "role": "Insumo do Mapa Inteligente: subestações georreferenciadas "
            "(latitude e longitude reais).",
    "schema": SCHEMA_SUBESTACAO,
    "pattern": S3 + "/subestacao/SUBESTACAO.csv",
    "granularity": "cadastral · por subestação",
    "period": "único",
    "lag_note": "Cadastro da rede de operação; nível de tensão da rede básica.",
    "approx_bytes": 250_000,
}

CURATED["capacidade_trafo"] = {
    "package": "capacidade-transformacao",
    "title": "Capacidade de Transformação da Rede Básica",
    "role": "Dimensiona a área de influência e a carga atendida por subestação.",
    "schema": SCHEMA_CAPACIDADE_TRAFO,
    "pattern": S3 + "/capacidade-transformacao/CAPACIDADE_TRANSFORMACAO.csv",
    "granularity": "cadastral · por transformador",
    "period": "único",
    "lag_note": "Inclui data de entrada em operação e de desativação.",
    "approx_bytes": 1_600_000,
}

CURATED["modalidade"] = {
    "package": "modalidade-usina",
    "title": "Modalidade de Operação de Usinas",
    "role": "Identifica usinas Tipo III conectadas à rede de distribuição, "
            "com ponto de conexão e potência autorizada.",
    "schema": SCHEMA_MODALIDADE,
    "pattern": S3 + "/modalidade_usina/MODALIDADE_USINA.csv",
    "granularity": "cadastral · por usina",
    "period": "único",
    "lag_note": "Classificação em revisão pelo ONS.",
    "approx_bytes": 900_000,
}


# Conjuntos catalogados para a fase presencial, exibidos na interface.
PLANNED: list[dict] = [
    {"package": "capacidade-geracao", "role": "Capacidade instalada por fonte e modalidade."},
    {"package": "modalidade-usina", "role": "Identificação de usinas Tipo I / II / III."},
    {"package": "subestacao", "role": "Georreferência de subestações de fronteira."},
    {"package": "fator-capacidade-2", "role": "Validação do estimador de geração."},
    {"package": "demanda_maxima_di", "role": "Extremos de demanda por dia."},
    {"package": "cmo-semi-horario", "role": "Valoração econômica do corte."},
    {"package": "restricao_coff_eolica_detail", "role": "Vento verificado por usina."},
    {"package": "restricao_coff_fotovoltaica_detail", "role": "Irradiância verificada por usina."},
    {"package": "geracao-usina-2", "role": "Geração por usina supervisionada."},
    {"package": "intercambio-nacional", "role": "Limites de exportação entre subsistemas."},
]

EXTERNAL: list[dict] = [
    {
        "name": "BDGD — Base de Dados Geográfica da Distribuidora (ANEEL)",
        "role": "Camada 2 da triangulação: topologia, alimentador, transformador.",
        "cadence": "anual",
        "status": "contrato implementado · base real pendente",
    },
    {
        "name": "Empreendimentos de Geração Distribuída (ANEEL)",
        "role": "Camada 3 da triangulação: homologação e data de registro.",
        "cadence": "diária",
        "status": "contrato implementado · base real pendente",
    },
    {
        "name": "Imagens de satélite + visão computacional",
        "role": "Camada 1 da triangulação: existência física do ativo.",
        "cadence": "mensal / trimestral",
        "status": "contrato implementado · aquisição pendente",
    },
    {
        "name": "Previsão numérica (ECMWF, GFS, WRF) e estações do INMET",
        "role": "Covariáveis meteorológicas futuras em operação.",
        "cadence": "várias rodadas diárias",
        "status": "proxy determinístico no protótipo",
    },
]


def resource_url(key: str, year: int = 0, month: int | None = None) -> str:
    spec = CURATED[key]
    if "{year}" not in spec["pattern"]:
        return spec["pattern"]          # recurso cadastral, sem periodo
    if "{month}" in spec["pattern"]:
        if month is None:
            raise ValueError("%s exige mês" % key)
        return spec["pattern"].format(year=year, month="%02d" % month)
    return spec["pattern"].format(year=year)


def resource_name(key: str, year: int, month: int | None = None) -> str:
    return resource_url(key, year, month).rsplit("/", 1)[-1]


def curated_summary() -> list[dict]:
    out = []
    for key, spec in CURATED.items():
        out.append({
            "key": key,
            "package": spec["package"],
            "title": spec["title"],
            "role": spec["role"],
            "granularity": spec["granularity"],
            "period": spec["period"],
            "lag_note": spec["lag_note"],
            "fields": list(spec["schema"].keys()),
            "approx_bytes": spec.get("approx_bytes", 0),
            "since": spec.get("since", ""),
        })
    return out
