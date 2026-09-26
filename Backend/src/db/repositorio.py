"""Leitura e escrita dos recursos do contrato no banco. Único caminho de acesso às tabelas.

Escrita (`publicar`, usada pela etapa 5 do run_heavywork.py):
- valida CADA item contra src/contrato/modelos.py antes de gravar: dado fora do contrato não
  entra no banco, então a API não tem como servir algo que o dashboard recusaria;
- exige todos os recursos de RECURSOS na mesma execução, numa transação só: a API nunca vê uma execução
  pela metade (ex.: carga nova com previsão da rodada anterior).

Leitura (usada pela API): sempre a execução mais recente.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.contrato.modelos import RECURSOS
from src.db.tabelas import Execucao, Recurso

# Campo que identifica cada item nos recursos em lista. Os recursos sem entrada aqui usam a
# posição na lista. A restrição única (execucao, tipo, chave) recusa ids repetidos.
CAMPO_CHAVE = {"previsao": "horizonte", "riscos": "id", "alertas": "riscoUsinaId"}


def _utc(v: datetime) -> datetime:
    if v.tzinfo is None:
        raise ValueError("instante sem fuso; use UTC explícito")
    return v.astimezone(timezone.utc)


def publicar(sessao: Session, recursos: dict[str, dict | list[dict]],
             instante_referencia: datetime, origem: str) -> int:
    """Grava uma execução nova com todos os recursos do contrato. Devolve o id da execução."""
    faltando, sobrando = set(RECURSOS) - set(recursos), set(recursos) - set(RECURSOS)
    if faltando or sobrando:
        raise ValueError(f"publicação incompleta ou com recurso desconhecido: "
                         f"faltando={sorted(faltando)} sobrando={sorted(sobrando)}")
    execucao = Execucao(gerado_em=datetime.now(timezone.utc),
                        instante_referencia=_utc(instante_referencia), origem=origem)
    for tipo, (modelo, e_lista, _) in RECURSOS.items():
        bruto = recursos[tipo]
        if e_lista != isinstance(bruto, list):
            raise TypeError(f"{tipo}: esperado {'lista' if e_lista else 'objeto'}")
        for ordem, item in enumerate(bruto if e_lista else [bruto]):
            payload = modelo.model_validate(item).para_json()  # contrato: valida e normaliza
            campo = CAMPO_CHAVE.get(tipo)
            chave = str(payload[campo]) if campo else str(ordem)
            execucao.recursos.append(Recurso(tipo=tipo, chave=chave, ordem=ordem,
                                             mock=payload["mock"], payload=payload))
    with sessao.begin():
        sessao.add(execucao)
    return execucao.id


def ultima_execucao(sessao: Session) -> Execucao | None:
    return sessao.scalars(select(Execucao).order_by(Execucao.id.desc()).limit(1)).first()


def ler(sessao: Session, tipo: str, execucao: Execucao) -> dict | list[dict]:
    """Recurso inteiro da execução: lista (na ordem publicada) ou objeto único."""
    e_lista = RECURSOS[tipo].lista
    itens = sessao.scalars(select(Recurso.payload)
                           .where(Recurso.execucao_id == execucao.id, Recurso.tipo == tipo)
                           .order_by(Recurso.ordem)).all()
    if e_lista:
        return list(itens)
    if len(itens) != 1:
        raise LookupError(f"execução {execucao.id}: {tipo} deveria ter 1 item, tem {len(itens)}")
    return itens[0]


def ler_item(sessao: Session, tipo: str, chave: str, execucao: Execucao) -> dict | None:
    return sessao.scalars(select(Recurso.payload).where(
        Recurso.execucao_id == execucao.id, Recurso.tipo == tipo, Recurso.chave == chave)).first()
