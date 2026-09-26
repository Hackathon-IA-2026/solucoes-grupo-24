"""Rota da auditoria da MMGD em 3 camadas (visão computacional do time: pipeline/auditoria_*).

    GET /auditoria/mmgd -> Camada 1 (GeoJSON dos painéis) + Camadas 2/3 (desempate e fator)

Só LÊ as saídas que o pipeline grava (caminhos em config/visao.yaml); nunca roda o modelo aqui
(serviço web só de leitura, docs/Oraculo_planejamento.md §13.1). Prioridade: saída real; sem
ela, a saída do modo --mock, com `is_mock: true` no topo para a tela exibir o selo MOCK.
Nenhuma das duas -> 503 com o comando que gera.

A outra solução de visão computacional (detector clássico por subestação + adaptador YOLO do
protótipo) é servida pelo pacote `oraculo/` em /api/mapa/vision e /api/mapa/scene/{id}.
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

from src.utils.config import carregar
from src.utils.paths import RAIZ

COMANDO = ("python -m pipeline.auditoria_camada1 --mock && "
           "python -m pipeline.auditoria_camadas_2_3 --mock (em Backend/)")


def _ler(caminho: Path) -> dict | None:
    if not caminho.is_file():
        return None
    return json.loads(caminho.read_text(encoding="utf-8"))


def carregar_auditoria() -> dict:
    cfg = carregar("visao")
    real = (_ler(RAIZ / cfg["camada1"]["saida"]), _ler(RAIZ / cfg["auditoria"]["saida"]))
    mock = (_ler(RAIZ / cfg["camada1"]["saida_mock"]), _ler(RAIZ / cfg["auditoria"]["mock"]["saida"]))
    if real[0] is not None and real[1] is not None:
        camada1, camadas23, is_mock = real[0], real[1], False
    elif mock[0] is not None and mock[1] is not None:
        camada1, camadas23, is_mock = mock[0], mock[1], True
    else:
        raise LookupError(f"auditoria ainda não gerada: rode {COMANDO}")
    modelo = RAIZ / cfg["modelo"]["caminho"]
    return {
        "is_mock": is_mock or bool(camadas23.get("is_mock")),
        "camada1": camada1,
        "camadas23": camadas23,
        "modelo": {"caminho": cfg["modelo"]["caminho"], "presente": modelo.is_file(),
                   "confianca_minima": cfg["modelo"]["confianca_minima"],
                   "gsd_maximo_m": cfg["modelo"]["gsd_maximo_m"]},
        "satelite": {k: cfg["satelite"].get(k) for k in
                     ("bbox", "colecao", "escala_m", "data_inicio", "data_fim")},
        "parametros": cfg["auditoria"] | {"mock": None},
        "comando": COMANDO,
    }


def rotas_auditoria() -> APIRouter:
    r = APIRouter()

    @r.get("/auditoria/mmgd")
    def auditoria_mmgd():
        try:
            return carregar_auditoria()
        except LookupError as e:
            raise HTTPException(503, str(e)) from e

    return r
