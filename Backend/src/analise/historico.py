"""Peça B — histórico mensal do corte por razão, com MMGD e carga: a Figura 1 do pitch.

Pergunta: "a razão energética (ENE) domina o corte desde abr/2025?" (marco em config/analises.yaml).
A resposta sai CALCULADA dos dados (tabela e frase do relatório), não escrita à mão.

Entradas (todas de data/processed, etapa 2):
- curtailment_mensal.csv: energia cortada por mês × fonte × subsistema × razão (ENE, CNF, REL)
- capacidade_mmgd.csv: potência de MMGD cadastrada na ANEEL, acumulada por UF e data
- carga_supervisionada.csv: carga supervisionada por subsistema, 30 min

Saídas: docs/reports/historico_curtailment.md, historico_curtailment_mensal.csv e
figura1_curtailment_mensal.png.

Decisões de desenho (skill de visualização do projeto):
- SEM eixo duplo: três painéis empilhados com o mesmo eixo de tempo (corte por razão; MMGD
  cadastrada; carga supervisionada mínima do SIN). Grandezas diferentes, escalas diferentes.
- Cores das razões = as do dashboard (mesma razão, mesma cor em todo o produto).
- O último mês é marcado como parcial quando a base ainda não fechou o mês.
"""
from __future__ import annotations

import pandas as pd

from src.features.carga import series_largas
from src.models.relatorio_carga import _md
from src.processing.saidas import SAIDA_CAPACIDADE_MMGD, SAIDA_CARGA, SAIDA_CURTAILMENT_MENSAL
from src.utils.config import carregar
from src.utils.paths import DOCS_REPORTS, ensure

RAZOES = ("ENE", "CNF", "REL")
ARQ_MD = DOCS_REPORTS / "historico_curtailment.md"
ARQ_CSV = DOCS_REPORTS / "historico_curtailment_mensal.csv"
ARQ_FIG = DOCS_REPORTS / "figura1_curtailment_mensal.png"


def cfg() -> dict:
    return carregar("analises")["historico"]


# --------------------------------------------------------------------------- tabela mensal
def corte_mensal(cm: pd.DataFrame) -> pd.DataFrame:
    """Mês × razão (GWh, eólica + solar, todo o SIN), com total, % de cada razão e a dominante."""
    t = cm.pivot_table(index="mes", columns="razao", values="energia_cortada_gwh", aggfunc="sum")
    t = t.reindex(columns=list(RAZOES)).fillna(0.0)
    t.index = pd.to_datetime(t.index)
    t["total"] = t[list(RAZOES)].sum(axis=1)
    for r in RAZOES:
        t[f"pct_{r}"] = 100 * t[r] / t["total"].where(t["total"] > 0)
    t["dominante"] = t[list(RAZOES)].idxmax(axis=1).where(t["total"] > 0)
    return t


def mmgd_mensal(cap: pd.DataFrame, meses: pd.DatetimeIndex) -> pd.Series:
    """MMGD cadastrada no Brasil no FIM de cada mês (GW): soma das UFs da acumulada até a data.

    A acumulada de cada UF só existe nas datas com cadastro novo; o valor no fim do mês é o
    último conhecido até ele (ffill por UF antes de somar: nunca soma UF sem valor como zero
    depois do primeiro cadastro dela).
    """
    larga = cap.pivot_table(index=pd.to_datetime(cap["data"]), columns="uf",
                            values="potencia_acumulada_mw", aggfunc="last").sort_index()
    fim_mes = meses + pd.offsets.MonthEnd(0)
    no_fim = larga.reindex(larga.index.union(fim_mes)).ffill().reindex(fim_mes)
    return pd.Series(no_fim.sum(axis=1).to_numpy() / 1000, index=meses, name="mmgd_cadastrada_gw")


def carga_minima_mensal(carga: pd.DataFrame, meses: pd.DatetimeIndex) -> pd.Series:
    """Carga supervisionada mínima do SIN em cada mês (GW).

    SIN = soma dos 4 subsistemas só nas semi-horas em que os 4 existem (mesma função da
    previsão de carga: src/features/carga.py::series_largas). É a grandeza da curva de "carga
    mínima" do PAR/PEL: quando ela cai, sobra menos espaço para a geração renovável.
    """
    sin = series_largas(carga, "carga_supervisionada", 0)["SIN"].dropna()
    por_mes = sin.groupby(sin.index.to_period("M").to_timestamp()).min() / 1000
    return por_mes.reindex(meses).rename("carga_sup_minima_gw")


def resposta(t: pd.DataFrame, marco: pd.Timestamp) -> dict:
    """Números que respondem à pergunta da Figura 1 (usados na frase do relatório e nos testes)."""
    depois = t[t.index >= marco]
    antes = t[t.index < marco]
    return {
        "meses_desde_marco": len(depois),
        "meses_ene_dominante": int((depois["dominante"] == "ENE").sum()),
        "meses_outra_dominante": [f"{m:%m/%Y} ({d})" for m, d in depois["dominante"].items() if d != "ENE"],
        "pct_ene_desde_marco": 100 * depois["ENE"].sum() / depois["total"].sum(),
        "pct_ene_antes_marco": 100 * antes["ENE"].sum() / antes["total"].sum() if len(antes) else float("nan"),
        "ene_gwh_desde_marco": depois["ENE"].sum(),
    }


# --------------------------------------------------------------------------- figura
def desenhar(t: pd.DataFrame, parcial: pd.Timestamp | None, destino=ARQ_FIG) -> None:
    import matplotlib

    matplotlib.use("Agg")  # sem janela: roda no pipeline e no pytest
    import matplotlib.pyplot as plt

    c = cfg()
    marco = pd.Timestamp(c["marco_regime"])
    fig, (a1, a2, a3) = plt.subplots(3, 1, figsize=(11, 8.5), sharex=True,
                                     gridspec_kw={"height_ratios": [2.2, 1, 1], "hspace": 0.12})
    x = t.index
    largura = pd.Timedelta(days=24)
    base = pd.Series(0.0, index=x)
    for r in RAZOES:  # barras empilhadas; borda branca de 1,5 px = o espaçador entre segmentos
        a1.bar(x, t[r], width=largura, bottom=base, color=c["cores"][r], label=r,
               edgecolor="white", linewidth=1.5)
        base = base + t[r]
    a1.set_ylabel("Energia cortada (GWh/mês)")
    a1.legend(loc="upper left", frameon=False, ncol=3, title="Razão do corte (eólica + solar, SIN)")
    a2.plot(x, t["mmgd_cadastrada_gw"], color=c["cor_linha"], linewidth=2)
    a2.set_ylabel("MMGD cadastrada\n(GW, ANEEL)")
    a3.plot(x, t["carga_sup_minima_gw"], color=c["cor_linha"], linewidth=2)
    a3.set_ylabel("Carga supervisionada\nmínima do SIN (GW)")
    for ax in (a1, a2, a3):
        ax.axvline(marco, color="#64748b", linestyle="--", linewidth=1)
        ax.grid(axis="y", color="#e2e8f0", linewidth=0.8)
        ax.set_axisbelow(True)
        for lado in ("top", "right"):
            ax.spines[lado].set_visible(False)
    a1.annotate(f"marco: {marco:%m/%Y}", (marco, a1.get_ylim()[1] * 0.95), xytext=(4, 0),
                textcoords="offset points", fontsize=9, color="#475569")
    if parcial is not None:
        a1.annotate("mês parcial", (parcial, t.loc[parcial, "total"]), xytext=(0, 4),
                    textcoords="offset points", ha="center", fontsize=8, color="#475569")
    fig.suptitle("Corte de geração eólica e solar por razão × MMGD × carga mínima (dados do ONS e da ANEEL)",
                 fontsize=12, x=0.01, y=0.915, ha="left")
    fig.savefig(destino, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)


# --------------------------------------------------------------------------- relatório
def _milhar(x: float) -> str:
    """Número inteiro com ponto de milhar (pt-BR): 38611 -> '38.611'."""
    return f"{x:,.0f}".replace(",", ".")


def montar() -> tuple[str, pd.DataFrame]:
    c = cfg()
    cm = pd.read_csv(SAIDA_CURTAILMENT_MENSAL)
    t = corte_mensal(cm)
    t["mmgd_cadastrada_gw"] = mmgd_mensal(pd.read_csv(SAIDA_CAPACIDADE_MMGD), t.index)
    t["carga_sup_minima_gw"] = carga_minima_mensal(pd.read_csv(SAIDA_CARGA), t.index)
    # Mês parcial: a base termina antes do fim do último mês (visto nas semi-horas publicadas).
    ultimo = t.index.max()
    parcial = ultimo if ultimo + pd.offsets.MonthEnd(0) > pd.Timestamp.today().normalize() else None
    marco = pd.Timestamp(c["marco_regime"])
    r = resposta(t, marco)
    ensure(DOCS_REPORTS)
    desenhar(t, parcial)

    outras = ", ".join(r["meses_outra_dominante"]) or "nenhum"
    veredito = ("sim" if r["meses_ene_dominante"] == r["meses_desde_marco"] else
                "quase sempre" if r["meses_ene_dominante"] >= 0.75 * r["meses_desde_marco"] else "não")
    tab = t.reset_index().rename(columns={"mes": "mês"})
    tab["mês"] = tab["mês"].dt.strftime("%Y-%m")
    fmt = {**{k: ".0f" for k in (*RAZOES, "total")}, **{f"pct_{k}": ".0f" for k in RAZOES},
           "mmgd_cadastrada_gw": ".1f", "carga_sup_minima_gw": ".1f"}
    partes = [
        "# Histórico mensal do corte por razão (Peça B / Figura 1)",
        "",
        "Gerado por `python run_heavywork.py` (etapa `analises`; código em `Backend/src/analise/historico.py`). "
        "Não editar à mão.",
        "",
        "![Figura 1](figura1_curtailment_mensal.png)",
        "",
        f"## A razão energética domina o corte desde {marco:%m/%Y}? **{veredito}**",
        "",
        f"- Desde {marco:%m/%Y}: ENE é a maior razão em **{r['meses_ene_dominante']} de {r['meses_desde_marco']} meses** "
        f"(exceções: {outras}).",
        f"- Participação do ENE na energia cortada: **{r['pct_ene_desde_marco']:.0f}%** desde o marco, contra "
        f"{r['pct_ene_antes_marco']:.0f}% antes ({_milhar(r['ene_gwh_desde_marco'])} GWh de corte ENE desde o marco).",
        "- Energia cortada = GNRa (geração não realizada apurada, MW médio da semi-hora × 0,5 h) das bases tm de "
        "constrained-off do ONS, eólica (desde 10/2021) e solar (desde 04/2024), rateada entre razões pelos minutos "
        "de cada uma (mesma regra dos rótulos: `Backend/src/processing/tabelas.py`).",
        "- MMGD cadastrada: potência acumulada do cadastro da ANEEL no fim de cada mês (data = atualização cadastral).",
        "- Carga supervisionada mínima: menor semi-hora do mês no SIN (soma dos 4 subsistemas).",
        f"- {'O último mês (' + f'{parcial:%m/%Y}' + ') é parcial.' if parcial is not None else 'Todos os meses completos.'}",
        "",
        "## Mês a mês (GWh, % da energia cortada no mês)",
        "",
        _md(tab[["mês", *RAZOES, "total", *(f"pct_{k}" for k in RAZOES), "dominante",
                 "mmgd_cadastrada_gw", "carga_sup_minima_gw"]], fmt),
        "",
    ]
    return "\n".join(partes), t


def escrever() -> str:
    texto, t = montar()
    ARQ_MD.write_text(texto, encoding="utf-8")
    t.reset_index().to_csv(ARQ_CSV, index=False, float_format="%.3f")
    return f"Figura 1 e relatório em docs/reports/{ARQ_MD.name}"
