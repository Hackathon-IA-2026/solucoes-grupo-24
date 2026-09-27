"""Demanda bruta (carga global) para MESES à frente — Fase 1 da especificação do preditivo.

Especificação: docs/oraculo/especificacao/17-previsao-meses-carga-mmgd-pato.md (§5.5, camada 2). Parâmetros em
config/demanda_meses.yaml. Etapa `demanda_meses` do run_heavywork.py.

Modelo, por série (SE, S, NE, N, SIN), numa emissão E, para cada hora t dos meses seguintes:

    D̂(t) = B × C(E, t) × S(mês) × P̃(hora, dia-tipo, mês | mês alvo) + β(mês, hora) × a(t)

- B: média da demanda nos 12 meses antes de E (nível dessazonalizado, "centrado" em E − 6 meses).
- C: crescimento entre o centro de B e t. Backtest: taxa anual histórica (últimos 12 meses ÷ 12
  anteriores, só passado). Para a frente: trajetória do PLAN 2026-2030 2ª RQ (publicado em
  07/08/2026, antes da emissão para a frente; no backtest seria vazamento).
- S(mês): índice sazonal mensal = média mensal ÷ média móvel centrada de 12 meses (2×12 MA),
  média dos últimos `perfil_anos` anos.
- P̃: perfil horário normalizado (demanda ÷ média do próprio mês) por mês × dia-tipo × hora, dos
  últimos `perfil_anos` anos, e renormalizado DENTRO do mês alvo (a mistura de dias úteis,
  sábados e domingos/feriados muda de um mês para outro; a média do mês fica = B × C × S).
- β × a: sensibilidade à temperatura. a(t) = temperatura − climatologia (mês, hora) do ERA5;
  β por mês e hora, regressão do desvio intramensal da demanda contra o desvio intramensal da
  temperatura (os dois centrados no mês, para não confundir tempo com nível).
  Variante `era5`: a(t) observada nos alvos ("tempo perfeito": teto do que o tempo previsto dá).
  Variante `clim`: a(t) = 0 (sem tempo): o que se tem para meses até o SEAS5 entrar (Fase 2).
- Banda P10–P90: quantis do erro relativo (real ÷ P50) por horizonte (mês 1..6) e hora do dia,
  medidos nas emissões anteriores cujos alvos já tinham acontecido antes de E (só passado).

Dia-tipo: útil / sábado / domingo-ou-feriado (feriado tratado como domingo: coluna
`dia_semana_efetivo` do calendário). Resolução horária (MWmed = média das duas semi-horas): a
especificação trabalha em hora para meses; a carga supervisionada de 30 min do resto do projeto
não muda.

Garantia contra vazamento: `prever_emissao` recorta o histórico em `timestamp < E` ANTES de
qualquer conta (tests/test_demanda_meses.py perturba tudo depois de E e exige previsão idêntica).
A única informação de depois de E é a temperatura observada na variante `era5`, declarada como
"tempo perfeito" e nunca publicada como previsão.
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from src.processing.saidas import SAIDA_CALENDARIO, SAIDA_CARGA
from src.utils.config import carregar
from src.utils.paths import RAIZ, RAIZ_REPO, ensure

log = logging.getLogger("demanda_meses")

# Dia-tipo a partir de `dia_semana_efetivo` (0 = segunda ... 6 = domingo; feriado já vem 6).
DIA_TIPO = {0: "util", 1: "util", 2: "util", 3: "util", 4: "util", 5: "sabado", 6: "domingo"}
ANO = pd.Timedelta(days=365.25)


def cfg() -> dict:
    return carregar("demanda_meses")


def saida(rel: str):
    """Caminho de uma saída de config: `docs/...` é relativo à raiz do repositório, o resto a
    Backend/. Usado também pelo preditivo de MMGD e da curva do pato (src/models/*_meses.py)."""
    return (RAIZ_REPO if rel.startswith("docs/") else RAIZ) / rel


def caminho(chave: str):
    """Saídas da config da demanda de meses."""
    return saida(cfg()["saidas"][chave])


# --------------------------------------------------------------------------- dados
def carregar_horario() -> pd.DataFrame:
    """Demanda bruta horária por série + calendário (dia-tipo, patamar).

    Colunas: serie, timestamp (início da hora, horário local do projeto), y (MWmed), dia_tipo,
    patamar, mes, hora. SIN = soma dos 4 subsistemas só nas horas em que os 4 existem.
    """
    c = cfg()
    g = horario_largo(c["alvo"])
    longo = g[c["series"]].stack().rename("y").reset_index()
    longo.columns = ["timestamp", "serie", "y"]
    return longo.merge(calendario_horario(), on="timestamp", how="left")


def horario_largo(coluna: str) -> pd.DataFrame:
    """Uma coluna da carga processada na grade horária, largo: índice = hora, colunas = séries.

    Semi-hora -> hora: média das duas semi-horas (MWmed); hora com só uma semi-hora é
    descartada. SIN = soma dos 4 subsistemas só nas horas em que os 4 existem (soma parcial
    nunca vira SIN). Mesma regra para a demanda (carga global) e para a MMGD do ONS.
    """
    c = cfg()
    d = pd.read_csv(SAIDA_CARGA, usecols=["subsistema", "timestamp", coluna], parse_dates=["timestamp"])
    d = d[d["timestamp"] >= pd.Timestamp(c["inicio_dados"])]
    d["hora_ini"] = d["timestamp"].dt.floor("h")
    g = d.groupby(["subsistema", "hora_ini"])[coluna].agg(["mean", "count"])
    g = g[g["count"] == 2]["mean"].unstack("subsistema")
    ss = [s for s in c["series"] if s != "SIN"]
    if "SIN" in c["series"]:
        g["SIN"] = g[ss].sum(axis=1, min_count=len(ss))
    g.index.name = "timestamp"
    return g


def calendario_horario() -> pd.DataFrame:
    """Calendário na grade horária (a 1ª semi-hora de cada hora representa a hora).

    O calendário processado vai até o fim do ano seguinte, com feriados futuros: serve também
    para a previsão para a frente.
    """
    cal = pd.read_csv(SAIDA_CALENDARIO, usecols=["timestamp", "dia_semana_efetivo", "patamar"],
                      parse_dates=["timestamp"])
    cal = cal[cal["timestamp"].dt.minute == 0].copy()
    cal["dia_tipo"] = cal["dia_semana_efetivo"].map(DIA_TIPO)
    cal["mes"] = cal["timestamp"].dt.month
    cal["hora"] = cal["timestamp"].dt.hour
    return cal[["timestamp", "dia_tipo", "patamar", "mes", "hora"]]


def temperatura_horaria(serie: str, inicio: pd.Timestamp, fim: pd.Timestamp) -> pd.Series | None:
    """Temperatura ERA5 da área (média das capitais ponderada pela população), por hora.

    Reusa o cliente Open-Meteo do protótipo (oraculo/tempo/clima.py, com cache): uma fonte só.
    Sem rede e sem cache devolve None e a variante `era5` fica de fora (nunca inventa tempo).
    """
    from oraculo.tempo.clima import weather_for_area  # import tardio: só esta etapa precisa

    idx = pd.date_range(inicio.floor("h"), fim.floor("h"), freq="h")
    tempo, prov = weather_for_area(idx.values.astype("datetime64[s]"), serie)
    if tempo is None:
        log.warning("sem temperatura ERA5 para %s: %s", serie, prov.get("lag_note"))
        return None
    return pd.Series(tempo["temperature"], index=idx, name="temperatura")


# --------------------------------------------------------------------------- crescimento
def taxa_historica(hist: pd.DataFrame, emissao: pd.Timestamp, meses: int) -> float:
    """Crescimento anual = média dos últimos `meses` meses ÷ média dos `meses` anteriores − 1."""
    a = hist[hist["timestamp"] >= emissao - pd.DateOffset(months=meses)]["y"].mean()
    b = hist[(hist["timestamp"] >= emissao - pd.DateOffset(months=2 * meses))
             & (hist["timestamp"] < emissao - pd.DateOffset(months=meses))]["y"].mean()
    return float(a / b - 1.0)


def fator_plan(centro: pd.Timestamp, alvos: pd.Series) -> np.ndarray:
    """Crescimento do centro do nível até cada alvo pela carga global do SIN no PLAN 2026-2030.

    Os valores anuais (MWmed) são postos no meio de cada ano e interpolados linearmente; a
    razão entre o alvo e o centro é o fator. Aplica-se a TAXA do PLAN, não o nível (bases
    diferentes), e a mesma taxa a todos os subsistemas (o config do PLAN só traz o SIN).
    """
    from oraculo.config import ENE  # fonte única dos números transcritos do PLAN

    plan = ENE["plan"]["carga_global_mwmed"]
    anos = sorted(plan)
    x = np.array([pd.Timestamp(f"{a}-07-02").value for a in anos], dtype="f8")
    y = np.array([plan[a] for a in anos], dtype="f8")
    base = np.interp(pd.Timestamp(centro).value, x, y)
    # Fixa a resolução em ns antes de virar inteiro (datetime64[s] daria a escala errada).
    t = alvos.to_numpy(dtype="datetime64[ns]").astype("int64").astype("f8")
    return np.interp(t, x, y) / base


# --------------------------------------------------------------------------- ajuste
def _medias_mensais(hist: pd.DataFrame) -> pd.Series:
    """Média mensal só de meses completos (≥ 90% das horas)."""
    m = hist.set_index("timestamp")["y"].resample("MS").agg(["mean", "count"])
    horas = m.index.days_in_month * 24
    return m["mean"][m["count"] >= 0.9 * horas]


def indice_sazonal(hist: pd.DataFrame) -> pd.Series:
    """S(mês): média mensal ÷ média móvel centrada 2×12, média por mês do calendário."""
    mm = _medias_mensais(hist).asfreq("MS")
    ma = mm.rolling(12, center=True).mean().rolling(2).mean().shift(-1)
    r = (mm / ma).dropna()
    s = r.groupby(r.index.month).mean()
    return s / s.mean()  # índice médio = 1: o nível B já é a média anual


def ajustar(hist: pd.DataFrame, temp: pd.Series | None) -> dict:
    """Perfil, índice sazonal, climatologia de temperatura e β, só com `hist` (passado)."""
    h = hist.copy()
    mm = _medias_mensais(h)
    h["mes_ini"] = h["timestamp"].dt.to_period("M").dt.to_timestamp()
    h = h[h["mes_ini"].isin(mm.index)]
    h["rel"] = h["y"] / h["mes_ini"].map(mm)
    perfil = h.groupby(["mes", "dia_tipo", "hora"])["rel"].mean()
    modelo = {"perfil": perfil, "sazonal": indice_sazonal(hist), "beta": None, "clim_t": None}
    if temp is not None:
        h["t"] = h["timestamp"].map(temp)
        h = h.dropna(subset=["t"])
        clim_t = h.groupby(["mes", "hora"])["t"].mean()
        # Desvios INTRAMENSAIS (centrados no mês): o nível do mês já vem de B × C × S.
        h["ey"] = h["y"] - h["mes_ini"].map(mm) * h.set_index(["mes", "dia_tipo", "hora"]).index.map(perfil)
        h["et"] = h["t"] - h.groupby("mes_ini")["t"].transform("mean")
        h["ey"] = h["ey"] - h.groupby("mes_ini")["ey"].transform("mean")
        # β = cov/var por mês × hora (OLS sem intercepto sobre desvios centrados).
        g = h.assign(xy=h["ey"] * h["et"], xx=h["et"] ** 2).groupby(["mes", "hora"])[["xy", "xx"]].sum()
        modelo["beta"] = (g["xy"] / g["xx"]).where(g["xx"] > 0, 0.0)
        modelo["clim_t"] = clim_t
    return modelo


def prever_emissao(dados: pd.DataFrame, emissao: pd.Timestamp, meses: int, temp: pd.Series | None,
                   cal: pd.DataFrame, tendencia: str = "historico") -> pd.DataFrame:
    """P50 horário de UMA série nos `meses` meses a partir de `emissao`, variantes era5 e clim.

    `dados` é o histórico da série (pode conter o futuro: é recortado aqui, antes de tudo).
    `cal` é o calendário horário (dá dia-tipo e patamar das horas futuras).
    Devolve: timestamp, horizonte (mês 1..N), mes, hora, patamar, p50_clim e (se houver
    temperatura) p50_era5.
    """
    c = cfg()
    emissao = pd.Timestamp(emissao)
    hist = dados[dados["timestamp"] < emissao]  # ← corte temporal: nada depois daqui é usado
    ini_perfil = emissao - pd.DateOffset(years=c["perfil_anos"])
    # O índice sazonal precisa de 12 meses de cada lado da média centrada: janela +1 ano.
    janela = hist[hist["timestamp"] >= ini_perfil - pd.DateOffset(years=1)]
    recente = hist[hist["timestamp"] >= ini_perfil]
    t_passado = temp[temp.index < emissao] if temp is not None else None
    modelo = ajustar(recente, t_passado)
    modelo["sazonal"] = indice_sazonal(janela)

    nmeses = c["crescimento_janela_meses"]
    base = hist[hist["timestamp"] >= emissao - pd.DateOffset(months=12)]["y"].mean()
    centro = emissao - pd.DateOffset(months=6)
    fim = emissao + pd.DateOffset(months=meses)
    fut = cal[(cal["timestamp"] >= emissao) & (cal["timestamp"] < fim)].copy()
    if tendencia == "plan":
        cresc = fator_plan(centro, fut["timestamp"])
    else:
        g = taxa_historica(hist, emissao, nmeses)
        cresc = (1.0 + g) ** ((fut["timestamp"] - centro) / ANO).to_numpy()

    fut["horizonte"] = ((fut["timestamp"].dt.year - emissao.year) * 12
                        + fut["timestamp"].dt.month - emissao.month + 1)
    fut["mes_ini"] = fut["timestamp"].dt.to_period("M").dt.to_timestamp()
    p = fut.set_index(["mes", "dia_tipo", "hora"]).index.map(modelo["perfil"]).to_numpy(dtype="f8")
    fut["p"] = p / pd.Series(p, index=fut.index).groupby(fut["mes_ini"]).transform("mean")
    fut["p50_clim"] = base * cresc * fut["mes"].map(modelo["sazonal"]).to_numpy() * fut["p"]
    if modelo["beta"] is not None and temp is not None:
        chave = fut.set_index(["mes", "hora"]).index
        anomalia = fut["timestamp"].map(temp).to_numpy() - chave.map(modelo["clim_t"]).to_numpy(dtype="f8")
        # β e climatologia saem junto: a curva do pato aplica a MESMA sensibilidade à temperatura
        # de cada membro do ensemble (D_m = p50_clim + β × (T_m − t_clim)).
        fut["beta"] = chave.map(modelo["beta"]).to_numpy(dtype="f8")
        fut["t_clim"] = chave.map(modelo["clim_t"]).to_numpy(dtype="f8")
        fut["p50_era5"] = fut["p50_clim"] + fut["beta"] * anomalia
    return fut.drop(columns=["p", "mes_ini", "dia_tipo"])


# --------------------------------------------------------------------------- baselines
def baselines(dados: pd.DataFrame, emissao: pd.Timestamp, alvos: pd.Series, nmeses: int) -> pd.DataFrame:
    """Baselines obrigatórios da spec (§7), só com o passado de `emissao`.

    - sazonal_ingenuo: mesmo horário 364 dias antes (mesmo dia da semana) × crescimento anual
      histórico. Com horizonte ≤ 6 meses, t − 364 d é sempre anterior à emissão.
    - persistencia_semanal: a última semana completa antes da emissão, repetida.
    """
    hist = dados[dados["timestamp"] < pd.Timestamp(emissao)].set_index("timestamp")["y"]
    g = taxa_historica(dados[dados["timestamp"] < emissao], emissao, nmeses)
    ano = alvos - pd.Timedelta(days=364)
    if (ano >= emissao).any():
        raise ValueError("sazonal ingênuo pediria dado posterior à emissão (horizonte > 364 dias)")
    semanas = np.ceil(((alvos - emissao) + pd.Timedelta(hours=1)) / pd.Timedelta(days=7))
    sem = alvos - pd.to_timedelta(semanas * 7, unit="D")
    return pd.DataFrame({
        "sazonal_ingenuo": hist.reindex(ano).to_numpy() * (1.0 + g),
        "persistencia_semanal": hist.reindex(sem).to_numpy(),
    }, index=alvos.index)


# --------------------------------------------------------------------------- backtest
def emissoes_backtest(ultimo: pd.Timestamp) -> list[pd.Timestamp]:
    """Emissões mensais: as de calibração da banda antes do teste + as do teste até o fim."""
    b = cfg()["backtest"]
    primeira = pd.Timestamp(b["primeira_emissao"])
    ini = primeira - pd.DateOffset(months=b["calibracao_emissoes"] + b["horizonte_meses"])
    return list(pd.date_range(ini, ultimo, freq="MS"))


def backtest(dados: pd.DataFrame | None = None) -> pd.DataFrame:
    """Previsões fora da amostra de todas as emissões, séries e variantes, com o real."""
    c = cfg()
    dados = carregar_horario() if dados is None else dados
    cal = calendario_horario()
    b = c["backtest"]
    ultimo = dados["timestamp"].max()
    saida = []
    for serie in c["series"]:
        ds = dados[dados["serie"] == serie][["timestamp", "y", "mes", "hora", "dia_tipo"]]
        temp = temperatura_horaria(serie, ds["timestamp"].min(), ultimo) if "era5" in c["variantes"] else None
        for em in emissoes_backtest(ultimo):
            f = prever_emissao(ds, em, b["horizonte_meses"], temp, cal)
            f = f[f["timestamp"] <= ultimo]
            f = f.join(baselines(ds, em, f["timestamp"], c["crescimento_janela_meses"]))
            f["y"] = f["timestamp"].map(ds.set_index("timestamp")["y"])
            f["serie"], f["emissao"] = serie, em
            saida.append(f.dropna(subset=["y"]))
        log.info("backtest %s: %d emissões", serie, len(emissoes_backtest(ultimo)))
    bt = pd.concat(saida, ignore_index=True)
    return adicionar_bandas(bt, [v for v in c["variantes"] if f"p50_{v}" in bt])


def passado(bt: pd.DataFrame, emissao: pd.Timestamp, n: int) -> pd.DataFrame:
    """Linhas das últimas `n` emissões anteriores a `emissao`, só com alvos já ocorridos nela.

    Toda calibração (banda, resíduos, conformal) sai daqui: nada que a emissão não conheceria.
    """
    antes = bt[(bt["emissao"] < emissao) & (bt["timestamp"] < emissao)]
    ems = sorted(antes["emissao"].unique())[-n:]
    return antes[antes["emissao"].isin(ems)]


def quantis_razao(bt: pd.DataFrame, col_y: str, col_p: str, emissao: pd.Timestamp, n: int,
                  niveis: list[float], chaves=("serie", "horizonte", "hora")) -> pd.DataFrame:
    """Quantis (`niveis`) do erro relativo real ÷ previsto por `chaves`, só com o passado.

    Colunas: um nível por coluna (float) + `n` (tamanho da amostra).
    """
    antes = passado(bt, emissao, n)
    r = (antes[col_y] / antes[col_p]).rename("r")
    grp = pd.concat([antes[list(chaves)], r], axis=1).dropna().groupby(list(chaves))["r"]
    if antes.empty:  # 1ª emissão: sem passado, sem quantil (NaN), nunca inventado
        return pd.DataFrame(columns=[*niveis, "n"], dtype="f8")
    out = grp.quantile(niveis).unstack()
    out["n"] = grp.size()
    return out


def fatores_banda(bt: pd.DataFrame, variante: str, emissao: pd.Timestamp) -> pd.DataFrame:
    """Fatores P10 e P90 (erro relativo) por série, horizonte e hora da demanda."""
    c = cfg()
    q = c["quantis"]
    f = quantis_razao(bt, "y", f"p50_{variante}", emissao, c["backtest"]["calibracao_emissoes"], [q[0], q[-1]])
    return f.rename(columns={q[0]: "f_lo", q[-1]: "f_hi"})


def conformal(bt: pd.DataFrame, col_y: str, col_lo: str, col_hi: str, emissao: pd.Timestamp,
              n: int, cobertura: float, chaves=("serie", "horizonte")) -> pd.Series:
    """Alargamento conformal (CQR, Romano et al. 2019) da banda, por `chaves`, só com o passado.

    Escore = max(lo − y, y − hi); o alargamento é o quantil `cobertura` (com a correção de
    amostra finita) dos escores das últimas `n` emissões. Negativo = a banda encolhe.
    """
    antes = passado(bt, emissao, n)
    if antes.empty:
        return pd.Series(dtype="f8")
    s = np.maximum(antes[col_lo] - antes[col_y], antes[col_y] - antes[col_hi]).rename("s")
    grp = pd.concat([antes[list(chaves)], s], axis=1).dropna().groupby(list(chaves))["s"]
    return grp.apply(lambda x: np.quantile(x, min(1.0, cobertura * (1 + 1 / len(x)))))


def aplicar_conformal(df: pd.DataFrame, q: pd.Series, col_lo: str, col_hi: str,
                      chaves=("serie", "horizonte")) -> None:
    """Soma o alargamento `q` à banda de `df` (in place). Sem calibração passada: banda base."""
    k = pd.MultiIndex.from_frame(df[list(chaves)]) if len(chaves) > 1 else pd.Index(df[chaves[0]])
    d = k.map(q).to_numpy(dtype="f8")
    d = np.nan_to_num(d, nan=0.0)
    df[col_lo] = df[col_lo] - d
    df[col_hi] = df[col_hi] + d


def adicionar_bandas(bt: pd.DataFrame, variantes: list[str]) -> pd.DataFrame:
    """P10/P90 de cada emissão, só com o passado dela, em dois passos.

    1. Base: quantis do erro relativo por série × horizonte × hora (`p10_<v>_base`).
    2. Conformal: alargamento por série × horizonte medido nas bandas BASE das emissões
       anteriores (`conformal` da config). Sem ele a banda cobria 56–73%, não 80% (1º backtest).
    Horizonte sem erro passado fica sem banda (NaN), nunca inventada.
    """
    c = cfg()
    out = []
    for em, g in bt.groupby("emissao"):
        g = g.copy()
        for v in variantes:
            f = fatores_banda(bt, v, em)
            k = g.set_index(["serie", "horizonte", "hora"]).index
            g[f"p10_{v}_base"] = g[f"p50_{v}"].to_numpy() * k.map(f["f_lo"]).to_numpy(dtype="f8")
            g[f"p90_{v}_base"] = g[f"p50_{v}"].to_numpy() * k.map(f["f_hi"]).to_numpy(dtype="f8")
        out.append(g)
    bt = pd.concat(out, ignore_index=True)
    cf = c["conformal"]
    out = []
    for em, g in bt.groupby("emissao"):
        g = g.copy()
        for v in variantes:
            g[f"p10_{v}"], g[f"p90_{v}"] = g[f"p10_{v}_base"], g[f"p90_{v}_base"]
            q = conformal(bt, "y", f"p10_{v}_base", f"p90_{v}_base", em, cf["emissoes"], cf["cobertura"])
            aplicar_conformal(g, q, f"p10_{v}", f"p90_{v}")
        out.append(g)
    return pd.concat(out, ignore_index=True)


# --------------------------------------------------------------------------- métricas
def _pinball(y, q, tau):
    d = y - q
    return np.mean(np.maximum(tau * d, (tau - 1) * d))


def metricas(bt: pd.DataFrame) -> pd.DataFrame:
    """Métricas do TESTE (emissões ≥ primeira_emissao) por série, modelo e horizonte."""
    c = cfg()
    teste = bt[bt["emissao"] >= pd.Timestamp(c["backtest"]["primeira_emissao"])]
    modelos = [v for v in c["variantes"] if f"p50_{v}" in teste] + ["sazonal_ingenuo", "persistencia_semanal"]
    linhas = []
    for (serie, hz), g in teste.groupby(["serie", "horizonte"]):
        mae_base = {}
        for m in modelos:
            col = f"p50_{m}" if m in c["variantes"] else m
            ok = g[col].notna()
            e = g.loc[ok, "y"] - g.loc[ok, col]
            mae_base[m] = e.abs().mean()
            lin = {"serie": serie, "horizonte_mes": hz, "modelo": m, "n_horas": int(ok.sum()),
                   "emissoes": g.loc[ok, "emissao"].nunique(),
                   "mae_mw": e.abs().mean(), "rmse_mw": np.sqrt((e ** 2).mean()),
                   "mape_pct": 100 * (e.abs() / g.loc[ok, "y"]).mean(), "vies_mw": -e.mean()}
            for pat in ("minima_diurna", "ponta_noturna"):
                sel = ok & (g["patamar"] == pat)
                lin[f"mae_{pat}_mw"] = (g.loc[sel, "y"] - g.loc[sel, col]).abs().mean()
            if m in c["variantes"] and f"p10_{m}" in g:
                b = ok & g[f"p10_{m}"].notna()
                yb = g.loc[b, "y"]
                lin["cobertura_p10_p90"] = ((yb >= g.loc[b, f"p10_{m}"]) & (yb <= g.loc[b, f"p90_{m}"])).mean()
                lin["pinball_medio"] = np.mean([_pinball(yb, g.loc[b, f"p{int(t*100)}_{m}"], t)
                                                for t in c["quantis"]])
            linhas.append(lin)
        for lin in linhas[-len(modelos):]:
            lin["skill_vs_sazonal_ingenuo"] = 1 - lin["mae_mw"] / mae_base["sazonal_ingenuo"]
            lin["skill_vs_persistencia_semanal"] = 1 - lin["mae_mw"] / mae_base["persistencia_semanal"]
    return pd.DataFrame(linhas)


# --------------------------------------------------------------------------- previsão para a frente
def prever_frente(dados: pd.DataFrame | None = None, bt: pd.DataFrame | None = None) -> pd.DataFrame:
    """Previsão emitida logo depois do último dado, P10/P50/P90 horários, variante da config.

    A banda usa os erros relativos da mesma variante nas últimas emissões do backtest.
    """
    c = cfg()
    p = c["previsao"]
    v = p["variante"]
    dados = carregar_horario() if dados is None else dados
    bt = backtest(dados) if bt is None else bt
    cal = calendario_horario()
    emissao = dados["timestamp"].max() + pd.Timedelta(hours=1)
    saida = []
    for serie in c["series"]:
        ds = dados[dados["serie"] == serie][["timestamp", "y", "mes", "hora", "dia_tipo"]]
        f = prever_emissao(ds, emissao, p["horizonte_meses"], None, cal, tendencia=p["tendencia"])
        f["serie"], f["emissao"] = serie, emissao
        saida.append(f)
    fr = pd.concat(saida, ignore_index=True)
    fat = fatores_banda(bt, v, emissao)
    # Emissão no meio do mês: o último mês (parcial) vira horizonte N+1, que o backtest não
    # mede; ele usa os fatores do horizonte N (o mais longo medido), premissa declarada.
    fr["hz_banda"] = fr["horizonte"].clip(upper=c["backtest"]["horizonte_meses"])
    k = pd.MultiIndex.from_arrays([fr["serie"], fr["hz_banda"], fr["hora"]])
    fr = fr.rename(columns={f"p50_{v}": "p50"})
    fr["p10"] = fr["p50"].to_numpy() * k.map(fat["f_lo"]).to_numpy(dtype="f8")
    fr["p90"] = fr["p50"].to_numpy() * k.map(fat["f_hi"]).to_numpy(dtype="f8")
    cf = c["conformal"]
    q = conformal(bt, "y", f"p10_{v}_base", f"p90_{v}_base", emissao, cf["emissoes"], cf["cobertura"])
    aplicar_conformal(fr, q, "p10", "p90", chaves=("serie", "hz_banda"))
    fr["variante"], fr["tendencia"] = v, p["tendencia"]
    return fr[["serie", "emissao", "timestamp", "horizonte", "mes", "hora", "patamar",
               "p10", "p50", "p90", "variante", "tendencia"]]


# --------------------------------------------------------------------------- etapa
def executar() -> str:
    """Etapa `demanda_meses` do run_heavywork: backtest + métricas + previsão + relatório."""
    from src.models import relatorio_demanda_meses as rel

    dados = carregar_horario()
    bt = backtest(dados)
    ensure(caminho("backtest").parent)
    bt.to_parquet(caminho("backtest"), index=False)
    met = metricas(bt)
    fr = prever_frente(dados, bt)
    ensure(caminho("previsao").parent)
    fr.to_parquet(caminho("previsao"), index=False)
    rel.escrever(met, fr, bt)
    return (f"backtest {bt['emissao'].nunique()} emissões × {bt['serie'].nunique()} séries; "
            f"previsão {fr['timestamp'].min():%Y-%m-%d} a {fr['timestamp'].max():%Y-%m-%d}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(executar())
