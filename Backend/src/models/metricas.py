"""Métricas do backtest de carga (Fase 3): por série, horizonte, modelo e patamar.

Entrada: a tabela de previsões fora da amostra de src/models/carga.py (`prever`), só nas
linhas em que o real já é conhecido. A MESMA função calcula o relatório do backtest e os
números da tela Validação (DRY: a tela nunca mostra uma métrica calculada de outro jeito).

Métricas (todas sobre o P50, exceto pinball e cobertura, que usam os três quantis):
- MAE, RMSE (MW), MAPE (%), viés = média(previsto − real) (MW; > 0 = superestima)
- pinball médio dos quantis P10/P50/P90 (MW)
- cobertura P10–P90 (%): fração dos reais dentro da banda; o ideal é 80%
- por dia: erro de pico (máximo do dia), de vale (mínimo da mínima diurna) e de rampa
  (máximo da ponta noturna − mínimo da mínima diurna: o "pescoço do pato")
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.features.calendario import patamar

CHAVES = ["serie", "horizonte", "modelo"]
QUANTIS = {"p10": 0.1, "p50": 0.5, "p90": 0.9}


def com_real(prev: pd.DataFrame) -> pd.DataFrame:
    """Só linhas com real conhecido, com o patamar do alvo e a data do alvo.

    Decisão: o patamar é calculado da hora do alvo pela MESMA função do calendário
    (src/features/calendario.py::patamar, faixas na config), e não relido de
    data/processed/calendario.csv. Isso elimina duas classes de bug: (1) métricas e testes
    dependendo de um arquivo local que não existe num clone novo, e (2) alvo fora do
    intervalo do calendário virando patamar NaN em silêncio (e sumindo das métricas por
    patamar). Patamar é função pura da hora, então não há o que ler de disco.
    """
    p = prev.dropna(subset=["real"]).copy()
    p["patamar"] = patamar(p["alvo"].dt.hour + p["alvo"].dt.minute / 60).to_numpy()
    p["data"] = p["alvo"].dt.normalize()
    return p


def basicas(g: pd.DataFrame) -> pd.Series:
    """Métricas de um grupo de linhas (real, p10, p50, p90)."""
    real = g["real"].to_numpy()
    erro = g["p50"].to_numpy() - real
    pinball = np.mean([np.mean(np.maximum(q * (real - g[c]), (q - 1) * (real - g[c])))
                       for c, q in QUANTIS.items()])
    return pd.Series({
        "n": len(g),
        "mae": np.mean(np.abs(erro)),
        "rmse": np.sqrt(np.mean(erro ** 2)),
        "mape": 100 * np.mean(np.abs(erro) / np.abs(real)),
        "vies": np.mean(erro),
        "pinball": pinball,
        "cobertura": 100 * np.mean((g["p10"] <= real) & (real <= g["p90"])),
    })


def tabela(p: pd.DataFrame) -> pd.DataFrame:
    """Métricas por série × horizonte × modelo × patamar (patamar 'todos' = tudo junto)."""
    geral = p.groupby(CHAVES).apply(basicas, include_groups=False).assign(patamar="todos")
    por_pat = p.groupby([*CHAVES, "patamar"]).apply(basicas, include_groups=False)
    return pd.concat([geral.reset_index(), por_pat.reset_index()], ignore_index=True)


def extremos_diarios(p: pd.DataFrame) -> pd.DataFrame:
    """Erro médio (MW) de pico, vale e rampa diários, só em dias completos (48 semi-horas).

    Vetorizado (agregações por grupo, sem apply por dia): são dezenas de milhares de dias ×
    modelo no backtest.
    """
    k = [*CHAVES, "data"]
    cols = ["real", "p50"]
    n = p.groupby(k).size()
    pico = p.groupby(k)[cols].max()
    vale = p[p["patamar"] == "minima_diurna"].groupby(k)[cols].min()
    ponta = p[p["patamar"] == "ponta_noturna"].groupby(k)[cols].max()
    d = pd.DataFrame({
        "erro_pico": (pico["p50"] - pico["real"]).abs(),
        "erro_vale": (vale["p50"] - vale["real"]).abs(),
        "erro_rampa": ((ponta["p50"] - vale["p50"]) - (ponta["real"] - vale["real"])).abs(),
    })
    d = d[n.reindex(d.index) == 48]
    return d.groupby(level=CHAVES).mean().reset_index()


def erro_diario(p: pd.DataFrame) -> pd.DataFrame:
    """MAE e RMSE por dia (histórico da tela Validação)."""
    e = p.assign(erro=p["p50"] - p["real"])
    return e.groupby("data")["erro"].agg(
        mae=lambda s: float(np.mean(np.abs(s))),
        rmse=lambda s: float(np.sqrt(np.mean(s ** 2))),
        n="size").reset_index()


def skill(mae_modelo: float, mae_referencia: float) -> float:
    """1 − MAE_modelo / MAE_referência (> 0 = melhor que a referência; 1 = perfeito)."""
    return 1 - mae_modelo / mae_referencia


# --------------------------------------------------------------------------- classificação (curtailment)
def classificacao(real: np.ndarray, score: np.ndarray, limiar: float = 0.5) -> dict[str, float]:
    """Métricas de um classificador de corte (real 0/1; score = probabilidade ou baseline).

    - roc_auc: ordena bem quem corta de quem não corta (0,5 = acaso)
    - pr_auc (average precision): o mesmo, focado na classe rara "corte"
    - brier: erro quadrático da probabilidade (calibração + discriminação; menor é melhor)
    - precisao / recall no limiar de decisão
    """
    from sklearn.metrics import average_precision_score, roc_auc_score

    real = np.asarray(real, dtype=int)
    score = np.asarray(score, dtype=float)
    previsto = score >= limiar
    vp = int(np.sum(previsto & (real == 1)))
    duas_classes = 0 < real.sum() < len(real)
    return {
        "n": len(real),
        "prevalencia": 100 * real.mean(),
        "roc_auc": roc_auc_score(real, score) if duas_classes else np.nan,
        "pr_auc": average_precision_score(real, score) if duas_classes else np.nan,
        "brier": float(np.mean((score - real) ** 2)),
        "precisao": 100 * vp / previsto.sum() if previsto.any() else np.nan,
        "recall": 100 * vp / real.sum() if real.any() else np.nan,
    }
