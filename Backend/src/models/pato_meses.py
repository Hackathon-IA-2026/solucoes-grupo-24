"""MMGD e curva do pato prevista para MESES à frente — Fases 2 e 3 de
docs/oraculo/especificacao/17-previsao-meses-carga-mmgd-pato.md. Config: config/pato_meses.yaml.

Cadeia, numa emissão E, por subsistema (SE, S, NE, N) e SIN:

    D_k(t) = demanda de meses (src/models/demanda_meses.py, Fase 1) com a temperatura do membro k
    G_k(t) = Cap(t) × PR × U(t − k anos)             MMGD física (oraculo/tempo/pato.pv_mw)
    L_k(t) = D_k(t) − G_k(t)                         carga líquida = curva do pato prevista

- Membro k = ano-análogo: a sequência horária REAL do ERA5 k anos antes (radiação e temperatura).
  O MESMO membro alimenta demanda (temperatura) e MMGD (radiação): dia de sol forte é quente, a
  carga sobe e a MMGD também (spec §5.6). Só entram análogos anteriores à emissão.
- U(t): geração por MW instalado com PR = 1, média das células de ~2,5° do subsistema pesada pela
  MMGD cadastrada em cada célula (oraculo/tempo/pato.clusters sobre a base da Fronteira T–D).
- Cap(t): cadastro acumulado da ANEEL no subsistema (capacidade_mmgd.csv), projetado a partir de
  (E − defasagem de cadastro). Backtest: taxa histórica do cadastro. Para a frente: cenários
  baixo (PAR/PEL 2025) / referência (PLAN 2026-2030 2ª RQ) / alto (taxa histórica).
- PR por subsistema recalibrado em cada emissão para a física reproduzir a MMGD do ONS nos 12
  meses anteriores (spec §5.4; a MMGD do ONS é estimativa, o viés dela é herdado e declarado).
- Quantis: sobre os membros, alargados por calibração conformal (CQR, a mesma função da Fase 1)
  medida nas emissões anteriores — sem ela o conjunto de ~6 membros cobre pouco.
- Métricas do pato por dia: barriga = mínimo de L na mínima diurna, ponta = máximo na ponta
  noturna, rampa = ponta − barriga (patamares do CLAUDE.md, config `pato`).

Garantia contra vazamento: demanda recortada em E (demanda_meses.prever_emissao); PR, limiar de
risco e conformal só com alvos < E; membros só com tempo < E (tests/test_pato_meses.py).
"""
from __future__ import annotations

import json
import logging

import numpy as np
import pandas as pd

from src.models import demanda_meses as dm
from src.processing.saidas import SAIDA_CAPACIDADE_MMGD
from src.utils.config import carregar
from src.utils.paths import ensure

log = logging.getLogger("pato_meses")

SUBS = ("SE", "S", "NE", "N")


def cfg() -> dict:
    return carregar("pato_meses")


def caminho(chave: str):
    return dm.saida(cfg()["saidas"][chave])


# --------------------------------------------------------------------------- A. células e capacidade
def celulas() -> pd.DataFrame:
    """Células de MMGD (id, ss, mw, lat, lon, mun) a partir da MMGD por município (Fronteira T–D).

    Sem a base da Fronteira não há como localizar a MMGD: erro com instrução, nunca inventa.
    """
    from oraculo.fronteira import base as FB
    from oraculo.tempo import pato as P

    c = cfg()["celulas"]
    fb = FB.load_cached()
    if fb is None:
        raise RuntimeError("falta a base da Fronteira T–D (MMGD por município): rode a Fronteira antes")
    pts = P.clusters(fb["mun"], fb["centroid"], cell_deg=c["graus"], min_mw=c["min_mw"])
    df = pd.DataFrame(pts)
    df["id"] = [f"{r.ss}{i:02d}" for i, r in enumerate(df.itertuples())]
    return df[["id", "ss", "mw", "lat", "lon", "mun"]]


def cap_ss_diaria() -> pd.DataFrame:
    """Cadastro acumulado de MMGD (MW) por subsistema e dia, só com o que já estava cadastrado."""
    from oraculo.tempo.pato import UF_SS

    cap = pd.read_csv(SAIDA_CAPACIDADE_MMGD, parse_dates=["data"])
    w = cap.pivot_table(index="data", columns="uf", values="potencia_acumulada_mw", aggfunc="last")
    w = w.reindex(pd.date_range(w.index.min(), w.index.max(), freq="D")).ffill().fillna(0.0)
    return w.T.groupby(w.columns.map(UF_SS)).sum().T[list(SUBS)]


def _taxa_plan(chave: str):
    """Trajetórias oficiais (oraculo/config.py ENE): função t -> capacidade relativa."""
    from oraculo.config import ENE

    if chave == "referencia":
        gw = ENE["plan"]["mmgd_gw"]  # capacidade no fim de cada ano
        x = np.array([pd.Timestamp(f"{a}-12-31").value for a in sorted(gw)], dtype="f8")
        y = np.array([gw[a] for a in sorted(gw)], dtype="f8")
        return lambda t: np.interp(np.asarray(t, dtype="datetime64[ns]").astype("int64").astype("f8"), x, y)
    pp = ENE["parpel"]  # dez/2025 -> fim de 2029: taxa anual composta
    r = (pp["mmgd_2029_gw"] / pp["mmgd_dez2025_gw"]) ** (1 / 4) - 1
    t0 = pd.Timestamp("2025-12-31")
    return lambda t: pp["mmgd_dez2025_gw"] * (1 + r) ** ((pd.DatetimeIndex(t) - t0) / dm.ANO)


def cap_projetada(capd: pd.DataFrame, emissao: pd.Timestamp, alvos: pd.DatetimeIndex,
                  cenario: str = "historico") -> pd.DataFrame:
    """Capacidade (MW) por subsistema nos alvos, projetada só com o cadastro anterior à emissão.

    Parte de t0 = E − defasagem (o cadastro recente é sub-registrado). historico/alto: taxa do
    cadastro nos 12 meses até t0; referencia: PLAN; baixo: PAR/PEL (aplica-se a TAXA ao nível
    do cadastro, bases diferentes).
    """
    c = cfg()["capacidade"]
    t0 = (emissao - pd.DateOffset(months=c["defasagem_cadastro_meses"])).normalize()
    t0 = min(t0, capd.index.max())
    c0 = capd.loc[:t0].iloc[-1]
    anos = ((alvos - t0) / dm.ANO).to_numpy()
    if cenario in ("historico", "alto"):
        c1 = capd.loc[:t0 - pd.DateOffset(months=c["janela_taxa_meses"])].iloc[-1]
        g = (c0 / c1) - 1.0
        fat = (1.0 + g.to_numpy())[None, :] ** anos[:, None]
        return pd.DataFrame(c0.to_numpy()[None, :] * fat, index=alvos, columns=capd.columns)
    f = _taxa_plan(cenario)
    rel = np.asarray(f(alvos), dtype="f8") / float(np.asarray(f(pd.DatetimeIndex([t0])), dtype="f8")[0])
    return pd.DataFrame(c0.to_numpy()[None, :] * rel[:, None], index=alvos, columns=capd.columns)


# --------------------------------------------------------------------------- B. tempo
def tempo_celulas(cel: pd.DataFrame, fim: pd.Timestamp) -> tuple[pd.DataFrame, pd.DataFrame]:
    """GHI (W/m²) e temperatura (°C) horárias do ERA5 por célula, fuso UTC−3 fixo, rótulo do ONS.

    Um pedido por ano (cache do cliente Open-Meteo do protótipo; anos fechados ficam 30 dias).
    A radiação do Open-Meteo rotulada h é a média da hora anterior; o ONS rotula pelo início:
    desloca-se uma hora (oraculo/tempo/pato.SHIFT).
    """
    from oraculo.tempo import clima as W
    from oraculo.tempo.pato import SHIFT

    t = cfg()["tempo"]
    pts = cel[["lat", "lon"]].to_dict("records")
    ghi, tmp, idx = [], [], []
    for ano in range(pd.Timestamp(t["inicio_era5"]).year, fim.year + 1):
        ini = pd.Timestamp(f"{ano}-01-01")
        fim_ano = min(pd.Timestamp(f"{ano}-12-31"), fim.normalize())
        ttl = 30 * 86400 if fim_ano.year < fim.year else 3 * 3600
        b = W.era5(pts, f"{ini:%Y-%m-%d}", f"{fim_ano:%Y-%m-%d}", ttl=ttl, tz=t["fuso"])
        idx += b["time"]
        ghi.append(np.array(b["_"]["shortwave_radiation"], dtype="f8").T)
        tmp.append(np.array(b["_"]["temperature_2m"], dtype="f8").T)
    ix = pd.DatetimeIndex(pd.to_datetime(idx))
    G = pd.DataFrame(np.vstack(ghi), index=ix, columns=cel["id"]).shift(-SHIFT)
    T = pd.DataFrame(np.vstack(tmp), index=ix, columns=cel["id"]).shift(-SHIFT)
    return G, T


def geracao_unitaria(cel: pd.DataFrame, G: pd.DataFrame, T: pd.DataFrame) -> pd.DataFrame:
    """U(t) por subsistema: MW gerado por MW instalado (PR = 1), média das células pesada pela MMGD."""
    from oraculo.tempo.pato import pv_mw

    n = len(cel)
    u = pv_mw(G.to_numpy().T, T.to_numpy().T, np.ones(n), np.ones(n)).T  # [horas x células]
    u[~np.isfinite(G.to_numpy())] = np.nan
    out = {}
    for ss in SUBS:
        sel = (cel["ss"] == ss).to_numpy()
        w = cel.loc[sel, "mw"].to_numpy()
        out[ss] = (u[:, sel] * w).sum(axis=1) / w.sum()
        out[ss][np.isnan(u[:, sel]).any(axis=1)] = np.nan
    return pd.DataFrame(out, index=G.index)


def calibrar_pr(U: pd.DataFrame, capd: pd.DataFrame, ons: pd.DataFrame, emissao: pd.Timestamp) -> pd.Series:
    """PR por subsistema: Σ MMGD do ONS ÷ Σ Cap × U nos `janela_pr_meses` antes da emissão."""
    ini = emissao - pd.DateOffset(months=cfg()["geracao"]["janela_pr_meses"])
    h = U[(U.index >= ini) & (U.index < emissao)]
    cap = capd.reindex(h.index.normalize()).to_numpy()
    y = ons.reindex(h.index)[list(SUBS)]
    fis = h.to_numpy() * cap
    ok = np.isfinite(fis) & np.isfinite(y.to_numpy())
    return pd.Series([np.nansum(np.where(ok[:, i], y.to_numpy()[:, i], 0)) / np.nansum(np.where(ok[:, i], fis[:, i], 0))
                      for i in range(len(SUBS))], index=list(SUBS))


# --------------------------------------------------------------------------- membros
def deslocamentos(emissao: pd.Timestamp, alvos: pd.DatetimeIndex, inicio_tempo: pd.Timestamp,
                  primeiro_ano: int) -> list[int]:
    """Anos k de defasagem dos membros: todo o período análogo (alvos − k anos) antes da emissão
    e dentro do ERA5 disponível."""
    ks = []
    for k in range(1, 30):
        a0, a1 = alvos.min() - pd.DateOffset(years=k), alvos.max() - pd.DateOffset(years=k)
        if a0 < max(inicio_tempo, pd.Timestamp(f"{primeiro_ano}-01-01")):
            break
        if a1 < emissao:
            ks.append(k)
    return ks


def _analogo(s: pd.Series | pd.DataFrame, alvos: pd.DatetimeIndex, k: int):
    """Valores de `s` k anos antes de cada alvo (29/02 -> 28/02, pelo DateOffset)."""
    return s.reindex(alvos - pd.DateOffset(years=k))


def _dias(ts: pd.DatetimeIndex, v: np.ndarray, faixa: tuple[int, int], func) -> pd.DataFrame:
    """Agregado diário (min/max) de v [amostras x horas] nas horas [faixa)."""
    h = ts.hour
    sel = (h >= faixa[0]) & (h < faixa[1])
    df = pd.DataFrame(v[:, sel].T, index=ts[sel].normalize())
    return getattr(df.groupby(level=0), func)().T  # [amostras x dias]


def prever_serie(ctx: dict, serie: str, emissao: pd.Timestamp, meses: int, cenario: str,
                 tendencia: str) -> tuple[pd.DataFrame, pd.DataFrame] | None:
    """Horário e diário de uma série numa emissão: quantis de D, G e L sobre os membros."""
    c = cfg()
    ds = ctx["dados"][ctx["dados"]["serie"] == serie][["timestamp", "y", "mes", "hora", "dia_tipo"]]
    f = dm.prever_emissao(ds, emissao, meses, ctx["temp"][serie], ctx["cal"], tendencia=tendencia)
    f = f[f["timestamp"] <= ctx["fim_tempo"]] if tendencia == "historico" else f
    if f.empty or "beta" not in f:
        return None
    alvos = pd.DatetimeIndex(f["timestamp"])
    ks = deslocamentos(emissao, alvos, ctx["U"].index.min(), c["tempo"]["primeiro_ano_analogo"])
    if len(ks) < 2:
        return None
    ss = list(SUBS) if serie == "SIN" else [serie]
    cap = cap_projetada(ctx["capd"], emissao, alvos, cenario)[ss].to_numpy()
    pr = calibrar_pr(ctx["U"], ctx["capd"], ctx["ons"], emissao)[ss].to_numpy()
    beta = np.nan_to_num(f["beta"].to_numpy())
    D, G = [], []
    for k in ks:
        tk = _analogo(ctx["temp"][serie], alvos, k).to_numpy()
        D.append(f["p50_clim"].to_numpy() + beta * (tk - f["t_clim"].to_numpy()))
        G.append((cap * pr * _analogo(ctx["U"][ss], alvos, k).to_numpy()).sum(axis=1))
    D, G = np.array(D), np.array(G)
    L = D - G
    out = pd.DataFrame({"serie": serie, "emissao": emissao, "cenario": cenario, "timestamp": alvos,
                        "horizonte": f["horizonte"].to_numpy(), "hora": alvos.hour, "membros": len(ks)})
    for nome, m in (("d", D), ("g", G), ("l", L)):
        q = np.nanquantile(m, [0.1, 0.5, 0.9], axis=0)
        out[f"{nome}_p10"], out[f"{nome}_p50"], out[f"{nome}_p90"] = q
    # Tempo perfeito (Fase 2, separa erro de tempo do erro do modelo): ERA5 observado nos alvos.
    out["g_perfeito"] = (cap * pr * ctx["U"][ss].reindex(alvos).to_numpy()).sum(axis=1)

    p = c["pato"]
    bar = _dias(alvos, L, tuple(p["barriga_horas"]), "min")
    pon = _dias(alvos, L, tuple(p["ponta_horas"]), "max")
    dias = bar.columns.intersection(pon.columns)
    ram = pon[dias] - bar[dias]
    # Limiar de carga líquida mínima: quantil da barriga OBSERVADA nos 12 meses antes da emissão.
    obs = ctx["obs_l"][serie]
    hist = obs[(obs.index >= emissao - pd.DateOffset(years=1)) & (obs.index < emissao)]
    hb = hist[(hist.index.hour >= p["barriga_horas"][0]) & (hist.index.hour < p["barriga_horas"][1])]
    limiar = float(hb.groupby(hb.index.normalize()).min().quantile(p["limiar_quantil"]))
    diario = pd.DataFrame({"serie": serie, "emissao": emissao, "cenario": cenario, "data": dias,
                           "limiar_mw": limiar,
                           "risco_carga_minima": (bar[dias] < limiar).mean(axis=0).to_numpy()})
    for nome, m in (("barriga", bar[dias]), ("rampa", ram)):
        q = np.nanquantile(m.to_numpy(), [0.1, 0.5, 0.9], axis=0)
        diario[f"{nome}_p10"], diario[f"{nome}_p50"], diario[f"{nome}_p90"] = q
    hz = out.groupby(out["timestamp"].dt.normalize())["horizonte"].first()
    diario["horizonte"] = diario["data"].map(hz).to_numpy()
    return out, diario


# --------------------------------------------------------------------------- contexto e backtest
def contexto() -> dict:
    """Tudo que o backtest e a previsão leem, carregado uma vez."""
    c = dm.cfg()
    dados = dm.carregar_horario()
    ultimo = dados["timestamp"].max()
    cel = celulas()
    G, T = tempo_celulas(cel, ultimo)
    U = geracao_unitaria(cel, G, T)
    ons = dm.horario_largo("mmgd_estimada")
    dem = dm.horario_largo(c["alvo"])
    temp = {s: dm.temperatura_horaria(s, dados["timestamp"].min(), ultimo)
            for s in c["series"]}
    fim_tempo = U.dropna().index.max()
    return {"dados": dados, "cal": dm.calendario_horario(), "cel": cel, "U": U, "ons": ons,
            "capd": cap_ss_diaria(), "temp": temp, "obs_l": (dem - ons), "obs_d": dem,
            "ultimo": ultimo, "fim_tempo": fim_tempo}


def _obs_diario(ctx, serie, datas) -> pd.DataFrame:
    """Barriga e rampa observadas (carga supervisionada = carga global − MMGD do ONS)."""
    p = cfg()["pato"]
    obs = ctx["obs_l"][serie]
    ts = pd.DatetimeIndex(obs.index)
    v = obs.to_numpy()[None, :]
    bar = _dias(ts, v, tuple(p["barriga_horas"]), "min").iloc[0]
    pon = _dias(ts, v, tuple(p["ponta_horas"]), "max").iloc[0]
    return pd.DataFrame({"barriga_obs": bar.reindex(datas).to_numpy(),
                         "rampa_obs": (pon - bar).reindex(datas).to_numpy()})


def backtest(ctx: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Origem móvel mensal (mesmas emissões da Fase 1), cenário histórico, com observado,
    sazonal ingênuo e bandas conformais."""
    c, cd = cfg(), dm.cfg()
    b = c["backtest"]
    hor, dia = [], []
    for serie in cd["series"]:
        for em in dm.emissoes_backtest(ctx["ultimo"]):
            r = prever_serie(ctx, serie, em, b["horizonte_meses"], "historico", "historico")
            if r is None:
                continue
            h, d = r
            h = h[h["timestamp"] <= ctx["ultimo"]].copy()
            ts = pd.DatetimeIndex(h["timestamp"])
            h["y_d"] = ctx["obs_d"][serie].reindex(ts).to_numpy()
            h["y_g"] = ctx["ons"][serie].reindex(ts).to_numpy()
            h["y_l"] = h["y_d"] - h["y_g"]
            # Sazonal ingênuo (spec §7): 364 dias antes; D escalada pela taxa histórica da carga,
            # G pela razão de capacidade instalada (cadastro projetado ÷ cadastro de então).
            ss = list(SUBS) if serie == "SIN" else [serie]
            ant = ts - pd.Timedelta(days=364)
            ds = ctx["dados"][ctx["dados"]["serie"] == serie]
            g = dm.taxa_historica(ds[ds["timestamp"] < em], em, cd["crescimento_janela_meses"])
            cap_now = cap_projetada(ctx["capd"], em, ts, "historico")[ss].sum(axis=1).to_numpy()
            cap_ant = ctx["capd"][ss].sum(axis=1).reindex(ant.normalize()).to_numpy()
            h["saz_d"] = ctx["obs_d"][serie].reindex(ant).to_numpy() * (1 + g)
            h["saz_g"] = ctx["ons"][serie].reindex(ant).to_numpy() * cap_now / cap_ant
            h["saz_l"] = h["saz_d"] - h["saz_g"]
            hor.append(h.dropna(subset=["y_l"]))
            d = d[d["data"] <= ctx["ultimo"].normalize() - pd.Timedelta(days=1)].copy()
            d = pd.concat([d.reset_index(drop=True), _obs_diario(ctx, serie, d["data"])], axis=1)
            sazl = pd.Series(h["saz_l"].to_numpy(), index=ts)
            sl = sazl.to_numpy()[None, :]
            p = c["pato"]
            sb = _dias(ts, sl, tuple(p["barriga_horas"]), "min").iloc[0]
            sp = _dias(ts, sl, tuple(p["ponta_horas"]), "max").iloc[0]
            d["barriga_saz"] = sb.reindex(d["data"]).to_numpy()
            d["rampa_saz"] = (sp - sb).reindex(d["data"]).to_numpy()
            dia.append(d.dropna(subset=["barriga_obs"]))
        log.info("pato backtest %s", serie)
    H = pd.concat(hor, ignore_index=True)
    D = pd.concat(dia, ignore_index=True)
    return calibrar_bandas(H, D)


def calibrar_bandas(H: pd.DataFrame, D: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Conformal (CQR) por série × horizonte em D, G, L (horário) e barriga, rampa (diário)."""
    cf = cfg()["conformal"]
    D = D.rename(columns={"data": "timestamp"})
    specs = [(H, "d", "y_d"), (H, "g", "y_g"), (H, "l", "y_l"), (D, "barriga", "barriga_obs"),
             (D, "rampa", "rampa_obs")]
    for df, nome, y in specs:
        df[f"{nome}_p10_base"], df[f"{nome}_p90_base"] = df[f"{nome}_p10"], df[f"{nome}_p90"]
    for df, nome, y in specs:
        partes = []
        for em, g in df.groupby("emissao"):
            g = g.copy()
            q = dm.conformal(df, y, f"{nome}_p10_base", f"{nome}_p90_base", em, cf["emissoes"], cf["cobertura"])
            dm.aplicar_conformal(g, q, f"{nome}_p10", f"{nome}_p90")
            partes.append(g)
        df[[f"{nome}_p10", f"{nome}_p90"]] = pd.concat(partes).loc[df.index, [f"{nome}_p10", f"{nome}_p90"]]
    return H, D.rename(columns={"timestamp": "data"})


# --------------------------------------------------------------------------- métricas
def metricas(H: pd.DataFrame, D: pd.DataFrame) -> dict:
    """Métricas do TESTE: MMGD por hora do dia (Fase 2) e curva do pato (Fase 3)."""
    ini = pd.Timestamp(cfg()["backtest"]["primeira_emissao"])
    h, d = H[H["emissao"] >= ini], D[D["emissao"] >= ini]
    cob = lambda df, n, y: float(((df[y] >= df[f"{n}_p10"]) & (df[y] <= df[f"{n}_p90"])).mean())
    mae = lambda a, b: float((a - b).abs().mean())
    resumo = []
    for s, g in h.groupby("serie"):
        dd = d[d["serie"] == s]
        dia_sol = g[(g["hora"] >= 9) & (g["hora"] < 16)]
        lin = {
            "serie": s,
            "mmgd_mae_mw": mae(g["y_g"], g["g_p50"]),
            "mmgd_mae_tempo_perfeito_mw": mae(g["y_g"], g["g_perfeito"]),
            "mmgd_mae_sazonal_mw": mae(g["y_g"], g["saz_g"]),
            "mmgd_mae_diurno_mw": mae(dia_sol["y_g"], dia_sol["g_p50"]),
            "l_mae_mw": mae(g["y_l"], g["l_p50"]), "l_mae_sazonal_mw": mae(g["y_l"], g["saz_l"]),
            "l_cobertura": cob(g, "l", "y_l"), "d_cobertura": cob(g, "d", "y_d"), "g_cobertura": cob(g, "g", "y_g"),
            "barriga_mae_mw": mae(dd["barriga_obs"], dd["barriga_p50"]),
            "barriga_mae_sazonal_mw": mae(dd["barriga_obs"], dd["barriga_saz"]),
            "rampa_mae_mw": mae(dd["rampa_obs"], dd["rampa_p50"]),
            "rampa_mae_sazonal_mw": mae(dd["rampa_obs"], dd["rampa_saz"]),
            "barriga_cobertura": cob(dd, "barriga", "barriga_obs"),
            "risco_medio_previsto": float(dd["risco_carga_minima"].mean()),
            "freq_observada_abaixo_limiar": float((dd["barriga_obs"] < dd["limiar_mw"]).mean()),
            "dias": int(len(dd)), "emissoes": int(g["emissao"].nunique()),
        }
        for k in ("mmgd", "l", "barriga", "rampa"):
            lin[f"skill_{k}"] = 1 - lin[f"{k}_mae_mw"] / lin[f"{k}_mae_sazonal_mw"]
        resumo.append(lin)
    por_hora = (h.assign(e=(h["y_g"] - h["g_p50"]).abs(), ep=(h["y_g"] - h["g_perfeito"]).abs())
                .groupby(["serie", "hora"])[["e", "ep", "y_g"]].mean().reset_index()
                .rename(columns={"e": "mae_mw", "ep": "mae_tempo_perfeito_mw", "y_g": "mmgd_media_mw"}))
    r = pd.DataFrame(resumo)
    sub = r[r["serie"].isin(SUBS)]
    aceite = {
        "fase2_mmgd_medida": True,
        "fase3_skill_barriga_subsistemas_positivos": int((sub["skill_barriga"] > 0).sum()),
        "fase3_skill_barriga_ok": bool((sub["skill_barriga"] > 0).sum() >= 3),
        "fase3_cobertura_l_ok": bool(r["l_cobertura"].between(0.75, 0.85).all()),
    }
    return {"resumo": r, "por_hora": por_hora, "aceite": aceite}


# --------------------------------------------------------------------------- previsão para a frente
def prever_frente(ctx: dict, H: pd.DataFrame, D: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Emissão logo depois do último dado, 3 cenários de capacidade, bandas pela conformal do
    backtest (horizonte do último mês parcial = o mais longo medido)."""
    c, cd = cfg(), dm.cfg()
    cf = c["conformal"]
    em = ctx["ultimo"] + pd.Timedelta(hours=1)
    meses = cd["previsao"]["horizonte_meses"]
    hmax = c["backtest"]["horizonte_meses"]
    hor, dia = [], []
    for cen in c["capacidade"]["cenarios"]:
        for serie in cd["series"]:
            r = prever_serie(ctx, serie, em, meses, cen, cd["previsao"]["tendencia"])
            if r is None:
                continue
            hor.append(r[0])
            dia.append(r[1])
    fh, fd = pd.concat(hor, ignore_index=True), pd.concat(dia, ignore_index=True)
    for df, base, specs in ((fh, H, [("d", "y_d"), ("g", "y_g"), ("l", "y_l")]),
                            (fd, D.rename(columns={"data": "timestamp"}), [("barriga", "barriga_obs"), ("rampa", "rampa_obs")])):
        df["hz_banda"] = df["horizonte"].clip(upper=hmax)
        for nome, y in specs:
            q = dm.conformal(base, y, f"{nome}_p10_base", f"{nome}_p90_base", em, cf["emissoes"], cf["cobertura"])
            dm.aplicar_conformal(df, q, f"{nome}_p10", f"{nome}_p90", chaves=("serie", "hz_banda"))
    return fh, fd


# --------------------------------------------------------------------------- painel (JSON da tela)
def painel(fh: pd.DataFrame, fd: pd.DataFrame, met: dict, met_dem: pd.DataFrame, ctx: dict) -> dict:
    """JSON compacto para a tela "Previsão de meses" (rota só de leitura, fora do contrato)."""
    c, cd = cfg(), dm.cfg()
    fh = fh.assign(mes=fh["timestamp"].dt.to_period("M").astype(str))
    fd = fd.assign(mes=pd.to_datetime(fd["data"]).dt.to_period("M").astype(str))
    r2 = lambda v: None if v is None or not np.isfinite(v) else round(float(v), 1)
    series = {}
    for (serie, cen), g in fh.groupby(["serie", "cenario"]):
        gd = fd[(fd["serie"] == serie) & (fd["cenario"] == cen)]
        meses = []
        for mes, gm in g.groupby("mes"):
            dm_ = gd[gd["mes"] == mes]
            perfil = gm.groupby("hora")[[f"{n}_p{q}" for n in "dgl" for q in (10, 50, 90)]].mean()
            i_bar = perfil["l_p50"].iloc[c["pato"]["barriga_horas"][0]:c["pato"]["barriga_horas"][1]].idxmin()
            meses.append({
                "mes": mes, "dias": int(gm["timestamp"].dt.normalize().nunique()),
                "perfil": {k: [r2(v) for v in perfil[k]] for k in perfil.columns},
                "media": {k: r2(gm[k].mean()) for k in ("d_p50", "g_p50", "l_p50", "l_p10", "l_p90")},
                "barriga": {q: r2(dm_[f"barriga_{q}"].mean()) for q in ("p10", "p50", "p90")},
                "hora_barriga": int(i_bar),
                "rampa": {q: r2(dm_[f"rampa_{q}"].mean()) for q in ("p10", "p50", "p90")},
                "risco_carga_minima": r2(100 * dm_["risco_carga_minima"].mean()),
                "limiar_mw": r2(dm_["limiar_mw"].iloc[0]) if len(dm_) else None,
                "participacao_mmgd_barriga": r2(100 * perfil["g_p50"].iloc[i_bar] / perfil["d_p50"].iloc[i_bar]),
            })
        series.setdefault(serie, {})[cen] = {"membros": int(g["membros"].iloc[0]), "meses": meses}
    res = met["resumo"].replace({np.nan: None})
    ph = met["por_hora"][met["por_hora"]["serie"] == "SIN"]
    dem = met_dem[met_dem["modelo"].isin(["clim", "era5", "sazonal_ingenuo"])]
    dem = dem.groupby(["serie", "modelo"])[["mae_mw", "mape_pct", "skill_vs_sazonal_ingenuo", "cobertura_p10_p90"]].mean().reset_index()
    return {
        "emissao": f"{fh['emissao'].iloc[0]:%Y-%m-%dT%H:%M}",
        "ultimo_dado": f"{ctx['ultimo']:%Y-%m-%dT%H:%M}",
        "series": series,
        "cenarios": c["capacidade"]["cenarios"],
        "patamares": {"barriga": c["pato"]["barriga_horas"], "ponta": c["pato"]["ponta_horas"]},
        "celulas": ctx["cel"].round(3).to_dict("records"),
        "validacao": {
            "aceite": met["aceite"],
            "pato": json.loads(res.to_json(orient="records")),
            "mmgd_por_hora_sin": json.loads(ph.round(1).to_json(orient="records")),
            "demanda": json.loads(dem.round(4).to_json(orient="records")),
            "primeira_emissao": c["backtest"]["primeira_emissao"],
        },
        "fontes": [
            "ONS · carga global e MMGD estimada (30 min), dados abertos",
            "ANEEL · cadastro de MMGD (capacidade acumulada por UF) e base da Fronteira T–D (MMGD por município)",
            "Open-Meteo · ERA5 horário (radiação e temperatura) nas células de MMGD e nas capitais",
            "ONS/EPE/CCEE · PLAN 2026-2030 2ª RQ (carga global e MMGD) · ONS PAR/PEL 2025 (MMGD)",
        ],
        "premissas": [
            "Membros = anos-análogos do ERA5 (sequência horária real de k anos antes); o mesmo membro dá a temperatura da demanda e a radiação da MMGD.",
            "Meses à frente não têm previsão de tempo: a banda é a variabilidade climática dos análogos, calibrada por conformal no backtest.",
            "MMGD física (PR recalibrado por subsistema contra a MMGD do ONS nos 12 meses anteriores); a MMGD do ONS é estimativa.",
            "Distribuição espacial da MMGD = cadastro atual; o nível no tempo segue o cadastro do subsistema.",
            "Cenários de capacidade: baixo = PAR/PEL 2025, referência = PLAN 2026-2030, alto = taxa do cadastro dos últimos 12 meses.",
            "Crescimento da demanda para a frente: taxa da carga global do SIN no PLAN 2026-2030, aplicada aos subsistemas.",
            "Não implementado: condicionamento pelo SEAS5, FourCastNet 3 (sem GPU), fator de correção da visão computacional.",
        ],
    }


# --------------------------------------------------------------------------- etapa
def executar() -> str:
    """Etapa `pato_meses`: backtest (Fases 2 e 3) + previsão para a frente + painel + relatório."""
    ctx = contexto()
    H, D = backtest(ctx)
    ensure(caminho("backtest_pato").parent)
    H.to_parquet(caminho("backtest_pato"), index=False)
    D.to_parquet(caminho("backtest_mmgd").with_name("backtest_pato_diario.parquet"), index=False)
    met = metricas(H, D)
    fh, fd = prever_frente(ctx, H, D)
    ensure(caminho("previsao_pato").parent)
    fh.to_parquet(caminho("previsao_pato"), index=False)
    fd.to_parquet(caminho("metricas_pato"), index=False)
    met_dem = pd.read_csv(dm.caminho("metricas")) if dm.caminho("metricas").exists() else pd.DataFrame(
        columns=["serie", "modelo", "mae_mw", "mape_pct", "skill_vs_sazonal_ingenuo", "cobertura_p10_p90"])
    pan = painel(fh, fd, met, met_dem, ctx)
    ensure(caminho("painel").parent)
    caminho("painel").write_text(json.dumps(pan, ensure_ascii=False), encoding="utf-8")
    ensure(caminho("metricas").parent)
    met["resumo"].to_csv(caminho("metricas"), index=False)
    escrever_relatorio(met, pan)
    return f"pato de meses: {H['emissao'].nunique()} emissões no backtest; aceite {met['aceite']}"


def escrever_relatorio(met: dict, pan: dict) -> None:
    """Relatório curto (docs/reports/pato_meses.md); a leitura principal é a tela."""
    r = met["resumo"]
    col = ["serie", "mmgd_mae_mw", "mmgd_mae_tempo_perfeito_mw", "skill_mmgd", "l_mae_mw", "skill_l",
           "barriga_mae_mw", "skill_barriga", "skill_rampa", "l_cobertura", "barriga_cobertura"]
    linhas = ["| " + " | ".join(col) + " |", "|" + "---|" * len(col)]
    for x in r[col].itertuples(index=False):
        linhas.append("| " + " | ".join(str(v) if isinstance(v, str) else f"{v:,.3f}" if abs(v) < 5 else f"{v:,.0f}" for v in x) + " |")
    sin = pan["series"]["SIN"]["referencia"]["meses"]
    prev = ["| mês | carga líquida P50 | barriga P10–P50–P90 | rampa P50 | risco carga mínima |", "|---|---|---|---|---|"]
    for m in sin:
        b = m["barriga"]
        prev.append(f"| {m['mes']} | {m['media']['l_p50']:,.0f} | {b['p10']:,.0f} – {b['p50']:,.0f} – {b['p90']:,.0f} | "
                    f"{m['rampa']['p50']:,.0f} | {m['risco_carga_minima']:.0f}% |")
    texto = f"""# MMGD e curva do pato prevista para meses — backtest (Fases 2 e 3)

Gerado por `src/models/pato_meses.py`. Parâmetros: `Backend/config/pato_meses.yaml`. Tela: **Operação ›
Previsão de meses** (`/previsao-meses`). Especificação: `docs/oraculo/especificacao/17-previsao-meses-carga-mmgd-pato.md`.

Backtest com origem móvel mensal desde {pan['validacao']['primeira_emissao']}, horizontes 1–6 meses, membros =
anos-análogos do ERA5, cenário de capacidade histórico. Baseline: sazonal ingênuo (364 dias antes).

**Aceite:** {met['aceite']}

{chr(10).join(linhas)}

## Previsão para a frente — SIN, cenário de referência (média do mês, MW)

{chr(10).join(prev)}

## Premissas

""" + "\n".join(f"- {p}" for p in pan["premissas"]) + "\n"
    ensure(caminho("relatorio").parent)
    caminho("relatorio").write_text(texto, encoding="utf-8")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(executar())
