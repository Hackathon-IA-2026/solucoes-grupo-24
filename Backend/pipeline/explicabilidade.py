"""Explicabilidade "glass box" dos alertas de curtailment.

Entrada: o dicionário de saída de um modelo (probabilidade, motivos com peso por razão e as
variáveis que explicam a previsão). Saída: o payload glass box

    {probabilidade, motivos_por_peso, variaveis_shap, dataset_origem, timestamp, ...}

consumido pelo dashboard (Detalhe do Alerta) e por gerar_texto_alerta().

Estado atual — STUB: os modelos reais (classificadores ENE/CNF do Tiago) ainda não existem.
Por isso a contribuição de cada variável vem PRONTA no dicionário (chave `variaveis_shap`) e é
só normalizada aqui (`ExplicadorPrecomputado`). Quando o modelo existir, passa-se um
`ExplicadorShap(modelo, dados_referencia, nomes_features)` e o dicionário traz as `features` da
previsão no lugar de `variaveis_shap`. A assinatura de explicar_saida() não muda.

Decisões:
- A lib `shap` é importada só dentro de ExplicadorShap (import tardio). O stub, os testes e o
  gerador de mocks funcionam sem shap/numpy instalados; quem usa o modelo real instala o extra
  `pip install -e ".[explicabilidade]"`.
- Pesos de motivo viram percentuais INTEIROS que somam exatamente 100 (maior resto), para o
  texto "62% ENE · 25% CNF · 13% REL" nunca somar 99 ou 101.
- A flag `mock` da entrada é propagada ao payload: dado ilustrativo não perde a marca no caminho.
"""
from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol
from zoneinfo import ZoneInfo

RAZOES_VALIDAS = ("REL", "CNF", "ENE")
JANELAS_VALIDAS = ("30min", "3h", "D+1")

# Fuso de EXIBIÇÃO do texto do alerta: o mesmo de config/processamento.yaml (tempo.fuso), lido
# de lá quando o pacote src/ + pyyaml estão disponíveis. O fallback (UTC-3 fixo, idêntico ao
# config) evita que gerar um texto dependa de ter o ambiente de dados completo instalado.
try:
    from src.utils.config import carregar as _carregar_config

    FUSO_EXIBICAO = ZoneInfo(_carregar_config("processamento")["tempo"]["fuso"])
except Exception:  # noqa: BLE001
    FUSO_EXIBICAO = timezone(timedelta(hours=-3))


class ErroSaidaModelo(ValueError):
    """Dicionário de saída de modelo fora do formato esperado (a mensagem diz qual campo)."""


# ---------------------------------------------------------------------------------------------
# Explicadores: estratégia que transforma a saída do modelo em contribuição por variável
# ---------------------------------------------------------------------------------------------


class Explicador(Protocol):
    """Qualquer objeto com `contribuicoes(saida)` -> {variável: contribuição com sinal}.

    Sinal positivo = a variável AUMENTA a probabilidade de curtailment; negativo = reduz.
    """

    def contribuicoes(self, saida: Mapping[str, Any]) -> dict[str, float]: ...


class ExplicadorPrecomputado:
    """STUB atual: usa as contribuições já presentes em `saida["variaveis_shap"]`."""

    def contribuicoes(self, saida: Mapping[str, Any]) -> dict[str, float]:
        bruto = saida.get("variaveis_shap")
        if not isinstance(bruto, Mapping) or not bruto:
            raise ErroSaidaModelo("variaveis_shap ausente: sem modelo real, as contribuições vêm prontas")
        return {str(k): float(v) for k, v in bruto.items()}


class ExplicadorLightGBM:
    """SHAP exato (TreeSHAP) calculado pelo próprio LightGBM (`predict(..., pred_contrib=True)`).

    As contribuições por variável já vêm calculadas por src/models/curtailment.py::explicar
    (em log-odds, com sinal), agrupadas em rótulos legíveis. Não depende da lib `shap`: o
    LightGBM implementa o TreeSHAP internamente. Uma instância por previsão explicada.
    """

    def __init__(self, contribuicoes: Mapping[str, float]) -> None:
        if not contribuicoes:
            raise ErroSaidaModelo("ExplicadorLightGBM sem contribuições")
        self._c = {str(k): float(v) for k, v in contribuicoes.items()}

    def contribuicoes(self, saida: Mapping[str, Any]) -> dict[str, float]:
        return dict(self._c)


class ExplicadorShap:
    """Explicador real via `shap`, para qualquer modelo com função de probabilidade.

    modelo: callable que recebe uma matriz (n, k) e devolve a probabilidade de curtailment (n,)
            — ex.: `lambda X: clf.predict_proba(X)[:, 1]` de um LightGBM/sklearn.
    dados_referencia: amostra (m, k) do treino usada como base do SHAP (background).
    nomes_features: ordem das colunas; `saida["features"]` é um dict {nome: valor}.
    """

    def __init__(
        self,
        modelo: Callable[[Any], Any],
        dados_referencia: Any,
        nomes_features: Sequence[str],
    ) -> None:
        import numpy as np
        import shap  # import tardio: só quem usa modelo real precisa da lib

        self._np = np
        self.nomes = list(nomes_features)
        self._explainer = shap.Explainer(modelo, np.asarray(dados_referencia, dtype=float), feature_names=self.nomes)

    def contribuicoes(self, saida: Mapping[str, Any]) -> dict[str, float]:
        feats = saida.get("features")
        if not isinstance(feats, Mapping):
            raise ErroSaidaModelo("features ausente: ExplicadorShap precisa dos valores de entrada do modelo")
        faltando = [n for n in self.nomes if n not in feats]
        if faltando:
            raise ErroSaidaModelo(f"features sem as colunas {faltando}")
        linha = self._np.asarray([[float(feats[n]) for n in self.nomes]])
        valores = self._explainer(linha).values[0]
        return {n: float(v) for n, v in zip(self.nomes, valores)}


# ---------------------------------------------------------------------------------------------
# Payload glass box
# ---------------------------------------------------------------------------------------------


def _pct_inteiros(pesos: Mapping[str, float]) -> list[tuple[str, int]]:
    """Normaliza pesos >= 0 para percentuais inteiros que somam 100 (método do maior resto).

    Ordenado do maior para o menor; empate desempata pela ordem de RAZOES_VALIDAS.
    """
    total = sum(pesos.values())
    if total <= 0:
        raise ErroSaidaModelo("motivos: a soma dos pesos precisa ser > 0")
    exatos = {k: v * 100 / total for k, v in pesos.items()}
    base = {k: math.floor(v) for k, v in exatos.items()}
    sobra = 100 - sum(base.values())
    for k in sorted(exatos, key=lambda k: exatos[k] - base[k], reverse=True)[:sobra]:
        base[k] += 1
    ordem = {r: i for i, r in enumerate(RAZOES_VALIDAS)}
    return sorted(base.items(), key=lambda kv: (-kv[1], ordem.get(kv[0], 99)))


def _datetime_utc(valor: Any, campo: str) -> datetime:
    """Aceita datetime com fuso ou texto ISO-8601; recusa horário sem fuso (ambíguo)."""
    dt = datetime.fromisoformat(valor.replace("Z", "+00:00")) if isinstance(valor, str) else valor
    if not isinstance(dt, datetime) or dt.tzinfo is None:
        raise ErroSaidaModelo(f"{campo}: precisa de data/hora COM fuso (ex.: 2026-09-26T15:00:00Z)")
    return dt.astimezone(timezone.utc)


def _iso_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def explicar_saida(
    saida: Mapping[str, Any],
    explicador: Explicador | None = None,
    agora: datetime | None = None,
) -> dict[str, Any]:
    """Transforma a saída de um modelo no payload glass box.

    Campos da `saida`:
        probabilidade      float 0–1 (saída do classificador)
        montante_mw        MW previstos de corte
        usina              nome exibido no alerta
        horario_previsto   datetime com fuso ou ISO-8601 (início do intervalo previsto)
        janela_previsao    "30min" | "3h" | "D+1"
        motivos            {razão: peso >= 0}, razões em REL/CNF/ENE
        dataset_origem     nome do dataset que alimentou a previsão (rastreabilidade)
        atualizado_em      (opcional) quando a previsão foi gerada; padrão = agora
        variaveis_shap     {variável: contribuição}  — modo stub (ExplicadorPrecomputado)
        features           {variável: valor}         — modo modelo real (ExplicadorShap)
        mock               (opcional) bool, propagado ao payload

    `agora` existe para testes e para gerar mocks de forma determinística.
    """
    agora_utc = _datetime_utc(agora or datetime.now(timezone.utc), "agora")
    explicador = explicador or ExplicadorPrecomputado()

    try:
        prob = float(saida["probabilidade"])
        montante = float(saida["montante_mw"])
        usina = str(saida["usina"])
        janela = str(saida["janela_previsao"])
        motivos = {str(k): float(v) for k, v in saida["motivos"].items()}
        dataset = str(saida["dataset_origem"])
        horario = _datetime_utc(saida["horario_previsto"], "horario_previsto")
    except KeyError as e:
        raise ErroSaidaModelo(f"campo obrigatório ausente: {e.args[0]}") from None

    if not 0 <= prob <= 1:
        raise ErroSaidaModelo(f"probabilidade deve estar em 0–1 (veio {prob})")
    if janela not in JANELAS_VALIDAS:
        raise ErroSaidaModelo(f"janela_previsao inválida: {janela!r} (use {JANELAS_VALIDAS})")
    invalidas = set(motivos) - set(RAZOES_VALIDAS)
    if invalidas or any(v < 0 for v in motivos.values()):
        raise ErroSaidaModelo(f"motivos: razões válidas {RAZOES_VALIDAS} e pesos >= 0 (veio {motivos})")

    # Contribuições -> peso relativo (0–1, soma 1) + direção, da maior para a menor.
    contrib = explicador.contribuicoes(saida)
    soma_abs = sum(abs(v) for v in contrib.values())
    if soma_abs <= 0:
        raise ErroSaidaModelo("variáveis SHAP: todas as contribuições são zero")
    variaveis = sorted(
        (
            {
                "variavel": nome,
                "peso": abs(v) / soma_abs,
                "direcao": "aumenta" if v > 0 else "reduz",
                "contribuicao": v,
            }
            for nome, v in contrib.items()
        ),
        key=lambda d: -d["peso"],
    )

    atualizado = _datetime_utc(saida.get("atualizado_em", agora_utc), "atualizado_em")
    return {
        "probabilidade": round(prob * 100, 1),  # percentual 0–100
        "motivos_por_peso": [{"razao": r, "peso_pct": p} for r, p in _pct_inteiros(motivos)],
        "variaveis_shap": variaveis,
        "dataset_origem": dataset,
        "timestamp": _iso_utc(atualizado),  # quando a previsão foi gerada (rastreabilidade)
        # Contexto necessário ao texto do alerta e ao dashboard:
        "montante_mw": montante,
        "usina": usina,
        "horario_previsto": _iso_utc(horario),
        "janela_previsao": janela,
        "atualizado_ha_min": max(0, int((agora_utc - atualizado).total_seconds() // 60)),
        "metodo_explicacao": type(explicador).__name__,
        "mock": bool(saida.get("mock", False)),
    }


# ---------------------------------------------------------------------------------------------
# Texto do alerta
# ---------------------------------------------------------------------------------------------


def _num_br(v: float, casas: int = 0) -> str:
    """1032 -> "1.032"; 87.5 -> "87,5" (pt-BR, sem depender do locale do sistema)."""
    s = f"{v:,.{casas}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def _pct_texto(v: float) -> str:
    """87.0 -> "87"; 87.5 -> "87,5"."""
    return _num_br(v, 0 if float(v).is_integer() else 1)


def _quando(horario: datetime, referencia: datetime) -> str:
    """"amanhã" / "hoje" / "em DD/MM", comparando as datas no fuso de exibição."""
    dias = (horario.astimezone(FUSO_EXIBICAO).date() - referencia.astimezone(FUSO_EXIBICAO).date()).days
    if dias == 1:
        return "amanhã"
    if dias == 0:
        return "hoje"
    return f"em {horario.astimezone(FUSO_EXIBICAO):%d/%m}"


def gerar_texto_alerta(payload: Mapping[str, Any]) -> str:
    """Texto do alerta no formato fixo do protótipo (4 linhas).

    Para previsões de amanhã com janela D+1 o texto sai EXATAMENTE no formato combinado
    ("amanhã às HH:MM", "janela de previsão D+1"). Decisão: o dia e a janela vêm do payload em
    vez de fixos, porque um alerta de 3h para hoje escrito como "amanhã ... D+1" seria uma
    informação falsa. O dia é relativo ao `timestamp` do payload (momento da previsão), não ao
    relógio, então o mesmo payload gera sempre o mesmo texto.
    """
    horario = _datetime_utc(payload["horario_previsto"], "horario_previsto")
    referencia = _datetime_utc(payload["timestamp"], "timestamp")
    motivos = " · ".join(f"{m['peso_pct']}% {m['razao']}" for m in payload["motivos_por_peso"])
    return "\n".join(
        [
            "⚠ ALERTA — Risco de Curtailment",
            f"Probabilidade de {_pct_texto(payload['probabilidade'])}% de curtailment de "
            f"{_num_br(payload['montante_mw'])} MW em {payload['usina']}, "
            f"{_quando(horario, referencia)} às {horario.astimezone(FUSO_EXIBICAO):%H:%M}.",
            f"Motivo: {motivos}",
            f"Fonte: {payload['dataset_origem']} · janela de previsão {payload['janela_previsao']} · "
            f"atualizado há {payload['atualizado_ha_min']} min",
        ]
    )
