# Real vs. mock

Regra do `CLAUDE.md`: dado sintético ou placeholder só com flag explícita (`mock=True` ou coluna/campo `is_mock`) e registrado aqui. Tudo o que não aparece nesta tabela é dado real, com origem rastreável em `docs/reports/download_log.csv`.

| Artefato | Real ou mock | Flag | Origem / motivo | Desde |
|---|---|---|---|---|
| `Backend/data/processed/calendario.csv` | Real (derivado) | — | biblioteca `holidays` (feriados nacionais) + regras do `CLAUDE.md` | 2026-09-25 |
| `Backend/data/processed/carga_supervisionada.csv` | Real | — | API de carga verificada do ONS. MMGD ausente fica NaN (`mmgd_disponivel=False`), nunca zero | 2026-09-25 |
| `Backend/data/processed/rotulos_curtailment.parquet` | Real | coluna `corte_origem` | bases tm do ONS. `corte_origem='ref_menos_ger'` = GNRa não publicada, recalculada pela mesma fórmula do ONS (não é estimativa) | 2026-09-25 |
| `Backend/data/processed/mapeamento_subsistema_area.csv` | Real | — | especificação oficial da API de carga do ONS | 2026-09-25 |
| `Backend/data/processed/capacidade_mmgd.csv` | Real | — | cadastro de MMGD da ANEEL (só UF, data e potência; nenhuma coluna pessoal). Data = atualização cadastral (a ANEEL não publica data de conexão): capacidade no passado fica subestimada | 2026-09-25 |
| API `GET /api/carga/snapshot` | **Real** | `mock: false` | carga e MMGD do ONS (SIN = 4 subsistemas completos) na última semi-hora disponível + capacidade da ANEEL até a data | 2026-09-25 |
| API `GET /api/previsao` | **Parcial → mock** | `mock: true` | pontos P10/P50/P90 e rampa **reais** (LightGBM fora da amostra, `Backend/src/models/carga.py`); `fatoresClimaticos` ainda **do mock** do dashboard (não há fonte meteorológica). Registro com parte mock é mock inteiro, então a curva sai `mock: true` até haver meteorologia ou o contrato permitir fatores ausentes (`FATORES_CLIMATICOS_REAIS` em `src/publicacao/montar.py`) | 2026-09-26 |
| API `GET /api/validacao` | **Real** | `mock: false` | métricas do backtest fora da amostra (SIN, D+1) até o "agora", histórico diário do modelo e da climatologia, metadados do treino (split da config, versão = hash da config) e status das fontes a partir do manifesto de download | 2026-09-26 |
| `Backend/data/modelos/carga/` e `docs/reports/baseline_carga.md` | Real (derivado) | — | modelos, previsões fora da amostra e backtest da carga (Fase 3) | 2026-09-26 |
| API `GET /api/riscos` | **Parcial → mock** | `mock: true` | usina, razão, probabilidade, montante, horizonte, severidade e ação **reais** (classificador de curtailment fora da amostra, `Backend/src/models/curtailment.py`); `distribuidora` = "a definir" até o Luiz definir o que o campo mostra para usinas da rede básica (`DISTRIBUIDORA_PENDENTE` em `src/publicacao/montar.py`); `lat`/`lon` = **sede da UF** (`posicao_uf` em `config/publicacao.yaml`), porque o projeto não ingere coordenada por usina (`POSICAO_USINA_REAL`) | 2026-09-26 |
| API `GET /api/alertas/{id}` | **Real** | `mock: false` | mesmo classificador; motivos = probabilidade de cada razão; variáveis = SHAP exato do LightGBM (`pred_contrib`) agrupado em rótulos legíveis | 2026-09-26 |
| `Backend/data/modelos/curtailment/` e `docs/reports/classificador_curtailment.md` | Real (derivado) | — | modelos, previsões fora da amostra e backtest do classificador (Fase 4) | 2026-09-26 |
| API `GET /api/mmgd/densidade` | **Mock** | `mock: true` | servido a partir do mock do dashboard (`mmgd_densidade.json`, sintético) até a MMGD por mancha existir (Fase 6) | 2026-09-26 |
| API `GET /api/excedentes` | **Mock** | `mock: true` em todo item | servido a partir do mesmo mock do dashboard (`Frontend/.../src/data/mock/`) até a MMGD por mancha existir (Fase 6); a publicação recusa mock sem flag | 2026-09-25 |

## Proxies (reais, mas não são a grandeza pedida)

| Grandeza pedida | Situação | Proxy usado |
|---|---|---|
| Limite de exportação NE e N/NE | Não existe no portal (ver `docs/inventario_portal_ons.md`) | nenhum por enquanto; o CNF usa só o intercâmbio verificado |
| Capacidade instalada de MMGD por subsistema | Não existe no ONS | relação de empreendimentos de MMGD da ANEEL (`Backend/data/raw/aneel/`) |

## Dashboard (`Frontend/oraculo-dashboard`)

Todos os registros abaixo têm `mock: true`. No modo mock, `src/data/dataSource.ts` rejeita
qualquer registro sem essa flag, e o modo é escolhido por `VITE_DATA_SOURCE` (`api` padrão | `mock`, via `npm run dev:mock`). A topbar
sempre mostra a origem: "DADOS MOCK" no modo mock, "DADOS DE dd/mm HH:MM" com a API (e, na API,
cada card ainda leva o selo MOCK quando o registro publicado tem `mock: true`).

| Arquivo | Conteúdo | Origem dos valores | Substituir por |
|---|---|---|---|
| `src/data/mock/carga.json` | CargaSnapshot | Seed do protótipo (57 973 / 26 169 / 31 804 MW; 44,8%). `mmgdSobreCapacidadeInstalada = 0.61` e o timestamp são inventados | carga supervisionada (`data/processed/carga_supervisionada.csv`) + estimativa de MMGD |
| `src/data/mock/previsao.json` | PrevisaoCurva × 3 horizontes | Gerado por `scripts/gerar-mocks-series.mjs` (curva do pato determinística, bandas por horizonte); fatores climáticos inventados | saídas do TFT / baselines (P10/P50/P90) |
| `src/data/mock/riscos.json` | RiscoUsina × 7 | Seed do protótipo Figma (nome, UF, razão, %, MW, horizonte, severidade). **Inventados:** `id`, `distribuidora`, `fonte` (inferida do nome), `acaoRecomendada`, `lat`/`lon` (posição aproximada da região, não a da usina) | classificadores ENE/CNF |
| `src/data/mock/alertas.json` | AlertaDetalhado × 7 | **Gerado** por `python -m pipeline.gerar_alertas_mock` (dentro de `Backend/`) (pipeline de explicabilidade real sobre entradas mock). Prob./MW/horizonte vêm de `riscos.json`; o resto de `Backend/pipeline/mock/saidas_modelo.json` | saída dos classificadores + `ExplicadorShap` |
| `src/data/mock/excedentes.json` | ExcedenteTsoDso × 5 | Seed do protótipo (prioridade normalizada para `high/medium/low`); `lat`/`lon` são pontos aproximados da região, inventados | cálculo de excedentes por mancha + ponto de fronteira real |
| `src/data/mock/mmgd_densidade.json` | DensidadeMmgd (heatmap) | **Sintético**, gerado por `scripts/gerar-mocks-series.mjs` (nuvens em torno de capitais, pesos ilustrativos) | capacidade de MMGD por mancha (BDGD + satélite) |
| `src/data/mock/validacao.json` | MetricasValidacao | Gerado por `scripts/gerar-mocks-series.mjs`: erro do modelo e do baseline (climatologia) inventados; skill derivado deles; MAPE, status das fontes e metadados do modelo (`0.0.0-placeholder`) inventados | métricas do backtest cronológico + registro do modelo treinado |

Observação: os seeds de risco usam a razão **REL**, mas `Backend/config/projeto.yaml` tem
`incluir_rel: false` (nenhum modelo prevê REL). Com dado real, esses registros tendem a sumir
ou mudar de razão.

## Backend (`Backend/pipeline`)

| Arquivo | Conteúdo | Origem dos valores | Substituir por |
|---|---|---|---|
| `Backend/pipeline/mock/saidas_modelo.json` | "Saídas de modelo" por risco: motivos, contribuições SHAP, horário previsto, dataset, hora da previsão | Inventados (migrados do antigo `alertas.json`); `mock: true` | saídas reais dos classificadores ENE/CNF |
| `explicabilidade.ExplicadorPrecomputado` | Stub: usa as contribuições prontas da entrada em vez de calcular SHAP | — | `ExplicadorShap(modelo, dados_referencia, nomes_features)` |
