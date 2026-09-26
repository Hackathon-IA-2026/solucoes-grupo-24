# Backend: como funciona e como rodar

Arquitetura completa em `docs/Oraculo_planejamento.md` §13.1. Duas partes, ligadas só pelo banco:

```
Backend/run_heavywork.py                                   Backend/main.py
ingestão → processamento → treino → previsão → publicação ──► banco ──► API FastAPI ──► dashboard
```

Todos os comandos rodam de dentro de `Backend/`, com o `.venv` ativo.

## 1. Trabalho pesado: `python run_heavywork.py`

Sem argumentos. Configuração em `config/heavywork.yaml` (liga/desliga etapas, `forcar`). Cada etapa é pulada quando as entradas (dados + código + config) não mudaram desde a última execução bem-sucedida.

| Etapa | Módulo | O que faz |
|---|---|---|
| ingestão | `src/ingestion/download.py` | baixa só o que falta ou foi republicado (ONS, ANEEL) |
| processamento | `src/processing/` | `data/processed/`: calendário, carga supervisionada, rótulos de curtailment, capacidade de MMGD |
| treino_carga | `src/models/carga.py` | baselines (persistência, sazonal-naïve, climatologia) + LightGBM quantílico da carga supervisionada, por série (SE, S, NE, N, SIN) e horizonte (30 min, 3 h, D+1), banda P10–P90 calibrada por conformal (CQR); split cronológico de `config/modelos_carga.yaml`; modelos em `data/modelos/carga/` |
| treino_curtailment | `src/models/curtailment.py` | classificador LightGBM de corte por razão (ENE, CNF) + regressor de MW cortados, por horizonte, para ~290 usinas/conjuntos; `config/modelos_curtailment.yaml`; modelos em `data/modelos/curtailment/` |
| previsao_carga | `src/models/carga.py`, `src/models/relatorio_carga.py` | previsões fora da amostra de todas as semi-horas desde o início do teste (modo replay) + `docs/reports/baseline_carga.md` |
| previsao_curtailment | `src/models/curtailment.py`, `src/models/relatorio_curtailment.py` | risco fora da amostra de cada usina e semi-hora desde o início do teste + `docs/reports/classificador_curtailment.md` |
| publicação | `src/publicacao/montar.py` | monta os 7 recursos do contrato (tabela `RECURSOS`), grava `output/contrato.json`, aplica as migrations e grava no banco |

## 2. Serviço web: `python main.py`

API só de leitura em `http://127.0.0.1:8000` (host, porta, prefixo e CORS em `config/api.yaml`). Documentação interativa em `/docs`. Rotas e formato: `docs/schema_contrato.md`.

- Serve sempre a **execução mais recente** publicada.
- Banco inexistente, em versão antiga ou sem publicação: **503**, com a instrução de rodar `python run_heavywork.py`.
- Execução publicada com um contrato anterior (campo novo ausente ou recurso que ela não tem): **503** com a mesma instrução, nunca um 500 de validação — cada resposta é revalidada contra o contrato atual.
- Rotas **geradas** da tabela `RECURSOS` (`src/contrato/modelos.py`): acrescentar recurso lá cria a rota; `tests/test_contrato.py` confere que cada rota existe em `ENDPOINTS` do `dataSource.ts`.
- Não importa nada da parte pesada (teste `test_servico_web_nao_carrega_a_parte_pesada`).

Dashboard ligado na API (2026-09-26):
- **Padrão do dashboard = API.** `npm run dev` já busca em `/api`, e o Vite repassa ao Backend; host, porta e prefixo do proxy são **lidos de `config/api.yaml`** (`vite.config.ts`), então mudar a porta aqui não quebra o dashboard. Mock só com `npm run dev:mock`.
- **Um servidor só para a demo:** com `npm run build`, `python main.py` também serve o `dist/` em `/` (caminho em `dashboard_dist` do `config/api.yaml`). Rotas do React Router devolvem o `index.html`; caminho inexistente sob `/api` é 404 JSON, nunca HTML (teste `test_api_serve_o_build_do_dashboard_sem_engolir_a_api`).
- **`/api/saude` tipada** (`Saude` em `src/api/app.py`, espelho de `SaudeApiSchema` no `types.ts`, fora do contrato dos recursos): alimenta a pill "DADOS DE dd/mm HH:MM" da topbar, que mostra o "agora" do replay servido.
- Erros da API chegam à tela com o `detail` do FastAPI (ex.: o 503 diz para rodar `python run_heavywork.py`); Backend desligado mostra "API INDISPONÍVEL" e a instrução de subir o `main.py`.

## 3. Banco de dados

- URL: variável `DATABASE_URL` (ex.: PostgreSQL); sem ela, SQLite em `Backend/oraculo.db` (caminho absoluto, fora do git). Factory única em `src/db/sessao.py`.
- Tabelas (`src/db/tabelas.py`): `execucao` (uma por publicação: quando, qual "agora") e `recurso` (um item de um recurso do contrato, JSON já validado). Instantes sempre em UTC com fuso (`UtcDateTime`).
- Migrations: Alembic em `migrations/`. A publicação aplica sozinha (`alembic upgrade head`). Mudou `src/db/tabelas.py`? Rode `alembic revision --autogenerate -m "..."`; o teste `test_migrations_batem_com_os_modelos` falha se esquecer.
- Escrita só por `src/db/repositorio.py::publicar`: valida cada item pelo contrato e grava todos os recursos de `RECURSOS` numa transação só (nunca uma publicação pela metade; id repetido é recusado pelo banco).

## 4. Garantias contra vazamento temporal (modelos)

- **Features**: toda defasagem passa por `src/features/defasagens.py`, que recusa olhar antes da emissão (alvo − horizonte). Testes perturbam todo o "futuro" e exigem features idênticas (`tests/test_features_carga.py`, `tests/test_modelos_curtailment.py`).
- **Split**: único, em `src/models/split.py` (treino por alvo até `fim_treino`; teste por emissão a partir de `inicio_teste`; recusa datas fora de ordem). Um teste treina duas vezes, mudando todo o período de teste, e exige modelos idênticos.
- **Previsões**: a etapa de previsão só emite previsões fora da amostra e recusa modelo salvo com outro split. A publicação escolhe o "agora" nessa tabela e recusa ponto emitido depois dele.
- **Impressão digital das etapas**: o código de cada etapa é o módulo e tudo o que ele importa do projeto (`src/utils/impressao.py::codigo_de`, lido dos `import`): nenhuma lista de dependências escrita à mão.
