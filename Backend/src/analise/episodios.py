"""Peça C — episódios de corte, lead time do classificador e o caso real (prova documental).

1. Episódios (rótulos processados, razão em config/analises.yaml): por usina, semi-horas com
   corte seguidas — interrupções de até `tolerancia_passos` semi-horas não quebram o episódio.
   Um episódio é um INÍCIO se a usina passou pelo menos `folga_minima_passos` sem corte antes
   (início colado no episódio anterior a persistência já "prevê"; não mede antecedência).
2. Lead time útil (Fase 4): para cada início no período de TESTE do classificador (fora da
   amostra), a probabilidade prevista para o instante do início, emitida 30 min, 3 h e 1 dia
   antes. "Avisou com h de antecedência" = p >= limiar_aviso nessa emissão. Comparado com a
   persistência (havia corte na emissão?), que por construção quase nunca avisa um início.
3. Caso real: o dia do teste com a maior fração de usinas cortadas ao mesmo tempo (proxy de
   restrição total), e o que o sistema disse na véspera (D+1): fração prevista × real e
   montante esperado × cortado, semi-hora a semi-hora.

Entradas: data/processed/rotulos_curtailment.parquet e as previsões fora da amostra do
classificador (data/modelos/curtailment/previsoes.parquet). Saídas em docs/reports/
(episodios_curtailment.md, lead_time_curtailment.csv, caso_real_curtailment.csv e a figura) e a
tabela completa de episódios em data/modelos/curtailment/episodios.parquet (grande: fora do git).
"""
from __future__ import annotations

import pandas as pd

from src.analise.historico import _milhar
from src.models import curtailment as mcur
from src.models.relatorio_carga import _md
from src.processing.saidas import SAIDA_ROTULOS
from src.utils.banco_analitico import conectar
from src.utils.config import carregar
from src.utils.paths import DOCS_REPORTS, ensure
from src.utils.tempo import PASSO

ARQ_EPISODIOS = mcur.ARQ_PREVISOES.with_name("episodios.parquet")
ARQ_MD = DOCS_REPORTS / "episodios_curtailment.md"
ARQ_LEAD = DOCS_REPORTS / "lead_time_curtailment.csv"
ARQ_CASO = DOCS_REPORTS / "caso_real_curtailment.csv"
ARQ_FIG = DOCS_REPORTS / "figura_caso_real_curtailment.png"


def cfg() -> dict:
    return carregar("analises")


# --------------------------------------------------------------------------- 1. episódios
def episodios(cortes: pd.DataFrame, inicio_base: pd.Series, tolerancia: int, folga_minima: int) -> pd.DataFrame:
    """Agrupa semi-horas com corte em episódios.

    cortes: linhas COM corte (chave, fonte, subsistema, timestamp, mw), qualquer ordem.
    inicio_base: primeiro instante de cada usina na base (índice = chave): a folga antes do
      primeiro episódio é contada a partir dele (antes disso não há como saber se havia corte).
    """
    c = cortes.sort_values(["chave", "timestamp"]).reset_index(drop=True)
    anterior = c.groupby("chave")["timestamp"].shift()
    passos = (c["timestamp"] - anterior) / PASSO                  # NaN no primeiro corte da usina
    novo = passos.isna() | (passos > tolerancia + 1)
    c["ep"] = novo.cumsum()
    # folga antes do episódio = semi-horas sem corte entre o fim do anterior e este início
    folga = (passos - 1).where(~passos.isna(),
                               (c["timestamp"] - c["chave"].map(inicio_base)) / PASSO)
    c["folga"] = folga.where(novo)
    ep = c.groupby("ep").agg(chave=("chave", "first"), fonte=("fonte", "first"),
                             subsistema=("subsistema", "first"), inicio=("timestamp", "min"),
                             fim=("timestamp", "max"), semihoras_com_corte=("timestamp", "size"),
                             energia_mwh=("mw", lambda s: 0.5 * s.sum(min_count=1)),
                             pico_mw=("mw", "max"), folga_antes_passos=("folga", "first"))
    ep["duracao_h"] = ((ep["fim"] - ep["inicio"]) / PASSO + 1) / 2
    ep["eh_inicio"] = ep["folga_antes_passos"] >= folga_minima
    return ep.reset_index(drop=True)


def ler_episodios(razao: str) -> pd.DataFrame:
    c = cfg()["episodios"]
    con = conectar()
    src = SAIDA_ROTULOS.as_posix()
    cortes = con.execute(f"""SELECT chave, fonte, subsistema, timestamp, corte_MW_{razao} AS mw
                             FROM '{src}' WHERE flag_{razao}""").df()
    inicio = con.execute(f"SELECT chave, min(timestamp) AS t FROM '{src}' GROUP BY chave").df()
    con.close()
    return episodios(cortes, inicio.set_index("chave")["t"], c["tolerancia_passos"], c["folga_minima_passos"])


# --------------------------------------------------------------------------- 2. lead time
def avisos_nos_inicios(ep: pd.DataFrame, razao: str) -> pd.DataFrame:
    """Probabilidade e persistência prevista para o instante de cada início, por horizonte."""
    r = razao.lower()
    inicios = ep.loc[ep["eh_inicio"], ["chave", "inicio"]].rename(columns={"inicio": "alvo"})
    con = conectar()
    con.register("inicios", inicios)
    df = con.execute(f"""SELECT p.chave, p.alvo, p.horizonte, p.p_{r} AS p,
                                p.base_persistencia_{r} AS persistencia
                         FROM '{mcur.ARQ_PREVISOES.as_posix()}' p JOIN inicios i
                           ON p.chave = i.chave AND p.alvo = i.alvo""").df()
    con.close()
    return df


def lead_time(av: pd.DataFrame, horizontes: dict[str, int], limiar: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(por horizonte: % de inícios avisados pelo modelo e pela persistência;
        por início: a MAIOR antecedência com aviso — o lead time útil)."""
    av = av.assign(aviso=av["p"] >= limiar, aviso_persistencia=av["persistencia"] >= limiar)
    por_h = av.groupby("horizonte").agg(inicios=("p", "size"), pct_avisados=("aviso", "mean"),
                                        pct_persistencia=("aviso_persistencia", "mean"),
                                        p_mediana=("p", "median")).reset_index()
    por_h[["pct_avisados", "pct_persistencia"]] *= 100
    por_h["_o"] = por_h["horizonte"].map(horizontes)
    por_h = por_h.sort_values("_o").drop(columns="_o")
    # lead time útil por início: maior h com aviso (só inícios com os 3 horizontes previstos)
    completos = av.groupby(["chave", "alvo"]).filter(lambda g: len(g) == len(horizontes)) if len(av) else av
    com_aviso = completos[completos["aviso"]].assign(passos=lambda d: d["horizonte"].map(horizontes))
    maior = com_aviso.groupby(["chave", "alvo"])["passos"].max()
    todos = completos.groupby(["chave", "alvo"]).size().index
    rotulo = {v: k for k, v in horizontes.items()}
    lt = maior.reindex(todos).map(rotulo).fillna("sem aviso")
    dist = (lt.value_counts(normalize=True) * 100).rename("pct_inicios").reset_index()
    dist.columns = ["maior_antecedencia_com_aviso", "pct_inicios"]
    ordem = [*sorted(rotulo, reverse=True)]
    dist["_o"] = dist["maior_antecedencia_com_aviso"].map({rotulo[p]: i for i, p in enumerate(ordem)}).fillna(99)
    return por_h, dist.sort_values("_o").drop(columns="_o")


# --------------------------------------------------------------------------- 3. caso real
def caso_real(razao: str, horizonte: str) -> tuple[pd.Timestamp, pd.DataFrame]:
    """Dia do teste com a maior fração de usinas cortadas numa semi-hora + a linha do tempo."""
    r = razao.lower()
    con = conectar()
    serie = con.execute(f"""SELECT alvo, count(*) AS usinas, avg(real_{r}) AS fracao_real,
                                   avg(p_{r}) AS fracao_prevista, sum(real_mw_{r}) AS mw_cortado,
                                   sum(montante_{r}) AS mw_esperado,
                                   sum((p_{r} >= {cfg()['episodios']['limiar_aviso']})::INT) AS usinas_em_alerta
                            FROM '{mcur.ARQ_PREVISOES.as_posix()}'
                            WHERE horizonte = '{horizonte}' AND real_{r} IS NOT NULL
                            GROUP BY alvo ORDER BY alvo""").df()
    con.close()
    serie["dia"] = serie["alvo"].dt.normalize()
    por_dia = serie.groupby("dia").agg(pico=("fracao_real", "max"), mwh=("mw_cortado", lambda s: 0.5 * s.sum()))
    dia = por_dia.sort_values(["pico", "mwh"], ascending=False).index[0]
    return dia, serie[serie["dia"] == dia].drop(columns="dia").reset_index(drop=True)


def desenhar_caso(dia: pd.Timestamp, t: pd.DataFrame, horizonte: str) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    cor_real, cor_prev = "#334155", cfg()["historico"]["cores"]["ENE"]
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(10, 6.5), sharex=True, gridspec_kw={"hspace": 0.15})
    x = t["alvo"]
    a1.plot(x, 100 * t["fracao_real"], color=cor_real, linewidth=2, label="real")
    a1.plot(x, 100 * t["fracao_prevista"], color=cor_prev, linewidth=2, linestyle="--",
            label=f"previsto na véspera ({horizonte})")
    a1.set_ylabel("Usinas com corte (%)")
    a2.plot(x, t["mw_cortado"], color=cor_real, linewidth=2, label="real")
    a2.plot(x, t["mw_esperado"], color=cor_prev, linewidth=2, linestyle="--",
            label=f"esperado na véspera ({horizonte})")
    a2.set_ylabel("Corte somado (MW)")
    for ax in (a1, a2):
        ax.legend(loc="upper left", frameon=False)
        ax.grid(axis="y", color="#e2e8f0", linewidth=0.8)
        ax.set_axisbelow(True)
        for lado in ("top", "right"):
            ax.spines[lado].set_visible(False)
    import matplotlib.dates as mdates
    a2.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    fig.suptitle(f"Caso real fora da amostra: {dia:%d/%m/%Y} — corte ENE de eólicas e solares", x=0.01,
                 ha="left", fontsize=12)
    fig.savefig(ARQ_FIG, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)


# --------------------------------------------------------------------------- relatório
def escrever() -> str:
    c = cfg()
    razao, limiar = c["episodios"]["razao"], c["episodios"]["limiar_aviso"]
    horizonte_caso = c["caso_real"]["horizonte"]
    horizontes = carregar("modelos_carga")["horizontes"]
    teste = pd.Timestamp(mcur.cfg()["split"]["inicio_teste"])

    ep = ler_episodios(razao)
    ensure(ARQ_EPISODIOS.parent)
    ep.to_parquet(ARQ_EPISODIOS, index=False)
    ep_teste = ep[ep["inicio"] >= teste]
    por_h, dist = lead_time(avisos_nos_inicios(ep_teste, razao), horizontes, limiar)
    dia, linha = caso_real(razao, horizonte_caso)
    ensure(DOCS_REPORTS)
    desenhar_caso(dia, linha, horizonte_caso)
    por_h.to_csv(ARQ_LEAD, index=False, float_format="%.3f")
    linha.to_csv(ARQ_CASO, index=False, float_format="%.3f")

    anual = ep.assign(ano=ep["inicio"].dt.year).groupby("ano").agg(
        episodios=("chave", "size"), inicios=("eh_inicio", "sum"), usinas=("chave", "nunique"),
        duracao_mediana_h=("duracao_h", "median"), energia_gwh=("energia_mwh", lambda s: s.sum() / 1000)).reset_index()
    pico = linha.loc[linha["fracao_real"].idxmax()]
    mwh_real, mwh_esp = 0.5 * linha["mw_cortado"].sum(), 0.5 * linha["mw_esperado"].sum()
    partes = [
        "# Episódios de corte, lead time e o caso real (Peça C)",
        "",
        "Gerado por `python run_heavywork.py` (etapa `analises`; código em `Backend/src/analise/episodios.py`). "
        "Não editar à mão.",
        "",
        f"- Razão: **{razao}**. Episódio = semi-horas com corte da mesma usina, com interrupções de até "
        f"{c['episodios']['tolerancia_passos'] * 30} min. Início = episódio depois de pelo menos "
        f"{c['episodios']['folga_minima_passos'] / 2:.0f} h sem corte naquela usina.",
        f"- Lead time e caso real: só o período de TESTE do classificador (a partir de {teste:%d/%m/%Y}), "
        "previsões fora da amostra. Aviso = probabilidade prevista >= "
        f"{limiar:.0%} (o mesmo limiar da precisão/recall em `classificador_curtailment.md`).",
        "",
        "## Episódios por ano",
        "",
        _md(anual, {"duracao_mediana_h": ".1f", "energia_gwh": ".0f"}),
        "",
        f"## Lead time: o sistema avisa o INÍCIO de um corte com quanta antecedência? ({len(ep_teste[ep_teste['eh_inicio']])} inícios no teste)",
        "",
        _md(por_h, {"pct_avisados": ".1f", "pct_persistencia": ".1f", "p_mediana": ".2f"}),
        "",
        "`pct_avisados`: % dos inícios com p >= limiar na emissão daquele horizonte. `pct_persistencia`: o mesmo "
        "para o baseline de persistência (havia corte na emissão?).",
        "",
        "Maior antecedência com aviso, por início (lead time útil):",
        "",
        _md(dist, {"pct_inicios": ".1f"}),
        "",
        f"## Caso real fora da amostra: {dia:%d/%m/%Y}",
        "",
        "![Caso real](figura_caso_real_curtailment.png)",
        "",
        f"- Escolhido automaticamente: o dia do teste com a maior fração de usinas cortadas por {razao} ao mesmo tempo "
        f"(**{pico['fracao_real']:.0%}** das {int(pico['usinas'])} usinas às {pico['alvo']:%H:%M}).",
        f"- Na véspera ({horizonte_caso}), para esse mesmo instante, o sistema previa em média "
        f"**{pico['fracao_prevista']:.0%}** de probabilidade de corte e punha **{int(pico['usinas_em_alerta'])}** usinas "
        f"em alerta (p >= {limiar:.0%}).",
        f"- Energia cortada no dia: {_milhar(mwh_real)} MWh reais × {_milhar(mwh_esp)} MWh esperados na véspera.",
        "",
    ]
    ARQ_MD.write_text("\n".join(partes), encoding="utf-8")
    return f"{_milhar(len(ep))} episódios; relatório em docs/reports/{ARQ_MD.name}"
