"""Capacidade de MMGD por mancha: BDGD (onde está) × cadastro da ANEEL (quanto e desde quando).

O "desempate" das camadas 2 e 3 do Pilar 2 (docs/Oraculo_planejamento.md): a BDGD localiza a
unidade na rede (subestação), mas é anual; o cadastro de MMGD da ANEEL é diário, mas não diz a
subestação. O cruzamento é pelo código do empreendimento (CEG_GD da BDGD = CodEmpreendimento
da ANEEL) e dá três categorias por unidade:

| categoria              | está na BDGD | está na ANEEL | entra na capacidade?                       |
|------------------------|--------------|---------------|--------------------------------------------|
| bdgd_e_aneel           | sim          | sim           | sim: potência da ANEEL, mancha da BDGD     |
| lag_sistema            | não          | sim           | sim: rateada entre as manchas do município |
| bdgd_sem_homologacao   | sim          | não           | NÃO (exceção, só no relatório)             |

Decisões:
- Potência = a da ANEEL. Na BDGD 2025 da Enel RJ o POT_INST vem ~5× menor que o cadastro para o
  MESMO empreendimento (mediana 0,2); na LIGHT bate (mediana 1,0). O cadastro é a base oficial
  e é o que o ONS usa; a BDGD entra pelo que ela tem de único: a posição na rede.
- Lag de sistema (homologada na ANEEL e ausente da BDGD, em geral porque entrou depois da data
  de referência da BDGD): rateada entre as manchas da MESMA distribuidora no MESMO município,
  na proporção da capacidade já localizada (bdgd_e_aneel) de cada mancha ali; sem capacidade
  localizada no município, na proporção da potência dos transformadores MT/BT (proxy de onde a
  rede está). Sem rede da distribuidora no município: fica sem mancha e vai para o relatório.
- Unidade só na BDGD: é a "instalação não homologada" do plano. Não entra na capacidade (não
  inflar a MMGD com base errada), é contada à parte no relatório.
- Data de entrada de cada unidade = DthAtualizaCadastralEmpreend, a mesma convenção de
  data/processed/capacidade_mmgd.csv (src/processing/tabelas.py): a capacidade de uma mancha
  numa data só conta o que foi cadastrado até ela.
- Fator de correção por imagem de satélite (Luiz): CSV em config/projeto.yaml
  (caminho_fator_correcao) com mancha_id,fator_correcao. Vazio = sem correção (fator nulo e
  capacidade corrigida = capacidade cadastrada), registrado como tal.
- PRIVACIDADE: do cadastro só saem código do empreendimento, agente, município, potência, data
  e fonte. CPF/CNPJ e nome do titular nunca são lidos.
"""
from __future__ import annotations

import pandas as pd

from src.processing.tabelas import APELIDO_ANEEL_MMGD
from src.spatial import bdgd
from src.utils.banco_analitico import conectar
from src.utils.config import arquivo_direto, projeto
from src.utils.paths import RAIZ

# Nome da fonte no contrato para os tipos de geração do cadastro (SigTipoGeracao).
FONTE_CONTRATO = {"UFV": "Solar FV", "EOL": "Eólica", "CGH": "Hidráulica (CGH)", "UTE": "Térmica"}


def cadastro_aneel(agentes: list[str]) -> pd.DataFrame:
    """Empreendimentos de MMGD da ANEEL dos agentes pedidos (só colunas não pessoais)."""
    fonte = arquivo_direto(APELIDO_ANEEL_MMGD).as_posix()
    lista = ", ".join(f"'{a}'" for a in agentes)
    con = conectar()
    df = con.sql(f"""
        SELECT CodEmpreendimento AS ceg, SigAgente AS agente,
               CAST(CAST(CodMunicipioIbge AS BIGINT) AS VARCHAR) AS mun,
               MdaPotenciaInstaladaKW AS pot_aneel_kw, DthAtualizaCadastralEmpreend AS data,
               SigTipoGeracao AS tipo
        FROM read_parquet('{fonte}')
        WHERE SigAgente IN ({lista}) AND MdaPotenciaInstaladaKW IS NOT NULL
    """).df()
    con.close()
    df["ceg"] = df["ceg"].astype("string").str.strip()
    df["data"] = pd.to_datetime(df["data"])
    return df


def desempatar(bd: pd.DataFrame, an: pd.DataFrame) -> pd.DataFrame:
    """Une BDGD e ANEEL de UMA distribuidora pelo CEG; uma linha por empreendimento.

    `bd`: unidades_mmgd da BDGD (ceg, mancha_id, mun, pot_bdgd_kw); `an`: cadastro_aneel.
    Devolve ceg, categoria, mancha_id (NaN se só ANEEL), ctmt, mun, pot_bdgd_kw, pot_aneel_kw, data, tipo.
    Um CEG repetido na BDGD (mesmo empreendimento em mais de uma camada ou UC) conta uma vez:
    fica a primeira ocorrência (a potência vem da ANEEL, então a repetição não soma).
    """
    bd = bd.drop_duplicates("ceg")
    an = an.drop_duplicates("ceg")
    m = bd[["ceg", "mancha_id", "ctmt", "mun", "pot_bdgd_kw"]].merge(
        an[["ceg", "mun", "pot_aneel_kw", "data", "tipo"]], on="ceg", how="outer",
        suffixes=("_bdgd", "_aneel"), indicator=True)
    m["categoria"] = m["_merge"].map({"both": "bdgd_e_aneel", "right_only": "lag_sistema",
                                      "left_only": "bdgd_sem_homologacao"}).astype(str)
    # município: o da ANEEL quando existe (cadastro oficial), senão o da BDGD
    m["mun"] = m["mun_aneel"].fillna(m["mun_bdgd"])
    return m.drop(columns=["_merge", "mun_aneel", "mun_bdgd"])


def ratear_lag(u: pd.DataFrame, trafos: pd.DataFrame) -> pd.DataFrame:
    """Distribui as unidades lag_sistema entre as manchas do município (ver docstring do módulo).

    `u`: saída de `desempatar`; `trafos`: mancha_id, MUN, POT_NOM (uma distribuidora).
    Devolve as linhas de `u` com mancha localizada, mais as de lag rateadas (uma linha por
    unidade × mancha, com `fracao`); lag sem rede no município sai com mancha_id NaN.
    Invariante (testada): a soma de pot_aneel_kw × fracao de cada unidade é a potência dela.
    """
    loc = u[u["categoria"] == "bdgd_e_aneel"].assign(fracao=1.0)
    lag = u[u["categoria"] == "lag_sistema"].drop(columns="mancha_id")
    w1 = loc.groupby(["mun", "mancha_id"])["pot_aneel_kw"].sum().rename("peso").reset_index()
    w2 = (trafos.rename(columns={"MUN": "mun"}).groupby(["mun", "mancha_id"])["POT_NOM"].sum()
          .rename("peso").reset_index())
    w2 = w2[~w2["mun"].isin(w1["mun"])]  # proxy só onde não há capacidade localizada
    pesos = pd.concat([w1, w2], ignore_index=True)
    pesos = pesos[pesos["peso"] > 0]
    pesos["fracao"] = pesos["peso"] / pesos.groupby("mun")["peso"].transform("sum")
    rateado = lag.merge(pesos[["mun", "mancha_id", "fracao"]], on="mun", how="left")
    rateado["fracao"] = rateado["fracao"].fillna(1.0)  # sem rede no município: fica inteiro, sem mancha
    # As sem homologação seguem junto (fração 1, na mancha da BDGD): não entram na capacidade,
    # mas o relatório e o resumo por mancha precisam delas. Nenhuma categoria some aqui.
    sem = u[u["categoria"] == "bdgd_sem_homologacao"].assign(fracao=1.0)
    out = pd.concat([loc, rateado, sem], ignore_index=True)
    if set(out["categoria"]) - set(u["categoria"]) or len(out.drop_duplicates("ceg")) != len(u.drop_duplicates("ceg")):
        raise AssertionError("ratear_lag perdeu ou inventou empreendimentos")
    return out


def fator_correcao_satelite() -> pd.Series:
    """Fator de correção por mancha (Luiz). Vazio enquanto o arquivo não existir."""
    caminho = projeto()["caminho_fator_correcao"]
    if not caminho:
        return pd.Series(dtype=float, name="fator_correcao")
    arq = RAIZ / caminho
    if not arq.exists():
        raise FileNotFoundError(f"config/projeto.yaml: caminho_fator_correcao aponta para {arq}, que não existe")
    f = pd.read_csv(arq, dtype={"mancha_id": str})
    if not {"mancha_id", "fator_correcao"} <= set(f.columns):
        raise KeyError(f"{arq.name}: esperava as colunas mancha_id e fator_correcao")
    return f.set_index("mancha_id")["fator_correcao"].astype(float)


def para_fronteira(unidades: pd.DataFrame) -> pd.DataFrame:
    """Leva a capacidade de "onde a usina está" para "por onde ela chega à rede básica".

    Duas chaves de mancha, com usos diferentes:
    - mancha_id (onde está): a subestação que a BDGD informa na unidade geradora (UG.SUB). É a
      do mapa e da densidade.
    - mancha_fronteira (por onde sai): a subestação de ORIGEM do alimentador da unidade
      (CTMT.SUB). É onde a carga dos alimentadores é somada e onde o fluxo reverso aparece para
      o ONS, então é a chave dos excedentes. Na LIGHT as duas diferem em ~15% das unidades
      (subestações satélite); na Enel RJ coincidem.
    Unidade com alimentador conhecido: fronteira = origem dele. Sem alimentador (UGAT, ou lag
    de sistema, que não está na BDGD): a potência da mancha é repartida entre fronteiras na
    mesma proporção das unidades localizadas dela; mancha sem nenhuma, fronteira = ela mesma.
    Devolve as linhas de `unidades` (repartidas) com mancha_fronteira e pot_kw ajustado.
    Invariante (testada): a soma de pot_kw não muda.
    """
    com = unidades[unidades["mancha_fronteira"].notna()]
    sem = unidades[unidades["mancha_fronteira"].isna() & unidades["mancha_id"].notna()].drop(columns="mancha_fronteira")
    matriz = com.groupby(["mancha_id", "mancha_fronteira"])["pot_kw"].sum().rename("peso").reset_index()
    matriz = matriz[matriz["peso"] > 0]
    matriz["parte"] = matriz["peso"] / matriz.groupby("mancha_id")["peso"].transform("sum")
    sem = sem.merge(matriz[["mancha_id", "mancha_fronteira", "parte"]], on="mancha_id", how="left")
    sem["mancha_fronteira"] = sem["mancha_fronteira"].fillna(sem["mancha_id"])
    sem["pot_kw"] = sem["pot_kw"] * sem["parte"].fillna(1.0)
    fora = unidades[unidades["mancha_id"].isna() & unidades["mancha_fronteira"].isna()]
    return pd.concat([com, sem.drop(columns="parte"), fora], ignore_index=True)


def construir(fator: pd.Series | None = None) -> dict[str, pd.DataFrame]:
    """Unidades desempatadas, capacidade diária por fronteira e energia gerada mensal.

    `fator`: fator de correção do satélite por mancha (onde está); aplicado na potência de cada
    unidade antes de levá-la à fronteira. None/vazio = sem correção.
    Devolve:
    - unidades: uma linha por empreendimento × mancha (categoria, fracao, potência, data);
    - diaria_fronteira: mancha_fronteira × data com potência cadastrada no dia e acumulada
      (kW, já corrigida), gravada com a coluna mancha_id = a mancha da fronteira;
    - energia_mensal: mancha (fronteira) × ene_01..12 (kWh gerados informados na BDGD, todas as
      unidades de MMGD da BDGD, inclusive sem homologação: é energia física, entra na carga
      bruta da subestação por onde sai).
    """
    fator = fator if fator is not None else pd.Series(dtype=float)
    dists = bdgd.distribuidoras()
    an = cadastro_aneel([d.agente_aneel for d in dists])
    unidades, energia = [], []
    for d in dists:
        bd = bdgd.unidades_mmgd(d)
        trafos = bdgd.trafos_distribuicao(d)[["mancha_id", "MUN", "POT_NOM"]]
        origem = bdgd.circuitos(d).set_index("COD_ID")["mancha_id"]
        u = ratear_lag(desempatar(bd, an[an["agente"] == d.agente_aneel]), trafos)
        u["mancha_fronteira"] = u["ctmt"].map(origem)
        u["distribuidora"] = d.nome
        u["data_bdgd"] = bdgd.data_referencia(d)
        unidades.append(u)
        # energia gerada por fronteira (origem do alimentador; sem alimentador, a própria mancha):
        # src/spatial/excedentes.py::pesos_carga soma na carga bruta da mesma subestação
        e = bd.assign(mancha_id=bd["ctmt"].map(origem).fillna(bd["mancha_id"]))
        energia.append(e.groupby("mancha_id")[[f"ene_{m}" for m in bdgd.MESES]].sum())
    unidades = pd.concat(unidades, ignore_index=True)
    unidades["pot_kw"] = unidades["pot_aneel_kw"] * unidades["fracao"]

    cap = unidades[unidades["categoria"] != "bdgd_sem_homologacao"].dropna(subset=["mancha_id", "data"]).copy()
    cap["pot_kw"] = cap["pot_kw"] * cap["mancha_id"].map(fator).fillna(1.0)
    cap = para_fronteira(cap)
    diaria = (cap.groupby(["mancha_fronteira", "data"])["pot_kw"].sum().rename("potencia_kw_dia")
              .rename_axis(["mancha_id", "data"]).reset_index().sort_values(["mancha_id", "data"]))
    diaria["potencia_kw_acumulada"] = diaria.groupby("mancha_id")["potencia_kw_dia"].cumsum()
    return {"unidades": unidades, "diaria_fronteira": diaria,
            "energia_mensal": pd.concat(energia).groupby(level=0).sum().rename_axis("mancha_id").reset_index()}


def resumo_por_mancha(unidades: pd.DataFrame, fator: pd.Series) -> pd.DataFrame:
    """Capacidade atual (todo o cadastro baixado) por mancha, por categoria, e fonte dominante.

    Colunas: mancha_id, capacidade_mmgd_bdgd_kw (POT_INST da própria BDGD, só para comparação),
    capacidade_homologada_localizada_kw, capacidade_lag_kw, capacidade_mmgd_kw (as duas
    anteriores), pot_sem_homologacao_kw, n_unidades, n_sem_homologacao, fonte, fator_correcao,
    capacidade_mmgd_corrigida_kw.
    """
    u = unidades.dropna(subset=["mancha_id"])

    def soma(cat, col):
        return u[u["categoria"] == cat].groupby("mancha_id")[col].sum()

    r = pd.DataFrame({
        "capacidade_mmgd_bdgd_kw": u[u["categoria"] != "lag_sistema"].groupby("mancha_id")["pot_bdgd_kw"].sum(),
        "capacidade_homologada_localizada_kw": soma("bdgd_e_aneel", "pot_kw"),
        "capacidade_lag_kw": soma("lag_sistema", "pot_kw"),
        "pot_sem_homologacao_kw": soma("bdgd_sem_homologacao", "pot_bdgd_kw"),
        "n_unidades": u[u["categoria"] != "bdgd_sem_homologacao"].groupby("mancha_id")["fracao"].sum(),
        "n_sem_homologacao": u[u["categoria"] == "bdgd_sem_homologacao"].groupby("mancha_id").size(),
    }).fillna(0.0)
    r["capacidade_mmgd_kw"] = r["capacidade_homologada_localizada_kw"] + r["capacidade_lag_kw"]
    tipo = (u.dropna(subset=["tipo"]).groupby(["mancha_id", "tipo"])["pot_kw"].sum().reset_index()
            .sort_values("pot_kw").drop_duplicates("mancha_id", keep="last").set_index("mancha_id")["tipo"])
    r["fonte"] = tipo.map(FONTE_CONTRATO).reindex(r.index)
    r["fator_correcao"] = fator.reindex(r.index)
    r["capacidade_mmgd_corrigida_kw"] = r["capacidade_mmgd_kw"] * r["fator_correcao"].fillna(1.0)
    return r.round(3).rename_axis("mancha_id").reset_index()
