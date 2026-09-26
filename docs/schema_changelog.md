# Changelog do schema do contrato (Tiago → Luiz)

## v4 — áreas de influência das subestações no Mapa Híbrido (2026-09-26) ✅

Pedido do Tiago (validar a Fase 6 vendo o mapa). **Aditiva**: nenhum recurso existente mudou.

| Recurso | Mudança |
|---|---|
| `AreasInfluencia` (novo) | recurso `areas_influencia`, rota `GET /api/areas-influencia`: GeoJSON `FeatureCollection` (RFC 7946, coordenadas `[lon, lat]`) com `mock` e `descricao`. Cada `Feature` tem `geometry` (`Polygon`/`MultiPolygon`, dentro do Brasil, anel ≥ 4 pontos) e `properties`: `areaId`, `nome`, `distribuidora`, `classificacao`, `areaMae`, `latSub`, `lonSub`, `areaKm2`, `capacidadeMmgdMw`, `capacidadeLagMw`, `fatorCorrecao` (null = sem satélite), `excedenteMw` e `horizonteExcedente` (null = não é subestação de fronteira) |

Dashboard: camada "Áreas de influência (MMGD)" no Mapa Híbrido (`src/components/mapa/CamadaAreas.tsx`), botões "Área piloto"/"Brasil". Luiz: revise a camada e os textos quando puder.

## v3 — telas Excedentes, Validação e Mapa Híbrido (2026-09-26) ✅

Aprovado pelo Tiago (as três telas do Luiz vieram da branch `claude/eager-gauss-or90gs`).
Mudanças no `types.ts`, espelhadas em `Backend/src/contrato/modelos.py`:

| Recurso | Mudança |
|---|---|
| `RiscoUsina` | + `lat`, `lon` (caixa em torno do Brasil: lat −34…6, lon −74…−28; trocados = recusado) |
| `ExcedenteTsoDso` | + `lat`, `lon` (mesma caixa) |
| `MetricasValidacao` | + `baselineNome`; `historicoErro30d[]` + `maeBaseline`, `rmseBaseline`; + `modelo` {`nome`, `versao`, `dataTreino`, `periodoTreino`, `periodoTeste`} com a regra "teste começa depois do fim do treino" |
| `DensidadeMmgd` (novo) | recurso `mmgd_densidade`, rota `GET /api/mmgd/densidade`: `descricao` + `pontos` `[lat, lon, intensidade]` |

Banco publicado antes da v3: a API responde 503 pedindo `python run_heavywork.py` (e não 500).

## v2 — contrato oficial = `types.ts` do dashboard (2026-09-25) ✅

Decisão do Tiago: o contrato oficial é o que o dashboard já consome,
`Frontend/oraculo-dashboard/src/data/types.ts` (6 recursos, camelCase, UTC com `Z`). O Luiz
não precisa mudar nada. A v1 abaixo (JSON único por execução) foi **aposentada**; os arquivos
`schema_contrato_v1_proposta.json` e `exemplo_contrato_v1_proposta.json` saíram do repositório
(ficam no histórico do git). Detalhes em `docs/schema_contrato.md`.

Único ajuste de nome detectado ao espelhar em Python: nenhum no contrato; o gerador automático
de camelCase produziria `historicoErro30D`, e o alias foi fixado em `historicoErro30d` (o nome
do `types.ts`). O teste que valida os mocks do dashboard pegou a diferença.


## v1.0.0 — PROPOSTA (aguardando aprovação do Tiago)

Arquivos: `docs/schema_contrato_v1_proposta.json` (JSON Schema 2020-12) e `docs/exemplo_contrato_v1_proposta.json` (valores fictícios, todos os blocos com `is_mock: true`). O teste `Backend/tests/test_schema_contrato.py` valida o exemplo contra o schema.

> ⚠️ **Ponto de atenção:** o schema "atual" (`docs/schema_contrato.json`, rascunho de 2026-09-21 citado no STATUS) **não existe no repositório** — nunca foi commitado. Esta proposta foi montada a partir dos cinco blocos daquele rascunho (metadados, previsão de carga, risco de curtailment, excedentes, manchas) mais o que as 6 telas pedem. **Luiz: se você tem uma cópia local do rascunho antigo e o dashboard já usa algum nome de campo dele, avise antes da aprovação**, para reconciliarmos sem renomear nada que você já consome.

### Convenções gerais

| Regra | Por quê |
|---|---|
| Um JSON por execução do carregador; `metadados.execucao_id` identifica a execução | rastrear de qual rodada veio cada número |
| Todos os instantes em ISO 8601 com offset `-03:00`, marcando o **início** do intervalo de 30 min | fuso único do projeto (UTC-3 fixo) |
| `metadados.is_mock` diz, **por bloco**, se ele veio do exemplo | enquanto um modelo não tem saída real, o bloco entra do exemplo e o dashboard pode sinalizar isso |
| Razões de curtailment: só `ENE` e `CNF` | `incluir_rel: false` em `Backend/config/projeto.yaml` (nenhum modelo prevê REL) |
| Horizontes: `30min`, `3h`, `D+1`; subsistemas: `SE`, `S`, `NE`, `N` | regras do `CLAUDE.md`; códigos das bases do portal ONS |

### Campos novos e qual tela usa

| Bloco / campo | Tela | Por quê |
|---|---|---|
| `metadados.versao_schema` (`"1.0.0"`) | todas | o dashboard pode recusar versão que não conhece |
| `metadados.execucao_id` | 6 | identificar a rodada exibida |
| `metadados.gerado_em` | 4, rodapé do alerta ("atualizado há N min") | |
| `metadados.fuso` | todas | evita ambiguidade de horário |
| `metadados.is_mock.{bloco}` | todas | selo de "dado de exemplo" por bloco |
| `metadados.fontes_citadas` | 4, rodapé do alerta ("Fontes: Portal ONS, BDGD, ERA5") | |
| **`visao_geral`** (bloco novo) | 1 | |
| `visao_geral.subsistemas[].carga_supervisionada_mw` | 1 | carga supervisionada atual |
| `visao_geral.subsistemas[].mmgd_estimada_mw` | 1 | MMGD estimada atual |
| `visao_geral.subsistemas[].carga_global_mw` (opcional) | 1 | contexto |
| `visao_geral.risco_curtailment_agregado_pct` | 1 | risco agregado (%) |
| `previsao_carga.series[].pontos[].p10/p50/p90` | 2 | curva D+1 com quantis |
| `previsao_carga.series[].pontos[].rampa_mw_h` (opcional) | 2 | rampa projetada (MW/h) |
| `previsao_carga.series[].importancia_variaveis[]` | 2 | fatores que mais pesaram |
| `risco_curtailment.alertas[].chave`, `fonte`, `id_ons`, `nome_legivel`, `uf` | 3 | identificar usina/conjunto com nome legível; `chave` = fonte + id (chave composta das bases do ONS) |
| `risco_curtailment.alertas[].razao_principal`, `probabilidade`, `montante_previsto_mw`, `horizonte` | 3 | lista de riscos |
| `risco_curtailment.alertas[].montante_se_corte_mw` (opcional) | 4 | E[MW \| corte]; `montante_previsto_mw` = probabilidade × isso |
| `risco_curtailment.alertas[].pesos_variaveis[]` | 4 | pesos por variável |
| `risco_curtailment.alertas[].decomposicao_razao[]` (razão, %) | 4 e texto do alerta ("x% ENE · y% CNF") | |
| `risco_curtailment.alertas[].datasets_origem[]` | 4 | dataset de origem |
| `risco_curtailment.alertas[].timestamp_alvo`, `gerado_em` | 4 e texto do alerta ("amanhã às 14h") | |
| `excedentes.itens[].mancha_id`, `area_concessao`, `fronteira`, `prioridade`, `horizonte`, `excedente_projetado_mw`, `risco_fluxo_reverso` (0–1), `acao_recomendada` | 5 | lista de excedentes por área de concessão e fronteira |
| `manchas.geojson` | 5 (mapa) | geometrias ficam num GeoJSON em `Backend/output/`, ligadas por `mancha_id` (o JSON do contrato não carrega polígonos) |
| `manchas.itens[].capacidade_mmgd_bdgd_kw`, `fator_correcao`, `capacidade_mmgd_corrigida_kw` | 5 | tese TSO–DSO; `fator_correcao` é o do Luiz (null até existir) |
| **`validacao`** (bloco novo) | 6 | |
| `validacao.metricas[]` (modelo × baseline, por alvo/horizonte) | 6 | erro do modelo vs. baseline no período recente |
| `validacao.fontes[]` (status, último dado) | 6 | status e data do último dado de cada fonte |
| `validacao.modelos[]` | 6 | metadados do modelo |
| `validacao.limitacoes[]` | 6 | limitações declaradas |

### Como o texto do alerta sai dos campos

> "Probabilidade de **85%** (`probabilidade`) de curtailment de **312 MW** (`montante_previsto_mw`) no **Conjunto Eólico Exemplo** (`nome_legivel`), **amanhã às 14h** (`timestamp_alvo`). Motivo: **70% ENE · 30% CNF** (`decomposicao_razao`). Fontes: **Portal ONS, BDGD, ERA5** (`metadados.fontes_citadas`) · **D+1** (`horizonte`) · atualizado há **N min** (agora − `gerado_em`)"
