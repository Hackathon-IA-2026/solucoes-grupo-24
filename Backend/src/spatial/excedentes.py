"""Excedente de MMGD por mancha: quando a geração distribuída passa a carga local.

Excedente numa mancha = max(0, geração de MMGD − carga) na semi-hora. Positivo = a subestação
exporta para a rede básica (fluxo reverso na fronteira TSO–DSO), que é o que o ONS não vê.

Como cada termo é estimado (dados reais; método em docs/metodo_espacial.md):
- Geração de MMGD da mancha = capacidade cadastrada da mancha (src/spatial/mmgd.py) × fator de
  geração da área, onde fator = MMGD estimada pelo ONS na área de carga ÷ capacidade de MMGD
  cadastrada na ANEEL na UF (data/processed/capacidade_mmgd.csv). É a mesma razão do card
  "MMGD ÷ capacidade instalada", só que na área piloto. Hipótese: o fator de geração é o
  mesmo em todas as manchas da área (sem irradiância por mancha ainda).
- Tudo na subestação de FRONTEIRA (origem dos alimentadores), onde o fluxo reverso aparece para
  o ONS: capacidade levada para lá por mmgd.para_fronteira, carga somada lá por `pesos_carga`.
- Carga da subestação = carga global da área (ONS) × peso dela no mês, onde peso = energia bruta
  dela ÷ energia de todas (BDGD). Energia bruta = alimentadores (energia líquida medida) + MMGD
  que sai por ela + consumidores AT. A carga global do ONS também é bruta (inclui o que a MMGD
  atende).
- Previsão (horizontes do contrato): persistência sazonal de 1 dia. O valor de um alvo é o
  observado 24 h antes dele; para alvos até 24 h à frente isso só usa dado <= agora
  (garantido por `prever`, testado em tests/test_espacial.py). A capacidade é a cadastrada
  até o agora (cadastros futuros não existem no replay).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.spatial.bdgd import MESES
from src.utils.tempo import PASSO


# Rótulo interno da energia sem subestação na BDGD (nunca sai de pesos_carga).
SEM_MANCHA = "__sem_mancha__"


# --------------------------------------------------------------------------- carga por mancha
def pesos_carga(circuitos: pd.DataFrame, consumidores_at: pd.DataFrame,
                energia_mmgd: pd.DataFrame) -> pd.DataFrame:
    """Energia mensal bruta (kWh) e peso de cada subestação de fronteira no mês.

    `circuitos`: COD_ID, mancha_id (subestação de ORIGEM), ENE_01..12 (energia medida na saída,
    LÍQUIDA da MMGD: negativa quando o alimentador exporta); `consumidores_at`: mancha_id,
    ENE_01..12; `energia_mmgd`: mancha_id (fronteira, ver mmgd.para_fronteira), ene_01..12.
    Energia bruta da subestação = alimentadores dela + consumidores AT + MMGD que sai por ela.
    Tudo na subestação de origem, a mesma chave da capacidade dos excedentes: carga e geração
    precisam estar do mesmo lado da fronteira. (Uma versão anterior repartia a carga pelos trafos
    das subestações satélite e deixava a MMGD na origem: Brisamar e Centenário, que exportam
    energia medida na BDGD, ficavam com geração e sem carga, e sumiam da previsão.)
    Devolve mancha_id, mes (1–12), energia_kwh, peso (soma 1 em cada mês).
    """
    ene = [f"ENE_{m}" for m in MESES]
    mmgd = energia_mmgd.rename(columns={f"ene_{m}": f"ENE_{m}" for m in MESES})
    # Energia sem mancha (SUB em branco na BDGD) é carga real da área: fica no denominador dos
    # pesos, sob SEM_MANCHA, e sai da tabela no fim (não vira mancha).
    total = (pd.concat([circuitos[["mancha_id", *ene]].fillna({c: 0 for c in ene}),
                        consumidores_at[["mancha_id", *ene]].fillna({c: 0 for c in ene}),
                        mmgd[["mancha_id", *ene]]])
             .assign(mancha_id=lambda d: d["mancha_id"].fillna(SEM_MANCHA))
             .groupby("mancha_id")[ene].sum())
    longo = (total.rename(columns={f"ENE_{m}": int(m) for m in MESES}).stack()
             .rename("energia_kwh").rename_axis(["mancha_id", "mes"]).reset_index())
    # Ainda negativa = a MMGD da BDGD não cobre o que a subestação exporta (cadastro incompleto):
    # carga zero, nunca negativa.
    longo["energia_kwh"] = longo["energia_kwh"].clip(lower=0)
    longo["peso"] = longo["energia_kwh"] / longo.groupby("mes")["energia_kwh"].transform("sum")
    return longo[longo["mancha_id"] != SEM_MANCHA].reset_index(drop=True)


def alimentadores_exportadores(circuitos: pd.DataFrame) -> pd.DataFrame:
    """Alimentadores com energia LÍQUIDA negativa em algum mês: fluxo reverso medido na BDGD.

    É a evidência medida pela própria distribuidora de que a MMGD passou a carga local; serve
    para conferir se o modelo de excedentes aponta as mesmas manchas (docs/reports/desempate_mmgd.md).
    Devolve COD_ID, mancha_id (origem), meses_negativos, menor_energia_kwh.
    """
    ene = [f"ENE_{m}" for m in MESES]
    neg = circuitos[ene].lt(0)
    out = circuitos.loc[neg.any(axis=1), ["COD_ID", "mancha_id"]].copy()
    out["meses_negativos"] = neg.sum(axis=1)[out.index]
    out["menor_energia_kwh"] = circuitos.loc[out.index, ene].min(axis=1)
    return out.sort_values("menor_energia_kwh").reset_index(drop=True)


# --------------------------------------------------------------------------- fator de geração
def fator_geracao(carga_area: pd.DataFrame, capacidade_uf: pd.DataFrame, uf: str) -> pd.DataFrame:
    """timestamp, carga_global (MW), fator_mmgd (MW gerados por MW cadastrado) da área.

    `carga_area`: data/processed/carga_area.csv; `capacidade_uf`: capacidade_mmgd.csv.
    Capacidade na data do instante (acumulada até ela). Sem MMGD estimada: fator NaN.
    """
    c = carga_area.copy()
    c["timestamp"] = pd.to_datetime(c["timestamp"])
    cap = capacidade_uf[capacidade_uf["uf"] == uf][["data", "potencia_acumulada_mw"]].copy()
    if cap.empty:
        raise LookupError(f"capacidade_mmgd sem a UF {uf}")
    cap["data"] = pd.to_datetime(cap["data"])
    c["data"] = c["timestamp"].dt.normalize()
    c = pd.merge_asof(c.sort_values("data"), cap.sort_values("data"), on="data")
    c["fator_mmgd"] = c["mmgd_estimada"] / c["potencia_acumulada_mw"]
    return c.sort_values("timestamp")[["timestamp", "carga_global", "fator_mmgd"]].reset_index(drop=True)


# --------------------------------------------------------------------------- previsão
def prever(fator: pd.DataFrame, capacidade_mw: pd.Series, pesos: pd.DataFrame, agora: pd.Timestamp,
           passos: int, defasagem: int) -> pd.DataFrame:
    """Geração, carga e excedente previstos por mancha para os próximos `passos` alvos.

    `fator`: saída de fator_geracao; `capacidade_mw`: mancha_id -> MW (cadastro até o agora,
    já com o fator de correção do satélite, se houver); `pesos`: saída de pesos_carga.
    Persistência sazonal: alvo t usa o observado em t − defasagem passos. Exige
    passos <= defasagem, senão o modelo precisaria de dado depois do agora.
    Devolve mancha_id, alvo, passo (1..passos), origem, geracao_mw, carga_mw, excedente_mw.
    """
    if passos > defasagem:
        raise ValueError(f"horizonte de {passos} passos passa da defasagem sazonal ({defasagem}): vazaria dado futuro")
    hist = fator[fator["timestamp"] <= agora].set_index("timestamp")
    alvos = pd.DataFrame({"passo": range(1, passos + 1)})
    alvos["alvo"] = agora + alvos["passo"] * PASSO
    alvos["origem"] = alvos["alvo"] - defasagem * PASSO
    if (alvos["origem"] > agora).any():  # invariante do replay; nunca deveria acontecer
        raise RuntimeError("previsão de excedente usando dado posterior ao agora")
    alvos = alvos.join(hist[["carga_global", "fator_mmgd"]], on="origem")
    if alvos[["carga_global", "fator_mmgd"]].isna().all().any():
        raise LookupError(f"sem carga/MMGD da área nas 24 h antes de {agora}: rode a ingestão")
    alvos["mes"] = alvos["alvo"].dt.month

    # Grade completa mancha × alvo: mancha com MMGD e sem carga conhecida entra com carga zero
    # (antes o merge com os pesos a descartava, e com ela o excedente dela).
    todas = pd.Index(sorted(set(pesos["mancha_id"]) | set(capacidade_mw.index)), name="mancha_id")
    base = pd.MultiIndex.from_product([todas, alvos.index], names=["mancha_id", "i"]).to_frame(index=False)
    base = base.join(alvos, on="i").drop(columns="i")
    base = base.merge(pesos[["mancha_id", "mes", "peso"]], on=["mancha_id", "mes"], how="left")
    base["peso"] = base["peso"].fillna(0.0)
    base["capacidade_mw"] = base["mancha_id"].map(capacidade_mw).fillna(0.0)
    base["geracao_mw"] = base["capacidade_mw"] * base["fator_mmgd"]
    base["carga_mw"] = base["peso"] * base["carga_global"]
    base["excedente_mw"] = (base["geracao_mw"] - base["carga_mw"]).clip(lower=0)
    cols = ["mancha_id", "alvo", "passo", "origem", "geracao_mw", "carga_mw", "excedente_mw"]
    return base[cols].sort_values(["mancha_id", "alvo"]).reset_index(drop=True)


def pico_por_mancha(prev: pd.DataFrame, horizontes: dict[str, int]) -> pd.DataFrame:
    """Uma linha por mancha: o maior excedente previsto na janela e em que horizonte ele cai.

    horizonte = o menor horizonte do contrato cuja janela (agora, agora + h] contém o pico.
    Sem excedente na janela: pico = instante de maior penetração (geração ÷ carga), excedente 0.
    Devolve mancha_id, alvo, excedente_mw, geracao_mw, carga_mw, penetracao, horizonte.
    """
    p = prev.copy()
    # Penetração = geração ÷ carga. Sem carga: infinita só se houver geração (tudo exporta);
    # sem geração e sem carga, zero (antes saía infinita e a mancha vazia ia para o topo).
    p["penetracao"] = np.select([p["carga_mw"] > 0, p["geracao_mw"] > 0],
                                [p["geracao_mw"] / p["carga_mw"].where(p["carga_mw"] > 0), np.inf], 0.0)
    pico = (p.sort_values(["excedente_mw", "penetracao"], ascending=False)
            .drop_duplicates("mancha_id"))
    ordem = sorted(horizontes.items(), key=lambda kv: kv[1])
    pico["horizonte"] = [next(h for h, n in ordem if passo <= n) for passo in pico["passo"]]
    return pico.drop(columns=["passo", "origem"]).reset_index(drop=True)


def prioridade(excedente_mw: float, limiares: dict[str, float]) -> str:
    """Primeiro nível (de cima para baixo) cujo limiar em MW o excedente atinge."""
    return next(nivel for nivel, lim in limiares.items() if excedente_mw >= lim)


def capacidade_no_agora(diaria: pd.DataFrame, agora: pd.Timestamp) -> pd.Series:
    """mancha_id (fronteira) -> MW cadastrados até a data do agora.

    `diaria`: data/processed/mmgd_fronteira_diaria.csv (por subestação de fronteira, já com o
    fator de correção do satélite aplicado na origem). Cadastros depois do agora não entram.
    """
    d = diaria[pd.to_datetime(diaria["data"]) <= agora.normalize()]
    return d.groupby("mancha_id")["potencia_kw_acumulada"].last() / 1000


def selecionar(pico: pd.DataFrame, manchas: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """As manchas publicadas na tela Excedentes, com prioridade e ação.

    Entram as manchas com excedente > 0 (no máximo `top_manchas`), por excedente e depois
    penetração (geração ÷ carga). Se forem menos que `min_manchas` (dia nublado, janela à noite),
    completa com as de maior penetração, com excedente 0 e prioridade baixa: a tela mostra onde
    vigiar em vez de ficar vazia. `cfg` = seção excedentes de config/espacial.yaml. Nome exibido = nome da subestação; se dois nomes
    repetem na mesma distribuidora, entra o código da subestação (o dashboard usa
    área + distribuidora como chave da linha).
    """
    m = manchas[["mancha_id", "nome", "cod_sub", "distribuidora", "lat_sub", "lon_sub", "fonte"]]
    p = pico.merge(m, on="mancha_id", how="left")
    if p["nome"].isna().any():
        raise KeyError(f"excedente de mancha sem cadastro: {p.loc[p['nome'].isna(), 'mancha_id'].tolist()[:5]}")
    p = p.sort_values(["excedente_mw", "penetracao"], ascending=False)
    n = max(int((p["excedente_mw"] > 0).sum()), cfg["min_manchas"])
    p = p[p["penetracao"] > 0].head(min(n, cfg["top_manchas"])).copy()
    rep = p.duplicated(["nome", "distribuidora"], keep=False)
    p["area"] = p["nome"].where(~rep, p["nome"] + " (" + p["cod_sub"].astype(str) + ")")
    p["prioridade"] = [prioridade(x, cfg["prioridade"]) for x in p["excedente_mw"]]
    p["acao"] = p["prioridade"].map(cfg["acao"])
    p["fonte"] = p["fonte"].fillna("MMGD")
    return p.reset_index(drop=True)


# --------------------------------------------------------------------------- densidade
def pontos_densidade(manchas: pd.DataFrame) -> list[tuple[float, float, float]]:
    """[lat, lon, intensidade] por mancha com MMGD: intensidade = capacidade ÷ maior capacidade.

    `manchas`: lat_rep, lon_rep (ponto interno da mancha), capacidade_mmgd_corrigida_kw.
    """
    m = manchas[manchas["capacidade_mmgd_corrigida_kw"] > 0]
    if m.empty:
        raise LookupError("nenhuma mancha com MMGD: rode a etapa de espacialização")
    inten = m["capacidade_mmgd_corrigida_kw"] / m["capacidade_mmgd_corrigida_kw"].max()
    return [(round(la, 5), round(lo, 5), round(i, 4)) for la, lo, i in zip(m["lat_rep"], m["lon_rep"], inten)]
