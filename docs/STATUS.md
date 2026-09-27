# STATUS

Andamento das tarefas. Atualizado ao fim de cada tarefa.

> **Checklist das fases (o que está feito e o que falta): [`docs/FASES.md`](FASES.md).** Este arquivo é o diário detalhado de cada tarefa.

## 2026-09-21 — Setup, schema do contrato e inventário do portal ONS

### Parte 1 — Estrutura do repositório ✅

- Estrutura de pastas criada (`data/`, `notebooks/`, `src/{ingestion,spatial,models,utils}`, `docs/`, `reports/`, `output/`, `config/`, `tests/`), com `__init__.py` nos pacotes de `src/`.
- `pyproject.toml` com as dependências do plano; Python fixado em `>=3.11,<3.13`. `pytest` em `[dev]`.
- `.gitignore` cobrindo `data/raw/`, Parquet/DuckDB, checkpoints de modelo e `.env`.
- `src/utils/paths.py` — caminhos relativos à raiz (`parents[2]`), com auto-check em `__main__`.
- `README.md` reescrito seguindo `docs/modelo_readme_competicao.md` (o template que estava na raiz virou esse arquivo em `docs/`).
- `LICENSE` MIT já existia — mantido "Copyright (c) 2026 Hackathon-IA-COPPE-2026" por decisão do time.

### Parte 2 — Schema do contrato de dados 🟡 rascunho, aguardando Luiz

- `docs/schema_contrato.json` (JSON Schema draft 2020-12) com os blocos `metadados`, `previsao_carga`, `risco_curtailment`, `excedentes`, `manchas`.
- `docs/exemplo_contrato.json` — valores fictícios, `is_mock: true` em todos os blocos.
- `docs/schema_contrato.md` — tabela de campos obrigatórios × nice-to-have.
- `tests/test_schema_contrato.py` valida o exemplo contra o schema.
- **Pendente:** fechar o schema com o Luiz. Qualquer mudança depois disso exige aviso — o dashboard dele depende do contrato.

### Parte 3 — Inventário do portal ONS 🟡

- `docs/inventario_portal_ons.md` — ver o próprio arquivo para cobertura e lacunas.
- Nenhum dado baixado (só metadados e dicionários), conforme combinado.

## Próximos passos

- Fechar o schema com o Luiz.
- Catálogo de séries a partir do inventário → `data/processed/`.
- Baselines de carga supervisionada.

## 2026-09-25 — Dashboard: scaffold + design system ✅

- `Frontend/oraculo-dashboard`: React 19 + Vite + TypeScript + Tailwind v4 + React Router.
- Design system dark SCADA com tokens em `src/index.css` (`@theme`): fundos `#0a0e17`/`#0f1524`,
  accent ciano `#22d3ee`, escala de risco verde/âmbar/laranja/vermelho, JetBrains Mono para KPIs.
- Layout base: sidebar fixa com os 8 módulos (Visão Geral, Mapa Híbrido, Despacho Preditivo,
  Lista de Riscos, Detalhe do Alerta, Excedentes TSO-DSO, Validação, Metodologia), topbar com
  título, pill "SIN OPERANDO", filtros NORMAL/LOADING/CRITICAL/NO-RISK e relógio em BRT.
- Menu e rotas gerados do mesmo registro (`src/modules.tsx`): nome/ordem/caminho não divergem.
- Componentes reutilizáveis: `Card`, `SeverityBadge`, `StatusPill`. Filtros em contexto global
  (`useSeverityFilter`).
- Decisão a validar: mapeamento de filtros → cor em `src/theme/severity.ts`
  (NORMAL=verde, LOADING=âmbar, CRITICAL=vermelho, NO-RISK=neutro; laranja só na escala de risco).
- "SIN OPERANDO" é estático: ainda não há fonte de estado do SIN no Backend.
- Páginas vazias, sem nenhum dado exibido. `npm run build` e `npm run lint` limpos.

## 2026-09-25 — Dashboard: contrato de dados mockado ✅

- `src/data/types.ts`: schemas Zod + tipos inferidos (CargaSnapshot, PrevisaoCurva, RiscoUsina,
  AlertaDetalhado, ExcedenteTsoDso, MetricasValidacao). Validações de negócio no schema:
  supervisionada = global − MMGD, P10 ≤ P50 ≤ P90, motivos somam 100%.
- `src/data/mock/*.json` com os seeds pedidos, todos com `mock: true`; séries geradas por
  `npm run mocks:series` (determinístico). Registro em `docs/real_vs_mock.md`.
- `src/data/dataSource.ts`: `getCarga/getPrevisao/getRiscos/getAlerta/getExcedentes/getValidacao`,
  modo `mock` (padrão) ou `api` via `VITE_DATA_SOURCE`; toda resposta validada pelo schema;
  mock sem flag é rejeitado. Endpoints da API provisórios (Backend ainda não existe).
- Vitest: `npm test` (11 testes, incluindo os seeds exatos e as guardas do contrato).
- Desvios do pedido, a validar: campo extra `uf` em RiscoUsina; `prioridade` do excedente em
  minúsculas (mesma escala de severidade); horizonte `1h` só nos excedentes.
- Pendente: esses tipos são o contrato do lado do dashboard, mas `docs/schema_contrato.json`
  (citado acima) não está no repositório — alinhar os dois antes de ligar a API.

## 2026-09-25 — Dashboard: tela Visão Geral ✅

- 3 KPIs (`KpiCard`): carga supervisionada e MMGD estimada (GW, com MW exato e horário BRT) de
  `getCarga()`; risco de curtailment = média das probabilidades de `getRiscos()` **ponderada
  pelo montante (MW)** → 57,8% com os mocks, badge de severidade pelos limiares de
  `src/data/derivados.ts` (25/50/75%, provisórios).
- Composição da carga global em barra 100% empilhada (`components/charts/BarraComposicao.tsx`):
  supervisionada × MMGD, legenda com MW e %, hover com tooltip; abaixo, "% MMGD na geração" e
  "MMGD ÷ capacidade instalada".
- Novas peças reutilizáveis: `KpiCard`, `MockTag` (selo MOCK em todo dado mock), `Carregando`/
  `ErroDados`, hook `useDados` (estado loading/ok/erro tipado), `utils/format.ts` (pt-BR, BRT).
- Cores de gráfico `chart-1` (#0891b2) e `chart-2` (#8b5cf6) validadas para fundo escuro e
  daltonismo.
- Testes: 15 (4 novos para os derivados). Build e lint limpos.
- Conhecido: o layout não é responsivo (sidebar fixa de 256px esmaga o conteúdo no celular).

## 2026-09-25 — Dashboard: tela Despacho Preditivo ✅

- Gráfico Recharts (`components/charts/GraficoPrevisao.tsx`): banda P10–P90 sombreada + linha
  P50, tooltip com os três quantis, eixo em GW com ticks de 5 GW, horário BRT.
- Seletor de horizonte 30min / 3h / D+1 (`SegmentedControl`, opções lidas do schema); as três
  curvas são buscadas uma vez e a troca é instantânea.
- Rampa: `trechoDeRampa()` em `data/derivados.ts` acha a maior subida do P50 na janela
  `janelaRampaHoras`; o trecho é destacado e rotulado com o valor calculado (15,8 GW / 3h nos
  mocks). Teste garante que o valor bate com `rampaProjetadaMw`.
- Painel lateral de fatores climáticos em `MiniStat` (radiação, vento, temperatura, nuvens).
- Páginas passaram a ser carregadas sob demanda (`React.lazy` em `modules.ts`): o Recharts só
  é baixado ao abrir esta tela; bundle inicial voltou para ~275 kB.
- Mock corrigido: o gerador de séries dava um degrau à meia-noite (gaussiana sem distância
  circular). Testes: 17.

## 2026-09-25 — Dashboard: tela Lista de Riscos ✅

- Tabela com severidade, usina/UF, distribuidora, fonte, razão, probabilidade (número + barra),
  montante (MW), horizonte e ação recomendada; legenda das siglas REL/CNF/ENE.
- Ordenação `ordenarPorSeveridade()` em `data/derivados.ts`: severidade → probabilidade →
  montante → id (ordem nunca depende da chegada dos dados). Teste novo.
- Razão com cor categórica própria (`theme/razao.ts` + `RazaoBadge`): ENE=chart-1, CNF=chart-2,
  REL=chart-3 (#db2777, trio validado). Não usa cor de severidade para não parecer "crítico".
- Clique ou Enter/Espaço na linha abre `/detalhe-alerta/<id>`; a URL sai só de
  `rotaDetalheAlerta()` em `modules.ts` (caminho do módulo numa constante única).
- A página Detalhe do Alerta ainda está vazia (próximo prompt). Testes: 18.

## 2026-09-25 — Detalhe do Alerta + explicabilidade glass box ✅

- `Backend/pipeline/explicabilidade.py` (pasta pedida como `/pipeline`, colocada dentro de
  `Backend/` pela regra do CLAUDE.md):
  - `explicar_saida(saida, explicador=None, agora=None)` → payload glass box
    `{probabilidade, motivos_por_peso, variaveis_shap, dataset_origem, timestamp, ...}`.
  - Estratégia `Explicador`: `ExplicadorPrecomputado` (stub atual, contribuições vêm na saída)
    e `ExplicadorShap` (modelo real via `shap`, import tardio). Trocar um pelo outro não muda a
    chamada — testado com shap 0.51 e um modelo linear.
  - Motivos em % inteiros que somam 100 (maior resto); validação de campos com `ErroSaidaModelo`.
  - `gerar_texto_alerta(payload)`: formato exato do protótipo para D+1; dia ("hoje"/"amanhã")
    e janela vêm do payload para um alerta de 3h não sair como "amanhã ... D+1".
- `Backend/pipeline/gerar_alertas_mock.py` gera o `alertas.json` do dashboard pelo pipeline
  (texto do alerta com uma implementação só). Teste falha se o arquivo versionado estiver
  desatualizado. `tests/test_explicabilidade.py`: 13 testes.
- Contrato do dashboard: `AlertaDetalhado` ganhou `textoAlerta`, `atualizadoEm` e
  `metodoExplicacao`.
- Tela: bloco terminal com o texto, barras SHAP divergentes (tokens `shap-up`/`shap-down`
  validados), motivos por razão, rastreabilidade (dataset, hora da previsão, janela, método,
  id); sem id lista os alertas; id inexistente mostra "Alerta não encontrado".
- Ambiente: `numpy`/`shap`/`pytest` não estão no Python do sistema; testes rodados num venv.

## 2026-09-25 — Merge de `claude/eager-gauss-or90gs` na main ✅

- Entraram o dashboard (`Frontend/oraculo-dashboard`) e o pipeline de explicabilidade
  (`Backend/pipeline`).
- Conflitos resolvidos juntando os dois lados:
  - `README.md`: tecnologias, passos de execução (download → mapeamento → tabelas →
    explicabilidade → testes → dashboard) e pré-requisitos (Python + Node).
  - `docs/real_vs_mock.md`: ficaram as tabelas dos dados processados (main) e entraram as seções
    Dashboard/Backend (branch).
- `pytest`: 29 passaram, 3 foram pulados e 2 falharam em `tests/test_tabelas.py`. As falhas são
  dos dados locais em `data/processed`, que nenhum arquivo do merge toca (`carga_global` ≤ 0 em
  algum registro; 1 corte > 0 sem flag). Investigar em `src/processing/tabelas.py`.

## 2026-09-25 — Prompt 1 (fundação de dados) + reestruturação em `Backend/` 🟡

### Feito

- **Reestruturação** (prompt em `docs/prompts/prompt_reestruturacao_backend.md`): na raiz ficam só `Backend/`, `Frontend/` e `docs/`. `config`, `data`, `notebooks`, `output`, `src`, `tests`, `RDX` e o `pyproject.toml` foram para `Backend/`, que passou a ser a raiz de import (`python -m src...`, `python -m pipeline...`, sempre de dentro de `Backend/`). `src/utils/paths.py` ganhou `RAIZ_REPO` (docs e Frontend). `Backend/tests/test_estrutura.py` falha se voltar a aparecer pasta na raiz. A pasta vazia `reports/` saiu. Venv novo em `Backend/.venv`.
- `Backend/config/projeto.yaml` com os parâmetros do Prompt 1 (área piloto provisória).
- Inventário (`docs/inventario_portal_ons.md`): 85 conjuntos via API CKAN + contratos do MCP.
- MCP oficial do ONS (`ONSBR/TIAGO-Dados-Abertos`) documentado em `docs/mcp_ons.md`: cobre 80/85 conjuntos, mas não a carga verificada.
- Catálogo: `Backend/data/catalogo_series_selecionadas.md`.
- Download idempotente (`src/ingestion/download.py`): 15 conjuntos, **0 erros**. Sanidade: tm solar 1,02×, detail solar 1,04×, detail eólica 1,27×, tm eólica 1,64× do esperado (período até set/2026). Log por arquivo em `docs/reports/download_log.csv`.
- Mapeamento subsistema × área (`Backend/data/processed/mapeamento_subsistema_area.csv` + `docs/mapeamento_subsistema_area.md`), conferido numericamente; `src/utils/joins.py` é a única porta de cruzamento.
- Tabelas: `calendario.csv`, `carga_supervisionada.csv` (752 mil linhas) e `rotulos_curtailment.parquet` (16 M linhas). `pytest`: 33 passaram, 3 pulados (shap opcional; schema oficial ainda não aprovado).
- Área piloto: `docs/area_piloto_opcoes.md`.
- Proposta de schema v1: `docs/schema_contrato_v1_proposta.json`, exemplo e `docs/schema_changelog.md`.

### Bloqueado

- **Limites de exportação NE e N/NE**: não existem no portal nem no MCP. Afeta só a feature de folga do CNF (cortável).
- **`docs/schema_contrato.json` "atual" nunca foi commitado**: a proposta v1 partiu dos blocos citados neste STATUS.
- `import torch` falha no Windows (WinError 1114 em `c10.dll`). Não afeta o Prompt 1; afeta o TFT.

### Decisões

- Fuso único **UTC−3 fixo**; timestamp = **início** da semi-hora (`src/utils/tempo.py`). Antes de 2019, fica 1 h deslocado do horário civil com horário de verão.
- Carga supervisionada = `val_cargaglobal − val_cargammgd` (mesma base, MWmed, 30 min: sem reamostragem). MMGD ausente (antes de 2019-02-15) fica NaN. Carga ≤ 0 vira NaN com `carga_global_invalida`.
- Rótulos: corte = GNRa; sem GNRa publicada, `max(ref − ger, 0)` (idêntico à GNRa onde ambas existem; `corte_origem` marca). Divisão por razão proporcional aos minutos. `flag_X` = minutos > 0 ou razão declarada. `''` → NULL; minutos fora de [0, 30] → NULL; duplicatas do ONS removidas.
- `data/raw` só tem Parquet (CSVs convertidos na chegada); resposta vazia da API não gera arquivo.
- DuckDB sempre via `src/utils/banco_analitico.py`, com limites de memória e disco; consolidação por `id_ons` em grupos ordenados (1 arquivo por usina).
- A base de MMGD da ANEEL contém CPF/CNPJ e nomes: fica só em `data/raw`, e nenhuma tabela processada seleciona essas colunas.

### Pendências humanas (Tiago)

- **Confirmar a área piloto** (proposta: CEMIG-D, Norte de Minas, polo Janaúba–Jaíba) e **avisar o Luiz**.
- **Aprovar (ou ajustar) a proposta de schema v1** (`docs/schema_changelog.md`).
- Se quiser, liberar espaço: o cache do pip tem ~6,8 GB (`pip cache purge`).
- Torch no Windows: instalar o Visual C++ Redistributable 2015–2022 ou fixar outra versão do torch antes do TFT.

### Enviar ao Luiz

- `docs/area_piloto_opcoes.md` (área piloto provisória).
- `docs/schema_changelog.md` (proposta v1 do contrato; confirmar se ele tem cópia do rascunho antigo).
- Mudança de estrutura: o Python agora roda de dentro de `Backend/` (`python -m pipeline.gerar_alertas_mock`).

### Falta no Prompt 1

- Executar `Backend/notebooks/01_eda_bases_tm.ipynb` e `02_figura1_parpel.ipynb` (gera `docs/reports/figura1_parpel.png`).

## 2026-09-25 — Notebooks Jupyter removidos ✅

- Decisão do Tiago: o produto é um serviço (ingestão → processamento → modelos → banco → FastAPI →
  dashboard) e notebook não é chamado por nenhuma etapa. `Backend/notebooks/` (01_eda_bases_tm,
  02_figura1_parpel) e `src/utils/notebooks.py` saíram; `jupyter`/`nbconvert`/`ipykernel` saíram do
  `[dev]` do `pyproject.toml`; `NOTEBOOKS` saiu de `src/utils/paths.py`.
- Trava: `tests/test_estrutura.py::test_nenhum_notebook_jupyter_versionado` falha se algum `.ipynb`
  voltar a ser versionado.
- O item "executar os notebooks" do Prompt 1 fica **substituído** pela Fatia 1 como código do
  backend (validação de qualidade das bases tm, série histórica de curtailment por razão e
  episódios de corte), a implementar.

## 2026-09-25 — Plano transcrito para `docs/Oraculo_planejamento.md` ✅

- Transcrição em Markdown do PDF `ORACULO_Planejamento_v2` (seções 1–12; figuras do PAR/PEL
  indicadas só pela legenda).
- Seção 13 (adendo, não está no PDF) com as decisões de implementação:
  - **13.1 Gatilho da ingestão = endpoint FastAPI** (`POST /ingestao` em segundo plano +
    `GET /ingestao/{id}`; uma execução por vez, `409` se já houver outra). Sem cron/agendador no
    hackathon. Cadência de 30 min do PDF demonstrada em modo replay.
  - 13.2 Fatia 1 sem notebooks; 13.3 ingestão via CKAN (o MCP não cobre a carga verificada).
  - 13.4 Decisões pendentes: área piloto (o PDF não define; CEMIG provisória × RJ/RDX), contrato
    do dashboard (`types.ts` × `schema_contrato_v1_proposta.json`), campo `distribuidora` do risco.

### Pendências humanas (Tiago)

- Escolher a área piloto (ver 13.4) e avisar o Luiz.
- Decidir qual contrato vale: `types.ts` do dashboard ou a proposta v1.

## 2026-09-25 — Arquitetura de execução: `run_heavywork.py` + web só de leitura ✅ (definição)

- `docs/Oraculo_planejamento.md` §13.1 reescrita (substitui o gatilho por endpoint registrado acima):
  - **Trabalho pesado** num script único, `Backend/run_heavywork.py`, sem argumentos (config em
    `config/*.yaml`): ingestão (baixa só o que falta/está desatualizado) → processamento + qualidade
    → treino e backtest → previsões da janela da demo (replay) → publicação no banco. Cada etapa
    pula o que já está em dia.
  - **Serviço web** (FastAPI + dashboard) só lê o banco: sem endpoint de ingestão, sem agendador,
    sem dependências pesadas.
  - Dado bruto só é usado pelas etapas de ingestão e processamento; regra a ser garantida por teste.
- Ainda **não implementado**: `run_heavywork.py`, o teste de isolamento do bruto, a API e o banco.

## 2026-09-25 — `Backend/run_heavywork.py` (etapas 1 e 2) ✅

### Feito

- `python run_heavywork.py` (de `Backend/`, sem argumentos; config em `config/heavywork.yaml`):
  ingestão → processamento → treino → previsão → publicação. Treino, previsão e publicação estão
  declaradas e aparecem como `nao_implementada` no resumo (não fingem rodar).
- Motor genérico em `src/heavywork/orquestrador.py` (etapas em `src/heavywork/etapas.py`): cada etapa
  tem uma impressão digital das entradas (dados + código + config) e é **pulada** se nada mudou e as
  saídas existem; falha interrompe as seguintes e não marca a etapa como concluída. Estado local em
  `data/_estado_heavywork.json`, trava em `data/_heavywork.lock` (ambos fora do git).
- Ingestão (`download.py`) agora detecta **arquivo republicado** pelo portal (`size`/`metadata_modified`
  do CKAN guardados no manifesto) e rebaixa o cadastro da ANEEL após `atualizar_apos_dias`
  (por arquivo em `fontes_ons.yaml`; ANEEL = 7 dias). Lógica saiu do `main()` para
  `executar()`; `tabelas.py` e `mapeamento.py` ganharam `construir()`. Linha de comando de cada módulo
  continua para depuração.
- Trava de processo movida para `src/utils/trava.py`; log em `src/utils/log.py`; hashes em
  `src/utils/impressao.py`.
- Execução real: 1ª rodada rebaixou 15 arquivos republicados (meses de 2026 e detail eólica 2023-05) e
  reconsolidou as bases detail (eólica 349 s, solar 81 s); ingestão 7,7 min, processamento 1,6 min.
  Rodada seguinte sem novidade: ingestão 10 s, processamento **pulado**.
- `pytest`: 53 passaram, 3 pulados.

### Bugs transformados em regra (classe eliminada)

- **Mês republicado duplicaria linhas na base detail** (a consolidação somava a versão nova à antiga):
  `sql_consolidacao()` faz os meses dos arquivos novos substituírem os mesmos meses do consolidado.
- **Processamento refeito em toda execução**: a ingestão rebaixa sempre a carga recente e a impressão
  usava a hora do download. Agora usa o sha256 do conteúdo (`conteudo` no manifesto).
- **Etapa com nome errado no YAML passaria em silêncio**: `validar_config()` recusa.
- **Camada de modelos/API lendo o bruto**: `test_so_ingestao_e_processamento_tocam_o_dado_bruto`.

### Decisões

- Comparação de atualização é portal × portal (metadados do CKAN no download × agora), não portal ×
  disco: se o `size` do CKAN não bater com os bytes servidos, não há rebaixamento em loop.
- A etapa de ingestão sempre roda (só as fontes sabem se há novidade); o download é idempotente.
- `src/utils` inteiro entra na impressão do processamento: no pior caso reprocessa à toa (~1,5 min),
  nunca deixa de reprocessar.

### Pendências

- Peça A da Fatia 1 (qualidade das bases) ainda não entra no processamento.
- Etapas 3–5 (treino, previsão/replay, publicação no banco) e a API.

## 2026-09-25 — Banco + API FastAPI + publicação (etapa 5) ✅

### Feito

- **Contrato oficial = `types.ts` do dashboard** (decisão do Tiago). Espelho Pydantic em
  `Backend/src/contrato/modelos.py`; `docs/schema_contrato.json` gerado dele
  (`python -m src.contrato.esquema`); explicação em `docs/schema_contrato.md`. Proposta v1 e seu
  teste removidos (histórico no git e em `docs/schema_changelog.md`).
- **Banco** (`src/db/`): SQLAlchemy 2 + Alembic (`alembic.ini`, `migrations/`), factory única com
  `DATABASE_URL` ou `Backend/oraculo.db`. Tabelas `execucao` e `recurso` (itens do contrato em JSON).
- **Publicação** = etapa 5 do `run_heavywork.py` (`src/publicacao/montar.py`): função única
  `montar_contrato()` -> `output/contrato.json` + banco. **Carga real** (SIN, último dado:
  2026-09-24 23:30 UTC−3, 83,7 GW, MMGD 206 MW); previsão, riscos, alertas, excedentes e validação
  vêm dos mocks do dashboard com `mock: true`.
- Nova tabela processada `capacidade_mmgd.csv` (ANEEL, UF × data, 53,97 GW cadastrados; só UF, data
  e potência são lidas: nenhuma coluna pessoal).
- **API** (`Backend/main.py` + `src/api/app.py`): 6 rotas GET do contrato + `/api/saude`; 503 com
  instrução se o banco não foi publicado; CORS para o `npm run dev`. Testada ao vivo com `python main.py`.
- Docs: `docs/backend.md` (como rodar), README (tecnologias e `python main.py`), plano §13.1/§13.4,
  `docs/real_vs_mock.md`. `pytest`: 75 passaram, 1 pulado.

### Bugs transformados em regra

- **Datas sem fuso vindas do SQLite** (`/api/saude` mostrava horário sem `Z`): tipo `UtcDateTime`
  recusa gravar sem fuso e sempre devolve UTC.
- **Alias camelCase divergente** (`historicoErro30D` × `historicoErro30d`): pego pelo teste que valida
  os mocks do dashboard contra o contrato do Backend; esse teste impede divergências futuras.
- **Publicação pela metade / fora do contrato / id repetido**: recusadas numa transação só.
- **Serviço web puxando a parte pesada**: teste sobe `main.py` num processo limpo e falha se pandas,
  DuckDB, ingestão, processamento etc. forem carregados.
- **Modelo do banco sem migration**: teste compara `src/db/tabelas.py` com as migrations.

### Decisões

- Banco guarda documentos JSON do contrato (não uma coluna por campo): o formato vive num lugar só.
- `percentualMmgdNaGeracao` = MMGD ÷ carga global × 100; `mmgdSobreCapacidadeInstalada` = MMGD do
  ONS ÷ capacidade ANEEL cadastrada até a data (data de atualização cadastral como aproximação).
- SQLite com caminho absoluto: `run_heavywork.py` e `main.py` nunca apontam para bancos diferentes.

### Enviar ao Luiz

- A API está pronta: `python main.py` em `Backend/`; contrato = o `types.ts` dele, sem mudança.
  Para ligar: `VITE_DATA_SOURCE=api` + proxy `/api` -> `http://127.0.0.1:8000` (ou
  `VITE_API_BASE_URL=http://127.0.0.1:8000/api`). Só a carga é real; o resto vem com `mock: true`.
- Ainda pendente com ele: o que mostrar no campo `distribuidora` do risco por usina.

## 2026-09-26 — Dashboard ligado na API do Backend ✅

O que já existia: Backend com 6 rotas do contrato + `/api/saude` (FastAPI, `main.py`) lendo o banco
publicado pelo `run_heavywork.py`; dashboard com Visão Geral, Despacho Preditivo, Lista de Riscos e
Detalhe do Alerta, mas lendo só os mocks (`VITE_DATA_SOURCE=mock` era o padrão).

Feito:
- **API é o padrão do dashboard**; mock virou opt-in explícito (`npm run dev:mock` = `vite --mode mock`).
  Os testes do Vitest fixam `VITE_DATA_SOURCE=mock` em `vite.config.ts`, sem depender de `.env` local.
- **Proxy do Vite** (`/api` → FastAPI) com host/porta/prefixo **lidos de `Backend/config/api.yaml`**
  (dependência dev `yaml`): a porta existe num lugar só, o proxy nunca aponta para uma porta antiga.
- **Backend serve o build do dashboard** (`dashboard_dist` em `config/api.yaml`): `npm run build` +
  `python main.py` = demo num servidor só (http://127.0.0.1:8000/). SPA fallback para as rotas do
  React Router; caminho inexistente sob `/api` responde 404 JSON (nunca `index.html` com 200, que
  esconderia um endpoint errado como "JSON inválido"); arquivo fora de `dist/` é recusado.
- **`/api/saude` tipada** (`Saude`, Pydantic) + `SaudeApiSchema`/`getSaude()` no dashboard.
- **Pill de origem dos dados na topbar** (`FonteDados`): "DADOS MOCK" | "DADOS DE dd/mm HH:MM"
  (instante do replay) | "API INDISPONÍVEL" (causa no tooltip). Dado mock nunca passa por real.
- **Erros da API legíveis na tela:** o `detail` do FastAPI entra na mensagem (o 503 diz para rodar
  `python run_heavywork.py`); Backend desligado mostra a instrução de subir o `main.py`.
- `StatusPill` não quebra linha (`whitespace-nowrap`).
- `pyproject.toml`: faltava `scikit-learn` (o `LGBMRegressor`/`LGBMClassifier` exigem; os testes de
  modelos falhavam num ambiente limpo).

Verificação: publiquei os mocks num SQLite temporário, subi `python main.py` e `npm run dev`, e abri
Visão Geral, Despacho Preditivo, Lista de Riscos e Detalhe do Alerta no Chromium (Playwright) pelos dois
caminhos (Vite com proxy e build servido pelo FastAPI): todas as chamadas `/api/*` com 200, nenhuma tela
com "Falha ao carregar dados", zero erros no console. Com o Backend desligado, a tela mostra "API
INDISPONÍVEL" e a instrução. Backend: 103 testes passam (3 novos em `test_db_api.py`); 2 de
`test_publicacao.py` falham neste ambiente por falta de `data/processed/calendario.csv` (dado local,
não relacionado). Dashboard: build, lint e 18 testes limpos.

Pendente (👤 Tiago + Luiz): as telas Excedentes, Validação e Mapa Híbrido prontas na branch
`claude/eager-gauss-or90gs` ainda não estão no `main`; elas mudam o contrato (`lat`/`lon` em risco e
excedente, `modelo` e `baselineNome`/`maeBaseline` na validação, recurso novo `DensidadeMmgd`) e
exigem espelhar isso no Backend — mudança de schema, aguardando decisão.
## 2026-09-25 — Dashboard: tela Excedentes TSO-DSO ✅

- Tabela por área de concessão: área, distribuidora, fonte, excedente (MW), badge de
  prioridade com rótulo High/Medium/Low (cor da escala de severidade), horizonte, ação e botão
  "Executar" — só interface: ao clicar a linha mostra "simulado · nada enviado".
- KPIs: excedente total (733 MW), MW em prioridade alta, nº de áreas.
- `ordenarExcedentes()` (prioridade → MW → área) com `compararSeveridade()` comum às
  ordenações (+ teste).
- `components/ui/Tabela.tsx`: moldura única de tabela (rolagem, cabeçalho, quebra só nas
  colunas `quebra`); Lista de Riscos migrada para ela.
- Pendente: "transformação de fronteira" (subestação/trafo TSO-DSO de cada área) não existe no
  contrato; não foi inventada. Testes: 19.

## 2026-09-25 — Dashboard: tela Validação ✅

- KPIs MAE, RMSE, MAPE e skill vs. climatologia.
- Dois gráficos Recharts lado a lado (MAE e RMSE, um eixo cada — sem eixo duplo): modelo
  (ciano) vs. baseline (tracejado), 30 dias, tooltip com ganho sobre o baseline.
- Cards de status por fonte (pill online/offline + última sincronização em BRT e "há X").
- Metadados do modelo (placeholder `0.0.0-placeholder`, com períodos de treino/teste).
- Limitações declaradas em `src/content/limitacoes.ts` (fonte única, reaproveitável).
- Contrato `MetricasValidacao`: + `baselineNome`, `maeBaseline`/`rmseBaseline` por dia e
  `modelo` (schema recusa teste que comece antes do fim do treino). Skill agora é derivado do
  histórico no gerador (teste confere).
- `utils/escala.ts::ticksRedondos()`: regra única de ticks para todos os gráficos (tirou os
  350/1.050 MW); Despacho Preditivo migrado. Testes: 21.

## 2026-09-25 — Dashboard: Mapa Híbrido ✅

- react-leaflet: usinas de `getRiscos()` como círculos na cor da severidade (tamanho ∝ MW) e
  excedentes de `getExcedentes()` como losangos na cor da prioridade.
- Camadas ligáveis (`ToggleChip`): usinas, excedentes e densidade de MMGD — heatmap
  `leaflet.heat` com dados SINTÉTICOS (`getDensidadeMmgd()`, `mmgd_densidade.json`, mock),
  gradiente violeta (identidade da MMGD).
- Painel "Subestações em risco" ordenado por severidade e sincronizado com os marcadores
  (hover destaca nos dois sentidos; clique no item centraliza). Clique no marcador de risco
  abre o Detalhe do Alerta; no de excedente, a tela Excedentes.
- Fundo offline: contorno do Brasil (Natural Earth via world-atlas, `npm run geo:brasil`) sempre
  desenhado; tiles escuros da CARTO por baixo quando a rede permite (bloqueados no ambiente de
  desenvolvimento, então as capturas mostram só o contorno).
- Contrato: `lat`/`lon` em RiscoUsina e ExcedenteTsoDso (schema recusa coordenada fora do
  Brasil, ex.: lat↔lon trocados); novo `DensidadeMmgd`.
- `theme/tokens.ts::corToken()` para Leaflet/canvas lerem as cores de index.css; `ToggleChip`
  compartilhado — os filtros da topbar passaram a usá-lo (corrige o NO-RISK desligado, que era
  indistinguível do ligado: agora fica riscado e com ponto vazado). Testes: 23.
## 2026-09-26 — Fase 3 (baseline de carga) ✅ e Fase 4 (classificador de curtailment) 🟡

- **Carga** (`src/models/carga.py`, `config/modelos_carga.yaml`): persistência, sazonal-naïve (dia e semana), climatologia e LightGBM quantílico por série (SE, S, NE, N, SIN) e horizonte (30 min, 3 h, D+1). Banda P10–P90 calibrada por conformal (CQR) e modelo reajustado com o treino inteiro. Teste fora da amostra de jul/2025 a set/2026: o LightGBM ganha do melhor baseline nas 15 combinações. SIN: MAE de 555 MW (30 min), 1 559 MW (3 h) e 1 685 MW (D+1), com MAPE entre 0,8% e 2,5% e cobertura P10–P90 em torno de 74%. Relatório em `docs/reports/baseline_carga.md`.
- Publicação: a `validacao` é real; a `previsao` tem pontos reais, mas sai com `mock: true` porque os fatores climáticos ainda são mock.
- Garantias:
  - `src/features/defasagens.py` recusa defasagem que olhe depois da emissão;
  - split único em `src/models/split.py`;
  - testes de vazamento: futuro perturbado e treino idêntico mudando o período de teste;
  - impressão digital das etapas derivada dos imports (`codigo_de`).
- **Bug transformado em regra:** o LightGBM 4.7.0 dá "access violation" no Windows. A versão foi fixada em <4.7 e ganhou um teste de fumaça.
- **Curtailment** (`src/features/curtailment.py`, `src/models/curtailment.py`, `config/modelos_curtailment.yaml`): classificador ENE/CNF + montante esperado, SHAP exato (`ExplicadorLightGBM`), publicação de riscos e alertas, etapas `treino_curtailment` e `previsao_curtailment`. Testes sintéticos passam. **Ainda não rodou com dado real**: a próxima execução de `python run_heavywork.py` treina, estimativa ~15 min.
- Etapas renomeadas de `treino`/`previsao` para `treino_carga`/`previsao_carga`; o estado local foi migrado.

## 2026-09-26 — Telas Excedentes, Validação e Mapa Híbrido integradas + contrato v3 ✅

Aprovado pelo Tiago: trazer as três telas do Luiz (branch `claude/eager-gauss-or90gs`, que não
estavam na main) e adaptar o Backend às mudanças de schema que elas trazem.

Frontend:
- Cherry-pick dos 3 commits (Excedentes TSO-DSO + `Tabela`; Validação + `GraficoErro`; Mapa
  Híbrido com react-leaflet e heatmap). Conflitos resolvidos juntando os dois lados (`saude` e
  `mmgdDensidade` em `ENDPOINTS`; `yaml` e `world-atlas` nas dependências; lockfile regenerado).
- Com isso as 7 telas de dados funcionam pela API (Metodologia segue vazia).

Backend (contrato v3, detalhes em `docs/schema_changelog.md`):
- `src/contrato/modelos.py`: `lat`/`lon` (caixa do Brasil) em risco e excedente; validação com
  `baselineNome`, `maeBaseline`/`rmseBaseline` e `modelo` (com a regra do split cronológico);
  recurso novo `DensidadeMmgd`. `RECURSOS` agora tem a rota de cada recurso (`DefRecurso`).
- **Rotas da API geradas de `RECURSOS`** e `esquema.py` sem cópia própria das rotas: recurso
  novo = uma linha. Teste confere que toda rota existe no `dataSource.ts` (as duas pontas não
  divergem mais em silêncio).
- **Banco publicado com contrato anterior → 503 "rode run_heavywork.py"**, não 500: toda resposta
  é revalidada contra o contrato atual. Evita que a próxima mudança de schema derrube o dashboard
  de quem ainda não republicou.
- Publicação (`montar.py`):
  - validação: erro diário da climatologia lado a lado; metadados do modelo — período de treino
    do split, teste até o último dia com real conhecido, versão = hash da config de treino e
    data do treino, gravados em `data/modelos/carga/metadados.json` pela etapa `treino_carga`
    (modelo antigo sem o arquivo: versão da config atual e data do `modelos.joblib`);
  - riscos: `lat`/`lon` = sede da UF (`posicao_uf` em `config/publicacao.yaml`), porque não há
    coordenada por usina no que o projeto ingere → risco continua `mock: true`
    (`POSICAO_USINA_REAL`); UF sem posição faz a publicação falhar;
  - `mmgd_densidade`: mock do dashboard (sintético) até a Fase 6.
- `docs/schema_contrato.json` regenerado; `schema_contrato.md`, `real_vs_mock.md`, `backend.md`.

Verificação: backend 118 testes passam (novos: rota × dataSource, posição fora do Brasil, split
invertido, 503 de contrato anterior, todas as rotas servidas, baseline/metadados da validação,
posições das 27 UFs, versão muda com a config). Dashboard: 23 testes, lint e build limpos. Ponta a
ponta no Chromium com o build servido pelo FastAPI: as 7 telas de dados carregam com 200 em todas
as rotas `/api/*` (inclusive `/api/mmgd/densidade`); os únicos erros de console são tiles/fontes
externos bloqueados pela rede deste ambiente.

Pendente: rodar `python run_heavywork.py` na máquina com os dados para republicar no contrato v3
(até lá a API responde 503 nos recursos que mudaram). Coordenada real por usina (SIGA/ANEEL)
tiraria o `mock` de posição dos riscos.

## 2026-09-26 — Passada geral nos prompts do frontend (1–12), design Figma e alinhamento com os PDFs ✅ (Luiz)

Referências: protótipo Figma "SCADA Dashboard Design" (zip), `Equipe24_LINKFY_ORACULO_pitch_Vfinal` e
`ORACULO_Planejamento_v2` (PDFs). Nenhuma mudança de schema: `src/data/types.ts` e o contrato do Backend
estão intactos.

### Auditoria prompt a prompt

| Prompt | Como estava | O que mudou |
|---|---|---|
| 1 · scaffold + design system | feito, mas os filtros NORMAL/LOADING/CRITICAL/NO-RISK **não agiam em nenhuma tela**; topbar estourava a 1440px | filtros ligados às telas; casca refeita no arranjo do Figma |
| 2 · contrato mockado | feito (o `types.ts` é o contrato oficial) | nada |
| 3 · Visão Geral | feito (3 KPIs + composição) | 4 KPIs, curva D+1 com patamares, coluna "Alertas ativos" com montante por razão |
| 4 · Despacho Preditivo | feito | equação carga global − MMGD = carga supervisionada (pitch, slide 9), faixas de mínima diurna/ponta noturna, painel "o erro que custa mais" |
| 5 · Lista de Riscos | feito | filtros + faixa de severidade na linha |
| 6 · Detalhe do Alerta + explicabilidade | feito (Backend + tela) | card "Ação recomendada" (o campo já vinha no contrato e não aparecia; slide 10) |
| 7 · Excedentes TSO-DSO | feito; tabela cortava o botão a 1440px | faixa "payload da interface ONS–DSO" (slide 7), barras por área, tabela na largura toda |
| 8 · Validação | feito | tipografia; lista de limitações virou componente comum |
| 9 · Mapa Híbrido | feito, mas os tiles da CARTO passaram a responder **"API KEY REQUIRED"** por cima do mapa | fundo 100% local (contorno Natural Earth + divisas das UFs do IBGE) |
| Metodologia | **vazia** | tela nova com o método dos PDFs (fontes → evidências → produtos, os dois desafios, auditoria em 3 camadas, validação, limites, fontes técnicas) |
| 10 · visão computacional | **não existia** | `pipeline/visao_comum.py`, `validar_modelo.py`, `auditoria_camada1.py`, `download_satelite.py` + `config/visao.yaml` |
| 11 · auditoria camadas 2 e 3 | **não existia** | `pipeline/auditoria_camadas_2_3.py` + mocks BDGD/ANEEL/painéis |
| 12 · harness e2e | **não existia** | `pipeline/teste_e2e.py` + `config/e2e.yaml` + cenário `dia_dos_pais_2024` |

### Feito

- **Design (Figma como base, com crítica):** IBM Plex Sans + JetBrains Mono empacotadas (offline), escala de texto por papel (`text-label` 11px, `text-body` 13px, `text-kpi` 30px), cantos retos, topbar de largura total com marca, sidebar de 13rem que vira coluna de ícones abaixo de `lg`, cabeçalho de módulo compacto, KPIs com borda superior de identidade, conteúdo com rolagem própria. Conferido no Chromium a 1440, 1024 e 390 px (sem estouro horizontal, zero erro de console).
- **Patamares e faixas de curtailment LIDOS de `Backend/config/processamento.yaml`** no build (`vite.config.ts` → `__CALENDARIO__` → `src/content/calendario.ts`, validado com Zod). Teste confere que o dashboard usa exatamente os horários do Backend.
- **Filtros de severidade** agem em Visão Geral, Mapa, Lista de Riscos e Excedentes; cada tela mostra quantos itens ficaram ocultos. KPIs de sistema continuam sobre todos os itens.
- **Visão computacional:** o `best.pt` disponível carrega (ultralytics 8.4, torch 2.14 CPU): YOLOv8s-seg, classe `solar-panel`, imgsz 640, treinado em 2023-07-10 por terceiros (`pkrawiec/projects/solar-panels`) — **modelo público, sem o fine-tuning local do planejamento**. Validação rodada à mão com as imagens de exemplo do ultralytics (não são de satélite, só para exercitar o código): o modelo marcou "solar-panel" em placas e letreiros de um ônibus (confiança 0,26–0,51).
- **Auditoria 1 → 2/3 em modo mock:** 12 painéis sintéticos → 5 Cadastrada, 3 Lag de Sistema, 1 Divergência cadastral, 3 Não homologada (fora do fator, escaladas como exceção); fator por alimentador 1,35 e 1,03 (valores de mock).
- **Teste e2e:** `docs/reports/teste_e2e.md` (nesta máquina: bases e modelos ausentes → contrato vem dos mocks, valida no contrato, alertas coerentes com os riscos).
- Testes: dashboard 34 (antes 23), Backend 145 passam e 8 pulados (33 novos em `test_visao_auditoria.py` e `test_teste_e2e.py`). Build, lint e typecheck limpos.

### Bugs transformados em regra

- **`text-base` ambíguo** (tamanho de fonte padrão do Tailwind **e** a cor `base`): texto quase preto sobre o fundo (valores da Metodologia sumiam; o logo também). Token renomeado para `fundo`; `src/theme/tokens.test.ts` falha se alguma cor tiver nome de tamanho de fonte.
- **Mapa dependente de serviço externo** (CARTO passou a exigir chave): fundo local; `src/pages/semServicoExterno.test.ts` falha se voltar `TileLayer`, URL `{z}/{x}/{y}` ou fonte/CSS de CDN.
- **Controle que não faz nada** (filtros): `SEVERIDADE_STATUS` é `Record` exaustivo sobre a severidade do contrato (severidade nova sem filtro não compila) + testes de filtragem e de ocultos.
- **"Adequado" sem gabarito** na validação do YOLO: o veredito agora é `ajustar` | `sanidade_ok_sem_gabarito` | `adequado`, e só dá `adequado` com `gabarito.csv`; imagens anotadas saem em `<imagens>/_anotadas/`.
- **Mock contaminando saída real:** a auditoria recusa gravar em `output/auditoria/` se qualquer entrada for mock; saídas mock vão para `output/auditoria/mock/` (fora do git).
- **Testes com APIs do Node no tsconfig do navegador:** `tsconfig.test.json` próprio (o código da tela continua sem tipos do Node).

### Decisões

- **Do Figma NÃO entrou:** frequência do SIN, ciclo DESSEM, "margem até o mínimo técnico" (30,4 GW), "modelo XGBoost+LSTM", botões "→ Gerdin", "Extrapolação de tendências" com fatores de crescimento sem fonte — nada disso existe em fonte do projeto. Também não entrou a semântica errada das razões (o Figma chama CNF de "intercâmbio/congestionamento" e REL de "rede N-1"; no dicionário do ONS CNF é confiabilidade e REL indisponibilidade externa), nem a paleta de cinzas de contraste ~2,6:1 e rótulos de 9px. Cores do Prompt 1 mantidas.
- **Prompt 12 sem chave manual mock/real:** o pedido previa um `data_sources_config.json` com "mock"/"real" por etapa; ficou `config/e2e.yaml` só com caminhos (regra do CLAUDE.md) e o status é lido dos dados — uma chave manual poderia dizer "real" com o dado em mock:true. O "trocar sem mexer no dashboard" já é garantido pela API + contrato.
- **Camada 1 `--mock` não roda o YOLO:** painéis sintéticos declarados em JSON passam pela mesma geometria do modo real (rodar o modelo em imagem placeholder não testaria nada).
- **"Recente" no desempate** = homologado depois da `data_referencia` da BDGD. Homologado antes e fora da BDGD vira "Divergência cadastral" (entra no fator, homologada; vai para revisão).
- **Premissa** `kwp_por_m2 = 0,18` (área → capacidade) em `config/visao.yaml`, registrada em `docs/real_vs_mock.md`.
- **Trava de resolução no download:** escala > `modelo.gsd_maximo_m` (0,5 m) é recusada sem `--forcar` — com Sentinel-2 (10 m) o modelo devolveria "zero painéis", um falso negativo que pareceria resultado.
- Módulos de visão (download, validação, Camada 1) entraram na lista de quem pode ler `data/raw` em `tests/test_estrutura.py`: são ingestão/processamento de imagem.

### Bloqueado

- Rodar a auditoria real: sem imagem submétrica da área piloto, sem BDGD real e sem bbox (área piloto ainda provisória).
- Cenário Dia dos Pais com dado real: as bases do ONS não estão nesta máquina (o cenário extrai do dado quando elas existem; testado com fixture sintética).

### Pendências humanas

- **Tiago:** confirmar a área piloto e preencher `satelite.bbox` (`config/visao.yaml`); ingerir a BDGD; rodar `python -m pipeline.teste_e2e` na máquina com as bases (gera o caso Dia dos Pais real). Lembrar: 2024-08-11 está no treino do classificador (in-sample).
- **Luiz:** projeto do Earth Engine (`satelite.gee_projeto`) e, principalmente, fonte de imagem **submétrica**; montar um `gabarito.csv` com imagens da área e revisar a confiança mínima (0,25 deixou passar falsos positivos); decidir onde os pesos `.pt` ficam para o time (estão fora do git).
- **Time:** este trabalho foi feito na cópia `solucoes-grupo-24` (repositório da competição), que está idêntica ao `HackaIA_Oraculo` + estas mudanças; decidir em qual repositório publicar.

### Enviar ao Tiago

- O dashboard agora lê `calendario.patamares` e `calendario.faixas_curtailment` de `Backend/config/processamento.yaml` no build: mudar os horários lá muda a tela.
- `src/utils/log.py::console_utf8()` (acentos legíveis no console do Windows) e extra `[visao]` no `pyproject.toml`.
- `tests/test_estrutura.py`: allowlist do dado bruto ampliada para os 4 módulos de visão.

## 2026-09-26 — Visão geral do sistema ✅ (Luiz)

- `docs/visao_geral_sistema.md`: o sistema como um todo — problema e produtos, fluxo ponta a ponta (diagrama), fontes de dados e como chegam, tratamento (tempo, recortes, tabelas processadas), modelos de carga e curtailment com resultados do backtest, garantias contra vazamento, publicação/banco/API (situação real × mock de cada rota), as 8 telas e de onde leem, auditoria da MMGD, teste e2e, regras garantidas por teste, pendências e mapa de pastas. README aponta para ele (link único para `docs/`).
- Pendência encontrada ao escrever: limiares de severidade divergentes entre o Backend (40/60/80%, `config/modelos_curtailment.yaml`) e o KPI agregado do dashboard (25/50/75%, `src/data/derivados.ts`); o mesmo 57,8% sai "Alto" no KPI e seria "Médio" na lista. Não corrigido aqui (decidir qual escala vale e ler de um lugar só).

## 2026-09-26 — Consolidação do protótipo O.R.A.C.U.L.O. (Equipe 24) no repositório ✅

- **Backend:** pacote `Backend/oraculo/` (antes `02-PROTOTIPO/oraculo`, Starlette + numpy/scipy) com as
  rotas incluídas no FastAPI de `main.py` (`_incluir_prototipo` em `src/api/app.py`): um servidor só
  para contrato, protótipo, documentação Sphinx (`/docs`), interface original (`/legado`) e dashboard.
  Swagger mudou para `/api-docs` (o `/docs` é a ajuda F1). Cache de trabalho em
  `Backend/data/oraculo_cache/` (fora do git). Suíte do protótipo em `Backend/tests_oraculo/`
  (521 passaram, 1 pulado). `run_oraculo_legado.py` e `run_oraculo_pipeline.py` mantidos.
- **Frontend:** as 17 telas do protótipo reescritas em React (`src/oraculo/pages/`), com o cliente do
  envelope de proveniência (`api.ts`), gráficos SVG portados (`charts.ts`), CSS escopado em
  `.oraculo`, seletor de área, ajuda F1 e grupos no menu (`grupo` no `ModuleDef`). Primeiro vêm as
  telas do protótipo, depois o grupo "Dashboard do contrato".
- **Visão computacional com as duas soluções:** Detector por subestação (protótipo, `/visao`) e
  Auditoria MMGD · 3 camadas (pipeline do time; nova rota só de leitura `/api/auditoria/mmgd`,
  `src/api/auditoria.py`, tela `/auditoria-mmgd`).
- **Docs:** `docs/oraculo/` (Sphinx com caminhos atualizados, especificações, apresentações).
- **Correções de bugs anteriores encontrados no caminho:** `tsconfig.test.json` não incluía
  `leaflet-heat.d.ts` (o `tsc -b` falhava); `semServicoExterno.test.ts` quebrava em caminho com espaço
  (`%20`). `test_servico_web_nao_carrega_a_parte_pesada` passou a permitir numpy (o protótipo calcula
  no serviço); pandas/DuckDB/modelos continuam proibidos.
- Ambiente: `Backend/.venv` com Python 3.12 (o 3.14 da máquina está fora de `requires-python`).

## 2026-09-26 — Branch `feat/design-prototipo-original`: visual do protótipo + OpenStreetMap ✅

- **Visual do protótipo de volta, fiel ao original** (`02-PROTOTIPO/web`): casca `src/oraculo/Casca.tsx`
  com a mesma marcação (`#shell`, `#sidebar`, `.brand`, `nav`, `#top`, `#content`), ícones, grupos e
  rótulos do menu original; `src/oraculo/oraculo.css` derivado regra a regra do CSS original (paleta,
  raios, sombras, fontes do sistema). Comparado por captura de tela com `/legado` (Despacho, Risco,
  Curva do pato, Fronteira): idêntico.
- **Tema claro e escuro** como no original: botão ☾/☀ na topbar, `data-theme` no `<html>`, escolha em
  `localStorage` (`oraculo.theme`, a mesma chave da interface original), aplicado antes do primeiro paint.
- **Dashboard do contrato dentro da casca**: grupo próprio no menu; as tokens do Tailwind apontam
  para a paleta do protótipo, então seguem o visual e o tema; filtros de severidade e origem da
  publicação aparecem na topbar só nessas telas. Saíram `AppLayout`, `Sidebar`, `Topbar`,
  `ModuleFrame`, `Clock` e `oraculo/Barra.tsx`.
- **OpenStreetMap** (`src/oraculo/MapaOsm.tsx`, único arquivo com tile remoto; o teste
  `semServicoExterno` trava a regra): cena georreferenciada da subestação sobreposta ao OSM com as
  detecções em polígonos e opacidade ajustável (Perfis por subestação, Visão computacional),
  subestações no mapa, SE × SED (Fronteira), sítios de BESS e painéis da auditoria MMGD. O mapa
  esquemático original continua em cada tela (chip "Esquemático"). No tema escuro os tiles são
  escurecidos; sem rede, as camadas vetoriais seguem e um aviso aparece.
- **Correção no backend**: com o `torch` instalado (dependência do time), o adaptador YOLO do
  protótipo se declarava disponível sem pesos carregados e zerava a MMGD do mapa. Agora só fica ativo
  com sessão de inferência; o detector clássico volta a ser usado. `/api/mapa/vision` devolve
  `reference.geo`.
- Testes: protótipo 522 passaram (1 pulado); frontend 45 passaram; `tsc -b`, `oxlint` e build limpos.

## 2026-09-26 — Perfis por subestação: Brasil → UF → subestação, com a visão computacional no mesmo mapa ✅

- **Mapa em três níveis, um Leaflet só** (`src/oraculo/pages/Mapa.tsx`): abre no Brasil (UFs do
  IBGE; só o RJ liberado, o resto "em breve"); clicar na UF voa até ela e mostra as subestações de
  fronteira; clicar de novo na subestação selecionada (ou em "ver amostra de satélite") voa até a
  cena de satélite dela, com os painéis detectados. Os dados da UF são pedidos na abertura (~18 s).
- **Visão computacional na mesma aba**: detalhe da subestação com o bloco "Visão computacional na
  amostra" (detector, ladrilhos, brutas → mantidas, duplicatas, área calibrada/bruta, P/R/F1/IoU);
  tabela de detecções sincronizada com o mapa; no fim da tela, o banco de ensaio do detector
  (`PainelVisao` exportado de `Visao.tsx`, sem a cena de referência).
- **Mapa da tela Visão computacional melhorado**: zoom pela roda, "cena"/"entorno", clicar numa
  detecção mostra os atributos, tabela das detecções sincronizada, legenda sobre o mapa, liga/desliga
  dos contornos; nomes dos chips sem ambiguidade ("vista padrão" × "contornos das detecções").
- **DRY**: `src/oraculo/CenaSatelite.tsx` reúne a cena (camada, controles, legenda, tabela, detalhe)
  que antes existia copiada em `Mapa.tsx` e `Visao.tsx`.
- **Correções no `MapaOsm`**: enquadramento inicial refeito depois do `invalidateSize`; `fitBounds`
  sem animação e voo só com a página visível (com a aba oculta o `requestAnimationFrame` pausa e o
  mapa ficava parado no meio); `.osm-mapa` com `isolation: isolate` (o Leaflet passava por cima do
  header sticky ao rolar); slot `sobreposicao` para a legenda.
- Testes: frontend 45 passaram; `tsc -b`, `oxlint` e build limpos. Conferido no navegador pelo DOM
  (os três níveis, seleção mapa ↔ tabela, troca de subestação na cena, voltar, seção do detector).

## 2026-09-26 — Limpeza de branches + fontes da tela Validação conferidas antes do run_heavywork ✅

- Branches `claude/eager-gauss-or90gs` e `claude/laughing-feynman-ntqc6y` apagadas (local e GitHub): o código delas já estava na main; o único resto era um commit com dados gerados (fora do git pelo `.gitignore`). `.claude/launch.json` entrou na main com caminhos relativos.
- `run_heavywork.py` completo nesta máquina (ingestão ~24 min, treinos ~16 + ~15 min) falhou só na **publicação**: 4 fontes novas no manifesto (BDGD Light/Enel RJ, malhas do IBGE, da Fase 6) sem grupo em `status_fontes` (`config/publicacao.yaml`).
- Classe de bug eliminada: `download.validar_grupos_fontes` confere `publicacao.yaml` × `fontes_ons.yaml` (fonte sem grupo **e** grupo citando fonte inexistente). Roda no **início** do `run_heavywork.py` (erro em segundos, não após ~70 min) e no teste `test_status_fontes_cobre_todas_as_fontes_declaradas`. Quem declarar fonte nova em `fontes_ons.yaml` precisa, no mesmo commit, dar grupo a ela.

## 2026-09-26 — Fase 6: pipeline da BDGD do RDX migrada para o backend (área piloto RJ) ✅

- **Área piloto: RJ (LIGHT + Enel RJ)**, reaproveitando o `Backend/RDX/` (`config/projeto.yaml`, não é mais provisória). Método em `docs/metodo_espacial.md`.
- **Ingestão**: BDGD 2025 da LIGHT e da Enel RJ (~2,1 GB, portal ArcGIS da ANEEL) e malhas do IBGE (API v3) entram como `arquivos_diretos`. `download.py`: chave do manifesto pelo arquivo de destino (a das URLs `.../data` do ArcGIS não mudava entre edições) e novo download quando a URL muda na config (`precisa_baixar_direto`). `contar_linhas` não conta mais `\n` de binário. Nova opção `--diretos`.
- **Processamento**: tabela `carga_area.csv` (área RJ do ONS). Um só leitor da carga verificada (`_ler_carga_verificada`) serve subsistemas e área. `arquivo_direto()` em `utils/config.py` é o único jeito de achar um arquivo direto.
- **`src/spatial/`** (etapa nova `espacializacao` no `run_heavywork`, ~1 min): `bdgd.py` lê o .gdb dentro do .zip; `areas_influencia.py` monta as 448 áreas de influência das subestações (fecho de trafos, sobreposições, Voronoi nos vazios, classificação e hierarquia do RDX); `mmgd.py` faz o desempate por CEG com o cadastro da ANEEL (1.908,7 MW, dos quais 293,5 MW de lag de sistema rateado por município); `excedentes.py` calcula carga bruta e excedente por subestação de fronteira; `saidas.py` guarda os caminhos.
- **Bugs do RDX que viraram impossíveis**: MMGD só com CEG `GD.` (o RDX somava 2,2 GW de UHE/UTE da UGAT); semente engolida por fecho vizinho; área de influência descartada em silêncio pelo recorte; id com código vazio ("LIGHT:") vira NA; `fillna(0)` que transformava SUB vazio na área "0"; carga e MMGD na mesma subestação de fronteira (antes, Brisamar e Centenário ficavam com geração e sem carga).
- **Publicação**: `excedentes` e `mmgd_densidade` saem reais (`mock: false`) sem mudar o schema. `RECURSOS_MOCK` ficou vazio.
- **Conferência**: os 3 maiores excedentes previstos (Centenário, Influência, Brisamar) estão entre as 9 subestações com fluxo reverso **medido** na BDGD (`docs/reports/alimentadores_fluxo_reverso.csv`).
- **Arquitetura**: `tests/test_estrutura.py` também pega leitura do bruto via `arquivo_direto(` e libera só os 3 módulos espaciais que leem a BDGD.
- Testes: 11 novos em `tests/test_espacial.py` + 1 em `test_download.py`; 137 passam (1 pulado). Ponta a ponta: publicação (execução 6) servida pela API e vista nas telas Excedentes e Mapa Híbrido.
- ⚠️ `src/models/*` importam `src/processing/tabelas.py` só pelas constantes `SAIDA_*`, então este commit força o retreino no próximo `run_heavywork` (~50 min).
- Pendências: fator de correção do satélite (Luiz); contrato das áreas de influência em GeoJSON (Luiz); rótulo "sintético" fixo no Mapa Híbrido (Luiz); fator de geração por área de influência e perfil intradiário.
- Segunda classe de bug (apontada pela sessão da Fase 6): os modelos importavam `src/processing/tabelas.py` só pelos caminhos `SAIDA_*`, e o `codigo_de` puxava o código do processamento para a impressão digital do treino. Qualquer mudança no processamento retreinava carga e curtailment (~50 min), mesmo com tabelas idênticas. Os caminhos foram para `src/processing/saidas.py`, sem lógica e no mesmo padrão de `src/spatial/saidas.py`. Modelos, publicação, etapas e testes leem de lá. O teste `test_modelos_nao_dependem_do_codigo_que_constroi_as_tabelas` impede a volta.

## 2026-09-26 — Fase 6: "manchas" renomeadas para "áreas de influência da subestação" ✅

- Pedido do Tiago: os polígonos por subestação são **áreas de influência da subestação**, não "manchas". A troca vale em código, config, testes e docs da Fase 6.
- Código: `src/spatial/manchas.py` → `areas_influencia.py`, `construir_manchas` → `construir_areas`, `mancha_id` → `area_id`, `mancha_fronteira` → `area_fronteira`, `mancha_mae` → `area_mae`, `top_manchas`/`min_manchas` → `top_areas`/`min_areas` (`config/espacial.yaml`).
- Saídas: `output/areas_influencia_rj.geojson`, `data/processed/mmgd_area_influencia.csv`, `carga_area_influencia_mensal.csv`. "Área de influência" vai por extenso nos nomes para não confundir com `carga_area.csv` (área de carga do ONS).
- Contrato inalterado: nenhum campo dele tinha "mancha". O rótulo e os textos do dashboard são do Luiz (`limitacoes.ts`, mock da densidade).
- `mmgd.py` não importa mais nada de `src/processing/tabelas.py`: o apelido do cadastro da ANEEL vem de `src/processing/saidas.py`, então a espacialização não depende do código do processamento.

- Terceira classe de bug: a ingestão levava ~25 min em **toda** execução. O ONS republica os 2 últimos meses do `coff_*_detail`, e o consolidado (só `id_ons=`, um arquivo por usina com todos os anos) era reescrito inteiro (~80 M linhas) a cada mês rebaixado. `consolidar_id_ons` agora grava em `ano=<AAAA>/id_ons=<id>/` e só refaz os anos dos meses novos; os anos fechados ficam intocados. A troca de pastas é recuperável (`_recuperar_troca`): antes, o `rmtree` + `rename` podia perder o consolidado se o processo morresse no meio. O layout antigo é migrado inteiro uma vez, na próxima execução (~25 min, só dessa vez). Testes: incremental não toca o ano fechado, migração do layout antigo e troca interrompida.
- `run_heavywork.py` completo na main, com a Fase 6: execução 7 publicada e as 8 telas do dashboard respondendo 200 (riscos e previsão seguem mock, conforme `docs/real_vs_mock.md`).

## 2026-09-26 — Mapa das áreas de influência no dashboard + correções achadas na conferência ✅

- Pedido do Tiago: validar a Fase 6 vendo no mapa. **Contrato v4 (aditivo)**: recurso `areas_influencia`, `GET /api/areas-influencia`, GeoJSON das 447 áreas com MMGD e excedente (`docs/schema_changelog.md`). Backend: `src/spatial/camada_mapa.py`. O pico de excedente é calculado uma vez por publicação (`montar.pico_excedentes`) e alimenta a tela Excedentes e o mapa (mesmos números).
- Dashboard: camada "Áreas de influência (MMGD)" (`CamadaAreas.tsx`) com tooltip (nome, subestação mãe, MMGD, lag, excedente), botões "Área piloto"/"Brasil" e contorno laranja nas fronteiras com excedente e tracejado nas satélites delas. O rótulo "(sintético)" da densidade só aparece quando o dado é mock. Mock de 3 áreas reais congeladas.
- **Bugs achados olhando o mapa e tornados impossíveis**:
  - polígono vazio (semente de 10 m apagada pela simplificação para a web) passava no Backend e derrubava a tela: o contrato do Backend agora exige o mesmo do Zod (anel ≥ 4 pontos), e a simplificação nunca apaga uma área;
  - 5 subestações perdiam o próprio ponto para a vizinha (regra do RDX "a primeira da fila leva a sobreposição"): a sobreposição passa a ir para a subestação mais próxima;
  - `buffer(+e).buffer(−e)` zerava áreas de até 482 km²: a limpeza não pode mais encolher uma área;
  - 47 geometrias inválidas na saída: `so_validas` corrige e confere.
- Verificação: pytest 151 ok (1 pulado); dashboard 23 testes, tsc, oxlint e build limpos. O JSON real da API passa no Zod. Conferência numérica e visual no navegador em `docs/metodo_espacial.md` ("Conferência no mapa").
- Para ver: a API em :8000 precisa ser reiniciada (`python main.py`) para ter a rota nova; depois é só abrir o Mapa Híbrido.

## 2026-09-26 — Backend do HackaIA_Oraculo trazido para a branch `feat/backend-sync-oraculo` ✅ (Tiago)

- **Origem**: o `Backend/` deste repositório tinha sido importado do HackaIA_Oraculo no commit `ada0d22` (diff vazio). Os 8 commits posteriores do HackaIA_Oraculo (`ffbfb86..d1edc99`: BDGD em `src/spatial`, áreas de influência, `saidas.py`, ingestão consolidada por ano, relatórios da execução 7, contrato v4) entraram por `git cherry-pick -x`, com autoria e mensagens preservadas, sobre a `feat/merge-prototipo-inicial` (protótipo `oraculo/`, auditoria por visão computacional, e2e).
- **Conflitos resolvidos pela união dos dois lados**: `fontes_ons.yaml` e `publicacao.yaml` (SIGA + malha municipal BR **e** BDGD + malhas do RJ, cada apelido em um grupo), `test_estrutura.py` (módulos espaciais **e** de visão podem ler o bruto), README (tecnologias), FASES (itens da auditoria do Luiz dentro da Fase 6). Relatórios de `docs/reports/`: versão da origem (execução 7), que é a que bate com os dados copiados.
- **Frontend (mínimo do contrato v4)**: `CamadaAreas.tsx`, `types.ts`, `dataSource.ts` e o mock entraram; a camada foi encaixada à mão no `MapaHibrido.tsx` novo do Luiz (toggle "Áreas de influência (MMGD)", botão "Área piloto" junto de Enquadrar/Brasil, legenda). `tsc -b` limpo, vitest 44/44.
- **DRY**: havia dois leitores da carga verificada (`carga_bruta.ler_carga_verificada` e `tabelas._ler_carga_verificada`). Ficou um só, em `carga_bruta.py`, já com a regra carga ≤ 0 → NaN + `carga_global_invalida`. `cadastro.py` lia `mapeamento_subsistema_area.csv` direto (quebrava `test_joins`): agora pede a lista a `joins.codigos_areacarga("area")`.
- **Dados copiados** (não rebaixados) do HackaIA_Oraculo: `data/raw` (4,2 GB, layout novo `ano=/id_ons=`), `data/processed`, `data/modelos`, `_estado_heavywork.json`, `oraculo.db` e `output/contrato.json`. Tudo fora do git (conferido com `git status --ignored`).
- ⚠️ Um `run_heavywork.py --help` rodou o pipeline de verdade (o script não lê argumentos) e foi parado antes do treino: ingestão incremental (SIGA, malha municipal BR, janelas novas da API de carga) e processamento concluíram e ficaram registrados no estado. Os relatórios dessa execução parcial foram descartados. Pelas impressões digitais, o próximo `run_heavywork.py` refaz espacialização, treinos (~50 min), previsões e publicação, porque a carga processada ganhou dados novos.
- Verificação: `pytest tests` 173 ok (8 pulados); API com o banco copiado: rotas do contrato, `/api/areas-influencia` (447 áreas, `mock: false`), `/api/health` do protótipo e `/api-docs` respondem 200. `tests_oraculo`: 670 ok; 22 falham só por `import torch` (WinError 1114 no venv do HackaIA_Oraculo usado aqui), não pelo código.
- Pendências: `cadastro.py` (SIGA, MMGD por município, carga por área) ainda não está ligado em `tabelas.construir`; unificar a ingestão e as subestações do protótipo (`oraculo/ons`, `oraculo/substations`) com `src/ingestion` e `src/spatial`; `run_heavywork.py` sem `--help`/`--dry-run`.

## 2026-09-26 — Perfis por subestação: rede da BDGD no desenho do mapa do RDX (dado real) ✅

- **Motivo**: a cena de satélite do protótipo é sintética (a própria API diz "imagem de demonstração");
  sobre o OSM ela não mostrava nada real. Decisão do Tiago: usar os dados reais da BDGD, com o mapa
  do RDX (`Backend/RDX/main.py`) como base.
- **Nível RJ do mapa** (`src/oraculo/pages/Mapa.tsx` + `src/oraculo/RedeBdgd.tsx`), tudo do recurso
  `areas_influencia` (`mock: false`): áreas de influência com a camada do time (`CamadaAreas`, agora
  com clique e seleção); subestações com os ícones do RDX por classificação (plena, satélite,
  transformadora pura, transporte/manobra), cada classe liga/desliga; hierarquia de alimentação
  mãe → satélite em linha tracejada animada (o AntPath do RDX, em CSS); fundo Mapa × Satélite.
  As subestações de fronteira do ONS (protótipo) continuam como camada.
- **Painel da subestação da BDGD**: distribuidora, classificação, mãe (link), área, MMGD, lag de
  cadastro, fator de correção e excedente previsto; lista das satélites que ela alimenta (links).
  Sem seleção: totais do RJ (447 áreas, 1.908,7 MW de MMGD, 293,5 MW de lag — os mesmos números de
  `docs/metodo_espacial.md`).
- **Saiu** o terceiro nível do mapa (cena sintética da subestação). O bloco de visão computacional
  do detalhe foi rotulado "amostra sintética (demonstração)"; o mapa de `/visao` avisa na legenda.
- **Fundo de satélite**: Esri World Imagery (sem chave, uso com atribuição) no lugar do tile do
  Google do RDX (sem a API oficial fere os termos). `semServicoExterno.test.ts` passou a aceitar
  esse endereço, ainda só em `MapaOsm.tsx`.
- **Lacuna**: o popup do RDX tinha carga instalada por classe de consumidor e sazonalidade de 12
  meses (UCBT/UCMT da BDGD). A pipeline migrada não gera o recorte por classe e o contrato não
  traz esses campos; entrar com eles é mudança de schema (combinar com o Luiz).
- Testes: frontend 45 passaram; `tsc -b` e `oxlint` limpos. Conferido no navegador pelo DOM (447
  áreas, 306 ícones com as classes padrão, 176 ligações, seleção por área/ícone/link, tiles da Esri).

## 2026-09-26 — Visão computacional: detecção em imagem de satélite real ✅

- **Pedido do Tiago**: o mapa de `/visao` deve ser terra real (satélite), não desenho; painéis em
  bounding box; o selecionado, uma borda.
- **Backend** (`oraculo/vision/satelite_real.py` + `GET /api/mapa/vision/real?lat=&lon=&lado_m=`):
  baixa os ladrilhos da Esri World Imagery (zoom 19, ~0,28 m/px no RJ) do quadrado em volta do
  ponto, costura, recorta e roda o MESMO `scan_scene` do protótipo. Cada detecção sai com o polígono
  em lat/lon. Cache em disco dos ladrilhos e do resultado (`data/oraculo_cache/satelite_esri`).
  Proveniência no envelope; aviso explícito: sem verdade fundamental, precisão/revocação não são
  medidas em imagem real (o detector clássico foi calibrado na cena sintética).
- **Tela** (`pages/Visao.tsx`, `CenaSatelite.tsx`): fundo de satélite; "Imagem real" é o padrão
  (clique no mapa analisa outro local); "Imagem sintética (banco de ensaio)" continua num chip.
  Detecção = bounding box só com contorno; selecionada = borda âmbar grossa; o clique na caixa não
  vaza para o mapa.
- Testes: `tests_oraculo/test_satelite_real.py` (GSD, projeção, recorte e georreferência com ladrilho
  falso, sem rede); backend 106 passaram (visão + API + novo); frontend 45; `tsc` e `oxlint` limpos.

## 2026-09-26 — Mapa (/mapa): ícones das subestações da BDGD estáveis no clique e no hover

- `RedeBdgd.tsx`: o marcador tinha `key` que mudava com a seleção, então o clique remontava o
  marcador sob o mouse (o ícone sumia). Agora a chave é estável e o react-leaflet só troca o ícone
  (`setIcon`) e o `zIndexOffset`; `autoPanOnFocus={false}` evita o mapa "pular" quando o clique
  foca o ícone; `tooltipAnchor` põe o tooltip acima do selo em vez de cobri-lo.
- `oraculo.css`: hover sem `transform: scale()` (gerava artefato visual dentro do marcador
  posicionado por `translate3d`); destaque por sombra e sem contorno de foco no clique.

## Deploy na AWS (Workshop Studio) — 2026-09-26

- **No ar:** https://or-b24113735a0b4c8d9d3ac76b44512935.ecs.us-west-2.on.aws (API + dashboard, dados reais do `oraculo.db`;
  conta temporária do workshop: a URL some quando o evento acabar).
- **Arquitetura:** ECS Fargate (modo Express: ALB HTTPS + security groups + autoscaling gerenciados). Autoscaling por
  CPU média (alvo 60%), 1 a 4 tasks (`--min-tasks/--max-tasks`). Um serviço só: a API serve o build do dashboard.
- **Por que não CloudFront / ECR / Lambda:** o papel do participante nega CloudFront, Application Auto Scaling direto,
  push no ECR, security group, EC2 e `PassRole` para Lambda. Só S3, ECS e criar as próprias roles passam (o Deny cobre
  roles `WS*`, `cdk-*`, `*CodeEditor*`). O Express Mode contorna isso com uma role de infraestrutura nossa.
- **Sem ECR:** a task usa a imagem pública `python:3.11-slim` e baixa do S3 o pacote (código + deps Linux + dist) com a
  task role, então novas tasks do autoscaling sobem mesmo depois de as credenciais temporárias expirarem.
- **Como refazer:** `npm run build` no dashboard; depois, de `Backend/`, com as credenciais no ambiente:
  `python deploy/deploy_ecs.py` (idempotente). O `Backend/deploy/Dockerfile` (testado local) serve para contas sem essas
  restrições (ECR + ECS/App Runner).
- **Segredos:** credenciais só em variáveis de ambiente, nunca em arquivo do repositório.

## 2026-09-26 — Ajuda F1: documentação escrita no frontend, com exportação ✅

- **Pedido do Tiago**: a documentação do F1 era fraca e dependia de script Python (Sphinx gerado por
  `build_docs.py` e servido pelo backend em `/docs`, via `/api/docs/status`); sem o build ou sem o
  backend, o quadro ficava vazio. Deve ser escrita no frontend e poder ser exportada.
- **Conteúdo** (`Frontend/oraculo-dashboard/src/oraculo/documentacao/`): 31 páginas em blocos
  TypeScript (`modelo.ts`: parágrafo, lista, tabela, aviso por tom, fórmula, código, com marcação
  inline e links `[[id]]` entre páginas). 5 gerais (o que é, como ler, proveniência, limitações,
  glossário) + uma por tela. Texto revisado do Sphinx e **atualizado** para o estado atual: rede
  real da BDGD no RJ no Perfis por subestação, detecção em satélite real na Visão, página nova da
  Auditoria em 3 camadas e as **8 telas do dashboard do contrato**, que não tinham documentação
  (a partir de `visao_geral_sistema.md`, `real_vs_mock.md` e `metodo_espacial.md`). Patamares,
  faixas horárias, limitações e a lista de telas são lidos de `content/calendario.ts`,
  `content/limitacoes.ts` e `modules.ts` (sem cópia).
- **Painel → página**: o `ajuda` de cada módulo em `modules.ts` é o id da página (as telas do
  contrato ganharam `ajuda`; a Auditoria passou de `visao` para `auditoria`). `moduloDaRota` foi
  para `modules.ts` (usado pela casca e pela ajuda).
- **Quadro F1** (`Ajuda.tsx` só com atalho/foco; `documentacao/QuadroAjuda.tsx` carregado sob
  demanda, para o texto não pesar no bundle inicial: 410 kB → a ajuda é um chunk de 138 kB que só
  desce no primeiro F1): índice por grupo com busca (sem acento, título primeiro), links entre
  páginas, "Abrir a tela", "← esta tela", paginação anterior/próxima, tema claro/escuro. F1 lê a tela
  da URL do navegador: o React Router navega em transição e, logo após navegar, o `pathname` do React
  ainda era o da tela anterior (achado na verificação no navegador).
- **Exportar** (`exportar.tsx`): página ou documentação completa em Markdown, HTML autocontido (o
  mesmo `Renderizador.tsx` da tela, via `renderToStaticMarkup` carregado sob demanda, CSS embutido)
  e Imprimir/PDF (iframe invisível + diálogo de impressão). Download comum em `utils/download.ts`
  (o CSV passou a usá-lo).
- **Testes** (`documentacao.test.ts`): toda tela do menu tem página; toda página de tela está ligada a
  uma tela; todo `[[link]]` existe; tabelas bem formadas; parser inline; busca; Markdown com âncoras
  válidas; HTML com todas as páginas e sem recurso externo; `Ajuda.tsx` sem `docs/status`/iframe.
  Frontend 59 testes, `tsc` limpo; verificado no navegador (F1, busca, links, abrir a tela, menu
  exportar, HTML gerado, tema claro, layout estreito).
- **Não mudou**: o Sphinx (`docs/oraculo/documentacao_sphinx`) e a rota `/api/docs/status` seguem
  servindo só a interface legada (`/legado`); o dashboard não os usa mais.

## Deploy automático na AWS (GitHub Actions) — 2026-09-26

- `.github/workflows/deploy-aws.yml`: a cada push na `main` (só se mexer em código/config/Frontend/deploy) faz o build do
  dashboard, roda `Backend/deploy/deploy_ecs.py` e espera o site responder 200. Também roda manualmente
  (Actions > Deploy AWS > Run workflow).
- **Secrets necessários** (Settings > Secrets and variables > Actions): `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`,
  `AWS_SESSION_TOKEN`. No Workshop Studio elas expiram em poucas horas: quando o job falhar em "Validar credenciais AWS",
  atualize os 3 secrets. O site que já está no ar não cai por isso.
- **Dados fora do git** (`oraculo.db`, `output/`, `data/oraculo_cache`): o deploy LOCAL (`python deploy/deploy_ecs.py`, de
  quem tem o banco) os envia ao S3 (`dados/dados.zip`); o CI os baixa de lá. Novos dados na demo = deploy local.
- `deploy_ecs.py`: agora distingue criar de atualizar (describe explícito) e força novo deployment das tasks, porque o pacote
  novo só é baixado quando a task reinicia.

## 2026-09-26 — Protótipo sem dado inventado: clima real, horizonte do risco, Triangulação e Mapa reais ✅

Auditoria das abas do dashboard (o que era real × sintético) seguida das correções no pacote `Backend/oraculo`:

- **Clima dos modelos** (Despacho preditivo, Risco e excedentes, Validação do método): o grupo de variáveis
  `clima` usava temperatura **sintética** (`synthetic_weather`, ruído aleatório) sem avisar na tela. Agora vem da
  reanálise ERA5 (Open-Meteo, dias recentes pela análise operacional do ECMWF), média das capitais de cada
  subsistema ponderada pela população (`WEATHER_POINTS` em `oraculo/config.py`; `tempo/clima.py::weather_for_area`).
  Entra na proveniência. Sem rede e sem cache o grupo sai do modelo — o proxy sintético foi removido.
- **Risco e excedentes**: o seletor de horizonte só trocava o rótulo (o modelo era calculado uma vez). Agora é um
  modelo por horizonte: a memória de restrição termina `config.HORIZONS[h]` horas antes do alvo, mais o estado
  das 3 últimas horas conhecidas na emissão. AUC mediana 0,94 (30 min) × 0,90 (D+1), ordem das áreas muda.
- **Triangulação**: as unidades eram aleatórias (`demo_units`). Agora são os **193 229 empreendimentos reais** de
  MMGD da LIGHT e da Enel RJ (BDGD 2025 × cadastro ANEEL, `src/spatial/mmgd.py`), gravados pela espacialização em
  `data/processed/mmgd_empreendimentos.parquet` (`por_empreendimento`). A camada 1 (satélite) ainda não cobre a
  área: `detected=None` ("não observado", nunca "não detectado") e a matriz vira BDGD × ANEEL, com a classe nova
  `cadastral`. Resultado: 24 704 empreendimentos em defasagem de sistema, 30 só na BDGD; fator de correção 1,16
  (Enel RJ) e 1,20 (LIGHT). O gerador só roda no modo demo.
- **Mapa · perfis por subestação** (e o cartão CLM por SE): composição e nível de MMGD vinham de ortoimagem
  **sintética**. Agora: composição pela energia faturada (BDGD MT/AT + SAMP BT) das SEDs associadas pela
  correlação fronteira T–D; MMGD pelo cadastro ANEEL nessas SEDs; nível = (MMGD ÷ carga média da SE) relativo à
  mesma razão no SIN (0,54). SE sem SED associada = "Sem dado". A amostra sintética fica só como demonstração do
  detector, rotulada (`mapper.with_frontier`, `service_mapa._real_profile`).
- Ajuda F1 (operação, mapa, triangulação) e texto da Fronteira atualizados. Testes novos em `tests_oraculo`
  (clima, horizonte, desempate sem satélite, perfil real) e `tests/test_espacial.py`. `tests_oraculo`: 538 ok;
  `tests/`: as 6 falhas de `test_modelos_*` (access violation do LightGBM) e o `test_tft` (sem torch) já
  existiam no HEAD, sem relação com esta tarefa.

Continua pendente (não dá para resolver só com código): Visão · auditoria 3 camadas (sem imagem da área piloto nem
`best.pt`), métricas do detector só no banco sintético, Projeção ENE demora >8 min no primeiro acesso.

## Conciliação de MMGD por transformador: ANEEL × BDGD × visão computacional — 2026-09-27

- **O quê:** capacidade de MMGD por transformador MT/BT no Rio (LIGHT) e em Niterói (Enel RJ). BDGD 2025 localiza,
  ANEEL mede a defasagem desde a data-base (31/12/2025), visão computacional aloca onde há imagem posterior à base.
  Método e medições em `docs/metodo_conciliacao.md`; números em `docs/reports/relatorio_conciliacao.md`.
- **Código:** `src/spatial/areas_trafo.py` (área atendida = Voronoi dos UNTRMT, 57.878 trafos), `pipeline/paineis_por_transformador.py`
  (lógica do Hackaton-Radix com ladrilhos Esri z19 + data da imagem por ladrilho), `src/spatial/conciliacao.py` (etapas 1–7,
  checagens), `src/spatial/relatorio_conciliacao.py`, config em `config/conciliacao.yaml`.
- **Saídas:** `data/processed/capacidade_mmgd_trafo.parquet`, `defasagem_municipio.parquet`, `capacidade_aneel_municipio.parquet`,
  `areas_atendidas_trafo.parquet`; camada `output/conciliacao/camada_mmgd_trafo.json` em `GET /api/conciliacao/mmgd-trafo`
  (formato do heatmap, fora do contrato) e botão **MMGD por transformador** no Mapa Híbrido.
- **Resultado:** cobertura BDGD/ANEEL 0,93 nos dois municípios; defasagem 27,5 MW (Rio) e 8,3 MW (Niterói), conservada.
  Só Icaraí tem imagem (28/01/2026) posterior à BDGD: a visão aloca lá; no Rio (imagem de 05 e 12/2025) todo excesso é resíduo.
- **Limitação principal:** o `best.pt` (treinado em Google z20) acha ~1 em 6 painéis na Esri z19 (medido: 11/60 a 10 m).
  O Google, usado na varredura anterior, não publica data de imagem. Próximo passo: fine-tuning em Esri.
- **Testes:** `tests/test_conciliacao.py` (20: etapas 4, 6 e 7, conservação, nada negativo, nada após data_ref);
  suíte 210 ok (o `test_tft.py` não coleta neste .venv: falta `pytorch_forecasting`, problema de ambiente anterior).

## 2026-09-27 — Classes de consumo com dado medido: perfis ANEEL CTR + composição BDGD/SAMP ✅

A página **Classes de consumo** (`/classes`) mostrava perfis horários **desenhados à mão** (`CANONICAL` em
`oraculo/profiles/classes.py`) e adivinhava a composição de cada subsistema encaixando a curva do ONS neles (NNLS).
O perfil "rural" (bombeamento de madrugada) tinha correlação **negativa** (−0,38) com o rural medido, e o ajuste
dava 35 % de rural ao Sudeste (energia faturada no RJ: 0,4 %). Agora tudo na página é dado real:

- **Forma horária por classe**: ANEEL *CTR – Curva de Carga Consumidor Tipo* (campanhas de medição das revisões
  tarifárias; 15 min; dia útil/sábado/domingo). Fonte nova `aneel_ctr_consumidor_tipo` em `config/fontes_ons.yaml`
  (~41 MB, grupo novo em `publicacao.yaml`). Tabela `perfis_classe` no processamento
  (`src/processing/perfis_classe.py` → `data/processed/perfis_classe_ctr.csv`): processo tarifário mais recente de
  cada distribuidora, cada curva em p.u. da própria média de dia útil, média simples (o arquivo não traz peso).
  3.675 curvas, 62 distribuidoras, 2016–2026.
- **Classes pelos subgrupos que a ANEEL mede** (mudança de chaves do JSON aprovada pelo Tiago): residencial (B1),
  rural (B2), comercial/serviços e demais BT (B3), média tensão (A4, AS), alta tensão (A1–A3a). Comercial × industrial
  deixou de existir porque o B3 junta os dois. Parâmetros em `config/perfis_classe.yaml`.
- **Composição por subsistema**: energia faturada real da base da Fronteira T–D (SAMP BT + BDGD MT/AT por SED; SED
  com UCs de MT e AT conta como MT e a fração é mostrada). Reaproveita a correlação existente; nada foi baixado de
  novo para isso. O `Backend/RDX/perfis_consumo.csv` foi avaliado e descartado: cobre só o RJ e não separa tensão.
- **Validação contra o ONS** (`oraculo/profiles/medidos.py`, `service_mapa.classes_payload`): curva montada
  (energia × forma, com o peso do dia útil corrigido pelo fim de semana medido) × **carga global** (o CTR mede
  consumo; a supervisionada desconta a MMGD). R²: S 0,93, SE 0,77 (bom). N e NE não validam (R² < 0) e a tela diz
  por quê: a distribuição cobre só 39 % (N) e 62 % (NE) da energia do ONS; o resto é rede básica/eletrointensivos.
- Rota com proveniência própria (ONS + ANEEL/IBGE da fronteira + ANEEL CTR). Sem a tabela ou sem a base da
  fronteira, a página abre com aviso; nunca troca por outra fonte. Limiares de telhado ficam rotulados PREMISSA.
- Interface legada (`web_legado`): a view de classes virou um encaminhamento para o dashboard (sem duas cópias da
  tela). Ajuda F1 e Sphinx (`classes-de-consumo.rst`, `referencia/profiles.rst`) reescritas.
- Testes: `tests/test_perfis_classe.py` (construção a partir do CTR), `tests_oraculo/test_perfis_medidos.py`
  (composição e montagem) e `test_mapa.py` atualizado. `tests_oraculo`: 545 ok; `test_estrutura`, `test_download`,
  `test_heavywork`: ok. Sem teste de vazamento temporal: a tabela é descritiva, sem treino nem previsão.

Pendente: o prior regional do Mapa · perfis por subestação (`service_mapa._regional_mix`) ainda usa o NNLS sobre os
perfis estilizados de `classes.py`; os perfis do CTR são nacionais (o arquivo não traz subsistema).
