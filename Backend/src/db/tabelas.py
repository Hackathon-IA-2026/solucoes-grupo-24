"""Tabelas do banco (SQLAlchemy 2.x ORM). Mudou algo aqui -> gere uma migration do Alembic:

    alembic revision --autogenerate -m "descrição"      (de dentro de Backend/)

tests/test_db_api.py falha se o modelo e as migrations divergirem.

Desenho: o banco guarda os RECURSOS DO CONTRATO já validados, como documentos JSON, agrupados
por execução da publicação.
- `execucao`: uma linha por rodada da etapa 5 do run_heavywork.py (quando, qual "agora").
- `recurso`: uma linha por item de cada recurso da API (carga, previsao, riscos, alertas,
  excedentes, validacao), com o JSON exatamente como o dashboard o recebe.
Por que documentos e não uma coluna por campo: o formato é definido em UM lugar
(src/contrato/modelos.py, espelho do types.ts). Uma coluna por campo seria uma segunda cópia
do contrato, que teria de mudar junto a cada campo novo (e uma migration a cada vez).
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator


class UtcDateTime(TypeDecorator):
    """Instante sempre em UTC, com fuso, na ida e na volta.

    Bug que motivou: o SQLite não guarda fuso e devolvia datetime "ingênuo" (sem tz); a API
    mostrava "2026-09-26T02:28:14" sem dizer se era UTC ou Brasília. Aqui gravar um horário sem
    fuso é erro, e todo valor lido volta com tz=UTC, em qualquer banco (SQLite ou PostgreSQL).
    """
    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, valor, dialeto):
        if valor is None:
            return None
        if valor.tzinfo is None:
            raise ValueError("instante sem fuso não pode ser gravado; use UTC explícito")
        return valor.astimezone(timezone.utc)

    def process_result_value(self, valor, dialeto):
        if valor is None:
            return None
        return valor.replace(tzinfo=timezone.utc) if valor.tzinfo is None else valor.astimezone(timezone.utc)


class Base(DeclarativeBase):
    pass


class Execucao(Base):
    __tablename__ = "execucao"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # Instantes em UTC com fuso garantido pelo tipo UtcDateTime (vale para SQLite e PostgreSQL).
    gerado_em: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)
    # O "agora" desta execução (modo replay: pode ser um instante passado).
    instante_referencia: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)
    origem: Mapped[str] = mapped_column(String(50), nullable=False)

    recursos: Mapped[list["Recurso"]] = relationship(back_populates="execucao",
                                                     cascade="all, delete-orphan")


class Recurso(Base):
    __tablename__ = "recurso"
    # Um item não pode aparecer duas vezes na mesma execução (ex.: dois alertas com o mesmo id,
    # e a API devolveria um deles ao acaso). O banco recusa.
    __table_args__ = (UniqueConstraint("execucao_id", "tipo", "chave", name="uq_recurso_item"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    execucao_id: Mapped[int] = mapped_column(ForeignKey("execucao.id", ondelete="CASCADE"),
                                             nullable=False, index=True)
    tipo: Mapped[str] = mapped_column(String(30), nullable=False)       # chave de RECURSOS
    chave: Mapped[str] = mapped_column(String(200), nullable=False)     # id do item no recurso
    ordem: Mapped[int] = mapped_column(Integer, nullable=False)         # ordem original na lista
    mock: Mapped[bool] = mapped_column(Boolean, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)         # JSON do contrato

    execucao: Mapped[Execucao] = relationship(back_populates="recursos")
