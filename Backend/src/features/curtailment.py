"""Features do classificador de risco de curtailment por razão (Fase 4).

Uma linha por (usina/conjunto, ALVO) num horizonte h. Tudo o que vem de dado observado passa
por src/features/defasagens.py (só valores até a emissão t − h), igual à carga:
- histórico da própria usina: corte na emissão, frações de tempo com corte (6 h, 1 dia, 1
  semana), mesmo horário do dia anterior e da semana anterior, MW cortados;
- estado do sistema na emissão: fração das usinas do mesmo subsistema e do SIN com corte;
- carga supervisionada e MMGD do subsistema da usina e do SIN (balanço carga–geração);
- calendário do ALVO (hora, faixa de curtailment, dia da semana com feriado = domingo, mês);
- atributos fixos: fonte, subsistema, UF, a própria usina (categoria).

Chave da usina = fonte + id (regra do CLAUDE.md), já pronta na coluna `chave` dos rótulos.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.features import carga as fc
from src.features import defasagens
from src.utils.config import carregar
from src.utils.tempo import PASSO

_FAIXAS = {nome: i for i, nome in enumerate(carregar("processamento")["calendario"]["faixas_curtailment"])}
_SUBSISTEMAS = {s: i for i, s in enumerate(fc.SUBSISTEMAS)}


@dataclass
class Painel:
    """Rótulos em formato largo (timestamp × chave), grade regular de 30 min."""
    flags: dict[str, pd.DataFrame]   # razão -> 1.0/0.0 (NaN = usina sem registro no instante)
    mw: dict[str, pd.DataFrame]      # razão -> MW cortados
    usinas: pd.DataFrame             # index chave: nom_usina, uf, subsistema, fonte, id_ons, codigo
    carga: pd.DataFrame              # carga supervisionada larga (SE, S, NE, N, SIN)
    mmgd: pd.DataFrame
    cal: pd.DataFrame                # calendário numérico + faixa de curtailment (código)

    @property
    def ultimo_dado(self) -> pd.Timestamp:
        return self.flags[next(iter(self.flags))].dropna(how="all").index.max()


def codigos_usinas(chaves, conhecidos: pd.Series | None) -> pd.Series:
    """Código numérico (categoria do LightGBM) de cada usina.

    Os códigos do TREINO são reaproveitados sempre (`conhecidos`, salvos com o modelo); usina
    nova recebe código novo, depois do maior. Numerar de novo a cada painel trocaria o código
    de uma usina por outro quando o conjunto de usinas muda: o modelo passaria a usar o
    histórico aprendido de uma usina para outra, sem erro nenhum. Aqui isso não tem como ocorrer.
    """
    conhecidos = pd.Series(dtype="int64") if conhecidos is None else conhecidos
    novos = sorted(set(chaves) - set(conhecidos.index))
    base = int(conhecidos.max()) + 1 if len(conhecidos) else 0
    todos = pd.concat([conhecidos, pd.Series(range(base, base + len(novos)), index=novos, dtype="int64")])
    return todos.reindex(list(chaves))


def montar_painel(rotulos: pd.DataFrame, atributos: pd.DataFrame, carga: pd.DataFrame,
                  calendario: pd.DataFrame, razoes: list[str], inicio: pd.Timestamp,
                  passos_futuros: int, codigos: pd.Series | None = None) -> Painel:
    """Monta o painel a partir das tabelas processadas (rótulos, carga, calendário).

    - `rotulos`: formato longo (chave, timestamp, flag_<razão>, corte_MW_<razão>);
    - `atributos`: uma linha por chave (nom_usina, uf, subsistema, fonte, id_ons), o registro
      mais recente de cada usina (algumas mudaram de nome/UF no ONS);
    - `inicio`: primeiro instante guardado (o chamador desconta a maior defasagem);
    - a grade vai até o último rótulo + `passos_futuros` (alvos além do último dado);
    - `codigos`: códigos das usinas salvos no treino (ver `codigos_usinas`).
    """
    r = rotulos[rotulos["timestamp"] >= inicio]
    fim = r["timestamp"].max() + passos_futuros * PASSO
    grade = pd.date_range(inicio, fim, freq=PASSO, name="timestamp")
    flags, mw = {}, {}
    for razao in razoes:
        flags[razao] = _larga(r, f"flag_{razao}", grade)
        mw[razao] = _larga(r, f"corte_MW_{razao}", grade)
    chaves = list(flags[razoes[0]].columns)
    usinas = atributos.set_index("chave").reindex(chaves)[["nom_usina", "uf", "subsistema", "fonte", "id_ons"]]
    usinas["codigo"] = codigos_usinas(usinas.index, codigos).to_numpy()
    cargas = fc.series_largas(carga, "carga_supervisionada", 0).reindex(grade)
    mmgd = fc.series_largas(carga, "mmgd_estimada", 0).reindex(grade)
    cal = fc.calendario(calendario).reindex(grade)
    cal["faixa"] = calendario.set_index(pd.to_datetime(calendario["timestamp"]))["faixa_curtailment"] \
        .map(_FAIXAS).reindex(grade).to_numpy()
    return Painel(flags=flags, mw=mw, usinas=usinas, carga=cargas, mmgd=mmgd, cal=cal)


def _larga(r: pd.DataFrame, coluna: str, grade: pd.DatetimeIndex) -> pd.DataFrame:
    """Longo -> largo (timestamp × chave), float32, na grade regular (sem registro = NaN)."""
    larga = r.pivot(index="timestamp", columns="chave", values=coluna).astype("float32")
    larga.columns = larga.columns.astype(str)
    return larga.reindex(grade)


def estado_do_sistema(painel: Painel) -> dict[str, pd.DataFrame]:
    """Por razão: fração das usinas com corte em cada instante, por subsistema e no SIN.

    Calculado uma vez (não por usina). As colunas são séries no tempo; a defasagem até a
    emissão é aplicada em `matriz_usina`, como qualquer outro dado observado.
    """
    out = {}
    for razao, f in painel.flags.items():
        cols = {"SIN": f.mean(axis=1)}
        for sub in fc.SUBSISTEMAS:
            chaves = painel.usinas.index[painel.usinas["subsistema"] == sub]
            cols[sub] = f[chaves].mean(axis=1) if len(chaves) else pd.Series(np.nan, index=f.index)
        out[razao] = pd.DataFrame(cols)
    return out


def matriz_usina(painel: Painel, sistema: dict[str, pd.DataFrame], chave: str, horizonte: int,
                 cfg_features: dict) -> pd.DataFrame:
    """Features de uma usina num horizonte (índice = timestamp do alvo, grade inteira)."""
    h = horizonte
    u = painel.usinas.loc[chave]
    sub = u["subsistema"]
    blocos = []
    for razao in painel.flags:
        pre = razao.lower()
        blocos.append(defasagens.montar(painel.flags[razao][chave], h, f"{pre}_usina",
                                        cfg_features["defasagens_recentes"],
                                        cfg_features["defasagens_sazonais"],
                                        cfg_features["janelas_media"]))
        blocos.append(defasagens.montar(painel.mw[razao][chave], h, f"{pre}_mw_usina", [0], [], [48]))
        for escopo in ("SIN", sub):
            nome = "sin" if escopo == "SIN" else "subsistema"
            blocos.append(defasagens.montar(sistema[razao][escopo], h, f"{pre}_{nome}", [0], [], [48]))
    for escopo, nome in (("SIN", "sin"), (sub, "subsistema")):
        blocos.append(defasagens.montar(painel.carga[escopo], h, f"carga_{nome}", [0], [], []))
        blocos.append(defasagens.montar(painel.mmgd[escopo], h, f"mmgd_{nome}", [0], [], []))
    x = pd.concat([*blocos, painel.cal], axis=1)
    x["fonte_solar"] = int(u["fonte"] == "solar")
    x["subsistema_cod"] = _SUBSISTEMAS.get(sub, -1)
    x["usina_cod"] = int(u["codigo"])
    return x.astype("float32")


def rotulos_usina(painel: Painel, chave: str) -> pd.DataFrame:
    """Alvos da usina: flag e MW por razão (NaN = sem registro, linha não entra)."""
    return pd.DataFrame({**{f"flag_{r}": painel.flags[r][chave] for r in painel.flags},
                         **{f"mw_{r}": painel.mw[r][chave] for r in painel.mw}})


# Nome exibido no Detalhe do Alerta para cada grupo de features (prefixo -> rótulo). As
# contribuições SHAP das features de um mesmo grupo (ex.: todas as defasagens do histórico da
# usina) são somadas: o operador lê "Histórico de cortes ENE da usina", não "ene_usina_media_48".
_ROTULOS_FIXOS = [
    ("carga_sin", "Carga supervisionada do SIN"),
    ("carga_subsistema", "Carga supervisionada do subsistema"),
    ("mmgd_sin", "Geração MMGD estimada (SIN)"),
    ("mmgd_subsistema", "Geração MMGD estimada (subsistema)"),
    ("hora_decimal", "Hora do dia"),
    ("faixa", "Faixa horária de curtailment"),
    ("patamar", "Patamar de carga"),
    ("dia_semana_efetivo", "Dia da semana (feriado = domingo)"),
    ("eh_feriado", "Dia da semana (feriado = domingo)"),
    ("dia_dos_pais", "Dia dos Pais"),
    ("mes", "Época do ano"),
    ("dia_do_ano", "Época do ano"),
    ("fonte_solar", "Fonte (eólica ou solar)"),
    ("subsistema_cod", "Subsistema"),
    ("usina_cod", "Perfil da usina"),
]


def rotulo_explicacao(feature: str) -> str:
    """Rótulo legível do grupo de uma feature (ver _ROTULOS_FIXOS e as features por razão)."""
    razao, _, resto = feature.partition("_")
    por_razao = {"mw_usina": "MW cortados por {R} na usina", "usina": "Histórico de cortes {R} da usina",
                 "sin": "Usinas com corte {R} no SIN", "subsistema": "Usinas com corte {R} no subsistema"}
    if razao in ("ene", "cnf", "rel"):
        for pre, rot in por_razao.items():
            if resto.startswith(pre):
                return rot.format(R=razao.upper())
    for pre, rot in _ROTULOS_FIXOS:
        if feature.startswith(pre):
            return rot
    raise KeyError(f"feature sem rótulo de explicação: {feature}")
