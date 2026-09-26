"""Gera o mock `alertas.json` do dashboard passando pelo pipeline de explicabilidade REAL.

Uso (da raiz do repositório):
    python -m pipeline.gerar_alertas_mock

Por que existe: o texto do alerta e o payload glass box só têm UMA implementação
(explicabilidade.py). Em vez de o dashboard reescrever o template em TypeScript (e os dois
divergirem), este script roda o pipeline sobre saídas de modelo ILUSTRATIVAS e grava o
resultado no formato do contrato do dashboard (camelCase, src/data/types.ts).

Entradas (todas mock: true — ver docs/real_vs_mock.md):
- Frontend/.../mock/riscos.json      seed da usina: nome, probabilidade, montante, horizonte
- Backend/pipeline/mock/saidas_modelo.json   o que só o "modelo" diria: motivos, SHAP,
                                              horário previsto, dataset, hora da previsão
Probabilidade/montante/horizonte vêm SÓ de riscos.json: o alerta nunca diverge do risco.

Saída: Frontend/oraculo-dashboard/src/data/mock/alertas.json
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from pipeline.explicabilidade import explicar_saida, gerar_texto_alerta
from src.utils.paths import BACKEND, DASHBOARD_MOCK

ENTRADA = BACKEND / "pipeline" / "mock" / "saidas_modelo.json"
RISCOS = DASHBOARD_MOCK / "riscos.json"
SAIDA = DASHBOARD_MOCK / "alertas.json"

# "Agora" fixo dos mocks = instante do CargaSnapshot mockado (carga.json). Determinístico:
# rodar de novo produz exatamente o mesmo arquivo.
AGORA_MOCK = datetime.fromisoformat("2026-09-25T17:30:00+00:00")


def para_contrato_dashboard(payload: dict[str, Any], risco_usina_id: str) -> dict[str, Any]:
    """Payload glass box (snake_case) -> AlertaDetalhado do dashboard (camelCase)."""
    return {
        "mock": payload["mock"],
        "riscoUsinaId": risco_usina_id,
        "probabilidadePct": payload["probabilidade"],
        "montanteMw": payload["montante_mw"],
        "horarioPrevisto": payload["horario_previsto"],
        "motivos": [{"razao": m["razao"], "pesoPct": m["peso_pct"]} for m in payload["motivos_por_peso"]],
        "fonteDataset": payload["dataset_origem"],
        "janelaPrevisao": payload["janela_previsao"],
        "atualizadoHaMin": payload["atualizado_ha_min"],
        "atualizadoEm": payload["timestamp"],
        "metodoExplicacao": payload["metodo_explicacao"],
        "shapValues": [
            {"variavel": v["variavel"], "peso": round(v["peso"], 4), "direcao": v["direcao"]}
            for v in payload["variaveis_shap"]
        ],
        "textoAlerta": gerar_texto_alerta(payload),
    }


def montar_alertas(saidas: list[dict[str, Any]], riscos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    por_id = {r["id"]: r for r in riscos}
    alertas = []
    for s in saidas:
        r = por_id.get(s["risco_usina_id"])
        if r is None:
            raise KeyError(f"saída de modelo para risco inexistente em riscos.json: {s['risco_usina_id']}")
        saida = {
            **s,
            "usina": r["nome"],
            "probabilidade": r["probabilidadePct"] / 100,
            "montante_mw": r["montanteMw"],
            "janela_previsao": r["horizonte"],
            # Basta UMA das fontes ser ilustrativa para o alerta inteiro ser mock.
            "mock": bool(s.get("mock")) or bool(r.get("mock")),
        }
        alertas.append(para_contrato_dashboard(explicar_saida(saida, agora=AGORA_MOCK), r["id"]))
    return alertas


def _ler(p: Path) -> Any:
    return json.loads(p.read_text(encoding="utf-8"))


def main() -> None:
    alertas = montar_alertas(_ler(ENTRADA), _ler(RISCOS))
    SAIDA.write_text(json.dumps(alertas, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"gerado {SAIDA} ({len(alertas)} alertas)")


if __name__ == "__main__":
    main()
