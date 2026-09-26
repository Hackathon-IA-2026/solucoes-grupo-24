"""Única factory de conexão com o banco (Regras de Compatibilidade de Banco de Dados, CLAUDE.md).

    DATABASE_URL=postgresql+psycopg://...   -> PostgreSQL
    (sem a variável)                          -> SQLite em Backend/oraculo.db

Decisão: o fallback é um caminho ABSOLUTO (Backend/oraculo.db), e não "sqlite:///./dev.db"
como no exemplo do CLAUDE.md. Com caminho relativo, rodar o run_heavywork.py de uma pasta e o
main.py de outra criaria dois bancos diferentes, e a API mostraria um banco vazio sem erro
nenhum. Absoluto, os dois lados sempre falam com o mesmo arquivo.
"""
from __future__ import annotations

import os
from functools import lru_cache

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from src.utils.paths import RAIZ

ARQUIVO_SQLITE = RAIZ / "oraculo.db"


def url_banco() -> str:
    return os.environ.get("DATABASE_URL", f"sqlite:///{ARQUIVO_SQLITE.as_posix()}")


@lru_cache(maxsize=None)
def _engine(url: str) -> Engine:
    engine = create_engine(url, echo=False)
    if url.startswith("sqlite"):
        # SQLite só respeita FOREIGN KEY (e o ON DELETE CASCADE) com este pragma ligado,
        # conexão a conexão. Sem ele, apagar uma execução deixaria recursos órfãos.
        @event.listens_for(engine, "connect")
        def _fk(conexao, _):
            conexao.execute("PRAGMA foreign_keys=ON")
    return engine


def engine() -> Engine:
    """Engine do banco configurado agora (DATABASE_URL lida a cada chamada: testes trocam)."""
    return _engine(url_banco())


def nova_sessao() -> Session:
    return sessionmaker(bind=engine(), expire_on_commit=False)()
