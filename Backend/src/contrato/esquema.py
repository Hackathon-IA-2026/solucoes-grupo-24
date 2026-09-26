"""Gera docs/schema_contrato.json (JSON Schema) a partir de src/contrato/modelos.py.

    python -m src.contrato.esquema        (de dentro de Backend/)

O arquivo é DERIVADO, nunca editado à mão: a fonte é types.ts (dashboard), espelhado em
modelos.py. tests/test_contrato.py falha se o arquivo versionado estiver desatualizado, então
documentação e código não têm como divergir.
"""
from __future__ import annotations

import json

from src.contrato.modelos import RECURSOS
from src.utils.paths import DOCS

ARQUIVO = DOCS / "schema_contrato.json"


def gerar() -> dict:
    recursos = {}
    for nome, r in RECURSOS.items():
        item = r.modelo.model_json_schema(by_alias=True, mode="serialization")
        # /alertas/{id} devolve UM alerta, embora o recurso seja uma coleção no banco.
        devolve_lista = r.lista and "{id}" not in r.rota
        recursos[nome] = {"rota": f"GET /api{r.rota}",
                          "resposta": {"type": "array", "items": item} if devolve_lista else item}
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Contrato O.R.A.C.U.L.O. — API do Backend para o dashboard",
        "description": ("GERADO por `python -m src.contrato.esquema` a partir de "
                        "Backend/src/contrato/modelos.py, espelho de "
                        "Frontend/oraculo-dashboard/src/data/types.ts (fonte oficial). "
                        "Não edite à mão. Explicação em docs/schema_contrato.md."),
        "recursos": recursos,
    }


def texto() -> str:
    return json.dumps(gerar(), ensure_ascii=False, indent=2) + "\n"


if __name__ == "__main__":
    ARQUIVO.write_text(texto(), encoding="utf-8")
    print(f"gravado {ARQUIVO}")
