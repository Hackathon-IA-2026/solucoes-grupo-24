"""Migrations do Alembic chamadas por código (sem depender de rodar `alembic` no terminal).

- `atualizar_banco()`: a etapa 5 do run_heavywork.py chama antes de gravar. Banco novo ou
  desatualizado vira banco na última versão, sem passo manual esquecível.
- `banco_em_dia()`: a API consulta para responder 503 com instrução clara em vez de um erro
  de SQL quando o banco não existe ou está numa versão antiga.
"""
from __future__ import annotations

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory

from src.db.sessao import engine
from src.utils.paths import RAIZ


def _config() -> Config:
    cfg = Config(str(RAIZ / "alembic.ini"))
    # Não deixar o fileConfig do alembic.ini reconfigurar o log do processo que chamou.
    cfg.attributes["configurar_log"] = False
    return cfg


def atualizar_banco() -> None:
    command.upgrade(_config(), "head")


def banco_em_dia() -> bool:
    cabeca = ScriptDirectory.from_config(_config()).get_current_head()
    with engine().connect() as conexao:
        return MigrationContext.configure(conexao).get_current_revision() == cabeca
