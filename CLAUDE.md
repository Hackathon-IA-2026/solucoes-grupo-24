# O.R.A.C.U.L.O. — Hackathon IA COPPE/UFRJ 2026

## Contexto

Solução para dois desafios do ONS:
- **Desafio 1 — curtailment:** prever risco e montante de corte de geração eólica e solar (constrained-off), com foco nas razões ENE e CNF conforme o dicionário de dados do ONS.
- **Desafio 2 — demanda:** prever a carga supervisionada (carga global menos MMGD estimada) com quantis.


-Infraestrutura
-Banco de dados: SQLite (Local) porém compatível com PostgreeSQL via sqlalchemy (como descrito nas # Regras de Compatibilidade de Banco de Dados)
-Backend: FastAPI(python)


Tese central: o gap TSO–DSO. A MMGD (micro e minigeração distribuída) é pouco visível ao ONS. Usamos a BDGD da distribuidora + imagens de satélite para estimar capacidade instalada por "mancha" de rede e corrigir as estimativas.



## Estrutura do repositório

Na raiz do repositório só existem três pastas (garantido por `Backend/tests/test_estrutura.py`):

```
Backend/    -> todo o Python: código, dados, config, notebooks, testes e o banco SQLite
Frontend/   -> todo o frontend
docs/       -> toda a documentação e relatórios (relatórios em docs/reports/)
```

Dentro de `Backend/` (raiz de import do Python; comandos rodam daqui: `python -m src...`):


Stack: Python, pandas, pyarrow, duckdb, geopandas, matplotlib, seaborn, lightgbm, pytorch-forecasting (ou neuralforecast) entre outros que forem necessários

## Regras do projeto

- Antes de começar a fazer qualquer alteração deve-se checar se existe atualizações da branch atual, se não tiver alterações conflitantes atualize com pull para ter a versão mais atual do time.
- **Nunca inventar dados.** não use dados mocados!
- **Split sempre cronológico.** Nunca aleatório. Toda etapa de modelagem precisa de um teste que prove ausência de vazamento temporal.
- **Nunca cruzar** recortes por subsistema e por área operativa sem `Backend/data/processed/mapeamento_subsistema_area.csv`.
- Bases tm de constrained-off: chave composta = fonte + id.
- Carga supervisionada = carga global − MMGD estimada, resolução 30 min, por subsistema.
- Feriados tratados como domingo.
- Patamares: ponta noturna 19–22h; mínima diurna 09–16h.
- Faixas horárias de curtailment: 00–07 | 07–09 e 16–18 | 09–16 | 18–24.
- Dados grandes em Parquet particionado. `Backend/data/raw` no `.gitignore`.
- Parâmetros (pesos da loss, datas de corte, caminhos) em `Backend/config/*.yaml`, nunca hardcoded.
- Antes de downloads longos ou treinos acima de ~10 min: avise e estime o tempo.
- Commits pequenos e descritivos. Ao fim de cada tarefa, registre o andamento em `docs/STATUS.md`.
- Após fazer commit faça imediatamente push para enviar logo as alterações para o time.
- Respeite os principios DRY! evite ao máximo ter mais de uma cópia do mesmo código!
- faça comentários dentro do código que explique cada parte do código inclusive inserindo decisões...
- Após terminar a tarefa faça commit no repositório descrevendo tudo que foi alterado e tudo que foi feito! e após terminar o commit faça push origin para subir as alterações para o GitHub imediatamente. (A menos que você esteja trabalhando para ligia).

## README (modelo da competição)

- O `README.md` da raiz segue **exatamente** o modelo em `docs/modelo_readme_competicao.md`: mesmas seções, mesma ordem, mesmos títulos. Não crie seções extras nele.
- Documentação detalhada (schema, status, real vs. mock, métodos) vai para `docs/`. No README, no máximo um link para ela dentro das seções existentes.
- O README é da equipe: a parte do dashboard e do link da demo é do Luiz. Não invente o que não está no repositório — deixe `TODO (Luiz)` e me avise.
- Sempre que mudar dependência, comando de execução ou pré-requisito, atualize as seções "Tecnologias utilizadas", "Como rodar o projeto" e "Pré-requisitos".

## Contrato

Schema em `docs/schema_contrato.json`, descrito em `docs/schema_contrato.md`. **Qualquer mudança no schema: pare e pergunte** —## Prioridade

- Nunca cortar: catálogo de séries, baselines, TFT com perda assimétrica, classificador ENE, JSON do contrato.
- Cortável: classificador CNF, rascunho das tools MCP.



# Regras de Compatibilidade de Banco de Dados

## Stack Obrigatória

- **ORM / Query Builder:** SQLAlchemy 2.x (Core ou ORM). Nunca usar `sqlite3`, `psycopg2` ou qualquer driver DB-API diretamente.
- **Migrations:** Alembic. Nunca criar ou alterar tabelas com DDL cru no código da aplicação.
- **Gerenciamento de sessão:** Usar `Session` (sync) ou `AsyncSession` (async) via factory. Nunca abrir conexões cruas.

## Convenção de Connection String

Todo acesso ao banco DEVE passar por uma única factory que lê variável de ambiente:

```python
import os
from sqlalchemy import create_engine

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "sqlite:///./dev.db"  # fallback para desenvolvimento
)

engine = create_engine(DATABASE_URL, echo=False)