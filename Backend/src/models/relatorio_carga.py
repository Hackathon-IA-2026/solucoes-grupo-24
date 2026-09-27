"""Relatório do backtest de carga: docs/reports/baseline_carga.md + metricas_carga.csv.

Gerado pela etapa 4 do run_heavywork.py logo depois das previsões (mesma tabela). O .md é
o que vai para a banca ("o modelo ganha dos baselines por horizonte?"); o .csv tem tudo.
"""
from __future__ import annotations

import pandas as pd

from src.models import carga as mc
from src.models import metricas as mt
from src.utils.paths import DOCS_REPORTS, ensure

ARQ_MD = DOCS_REPORTS / "baseline_carga.md"
ARQ_CSV = DOCS_REPORTS / "metricas_carga.csv"


def _md(df: pd.DataFrame, fmt: dict[str, str]) -> str:
    """DataFrame -> tabela Markdown (sem depender do pacote tabulate)."""
    linhas = ["| " + " | ".join(df.columns) + " |", "|" + "---|" * len(df.columns)]
    for _, r in df.iterrows():
        linhas.append("| " + " | ".join("—" if pd.isna(r[c]) else format(r[c], fmt.get(c, ""))
                                        for c in df.columns) + " |")
    return "\n".join(linhas)


def montar(prev: pd.DataFrame) -> tuple[str, pd.DataFrame]:
    c = mc.cfg()
    p = mt.com_real(prev)
    tab = mt.tabela(p)
    ext = mt.extremos_diarios(p)
    geral = tab[tab["patamar"] == "todos"].merge(ext, on=mt.CHAVES, how="left")
    clima = geral[geral["modelo"] == "climatologia"][["serie", "horizonte", "mae"]].rename(columns={"mae": "mae_clima"})
    geral = geral.merge(clima, on=["serie", "horizonte"])
    geral["skill"] = mt.skill(geral["mae"], geral["mae_clima"])
    ordem_h = list(c["horizontes"])
    ordem_m = list(mc.MODELOS_TODOS)
    geral["_h"] = geral["horizonte"].map(ordem_h.index)
    geral["_m"] = geral["modelo"].map(ordem_m.index)
    geral = geral.sort_values(["serie", "_h", "_m"]).drop(columns=["_h", "_m"])

    sp = mc.split()
    alvo_ini, alvo_fim = p["alvo"].min(), p["alvo"].max()
    pub = c["serie_publicada"]
    partes = [
        "# Backtest da previsão de carga supervisionada (Fase 3)",
        "",
        "Gerado por `python run_heavywork.py` (etapa 4; código em `Backend/src/models/`). "
        "Não editar à mão.",
        "",
        f"- Treino: alvos de {sp.inicio_treino:%Y-%m-%d} a {sp.fim_treino:%Y-%m-%d}. "
        f"Teste (fora da amostra): emissões a partir de {sp.inicio_teste:%Y-%m-%d}; alvos avaliados "
        f"de {alvo_ini:%Y-%m-%d} a {alvo_fim:%Y-%m-%d %H:%M} (horário UTC−3).",
        "- Split cronológico; cada previsão usa só dados até a emissão (alvo − horizonte). "
        "Testes: `Backend/tests/test_features_carga.py` e `test_modelos_carga.py`.",
        "- Features: calendário (feriado = domingo) + defasagens da carga supervisionada e da MMGD. "
        "Sem meteorologia (decisão de 2026-09-25).",
        "- P10/P90 dos baselines: P50 + quantis do resíduo no treino. LightGBM: um modelo por quantil.",
        "- TFT (quando treinado): Temporal Fusion Transformer multi-horizonte com perda pinball "
        "assimétrica por patamar (pesos em `Backend/config/modelos_tft.yaml`); o P50 é enviesado de "
        "propósito para o lado seguro de cada patamar (acima na ponta, abaixo na mínima), então o MAE "
        "não é a métrica que ele otimiza: veja também o viés por patamar. Banda calibrada por CQR.",
        "- skill = 1 − MAE / MAE da climatologia (média do treino por mês × dia da semana × horário).",
        "- Cobertura: % dos reais dentro de P10–P90 (ideal: 80%).",
        "",
        f"## {pub}: todos os modelos",
        "",
        _md(geral[geral["serie"] == pub][["horizonte", "modelo", "mae", "rmse", "mape", "pinball",
                                          "cobertura", "skill", "erro_pico", "erro_vale", "erro_rampa"]],
            {"mae": ".0f", "rmse": ".0f", "mape": ".2f", "pinball": ".0f", "cobertura": ".1f",
             "skill": ".3f", "erro_pico": ".0f", "erro_vale": ".0f", "erro_rampa": ".0f"}),
        "",
        "MW, exceto MAPE e cobertura (%) e skill (fração). Pico, vale e rampa: erro médio diário.",
        "",
        f"## {pub}: MAE por patamar (MW)",
        "",
    ]
    pat = tab[(tab["serie"] == pub) & (tab["patamar"] != "todos")]
    piv = pat.pivot_table(index=["horizonte", "modelo"], columns="patamar", values="mae").reset_index()
    piv["_h"] = piv["horizonte"].map(ordem_h.index)
    piv["_m"] = piv["modelo"].map(ordem_m.index)
    piv = piv.sort_values(["_h", "_m"]).drop(columns=["_h", "_m"])
    piv.columns.name = None
    partes += [_md(piv, {k: ".0f" for k in piv.columns if k not in ("horizonte", "modelo")}), ""]

    # Viés (previsto − real) por patamar: mostra o deslocamento pretendido da perda assimétrica.
    partes += [f"## {pub}: viés do P50 por patamar (MW; > 0 = superestima)", ""]
    vies = pat.pivot_table(index=["horizonte", "modelo"], columns="patamar", values="vies").reset_index()
    vies["_h"] = vies["horizonte"].map(ordem_h.index)
    vies["_m"] = vies["modelo"].map(ordem_m.index)
    vies = vies.sort_values(["_h", "_m"]).drop(columns=["_h", "_m"])
    vies.columns.name = None
    partes += [_md(vies, {k: ".0f" for k in vies.columns if k not in ("horizonte", "modelo")}), ""]

    # Veredito por série × horizonte: cada modelo aprendido ganha do MELHOR baseline?
    aprendidos = [m for m in mc.MODELOS_APRENDIDOS if m in set(geral["modelo"])]
    partes += [f"## {' e '.join(aprendidos)} × melhor baseline, por série e horizonte (MAE, MW)", ""]
    linhas = []
    for (serie, h), g in geral.groupby(["serie", "horizonte"], sort=False):
        base = g[g["modelo"].isin(mc.BASELINES)].sort_values("mae").iloc[0]
        for modelo in aprendidos:
            m = g[g["modelo"] == modelo].iloc[0]
            linhas.append({"serie": serie, "horizonte": h, "modelo": modelo,
                           "melhor_baseline": base["modelo"], "mae_baseline": base["mae"],
                           "mae_modelo": m["mae"], "ganho_pct": 100 * (1 - m["mae"] / base["mae"]),
                           "ganha": "sim" if m["mae"] < base["mae"] else "**não**"})
    partes += [_md(pd.DataFrame(linhas), {"mae_baseline": ".0f", "mae_modelo": ".0f",
                                           "ganho_pct": ".1f"}), ""]
    return "\n".join(partes), tab.merge(ext.assign(patamar="todos"), on=[*mt.CHAVES, "patamar"], how="left")


def escrever(prev: pd.DataFrame | None = None) -> str:
    texto, csv = montar(mc.ler_previsoes() if prev is None else prev)
    ensure(DOCS_REPORTS)
    ARQ_MD.write_text(texto, encoding="utf-8")
    csv.to_csv(ARQ_CSV, index=False, float_format="%.3f")
    return f"relatório em docs/reports/{ARQ_MD.name}"
