"""Rota da tela "Previsão de meses" (Operação), fora do contrato.

    GET /previsao-meses -> envelope {ok, mode, data, provenance, notes} das telas do protótipo

`data` = painel gravado por src/models/pato_meses.py (demanda, MMGD e curva do pato prevista para
1–6 meses, por série e cenário de capacidade, + validação do backtest). Fica fora do contrato,
como a camada de MMGD por transformador: não muda o schema (docs/schema_contrato.json).
Só LÊ o arquivo (serviço web só de leitura; o cálculo roda na máquina local). Sem ele: 503 com
o comando, no formato de erro que o cliente do protótipo entende.
"""
from __future__ import annotations

import json

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from src.utils.config import carregar
from src.utils.paths import RAIZ

COMANDO = "python -m src.models.demanda_meses && python -m src.models.pato_meses (em Backend/)"


def carregar_painel() -> dict:
    # Caminho pela config, sem importar src.models.pato_meses: o serviço web não carrega pandas
    # (tests/test_db_api.py::test_servico_web_nao_carrega_a_parte_pesada).
    arq = RAIZ / carregar("pato_meses")["saidas"]["painel"]
    if not arq.is_file():
        raise LookupError(f"previsão de meses ainda não gerada: rode {COMANDO}")
    return json.loads(arq.read_text(encoding="utf-8"))


def rotas_previsao_meses() -> APIRouter:
    r = APIRouter()

    @r.get("/previsao-meses")
    def previsao_meses():
        try:
            dado = carregar_painel()
        except LookupError as e:
            return JSONResponse(status_code=503, content={
                "ok": False, "error": {"code": "NO_DATA", "message": str(e), "hint": COMANDO}})
        prov = [{"dataset": f, "resource": "previsão de meses", "mode": "live"} for f in dado.get("fontes", [])]
        return {"ok": True, "mode": "live", "generated_at": dado.get("emissao"), "data": dado,
                "provenance": prov, "notes": dado.get("premissas", [])}

    return r
