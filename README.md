# O.R.A.C.U.L.O.

> Previsão de carga e de risco de curtailment para o SIN, usando dados do ONS e a MMGD vista pela rede de distribuição.

## Demo

- **Link da demo:** TODO (Luiz)

## Tecnologias utilizadas

- Linguagem: Python 3.11+ (dados e modelos), TypeScript (dashboard)
- Framework(s): pandas, DuckDB, LightGBM 4.6 (previsão de carga quantílica e classificador de curtailment, com SHAP exato), scikit-learn (métricas e API sklearn do LightGBM), pytorch-forecasting, geopandas, holidays, FastAPI + Uvicorn (API), SQLAlchemy 2 + Alembic (banco)
- Banco de dados: Parquet particionado + DuckDB (dados de trabalho); SQLite via SQLAlchemy no Backend (compatível com PostgreSQL)
- APIs / Serviços externos: dados.ons.org.br (CKAN), API de carga do ONS (apicarga.ons.org.br), MCP oficial do ONS, ANEEL (MMGD e BDGD), ERA5 (Copernicus CDS, opcional), Open Buildings, IBGE, OSM
- Dashboard: React 19 + Vite + TypeScript + Tailwind CSS v4 + React Router + Recharts + react-leaflet + Zod + Vitest (`Frontend/oraculo-dashboard`)

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
#    treina os modelos (carga e curtailment), gera as previsões fora da amostra e o backtest
#    (docs/reports/) e publica no banco. Sem argumentos: a config fica em config/heavywork.yaml.
#    Pode rodar a qualquer momento: pula o que está em dia.
#    Primeira vez: ~1,6 GB e ~30 min de download + ~25 min de treino e previsão.
python run_heavywork.py

# 2. Serviço web: API só de leitura sobre o banco publicado no passo 1
#    http://127.0.0.1:8000/api/carga/snapshot ... | documentação das rotas em /docs
python main.py

# 3. Explicabilidade: regenera os alertas mockados do dashboard
python -m pipeline.gerar_alertas_mock
# (modelo real com SHAP: pip install -e ".[explicabilidade]")

# 4. Testes
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

## Pré-requisitos

- Python 3.11 ou 3.12
- Node.js 20.19+ ou 22.12+ e npm (dashboard)
- ~5 GB livres em disco para `Backend/data/raw` e ~8 GB de RAM (limites do DuckDB em `Backend/config/fontes_ons.yaml`)
- Opcional: credencial do Copernicus CDS (`~/.cdsapirc`) para o ERA5 (`era5_disponivel` em `Backend/config/projeto.yaml`)
- Documentação detalhada (catálogo de séries, inventário do portal ONS, MCP, schema do contrato, real vs. mock, status): [`docs/`](./docs)

## Licença

Este projeto está sob a licença MIT — veja o arquivo [LICENSE](./LICENSE) para mais detalhes.
