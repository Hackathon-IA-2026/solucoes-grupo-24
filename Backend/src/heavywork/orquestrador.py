"""Motor genérico que roda as etapas do trabalho pesado em ordem, pulando o que está em dia.

Não sabe nada de ONS, modelos ou banco: recebe uma lista de `Etapa` (definidas em
src/heavywork/etapas.py) e decide, para cada uma, se roda ou não. Separado assim para ser
testável com etapas falsas (tests/test_heavywork.py), sem rede e sem dados.

Regras de decisão, na ordem:
1. Uma etapa anterior falhou nesta execução      -> "nao_rodou" (as seguintes dependem dela).
2. Desligada em config/heavywork.yaml             -> "desabilitada".
3. Ainda sem implementação (executar=None)        -> "nao_implementada". Não bloqueia as
   seguintes: cada etapa futura que depender dela vai falhar sozinha, com a mensagem dela.
4. Impressão digital das entradas igual à da última execução bem-sucedida, todas as saídas
   existem e a etapa não foi forçada               -> "pulada".
5. Senão                                          -> roda. Sucesso grava a impressão no estado;
   erro vira "falhou" e o estado da etapa NÃO é atualizado (a próxima execução tenta de novo).

Etapa sem função de entradas (entradas=None) sempre roda: é o caso da ingestão, que só sabe
se há novidade perguntando às fontes, e é idempotente por conta própria.
"""
from __future__ import annotations

import json
import logging
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

log = logging.getLogger("heavywork")

STATUS_OK = ("executada", "pulada")


@dataclass(frozen=True)
class Etapa:
    nome: str
    descricao: str
    # None = etapa planejada mas ainda não implementada (aparece no resumo, não finge rodar).
    executar: Callable[[], str | None] | None
    # Impressão digital das entradas (dados + código + config). None = sempre roda.
    entradas: Callable[[], str] | None = None
    # Arquivos que a etapa precisa deixar prontos; se algum sumir, ela roda de novo.
    saidas: tuple[Path, ...] = ()
    # Texto impresso antes de rodar (regra do projeto: avisar antes de etapas longas).
    estimativa: Callable[[], str | None] | None = None


@dataclass
class Resultado:
    nome: str
    status: str  # executada | pulada | nao_implementada | desabilitada | falhou | nao_rodou
    duracao_s: float = 0.0
    detalhe: str = ""


@dataclass
class Estado:
    """Última execução bem-sucedida de cada etapa, persistida em JSON (escrita atômica)."""
    caminho: Path
    dados: dict = field(default_factory=dict)

    @classmethod
    def ler(cls, caminho: Path) -> "Estado":
        dados = json.loads(caminho.read_text(encoding="utf-8")) if caminho.exists() else {}
        return cls(caminho, dados)

    def impressao(self, etapa: str) -> str | None:
        return self.dados.get(etapa, {}).get("impressao")

    def registrar(self, etapa: str, impressao: str | None) -> None:
        self.dados[etapa] = {"impressao": impressao,
                             "concluida_em": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.caminho.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.dados, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(self.caminho)


def validar_config(cfg: dict, etapas: list[Etapa]) -> tuple[dict[str, bool], set[str]]:
    """Lê `etapas` (liga/desliga) e `forcar` do config e recusa nome desconhecido.

    Um erro de digitação ("procesamento: false") desligaria nada em silêncio e forçaria
    nada em silêncio. Aqui ele vira erro imediato, antes de qualquer etapa rodar.
    """
    nomes = [e.nome for e in etapas]
    ligadas = cfg.get("etapas") or {}
    forcar = set(cfg.get("forcar") or [])
    desconhecidas = (set(ligadas) | forcar) - set(nomes)
    if desconhecidas:
        raise ValueError(f"config/heavywork.yaml cita etapas que não existem: {sorted(desconhecidas)}; "
                         f"etapas válidas: {nomes}")
    return {n: bool(ligadas.get(n, True)) for n in nomes}, forcar


def rodar(etapas: list[Etapa], estado: Estado, ligadas: dict[str, bool] | None = None,
          forcar: set[str] = frozenset()) -> list[Resultado]:
    """Roda as etapas em ordem (regras no docstring do módulo). Devolve um resultado por etapa."""
    ligadas = ligadas or {}
    resultados: list[Resultado] = []
    falhou = False
    for e in etapas:
        if falhou:
            resultados.append(Resultado(e.nome, "nao_rodou", detalhe="etapa anterior falhou"))
            continue
        if not ligadas.get(e.nome, True):
            resultados.append(Resultado(e.nome, "desabilitada", detalhe="config/heavywork.yaml"))
            continue
        if e.executar is None:
            resultados.append(Resultado(e.nome, "nao_implementada", detalhe=e.descricao))
            log.info("[%s] ainda não implementada: %s", e.nome, e.descricao)
            continue

        t0 = time.time()
        try:
            impressao = e.entradas() if e.entradas else None
            faltando = [str(p) for p in e.saidas if not Path(p).exists()]
            if (e.nome not in forcar and impressao is not None
                    and impressao == estado.impressao(e.nome) and not faltando):
                resultados.append(Resultado(e.nome, "pulada",
                                            detalhe="entradas iguais às da última execução"))
                log.info("[%s] em dia, pulada", e.nome)
                continue
            motivo = ("forçada em config/heavywork.yaml" if e.nome in forcar
                      else f"saídas ausentes: {faltando}" if faltando and estado.impressao(e.nome)
                      else "primeira execução" if estado.impressao(e.nome) is None
                      else "sempre roda" if impressao is None
                      else "entradas mudaram")
            log.info("[%s] rodando (%s): %s", e.nome, motivo, e.descricao)
            aviso = e.estimativa() if e.estimativa else None
            if aviso:
                log.info("[%s] estimativa: %s", e.nome, aviso)
            detalhe = e.executar() or ""
            estado.registrar(e.nome, impressao)
            resultados.append(Resultado(e.nome, "executada", time.time() - t0, detalhe))
        except Exception as exc:  # registra e interrompe: as etapas seguintes dependem desta
            log.error("[%s] falhou: %s\n%s", e.nome, exc, traceback.format_exc())
            resultados.append(Resultado(e.nome, "falhou", time.time() - t0, f"{type(exc).__name__}: {exc}"))
            falhou = True
    return resultados


def resumo(resultados: list[Resultado]) -> str:
    """Tabela de texto com o que aconteceu em cada etapa (impressa no fim do run_heavywork.py)."""
    linhas = [f"{'etapa':<14} {'status':<17} {'tempo':>8}  detalhe"]
    for r in resultados:
        tempo = f"{r.duracao_s / 60:.1f} min" if r.duracao_s >= 60 else f"{r.duracao_s:.0f} s"
        linhas.append(f"{r.nome:<14} {r.status:<17} {tempo:>8}  {r.detalhe}")
    return "\n".join(linhas)
