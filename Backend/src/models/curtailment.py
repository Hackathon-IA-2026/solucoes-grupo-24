"""Classificador de risco de curtailment por razão (Fase 4, Fatia 5).

Etapa 3 do run_heavywork.py (`treinar`) e etapa 4 (`prever`), ao lado da carga. Parâmetros
em config/modelos_curtailment.yaml; horizontes = os da carga (config/modelos_carga.yaml).

Por razão (ENE; CNF opcional) e horizonte (h = 1, 6, 48 passos de 30 min):
- classificador LightGBM: P(corte da razão na usina, no alvo);
- regressor LightGBM: E[MW cortados | corte], ajustado só nas semi-horas com corte;
- montante esperado = P(corte) × E[MW | corte].
Baselines (no relatório): persistência (havia corte na emissão?) e frequência recente (fração
do último dia com corte até a emissão).

Mesmas garantias da carga (src/models/split.py e src/features/defasagens.py): features só com
dados até a emissão; `prever` só emite previsões fora da amostra e recusa modelo de outro split.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import joblib
import numpy as np
import pandas as pd

from src.features import curtailment as fcur
from src.models import carga as mc
from src.models.split import Split
from src.processing.saidas import SAIDA_CALENDARIO, SAIDA_CARGA, SAIDA_ROTULOS
from src.utils.banco_analitico import conectar
from src.utils.config import carregar
from src.utils.paths import MODELOS, ensure
from src.utils.tempo import PASSO

log = logging.getLogger("modelos_curtailment")

DIR = MODELOS / "curtailment"
ARQ_MODELOS = DIR / "modelos.joblib"
ARQ_PREVISOES = DIR / "previsoes.parquet"
ARQ_USINAS = DIR / "usinas.parquet"      # nome, UF, subsistema, fonte de cada chave (publicação)
CATEGORICAS = ["usina_cod", "subsistema_cod"]
# Maior defasagem usada (semana + dia de folga): o painel começa isso antes do treino.
_FOLGA = pd.Timedelta(days=8)


def cfg() -> dict:
    return carregar("modelos_curtailment")


def horizontes() -> dict[str, int]:
    """Os mesmos horizontes da carga: risco e curva falam da mesma antecedência."""
    return mc.cfg()["horizontes"]


def split() -> Split:
    return Split.de(cfg()["split"])


def carregar_painel(inicio: pd.Timestamp | None = None, codigos: pd.Series | None = None) -> fcur.Painel:
    """Painel das tabelas processadas a partir de `inicio` (padrão: início do treino − folga).

    `inicio` menor serve às explicações da publicação: só a semana antes da emissão.
    """
    import pyarrow.parquet as pq

    c = cfg()
    inicio = split().inicio_treino - _FOLGA if inicio is None else inicio
    # Memória (máquina de 8 GB; ~12 M linhas): a parte longa lê só chave (como categoria),
    # instante e os números; os textos de cada usina vêm agregados pelo DuckDB (1 linha/usina).
    cols = ["chave", "timestamp", *[f"{p}_{r}" for r in c["razoes"] for p in ("flag", "corte_MW")]]
    rotulos = pq.read_table(SAIDA_ROTULOS, columns=cols, filters=[("timestamp", ">=", inicio)],
                            read_dictionary=["chave"]).to_pandas()
    con = conectar()
    atributos = con.execute(f"""
        SELECT chave, arg_max(nom_usina, timestamp) AS nom_usina, arg_max(uf, timestamp) AS uf,
               arg_max(subsistema, timestamp) AS subsistema, arg_max(fonte, timestamp) AS fonte,
               arg_max(id_ons, timestamp) AS id_ons
        FROM read_parquet('{SAIDA_ROTULOS.as_posix()}') WHERE timestamp >= ? GROUP BY chave
    """, [inicio.to_pydatetime()]).df()
    con.close()
    return fcur.montar_painel(rotulos, atributos, pd.read_csv(SAIDA_CARGA), pd.read_csv(SAIDA_CALENDARIO),
                              c["razoes"], inicio, max(horizontes().values()), codigos)


@dataclass
class _Amostra:
    x: list[pd.DataFrame]
    y: list[pd.DataFrame]


def _amostra_treino(painel: fcur.Painel, sistema, h: int, sp: Split, c: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Amostra uniforme das linhas de treino de todas as usinas (memória: ~1,5 M linhas)."""
    razao0 = c["razoes"][0]
    idx = painel.flags[razao0].index
    no_treino = sp.treino(idx)
    total = int(painel.flags[razao0][no_treino].notna().to_numpy().sum())
    frac = min(1.0, c["amostra_treino"] / max(total, 1))
    rng = np.random.default_rng(c["semente"] + h)
    am = _Amostra([], [])
    for chave in painel.usinas.index:
        y = fcur.rotulos_usina(painel, chave)
        ok = no_treino & y[f"flag_{razao0}"].notna().to_numpy()
        ok &= rng.random(len(ok)) < frac
        if not ok.any():
            continue
        am.x.append(fcur.matriz_usina(painel, sistema, chave, h, c["features"])[ok])
        am.y.append(y[ok])
    return pd.concat(am.x), pd.concat(am.y)


def treinar(painel: fcur.Painel | None = None) -> str:
    """Etapa 3 (curtailment): classificador + montante por razão e horizonte."""
    import lightgbm as lgb

    c, sp = cfg(), split()
    painel = painel or carregar_painel()
    sistema = fcur.estado_do_sistema(painel)
    salvo: dict = {"split": sp, "razoes": c["razoes"], "classificador": {}, "montante": {},
                   "features": {}, "codigos": painel.usinas["codigo"]}
    linhas = 0
    for nome_h, h in horizontes().items():
        x, y = _amostra_treino(painel, sistema, h, sp, c)
        linhas = len(x)
        salvo["features"][nome_h] = list(x.columns)
        for razao in c["razoes"]:
            alvo = y[f"flag_{razao}"].astype(int)
            salvo["classificador"][(razao, nome_h)] = lgb.LGBMClassifier(**c["lightgbm_classificador"]).fit(
                x, alvo, categorical_feature=CATEGORICAS)
            com_corte = (alvo == 1).to_numpy() & (y[f"mw_{razao}"] > 0).to_numpy()
            salvo["montante"][(razao, nome_h)] = lgb.LGBMRegressor(**c["lightgbm_montante"]).fit(
                x[com_corte], y[f"mw_{razao}"][com_corte], categorical_feature=CATEGORICAS)
            log.info("treinado %s %s: %d linhas (%d com corte)", razao, nome_h, len(x), int(com_corte.sum()))
    ensure(DIR)
    joblib.dump(salvo, ARQ_MODELOS)
    return (f"{len(salvo['classificador'])} classificadores + {len(salvo['montante'])} de montante "
            f"({', '.join(c['razoes'])}); amostra de {linhas:,} linhas por horizonte; "
            f"treino até {sp.fim_treino:%Y-%m-%d}")


def prever(painel: fcur.Painel | None = None) -> str:
    """Etapa 4 (curtailment): previsões fora da amostra de todas as usinas (modo replay).

    Uma linha por (usina, horizonte, alvo), com, por razão: probabilidade, E[MW|corte],
    montante esperado, os dois baselines e o real (NaN além do último dado).
    """
    c = cfg()
    salvo = joblib.load(ARQ_MODELOS)
    sp: Split = salvo["split"]
    if sp != split():
        raise RuntimeError("modelos de curtailment salvos com outro split: rode o treino de novo")
    import pyarrow as pa
    import pyarrow.parquet as pq

    painel = painel or carregar_painel(codigos=salvo["codigos"])
    sistema = fcur.estado_do_sistema(painel)
    ultimo = painel.ultimo_dado
    ensure(DIR)
    tmp = ARQ_PREVISOES.with_suffix(".tmp")
    escritor, n, usinas = None, 0, set()
    for nome_h, h in horizontes().items():
        for chave in painel.usinas.index:
            x = fcur.matriz_usina(painel, sistema, chave, h, c["features"])
            if list(x.columns) != salvo["features"][nome_h]:
                raise RuntimeError("features diferentes das do treino: rode o treino de novo")
            idx = x.index
            emissao = idx - h * PASSO
            y = fcur.rotulos_usina(painel, chave)
            # usina precisa estar ativa na emissão (tem registro); alvo pode ser futuro
            ativa = painel.flags[c["razoes"][0]][chave].shift(h).notna().to_numpy()
            sel = sp.teste(idx, h) & np.asarray(emissao <= ultimo) & ativa
            if not sel.any():
                continue
            xs = x[sel]
            df = pd.DataFrame({"chave": str(chave), "horizonte": nome_h, "alvo": idx[sel],
                               "emissao": emissao[sel]})
            for razao in c["razoes"]:
                r = razao.lower()
                p = salvo["classificador"][(razao, nome_h)].predict_proba(xs)[:, 1]
                mw = np.maximum(salvo["montante"][(razao, nome_h)].predict(xs), 0)
                df[f"p_{r}"] = p.astype("float32")
                df[f"mw_se_corte_{r}"] = mw.astype("float32")
                df[f"montante_{r}"] = (p * mw).astype("float32")
                # baselines: corte na emissão (0/1) e fração do último dia com corte
                df[f"base_persistencia_{r}"] = xs[f"{r}_usina_emissao_menos_0"].to_numpy()
                df[f"base_frequencia_{r}"] = xs[f"{r}_usina_media_48"].to_numpy()
                df[f"base_mw_{r}"] = xs[f"{r}_mw_usina_emissao_menos_0"].to_numpy()
                df[f"real_{r}"] = y[f"flag_{razao}"][sel].to_numpy()
                df[f"real_mw_{r}"] = y[f"mw_{razao}"][sel].to_numpy()
            # Grava usina a usina (memória: são ~10 M linhas no total) num arquivo temporário,
            # trocado pelo definitivo só no fim: previsão pela metade nunca fica publicada.
            tabela = pa.Table.from_pandas(df, preserve_index=False)
            escritor = escritor or pq.ParquetWriter(tmp, tabela.schema)
            escritor.write_table(tabela)
            n += len(df)
            usinas.add(chave)
    if escritor is None:
        raise LookupError("nenhuma previsão de curtailment fora da amostra (período de teste vazio?)")
    escritor.close()
    tmp.replace(ARQ_PREVISOES)
    painel.usinas.rename_axis("chave").reset_index().to_parquet(ARQ_USINAS, index=False)
    return (f"{n:,} previsões de curtailment fora da amostra ({len(usinas)} usinas; "
            f"emissões de {sp.inicio_teste:%Y-%m-%d} até {ultimo:%Y-%m-%d %H:%M})")


def ler_previsoes(colunas: list[str] | None = None, filtros: list | None = None) -> pd.DataFrame:
    """Previsões salvas; `colunas`/`filtros` (pyarrow) evitam carregar ~10 M linhas inteiras."""
    if not ARQ_PREVISOES.exists():
        raise FileNotFoundError(f"{ARQ_PREVISOES} não existe: rode python run_heavywork.py")
    return pd.read_parquet(ARQ_PREVISOES, columns=colunas, filters=filtros)


def ler_modelos() -> dict:
    return joblib.load(ARQ_MODELOS)


def explicar(linhas: pd.DataFrame, salvo: dict | None = None) -> list[dict[str, float]]:
    """Contribuições SHAP exatas (TreeSHAP do próprio LightGBM, `pred_contrib`) de cada linha.

    `linhas`: chave, horizonte, alvo, razao. Monta as features só da semana antes das emissões
    (painel pequeno) com os códigos de usina do treino. Contribuição em log-odds, com sinal:
    > 0 aumenta a probabilidade de corte. Devolve {feature: contribuição} por linha.
    """
    c = cfg()
    salvo = salvo or ler_modelos()
    hs = horizontes()
    emissoes = linhas["alvo"] - linhas["horizonte"].map(hs).astype(int) * PASSO
    painel = carregar_painel(inicio=emissoes.min() - _FOLGA, codigos=salvo["codigos"])
    sistema = fcur.estado_do_sistema(painel)
    out = []
    for r in linhas.itertuples():
        x = fcur.matriz_usina(painel, sistema, r.chave, hs[r.horizonte], c["features"])
        if list(x.columns) != salvo["features"][r.horizonte]:
            raise RuntimeError("features diferentes das do treino: rode o treino de novo")
        linha = x.loc[[r.alvo]]
        contrib = salvo["classificador"][(r.razao, r.horizonte)].predict_proba(linha, pred_contrib=True)[0]
        out.append(dict(zip(x.columns, map(float, contrib[:-1]))))  # último = valor base
    return out
