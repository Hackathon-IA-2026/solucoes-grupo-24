# 04 · Modelo de dados

## 4.1 Fontes reais utilizadas

Esquemas **verificados por inspeção direta** do Portal de Dados Abertos do ONS em
setembro de 2026 (API CKAN `package_show` + cabeçalho dos recursos CSV).

### 4.1.1 Balanço de Energia nos Subsistemas — `balanco-energia-subsistema`

Periodicidade horária, por subsistema. É a **espinha dorsal** do protótipo:
traz carga verificada e geração por fonte na mesma grade temporal.

```
id_subsistema;nom_subsistema;din_instante;val_gerhidraulica;val_gertermica;
val_gereolica;val_gersolar;val_carga;val_intercambio
```

| Campo | Tipo | Uso na solução |
|---|---|---|
| `id_subsistema` | texto (`N`, `NE`, `S`, `SE`, `SIN`) | chave de área |
| `din_instante` | timestamp (`YYYY-MM-DD HH:MM:SS`) | grade horária |
| `val_carga` | MWmed | **alvo**: carga supervisionada verificada |
| `val_gersolar` | MWmed | geração fotovoltaica **centralizada** supervisionada |
| `val_gereolica` | MWmed | geração eólica supervisionada |
| `val_gerhidraulica`, `val_gertermica` | MWmed | margem de fontes controláveis |
| `val_intercambio` | MWmed | contexto de exportação entre subsistemas |

Recurso: `.../dataset/balanco_energia_subsistema_ho/BALANCO_ENERGIA_SUBSISTEMA_<ano>.csv`
(≈ 4 MB/ano). Cobertura verificada: 2000 → 2026.

> **Atenção de modelagem.** `val_gersolar` é geração *supervisionada*. A MMGD
> **não** está nesta série — ela aparece apenas como redução de `val_carga`. Essa
> é exatamente a lacuna que o produto ataca (ver `06-modelos-analiticos.md`).

### 4.1.2 Curva de Carga Horária — `curva-carga`

```
id_subsistema;nom_subsistema;din_instante;val_cargaenergiahomwmed
```

Série de carga por subsistema (≈ 1,4 MB/ano). Usada para conferência cruzada com
`val_carga` do balanço e para preencher lacunas.

### 4.1.3 Constrained-off fotovoltaico — `restricao_coff_fotovoltaica`

Semi-horário, **por usina**. Fonte do rótulo do Produto 2.

```
id_subsistema;nom_subsistema;id_estado;nom_estado;nom_usina;id_ons;ceg;
din_instante;val_geracao;val_geracaolimitada;val_disponibilidade;
val_geracaoreferencia;val_geracaoreferenciafinal;cod_razaorestricao;
cod_origemrestricao;dsc_restricao;id_pontoconexao;nom_pontoconexao;
nom_agenteoperador;...
```

| Campo | Uso |
|---|---|
| `din_instante` | grade semi-horária → agregada para horária |
| `nom_usina`, `id_ons`, `ceg` | identificação do ativo |
| `id_estado` | agregação geográfica (proxy de área de concessão no protótipo) |
| `val_disponibilidade` | potência disponível no instante |
| `val_geracao` | geração verificada |
| `val_geracaoreferencia` | referência para apuração do montante restringido |
| `cod_razaorestricao` | **razão**: `REL`, `CNF`, `ENE`, `PAR` |
| `cod_origemrestricao` | **origem**: `LOC` (local) ou `SIS` (sistêmica) |
| `nom_pontoconexao` | ponto de conexão — proxy de transformação de fronteira |

Recurso mensal: `RESTRICAO_COFF_FOTOVOLTAICA_<ano>_<mês>.csv` (≈ 15 MB/mês).
Cobertura verificada: 2024-04 → 2026-09.

### 4.1.4 Constrained-off eólico — `restricao_coff_eolica_usi`

Mesmo esquema, cobertura 2021-10 → 2026-09. Recursos mensais em
`.../dataset/restricao_coff_eolica_tm/RESTRICAO_COFF_EOLICA_<ano>_<mês>.csv`.

### 4.1.5 Conjuntos auxiliares catalogados

Registrados no catálogo curado e navegáveis na interface, com uso previsto na
fase presencial:

| Conjunto | Uso previsto |
|---|---|
| `capacidade-geracao` | capacidade instalada por fonte e modalidade |
| `modalidade-usina` | identificação de usinas Tipo I / II / III |
| `subestacao` | georreferência de subestações de fronteira |
| `fator-capacidade-2` | validação do estimador de geração |
| `demanda_maxima_di` | extremos de demanda por dia |
| `cmo-semi-horario` | custo marginal de operação, para valorar o corte |
| `restricao_coff_*_detail` | vento e irradiância verificados por usina |
| `geracao-usina-2` | geração por usina supervisionada |

### 4.1.6 Fontes não públicas ou fora do protótipo

| Fonte | Estado | Tratamento |
|---|---|---|
| BDGD (ANEEL) | download volumoso por distribuidora, periodicidade anual | contrato implementado; conjunto demonstrativo com os campos reais |
| Planilha de Empreendimentos de GD (ANEEL) | atualização diária | contrato implementado; conjunto demonstrativo |
| Imagens de satélite | disponibilidade, custo e data de captura variáveis | contrato implementado; camada de evidência simulada com metadados reais |
| Previsão numérica (ECMWF, GFS, WRF) e INMET | requisito de produção | proxy determinístico de nebulosidade no protótipo |

## 4.2 Contratos internos

### 4.2.1 `Provenance`

Acompanha toda série e chega até a tela. Atende RNF-04.

```python
Provenance(
    dataset: str,        # "balanco-energia-subsistema"
    resource: str,       # "BALANCO_ENERGIA_SUBSISTEMA_2025.csv"
    url: str,            # URL completa do recurso
    fetched_at: str,     # ISO-8601 UTC do instante de extração
    rows: int,           # registros efetivamente lidos
    mode: str,           # "live" | "cache" | "demo"
    lag_note: str,       # defasagem declarada da fonte
    bytes_read: int,
)
```

### 4.2.2 `Frame`

Tabela colunar mínima: `dict[str, numpy.ndarray]` com o mesmo comprimento,
`Provenance` associada e operações `select`, `where`, `sort_by`, `group_by`,
`join_on`, `add_column`, `to_records`.

Por que não um `dict` simples: as operações de agrupamento por área e por hora
aparecem em cinco módulos distintos; concentrá-las evita divergência.

### 4.2.3 Séries canônicas do domínio

| Nome | Unidade | Grade | Origem |
|---|---|---|---|
| `carga_supervisionada` | MWmed | horária | `val_carga` do balanço |
| `mmgd_estimada` | MWmed | horária | estimador (`models/mmgd.py`) |
| `carga_global` | MWmed | horária | `carga_supervisionada + mmgd_estimada` |
| `ger_solar_centralizada` | MWmed | horária | `val_gersolar` |
| `ger_eolica` | MWmed | horária | `val_gereolica` |
| `margem_controlavel` | MWmed | horária | hidráulica + térmica − mínimo técnico estimado |
| `corte_mw` | MWmed | horária | agregação do constrained-off por área e razão |
| `restricao_ocorreu` | booleano | horária | `corte_mw > limiar` por área |

### 4.2.4 Áreas

O protótipo trabalha em duas granularidades, ambas presentes nos dados reais:

1. **Subsistema** (`N`, `NE`, `S`, `SE`) — grade do balanço de energia.
2. **Estado** (`id_estado` do constrained-off) — proxy de área de concessão,
   suficiente para demonstrar a localização do risco.

A granularidade-alvo em produção é **área de concessão + transformação de
fronteira**, que exige BDGD. O contrato já está desenhado para ela: a chave de
área é um campo livre, não um enumerado fechado.

## 4.3 Qualidade de dados: regras aplicadas na ingestão

| Regra | Ação |
|---|---|
| Campo numérico vazio | vira `NaN`, nunca zero — zerar inventa informação |
| `din_instante` ausente ou inválido | registro descartado, contagem reportada |
| Registro duplicado (área, instante) | mantém o último, conta a colisão |
| Lacuna na grade horária | preenchida com `NaN` e sinalizada em `gaps` |
| `id_ons` não é chave global entre fontes | chave composta `(fonte, id_ons)` |
| Subsistema ≠ área operativa | os dois recortes nunca são cruzados diretamente |

Todas as contagens de descarte e colisão entram no relatório de ingestão e ficam
visíveis no painel de Dados Abertos.
