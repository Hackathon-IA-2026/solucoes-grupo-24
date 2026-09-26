# Mapeamento subsistema × área de carga

Arquivo: `Backend/data/processed/mapeamento_subsistema_area.csv` (versionado; 33 linhas: 4 subsistemas, 25 áreas de carga, 4 de perdas). Gerado por `python -m src.processing.mapeamento` (dentro de `Backend/`) a partir de `Backend/config/mapeamento_areas.yaml`.

## Fonte oficial

Especificação OpenAPI "Carga Global OpenAPI 3.0" (v1.0.0) do ONS, parâmetro `cod_areacarga` do endpoint `/cargaverificada` da API `https://apicarga.ons.org.br/prd`, consultada em 2026-09-25. A especificação lista "Subsistemas, Áreas Geoelétricas e Perdas" agrupadas por subsistema (SECO: RJ, SP, MG, ES, MT, MS, DF, GO, AC, RO · S: PR, SC, RS · NE: BASE, BAOE, ALPE, PBRN, CE, PI · N: TON, PA, MA, AP, AM, RR), mais as perdas PESE, PES, PENE e PEN.

## Colunas

| Coluna | Conteúdo |
|---|---|
| `cod_areacarga` | código na API (inclui os próprios subsistemas e as perdas) |
| `nom_areacarga` | nome oficial |
| `tipo` | `subsistema`, `area` ou `perdas` |
| `cod_subsistema_api` | SECO / S / NE / N (códigos da API de carga) |
| `id_subsistema` | SE / S / NE / N (códigos das bases do portal: constrained-off, balanço, térmicas) |
| `ufs` | UFs cobertas pela área, separadas por `;` |

## Verificação numérica

Para cada subsistema e semi-hora: soma(áreas + perdas) comparada à carga global do próprio subsistema. Resultado completo em `docs/reports/mapeamento_fechamento.csv`.

| Período | Resultado |
|---|---|
| 2021 → hoje | Fechamento quase exato em SECO, S e NE (erro relativo mediano ≤ 0,25%; ~0,001% a partir de 2023). **Confirma o agrupamento.** |
| 2016 → 2020 | A soma fica ~4–15% abaixo do subsistema: as perdas só passam a ser publicadas em 2021. Esperado. |
| N, 2021 → 2025 | A soma passa do subsistema por ~2%, exatamente a carga de Roraima (RR ainda era sistema isolado). Em 2026, com a interligação, fecha em 0,01%. **RR pertence ao N só a partir da interligação.** |
| SECO, 2016 | Erro de ~500×: a área **GO publica ~20 milhões de MW** em 2016 (erro da fonte), e outras áreas têm picos implausíveis nesse ano. **Dados por área de 2016 não são confiáveis**; o nível de subsistema está correto. |

## Regras de uso

- **Todo cruzamento** entre subsistema, área de carga e UF passa por `src.utils.joins.cruzar_subsistema_area`. `Backend/tests/test_joins.py` falha se outro módulo ler o CSV diretamente.
- Traduções ambíguas levantam erro por padrão. Hoje, a única é **UF BA → áreas BASE e BAOE**. Quem precisar dela tem de pedir `ambiguos='marcar'` e decidir o que fazer.
- As bases de curtailment (tm) só têm subsistema e UF: nenhuma usina é atribuída a área de carga sem passar por essa regra.
