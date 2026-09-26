# O.R.A.C.U.L.O.

> Previsão de carga e de risco de curtailment para o SIN, usando dados do ONS e a MMGD vista pela rede de distribuição.

## Demo

- **Link da demo:** TODO (Luiz)

## Tecnologias utilizadas

- Linguagem: Python 3.11+ (dados e modelos), TypeScript (dashboard)
- Framework(s): pandas, DuckDB, LightGBM 4.6 (previsão de carga quantílica e classificador de curtailment, com SHAP exato), scikit-learn (métricas e API sklearn do LightGBM), pytorch-forecasting, geopandas + pyogrio/GDAL (BDGD lida direto do .zip) + shapely 2.1, pyproj (geometria da auditoria), holidays, FastAPI + Uvicorn (API), SQLAlchemy 2 + Alembic (banco); visão computacional opcional: Ultralytics YOLOv8-seg (painéis solares) e Google Earth Engine
- Banco de dados: Parquet particionado + DuckDB (dados de trabalho); SQLite via SQLAlchemy no Backend (compatível com PostgreSQL)
- APIs / Serviços externos: dados.ons.org.br (CKAN), API de carga do ONS (apicarga.ons.org.br), MCP oficial do ONS, ANEEL (cadastro de MMGD, SIGA e BDGD LIGHT/Enel RJ via portal ArcGIS), IBGE (API de malhas v3), ERA5 (Copernicus CDS, opcional), Google Earth Engine (imagem de satélite, opcional), Open Buildings, OSM
- Dashboard: React 19 + Vite + TypeScript + Tailwind CSS v4 + React Router + Recharts + react-leaflet + Zod + Vitest, fontes IBM Plex Sans e JetBrains Mono empacotadas (`Frontend/oraculo-dashboard`); o mapa funciona offline (sem tiles externos)

## Como rodar o projeto

```bash
# Clone o repositório
git clone https://github.com/DanielGudin/HackaIA_Oraculo.git
cd HackaIA_Oraculo/Backend      # todo o Python (código, dados, config, testes) fica em Backend/

# Ambiente e dependências
python -m venv .venv
.venv\Scripts\activate          # Windows (Linux/macOS: source .venv/bin/activate)
pip install -e ".[dev]"

# 1. Trabalho pesado: baixa das fontes só o que falta ou foi republicado, processa as tabelas,
#    monta as áreas de influência das subestações e a MMGD de cada uma (BDGD, área piloto RJ), treina os modelos (carga e curtailment),
#    gera as previsões fora da amostra e o backtest (docs/reports/) e publica no banco.
#    Sem argumentos: a config fica em config/heavywork.yaml. Pode rodar a qualquer momento:
#    pula o que está em dia. Primeira vez: ~3,7 GB e ~35 min de download + ~25 min de treino.
python run_heavywork.py

# 2. Serviço web: API só de leitura sobre o banco publicado no passo 1
#    http://127.0.0.1:8000/api/carga/snapshot ... | documentação das rotas em /api-docs
python main.py

# 3. Explicabilidade: regenera os alertas mockados do dashboard
python -m pipeline.gerar_alertas_mock
# (modelo real com SHAP: pip install -e ".[explicabilidade]")

# 4. Auditoria da MMGD em 3 camadas (satélite + BDGD + cadastro ANEEL) e fator de correção
python -m pipeline.auditoria_camada1 --mock        # sem imagem ainda: painéis sintéticos (is_mock)
python -m pipeline.auditoria_camadas_2_3 --mock    # desempate Lag de Sistema × Não homologada
# com modelo e imagens reais: pip install -e ".[visao]" e então
#   python -m pipeline.validar_modelo --imagens <pasta> --modelo <arquivo.pt>
#   python -m pipeline.download_satelite --bbox LON_MIN LAT_MIN LON_MAX LAT_MAX

# 5. Teste ponta a ponta (bases → modelos → contrato → dashboard → alerta): diz o que é real e
#    o que é mock lendo os próprios dados; relatório em docs/reports/teste_e2e.md
python -m pipeline.teste_e2e

# 6. Testes
pytest

# Dashboard (em outro terminal, a partir da raiz do repositório)
cd Frontend/oraculo-dashboard
npm install
npm run dev       # http://localhost:5173 — dados da API do passo 2 (o Vite repassa /api ao Backend)
npm run dev:mock  # alternativa sem Backend: lê os JSONs mockados (selo "DADOS MOCK" no topo)
npm test          # testes do contrato de dados

# Demo com um servidor só: com o build, `python main.py` também serve o dashboard em
# http://127.0.0.1:8000/ (caminho do build em Backend/config/api.yaml)
npm run build
```

## Protótipo O.R.A.C.U.L.O. consolidado (Equipe 24 — LINKFY)

O protótipo (antes em `02-PROTOTIPO`, HTML/JS puro + Starlette) foi trazido para este repositório,
com as telas reescritas em React dentro do mesmo dashboard. Um servidor só (`python main.py`)
serve a API do contrato, a API do protótipo, a documentação Sphinx (tecla F1) e o dashboard.

| Onde | O quê |
|---|---|
| `Backend/oraculo/` | pacote do protótipo: API (`/api/health`, `/api/mapa/...`, `/api/clm/...`, `/api/fronteira/...`, `/api/bess/...`, `/api/ene/...`, `/api/tempo/...`), modelos, ingestão ONS/ANEEL/IBGE/Open-Meteo, visão computacional clássica + adaptador YOLO |
| `Backend/oraculo/web_legado/` | interface original em HTML/JS, servida em `/legado` (referência) |
| `Backend/tests_oraculo/` | suíte do protótipo: `python -m pytest tests_oraculo` (em `Backend/`) |
| `Backend/data/oraculo_cache/` | cache de trabalho das fontes (fora do git; reconstruído sob demanda) |
| `Backend/src/api/auditoria.py` | `/api/auditoria/mmgd`: leitura da auditoria em 3 camadas (visão computacional do time) |
| `Frontend/oraculo-dashboard/src/oraculo/` | telas React do protótipo (grupos Operação, Análise, Mapa Inteligente, Visão computacional, Fronteira T–D, Investimento, Confiança), gráficos SVG, ajuda F1 |
| `docs/oraculo/` | documentação Sphinx (`documentacao_sphinx/`, `python build_docs.py`), especificações e apresentações |

Visão computacional com as duas soluções: **Detector por subestação** (protótipo, `/visao`) e
**Auditoria MMGD · 3 camadas** (pipeline do time, `/auditoria-mmgd`). Swagger da API em `/api-docs`.

## Pré-requisitos

- Python 3.11 ou 3.12
- Node.js 20.19+ ou 22.12+ e npm (dashboard)
- ~7 GB livres em disco para `Backend/data/raw` (a BDGD fica zipada, ~2,1 GB) e ~8 GB de RAM (limites do DuckDB em `Backend/config/fontes_ons.yaml`)
- Opcional: credencial do Copernicus CDS (`~/.cdsapirc`) para o ERA5 (`era5_disponivel` em `Backend/config/projeto.yaml`)
- Opcional (visão computacional): extra `pip install -e ".[visao]"` (~300 MB com o torch CPU), pesos do YOLO (`modelo.caminho` em `Backend/config/visao.yaml`, fora do git) e, para baixar imagem, `earthengine authenticate` + `satelite.gee_projeto`
- Documentação detalhada — comece pela visão geral do sistema (de onde vêm os dados, como são usados, modelos, API e telas) e siga para catálogo de séries, inventário do portal ONS, MCP, schema do contrato, real vs. mock e status: [`docs/visao_geral_sistema.md`](./docs/visao_geral_sistema.md)

## Licença

Este projeto está sob a licença MIT — veja o arquivo [LICENSE](./LICENSE) para mais detalhes.
