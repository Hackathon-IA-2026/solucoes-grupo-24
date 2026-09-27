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
| API `GET /api/previsao` | **Real** | `mock: false` | pontos P10/P50/P90 e rampa **reais** (modelo de `config/modelos_carga.yaml: curva.modelo`, previsões fora da amostra); `fatoresClimaticos` **reais**: Open-Meteo (ECMWF IFS 0,25°) nas sedes das UFs, média na janela da curva ponderada pela MMGD cadastrada em cada UF (radiação só nas horas de sol). Só exibição, não entra nos modelos. Se o tempo baixado não cobrir a janela, os fatores daquela curva voltam ao mock e ela sai `mock: true` (`fatores_climaticos` em `src/publicacao/montar.py`) | 2026-09-26 |
| API `GET /api/validacao` | **Real** | `mock: false` | métricas do backtest fora da amostra (SIN, D+1) até o "agora", histórico diário do modelo e da climatologia, metadados do treino (split da config, versão = hash da config) e status das fontes a partir do manifesto de download | 2026-09-26 |
| `Backend/data/modelos/carga/` e `docs/reports/baseline_carga.md` | Real (derivado) | — | modelos, previsões fora da amostra e backtest da carga (Fase 3) | 2026-09-26 |
| API `GET /api/riscos` | **Real** (por registro) | `mock: false`, exceto usina sem coordenada | usina, razão, probabilidade, montante, horizonte, severidade e ação **reais** (classificador de curtailment fora da amostra); `distribuidora` = **ponto de conexão** publicado pelo ONS na base tm ("Conexão: <SE>", decisão do Tiago em 2026-09-26: usinas da rede básica não têm distribuidora); `lat`/`lon` = **coordenada do SIGA/ANEEL** (média das usinas do conjunto ponderada pela potência, `data/processed/usinas_cadastro.csv`). ~18% das usinas não têm coordenada no SIGA: ficam na sede da UF (`posicao_uf`) e SÓ esse registro sai `mock: true` | 2026-09-26 |
| API `GET /api/alertas/{id}` | **Real** | `mock: false` | mesmo classificador; motivos = probabilidade de cada razão; variáveis = SHAP exato do LightGBM (`pred_contrib`) agrupado em rótulos legíveis | 2026-09-26 |
| `Backend/data/modelos/curtailment/` e `docs/reports/classificador_curtailment.md` | Real (derivado) | — | modelos, previsões fora da amostra e backtest do classificador (Fase 4) | 2026-09-26 |
| API `GET /api/mmgd/densidade` | **Real** | `mock: false` | capacidade de MMGD por área de influência da área piloto RJ (BDGD LIGHT + Enel RJ × cadastro da ANEEL; `docs/metodo_espacial.md`). Só o RJ: fora dele o calor fica vazio | 2026-09-26 |
| API `GET /api/areas-influencia` | **Real** | `mock: false` | polígonos das áreas de influência (BDGD 2025, simplificados a 30 m para a web) + capacidade de MMGD (BDGD × ANEEL) e pico de excedente previsto de cada uma, os mesmos números da tela Excedentes | 2026-09-26 |
| API `GET /api/excedentes` | **Real (estimativa)** | `mock: false` | excedente de MMGD previsto por subestação de fronteira do RJ: capacidade BDGD × ANEEL, fator de geração e carga da área RJ do ONS, persistência sazonal de 1 dia (sem dado posterior ao agora). Hipóteses (fator de geração único na área, perfil de carga plano no mês) em `docs/metodo_espacial.md` | 2026-09-26 |
| `Backend/data/processed/carga_area.csv` | Real | coluna `carga_global_invalida` | API de carga verificada do ONS, área de carga RJ (mesmo leitor da tabela por subsistema) | 2026-09-26 |
| `Backend/output/areas_influencia_rj.geojson`, `data/processed/mmgd_area_influencia.csv`, `mmgd_fronteira_diaria.csv`, `carga_area_influencia_mensal.csv` | Real (derivado) | coluna `categoria` nas unidades; `fator_correcao` vazio = sem correção | BDGD 2025 (ANEEL) + cadastro de MMGD (ANEEL) + malha do IBGE. Lag de sistema rateado por município; unidades só na BDGD (`bdgd_sem_homologacao`) fora da capacidade | 2026-09-26 |
| `Backend/data/processed/mmgd_empreendimentos.parquet` | Real (derivado) | coluna `categoria` | uma linha por empreendimento de MMGD (CEG) da LIGHT e da Enel RJ, desempate BDGD × ANEEL; só colunas não pessoais | 2026-09-26 |
| API do protótipo `GET /api/triangulation` | **Real** (camadas 2 e 3) | `layer1_available: false`, `detected: null` | empreendimentos acima; a camada 1 (satélite) não é presumida. Modo demo: gerador determinístico rotulado | 2026-09-26 |
| API do protótipo `GET /api/mapa/substations[/{id}]` | **Real** (composição e MMGD) | `real: true` por linha | energia faturada BDGD + SAMP e cadastro ANEEL das SEDs associadas (fronteira T–D). A seção de visão é amostra **sintética** de demonstração do detector, rotulada e fora dos números; sem a base da fronteira a linha sai `real: false` | 2026-09-26 |
| Grupo `clima` dos modelos do protótipo (`/api/forecast`, `/api/risk`, `/api/validation`) | **Real** | proveniência "Open-Meteo · ERA5" | temperatura e ponto de orvalho ERA5 nas capitais do subsistema (antes: proxy sintético, removido) | 2026-09-26 |

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
| `src/data/mock/excedentes.json` | ExcedenteTsoDso × 5 | Seed do protótipo (prioridade normalizada para `high/medium/low`); `lat`/`lon` são pontos aproximados da região, inventados | ✅ substituído na API pelos excedentes por subestação do RJ (Fase 6); o arquivo só serve ao modo mock |
| `src/data/mock/mmgd_densidade.json` | DensidadeMmgd (heatmap) | **Sintético**, gerado por `scripts/gerar-mocks-series.mjs` (nuvens em torno de capitais, pesos ilustrativos) | ✅ substituído na API pela capacidade por área de influência (Fase 6); o rótulo "(sintético)" do mapa agora só aparece quando o dado é mock |
| `src/data/mock/areas_influencia.json` | AreasInfluencia × 3 áreas | **Amostra congelada** de 3 áreas reais (Centenário, Influência, Carmo) da publicação de 2026-09-26, só para o modo mock; não se atualiza | a API (`/api/areas-influencia`) |
| `src/data/mock/validacao.json` | MetricasValidacao | Gerado por `scripts/gerar-mocks-series.mjs`: erro do modelo e do baseline (climatologia) inventados; skill derivado deles; MAPE, status das fontes e metadados do modelo (`0.0.0-placeholder`) inventados | métricas do backtest cronológico + registro do modelo treinado |

Observação: os seeds de risco usam a razão **REL**, mas `Backend/config/projeto.yaml` tem
`incluir_rel: false` (nenhum modelo prevê REL). Com dado real, esses registros tendem a sumir
ou mudar de razão.

## Backend (`Backend/pipeline`)

| Arquivo | Conteúdo | Origem dos valores | Substituir por |
|---|---|---|---|
| `Backend/pipeline/mock/saidas_modelo.json` | "Saídas de modelo" por risco: motivos, contribuições SHAP, horário previsto, dataset, hora da previsão | Inventados (migrados do antigo `alertas.json`); `mock: true` | saídas reais dos classificadores ENE/CNF |
| `explicabilidade.ExplicadorPrecomputado` | Stub: usa as contribuições prontas da entrada em vez de calcular SHAP | — | `ExplicadorShap(modelo, dados_referencia, nomes_features)` |

## Auditoria da MMGD em 3 camadas (`Backend/pipeline`, Luiz) — 2026-09-26

Todos os mocks abaixo têm `"mock": true` no arquivo e `is_mock: true` em cada saída; a auditoria
recusa gravar a saída real (`output/auditoria/`) se qualquer entrada for mock. As saídas mock vão
para `Backend/output/auditoria/mock/` (fora do git, regeneráveis).

| Arquivo | Conteúdo | Origem dos valores | Substituir por |
|---|---|---|---|
| `Backend/pipeline/mock/camada1_paineis_mock.json` | 12 painéis (centro, largura, altura, confiança) | **Sintético**, desenhado à mão em torno de Janaúba (MG), a área piloto provisória | `python -m pipeline.auditoria_camada1` com o YOLO sobre imagens georreferenciadas da área piloto |
| `Backend/pipeline/mock/bdgd_mock.json` | 10 unidades com GD, transformador, alimentador, potência e `data_referencia` | **Sintético**, coordenadas casadas com os painéis mock para cobrir todos os casos do desempate | BDGD da distribuidora da área piloto (Fase 6) |
| `Backend/pipeline/mock/aneel_cadastro_diario_mock.json` | 10 empreendimentos com data de homologação | **Sintético** (3 depois da data da BDGD, 1 antes, 2 sem painel detectado) | planilha diária de empreendimentos de GD da ANEEL da área piloto |

Premissa (não é dado): `auditoria.kwp_por_m2 = 0.18` em `Backend/config/visao.yaml` converte área
detectada em capacidade (módulos c-Si de ~19–22% de eficiência, descontando bordas da máscara).

## Dado real acrescentado ao dashboard — 2026-09-26

| Arquivo | Conteúdo | Origem |
|---|---|---|
| `Frontend/oraculo-dashboard/src/data/geo/ufs.geo.json` | divisas das 27 UFs (fundo do Mapa Híbrido) | API de malhas do IBGE, qualidade mínima (`npm run geo:ufs`) |
