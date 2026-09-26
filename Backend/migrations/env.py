"""Ambiente do Alembic do O.R.A.C.U.L.O.

A URL do banco NÃO vem do alembic.ini: vem da factory única src/db/sessao.py (regra do
CLAUDE.md). Assim migration, publicação e API nunca apontam para bancos diferentes.
`target_metadata` é o metadata das tabelas de src/db/tabelas.py, para o --autogenerate.
"""
from logging.config import fileConfig

from alembic import context

from src.db.sessao import engine, url_banco
from src.db.tabelas import Base

config = context.config
if config.config_file_name is not None and config.attributes.get("configurar_log", True):
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Gera o SQL sem conectar (alembic upgrade --sql)."""
    context.configure(url=url_banco(), target_metadata=target_metadata, literal_binds=True,
                      dialect_opts={"paramstyle": "named"}, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # render_as_batch: SQLite não tem ALTER TABLE completo; o modo batch recria a tabela
    # quando preciso. No PostgreSQL é inócuo. Mantém as migrations portáveis entre os dois.
    with engine().connect() as conexao:
        context.configure(connection=conexao, target_metadata=target_metadata, render_as_batch=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
