# Prompt — Reestruturação: tudo que é Python dentro de `Backend/`

Leia o `CLAUDE.md` e `docs/contexto dos prompts.txt`. Trabalhe na `main` (faça `git pull` antes).

## Objetivo

A raiz do repositório fica só com:

```
Backend/     # todo o código Python, dados, configuração, notebooks e testes
Frontend/    # dashboard (do Luiz — não altere nada lá)
docs/        # toda a documentação e relatórios
CLAUDE.md  README.md  LICENSE  .gitignore
```

E dentro de `Backend/`:

```
Backend/
  pyproject.toml      # o pacote Python mora aqui (raiz de import = Backend/)
  config/  data/  notebooks/  output/  src/  tests/
  pipeline/           # explicabilidade e geração de mocks (já existia)
  RDX/                # legado do hackathon anterior (BDGD/manchas do RJ), a migrar para src/spatial
```

## Passos

1. `git mv` de `src/`, `config/`, `notebooks/`, `tests/`, `output/`, `data/` e `RDX/` para `Backend/`. Os dados não versionados (`data/raw`, tabelas em `data/processed`) vão junto, porque o manifesto de download guarda caminhos **relativos** à raiz do backend.
2. `pyproject.toml` → `Backend/pyproject.toml`: pacotes `src*` e `pipeline*`; licença como texto (arquivo fora do projeto não é aceito); pytest com `pythonpath = ["."]`.
3. Imports: a raiz de import passa a ser `Backend/`. `Backend.pipeline.x` → `pipeline.x`. Comandos rodam de dentro de `Backend/` (`python -m src...`, `python -m pipeline...`).
4. `src/utils/paths.py`: `RAIZ` = `Backend/` (dados, config, saídas); `RAIZ_REPO` = raiz do git; `DOCS` e `FRONTEND` derivam de `RAIZ_REPO`. Continua sendo o único lugar que define caminhos.
5. Apague a pasta vazia `reports/` (relatórios ficam em `docs/reports/`) e os artefatos gerados (`*.egg-info`, `.pytest_cache`).
6. `.gitignore`: os padrões ancorados (`data/raw/` etc.) passam a apontar para `Backend/`.
7. Recrie o ambiente virtual em `Backend/.venv` (venv no Windows não se move) e rode `pip install -e ".[dev]"` de dentro de `Backend/`.
8. Atualize os caminhos citados em `docs/`, no `README.md` (seções "Como rodar o projeto" e "Pré-requisitos") e a seção "Estrutura do repositório" do `CLAUDE.md`.
9. Rode `pytest` dentro de `Backend/`: tudo precisa passar. Registre em `docs/STATUS.md`, commit e push.

## Regra para não voltar a acontecer

`Backend/tests/test_estrutura.py` falha se aparecer na raiz do repositório qualquer pasta fora de `Backend/`, `Frontend/` e `docs/` (ignorando as ocultas, como `.git` e `.venv`).
