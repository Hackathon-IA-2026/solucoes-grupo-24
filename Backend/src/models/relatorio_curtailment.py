"""Relatório do backtest do classificador de curtailment (Fase 4).

docs/reports/classificador_curtailment.md + metricas_curtailment.csv, gerados pela etapa 4
logo depois das previsões. Lido horizonte a horizonte (memória: ~10 M linhas no total).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.models import curtailment as mcur
from src.models import metricas as mt
from src.models.relatorio_carga import _md
from src.utils.paths import DOCS_REPORTS, ensure

ARQ_MD = DOCS_REPORTS / "classificador_curtailment.md"
ARQ_CSV = DOCS_REPORTS / "metricas_curtailment.csv"
SCORES = {"lightgbm": "p_{r}", "persistencia": "base_persistencia_{r}", "frequencia_1d": "base_frequencia_{r}"}
MONTANTES = {"lightgbm": "montante_{r}", "persistencia": "base_mw_{r}"}


def _metricas_horizonte(p: pd.DataFrame, razao: str, limiar: float) -> list[dict]:
    r = razao.lower()
    p = p.dropna(subset=[f"real_{r}"])
    linhas = []
    for fonte, g in [("todas", p), *p.groupby("fonte", observed=True)]:
        real = g[f"real_{r}"].to_numpy()
        for modelo, col in SCORES.items():
            m = mt.classificacao(real, g[col.format(r=r)].fillna(0).to_numpy(), limiar)
            mont = MONTANTES.get(modelo)
            if mont:
                erro = g[mont.format(r=r)].fillna(0).to_numpy() - g[f"real_mw_{r}"].to_numpy()
                m["mae_montante_mw"] = float(np.mean(np.abs(erro)))
            linhas.append({"razao": razao, "fonte": fonte, "modelo": modelo, **m})
    return linhas


def montar() -> tuple[str, pd.DataFrame]:
    c = mcur.cfg()
    limiar = c["publicacao"]["limiar_decisao"]
    usinas = mcur.ler_modelos()["codigos"].index
    linhas = []
    for nome_h in mcur.horizontes():
        p = mcur.ler_previsoes(filtros=[("horizonte", "=", nome_h)])
        p["fonte"] = p["chave"].astype(str).str.split(":").str[0]  # chave = fonte:id
        for razao in c["razoes"]:
            linhas += [{"horizonte": nome_h, **m} for m in _metricas_horizonte(p, razao, limiar)]
    tab = pd.DataFrame(linhas)
    sp = mcur.split()
    partes = [
        "# Backtest do classificador de risco de curtailment (Fase 4)",
        "",
        "Gerado por `python run_heavywork.py` (etapa 4; código em `Backend/src/models/curtailment.py`). "
        "Não editar à mão.",
        "",
        f"- {len(usinas)} usinas/conjuntos (chave = fonte + id). Treino: alvos de "
        f"{sp.inicio_treino:%Y-%m-%d} a {sp.fim_treino:%Y-%m-%d}; teste: emissões a partir de "
        f"{sp.inicio_teste:%Y-%m-%d} (fora da amostra).",
        "- Cada previsão usa só dados até a emissão (alvo − horizonte): histórico de cortes da usina, "
        "estado do sistema, carga supervisionada e MMGD, calendário do alvo. Sem meteorologia.",
        "- Baselines: **persistência** (havia corte na emissão?) e **frequência_1d** (fração do "
        "último dia com corte, até a emissão).",
        "- CNF sem os limites de exportação NE e N/NE (não existem no portal nem no MCP): só as "
        "mesmas features gerais.",
        f"- Precisão e recall no limiar {limiar:.0%} de probabilidade; montante = P(corte) × E[MW | corte] "
        "(persistência: MW cortados na emissão).",
        "",
    ]
    fmt = {"prevalencia": ".1f", "roc_auc": ".3f", "pr_auc": ".3f", "brier": ".4f", "precisao": ".1f",
           "recall": ".1f", "mae_montante_mw": ".2f", "n": ",.0f"}
    for razao in c["razoes"]:
        t = tab[(tab["razao"] == razao) & (tab["fonte"] == "todas")]
        partes += [f"## {razao}: todas as usinas", "",
                   _md(t[["horizonte", "modelo", "n", "prevalencia", "roc_auc", "pr_auc", "brier",
                          "precisao", "recall", "mae_montante_mw"]], fmt), "",
                   f"## {razao}: por fonte (LightGBM)", "",
                   _md(tab[(tab["razao"] == razao) & (tab["fonte"] != "todas") & (tab["modelo"] == "lightgbm")]
                       [["horizonte", "fonte", "n", "prevalencia", "roc_auc", "pr_auc", "brier",
                         "mae_montante_mw"]], fmt), ""]
    partes += ["Prevalência, precisão e recall em %; montante em MW por usina e semi-hora.", ""]
    return "\n".join(partes), tab


def escrever() -> str:
    texto, tab = montar()
    ensure(DOCS_REPORTS)
    ARQ_MD.write_text(texto, encoding="utf-8")
    tab.to_csv(ARQ_CSV, index=False, float_format="%.4f")
    return f"relatório em docs/reports/{ARQ_MD.name}"
