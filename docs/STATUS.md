# STATUS

Andamento das tarefas. Atualizado ao fim de cada tarefa.

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
