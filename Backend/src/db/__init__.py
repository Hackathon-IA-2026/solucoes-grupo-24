"""Banco de dados do O.R.A.C.U.L.O.: só o que o dashboard consome (docs/contexto dos prompts.txt).

Regras de Compatibilidade de Banco de Dados (CLAUDE.md): SQLAlchemy 2.x, migrations só pelo
Alembic, sessão só pela factory de src/db/sessao.py. Este pacote NÃO pode importar nada da
parte pesada (pandas, DuckDB, modelos): a API o usa e precisa continuar leve.
"""
