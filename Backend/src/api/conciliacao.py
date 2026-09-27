"""Rota da camada de MMGD conciliada por transformador (Mapa Híbrido), fora do contrato.

    GET /conciliacao/mmgd-trafo -> {mock, descricao, pontos: [[lat, lon, 0–1]], geradoEm, referenciaKw}

O corpo tem o MESMO formato do recurso mmgd_densidade do contrato (heatmap do Mapa Híbrido), e foi
validado com o mesmo modelo (src/contrato/modelos.py::DensidadeMmgd) quando src/spatial/conciliacao.py
o gravou. Fica fora do contrato (decisão do Luiz em 2026-09-27) para não mudar o que o heatmap atual
significa: o dashboard liga esta camada num botão à parte.
Só LÊ o arquivo gravado pela conciliação (serviço web só de leitura). Sem ele: 503 com o comando.
"""
from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException

from src.spatial.conciliacao_cfg import saida

COMANDO = ("python -m src.spatial.areas_trafo && python -m pipeline.paineis_por_transformador && "
           "python -m src.spatial.conciliacao (em Backend/)")


def carregar_camada() -> dict:
    arq = saida("camada_mapa")
    if not arq.is_file():
        raise LookupError(f"camada de MMGD por transformador ainda não gerada: rode {COMANDO}")
    return json.loads(arq.read_text(encoding="utf-8"))


def rotas_conciliacao() -> APIRouter:
    r = APIRouter()

    @r.get("/conciliacao/mmgd-trafo")
    def mmgd_trafo():
        try:
            return carregar_camada()
        except LookupError as e:
            raise HTTPException(503, str(e)) from e

    return r
