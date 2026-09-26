"""Testes do pipeline de explicabilidade (Backend/pipeline/explicabilidade.py)."""
import json
from datetime import datetime, timezone

import pytest

from pipeline.explicabilidade import (
    ErroSaidaModelo,
    ExplicadorPrecomputado,
    explicar_saida,
    gerar_texto_alerta,
)
from pipeline.gerar_alertas_mock import ENTRADA, RISCOS, SAIDA, montar_alertas

AGORA = datetime(2026, 9, 25, 17, 30, tzinfo=timezone.utc)  # 14:30 em Brasília


def saida_exemplo(**extra):
    base = {
        "probabilidade": 0.64,
        "montante_mw": 249,
        "usina": "Chapada Gaúcha Solar",
        "horario_previsto": "2026-09-26T15:00:00Z",  # amanhã 12:00 BRT
        "janela_previsao": "D+1",
        "motivos": {"ENE": 62, "CNF": 25, "REL": 13},
        "dataset_origem": "ONS — constrained-off FV (tm)",
        "atualizado_em": "2026-09-25T17:18:00Z",
        "variaveis_shap": {"Radiação": 0.36, "Carga prevista": -0.19, "MMGD": 0.24},
        "mock": True,
    }
    return {**base, **extra}


def test_texto_formato_exato_d1():
    texto = gerar_texto_alerta(explicar_saida(saida_exemplo(), agora=AGORA))
    assert texto == (
        "⚠ ALERTA — Risco de Curtailment\n"
        "Probabilidade de 64% de curtailment de 249 MW em Chapada Gaúcha Solar, amanhã às 12:00.\n"
        "Motivo: 62% ENE · 25% CNF · 13% REL\n"
        "Fonte: ONS — constrained-off FV (tm) · janela de previsão D+1 · atualizado há 12 min"
    )


def test_texto_nao_mente_sobre_dia_e_janela():
    # alerta de 3h para hoje não pode sair como "amanhã ... D+1"
    p = explicar_saida(saida_exemplo(horario_previsto="2026-09-25T20:30:00Z", janela_previsao="3h"), agora=AGORA)
    texto = gerar_texto_alerta(p)
    assert "hoje às 17:30" in texto and "janela de previsão 3h" in texto


def test_payload_glass_box():
    p = explicar_saida(saida_exemplo(), agora=AGORA)
    assert {"probabilidade", "motivos_por_peso", "variaveis_shap", "dataset_origem", "timestamp"} <= p.keys()
    assert p["probabilidade"] == 64.0
    assert p["timestamp"] == "2026-09-25T17:18:00Z"
    assert p["mock"] is True
    assert p["metodo_explicacao"] == "ExplicadorPrecomputado"
    # SHAP normalizado: pesos somam 1, ordenados, direção pelo sinal
    pesos = [v["peso"] for v in p["variaveis_shap"]]
    assert pesos == sorted(pesos, reverse=True) and sum(pesos) == pytest.approx(1)
    assert p["variaveis_shap"][2] == pytest.approx(
        {"variavel": "Carga prevista", "peso": 0.19 / 0.79, "direcao": "reduz", "contribuicao": -0.19}
    )


def test_motivos_sempre_somam_100():
    # 1/3 cada: arredondamento ingênuo daria 33+33+33 = 99
    p = explicar_saida(saida_exemplo(motivos={"ENE": 1, "CNF": 1, "REL": 1}), agora=AGORA)
    assert sum(m["peso_pct"] for m in p["motivos_por_peso"]) == 100


@pytest.mark.parametrize(
    "extra, trecho",
    [
        ({"probabilidade": 64}, "0–1"),
        ({"janela_previsao": "1h"}, "janela_previsao"),
        ({"motivos": {"XYZ": 1}}, "motivos"),
        ({"horario_previsto": "2026-09-26T15:00:00"}, "fuso"),
        ({"variaveis_shap": None}, "variaveis_shap"),
    ],
)
def test_entradas_invalidas(extra, trecho):
    with pytest.raises(ErroSaidaModelo, match=trecho):
        explicar_saida(saida_exemplo(**extra), agora=AGORA)


def test_campo_obrigatorio_ausente():
    s = saida_exemplo()
    del s["usina"]
    with pytest.raises(ErroSaidaModelo, match="usina"):
        explicar_saida(s, agora=AGORA)


def test_explicador_shap_real_mesma_interface():
    """Com um modelo real (aqui linear), ExplicadorShap entra no lugar do stub sem mudar a chamada."""
    np = pytest.importorskip("numpy")
    pytest.importorskip("shap")
    from pipeline.explicabilidade import ExplicadorShap

    nomes = ["vento", "carga", "mmgd"]
    coef = np.array([0.5, -0.3, 0.2])
    modelo = lambda X: np.asarray(X) @ coef  # noqa: E731
    fundo = np.zeros((20, 3))
    s = saida_exemplo(features={"vento": 2.0, "carga": 1.0, "mmgd": 0.5})
    del s["variaveis_shap"]
    p = explicar_saida(s, explicador=ExplicadorShap(modelo, fundo, nomes), agora=AGORA)
    # modelo linear com base zero: contribuição exata = coef * x
    por_nome = {v["variavel"]: v for v in p["variaveis_shap"]}
    assert por_nome["vento"]["contribuicao"] == pytest.approx(1.0)
    assert por_nome["carga"]["direcao"] == "reduz"
    assert p["metodo_explicacao"] == "ExplicadorShap"


def test_stub_nao_aceita_features_sem_modelo():
    s = saida_exemplo(features={"vento": 1.0})
    del s["variaveis_shap"]
    with pytest.raises(ErroSaidaModelo):
        explicar_saida(s, explicador=ExplicadorPrecomputado(), agora=AGORA)


def test_alertas_json_do_dashboard_esta_atualizado():
    """O alertas.json versionado precisa ser exatamente o que o pipeline gera hoje.

    Falhou? Rode `python -m pipeline.gerar_alertas_mock` e comite o arquivo.
    """
    ler = lambda p: json.loads(p.read_text(encoding="utf-8"))  # noqa: E731
    assert ler(SAIDA) == montar_alertas(ler(ENTRADA), ler(RISCOS))
