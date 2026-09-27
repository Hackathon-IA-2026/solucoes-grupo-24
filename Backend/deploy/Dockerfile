# O.R.A.C.U.L.O. — imagem única: API FastAPI + dashboard (build do Vite servido pela própria API).
#
# Build (a partir da RAIZ do repositório — o contexto precisa enxergar Backend/, Frontend/ e docs/):
#   docker build -f Backend/deploy/Dockerfile -t oraculo .
# Rodar local:  docker run -p 8000:8000 oraculo   ->  http://localhost:8000
#
# Decisão: um serviço só (mesma origem => sem CORS, um deploy). O layout dentro da imagem
# espelha o do repositório (/app/Backend, /app/Frontend, /app/docs) porque o código resolve
# caminhos relativos a esse layout (src/utils/paths.py, dashboard_dist em config/api.yaml).

# ---------- estágio 1: build do dashboard ----------
FROM node:22-slim AS front
WORKDIR /app/Frontend/oraculo-dashboard
COPY Frontend/oraculo-dashboard/package.json Frontend/oraculo-dashboard/package-lock.json ./
RUN npm ci
# O vite.config.ts LÊ Backend/config/{api,processamento}.yaml em tempo de build
# (fonte única dos patamares e do prefixo da API), então esses yamls entram neste estágio.
COPY Backend/config /app/Backend/config
COPY Frontend/oraculo-dashboard ./
RUN npm run build

# ---------- estágio 2: runtime da API ----------
FROM python:3.11-slim AS runtime
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
# Cache do protótipo vai na imagem (data/oraculo_cache): vale 30 dias, é um retrato publicado a cada build.
ENV ORACULO_CACHE_TTL=2592000
WORKDIR /app/Backend

COPY Backend/deploy/requirements-api.txt /tmp/requirements-api.txt
RUN pip install --no-cache-dir -r /tmp/requirements-api.txt

# Código, config, migrations e o banco publicado (oraculo.db é só leitura; vem do
# run_heavywork.py e está no .gitignore, então o build é feito a partir da máquina que o tem).
COPY Backend/main.py Backend/alembic.ini ./
COPY Backend/config ./config
COPY Backend/migrations ./migrations
COPY Backend/src ./src
COPY Backend/oraculo ./oraculo
COPY Backend/oraculo.db ./oraculo.db
COPY Backend/output ./output
# Cache real do protótipo (dados do ONS já baixados): a demo não depende da rede do ONS.
COPY Backend/data/oraculo_cache ./data/oraculo_cache
# Tabelas processadas que a API lê (mesma lista de DADOS do deploy_ecs.py): Triangulação (BDGD x
# ANEEL, oraculo/api/service.py) e formas horárias medidas das Classes de consumo (ANEEL CTR).
COPY Backend/data/processed/mmgd_empreendimentos.parquet ./data/processed/mmgd_empreendimentos.parquet
COPY Backend/data/processed/perfis_classe_ctr.csv ./data/processed/perfis_classe_ctr.csv
COPY --from=front /app/Frontend/oraculo-dashboard/dist /app/Frontend/oraculo-dashboard/dist

EXPOSE 8000
# 0.0.0.0 pela linha de comando (e não em config/api.yaml, que fica 127.0.0.1 no desenvolvimento):
# dentro do container 127.0.0.1 não recebe tráfego de fora.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
