"""ÚNICA função autorizada a cruzar recortes por subsistema, área de carga e UF.

Regra do CLAUDE.md: nunca cruzar subsistema × área operativa sem
data/processed/mapeamento_subsistema_area.csv. Centralizar aqui elimina duas classes de bug:
- tradução "na mão" de códigos (a API usa SECO, as bases do portal usam SE: um join direto
  dá resultado vazio sem erro nenhum);
- atribuição silenciosa de UF a área quando a UF se divide em mais de uma área
  (a Bahia está em BASE e em BAOE).
tests/test_joins.py garante que nenhum outro módulo lê o CSV de mapeamento diretamente.
"""
from functools import lru_cache

import pandas as pd

from src.utils.paths import DATA_PROCESSED

ARQUIVO_MAPEAMENTO = DATA_PROCESSED / "mapeamento_subsistema_area.csv"
CHAVES = ("cod_areacarga", "uf", "cod_subsistema_api", "id_subsistema")


@lru_cache(maxsize=1)
def _mapeamento() -> pd.DataFrame:
    if not ARQUIVO_MAPEAMENTO.exists():
        raise FileNotFoundError(
            f"{ARQUIVO_MAPEAMENTO} não existe: rode `python -m src.processing.mapeamento`. "
            "Sem ele nenhum cruzamento subsistema × área é permitido.")
    m = pd.read_csv(ARQUIVO_MAPEAMENTO, dtype=str)
    # Uma linha por (área, UF): explode a lista "BA;SE" para permitir cruzar por UF.
    m["uf"] = m["ufs"].str.split(";")
    return m.explode("uf").reset_index(drop=True)


def codigos_areacarga(tipo: str) -> list[str]:
    """Códigos de área de carga de um tipo do mapeamento ('subsistema' | 'area' | 'perdas').

    Quem só precisa da LISTA de áreas (ex.: carga por área de carga em processing/cadastro.py)
    pede aqui, em vez de abrir o CSV: o mapeamento continua sendo lido num lugar só.
    """
    m = _mapeamento()
    if tipo not in set(m["tipo"]):
        raise ValueError(f"tipo '{tipo}' fora do mapeamento: {sorted(set(m['tipo']))}")
    return sorted(m.loc[m["tipo"] == tipo, "cod_areacarga"].unique())


def cruzar_subsistema_area(df: pd.DataFrame, coluna: str, de: str, para: str,
                           ambiguos: str = "erro") -> pd.DataFrame:
    """Acrescenta a coluna `para` a `df`, traduzindo a partir de `df[coluna]` (que é do tipo `de`).

    de/para: 'cod_areacarga' | 'uf' | 'cod_subsistema_api' | 'id_subsistema'.
    ambiguos: o que fazer quando um valor de origem leva a MAIS DE UM destino
      (ex.: UF 'BA' -> áreas BASE e BAOE):
        'erro'   -> levanta ValueError (padrão: força quem chama a decidir)
        'marcar' -> destino fica vazio e a coluna `<para>_ambiguo` = True
    Valores de origem inexistentes no mapeamento sempre levantam erro.
    """
    if de not in CHAVES or para not in CHAVES or de == para:
        raise ValueError(f"de/para devem ser distintos e estar em {CHAVES}")
    m = _mapeamento()
    if de != "uf" and para != "uf":  # sem UF, a tabela é 1 linha por área
        m = m.drop(columns=["uf"]).drop_duplicates()
    tabela = m[[de, para]].drop_duplicates()
    # linhas de perdas/subsistema não têm área/UF: ficam fora de traduções que as exigem
    tabela = tabela.dropna()

    desconhecidos = set(df[coluna].dropna().unique()) - set(tabela[de])
    if desconhecidos:
        raise ValueError(f"valores de '{coluna}' fora do mapeamento ({de}): {sorted(desconhecidos)}")

    n_destinos = tabela.groupby(de)[para].nunique()
    amb = set(n_destinos[n_destinos > 1].index) & set(df[coluna].dropna().unique())
    if amb and ambiguos == "erro":
        raise ValueError(f"tradução {de}->{para} ambígua para {sorted(amb)}; "
                         "use ambiguos='marcar' e trate explicitamente")
    unicos = tabela[~tabela[de].isin(amb)].rename(columns={de: coluna})
    out = df.merge(unicos, on=coluna, how="left", validate="many_to_one")
    if ambiguos == "marcar":
        out[f"{para}_ambiguo"] = out[coluna].isin(amb)
    return out
