"""Leitura da BDGD (ANEEL) de cada distribuidora da área piloto, já normalizada.

Herdado de Backend/RDX/extrator.py (extrair_dados_completos_gdb, processar_geracao_distribuida),
com estas mudanças:
- Lê o .gdb DENTRO do .zip baixado (GDAL /vsizip/, via pyogrio): o disco da máquina é
  apertado e a BDGD descompactada passa de 5 GB por distribuidora.
- Lê só as colunas usadas. Nada de CPF/CNPJ ou nome sai daqui (a BDGD não tem; o cadastro da
  ANEEL tem, e é lido só por colunas em src/spatial/mmgd.py).
- Camadas vêm de config/espacial.yaml (mesmos nomes nas duas distribuidoras desde a BDGD 2022).
- MMGD = unidade geradora cujo CEG_GD casa `padrao_ceg_mmgd` ("GD."): o RDX contava qualquer
  CEG preenchido e somava usinas grandes da UGAT como se fossem MMGD.
- Toda subestação ganha `mancha_id` = "<sigla>:<COD_ID>" (chave composta: COD_ID só é único
  dentro da distribuidora). Nenhuma tabela deste módulo sai sem ela.
"""
from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pyogrio

from src.utils.config import arquivo_direto, carregar

MESES = [f"{m:02d}" for m in range(1, 13)]


def cfg() -> dict:
    return carregar("espacial")


@dataclass(frozen=True)
class Distribuidora:
    sigla: str
    nome: str
    apelido_bdgd: str
    agente_aneel: str


def distribuidoras() -> list[Distribuidora]:
    return [Distribuidora(**d) for d in cfg()["distribuidoras"]]


def caminho_gdb(dist: Distribuidora) -> str:
    """Caminho GDAL do .gdb dentro do .zip baixado (config/fontes_ons.yaml, arquivo direto).

    O nome da pasta .gdb é lido do próprio zip (a ANEEL muda a caixa: "Light_" x "LIGHT_").
    """
    zip_ = arquivo_direto(dist.apelido_bdgd)
    if not zip_.exists():
        raise FileNotFoundError(f"BDGD de {dist.nome} não baixada ({zip_}): rode a ingestão "
                                f"(python -m src.ingestion.download --diretos {dist.apelido_bdgd})")
    with zipfile.ZipFile(zip_) as z:
        pastas = {n.split("/")[0] for n in z.namelist() if n.split("/")[0].lower().endswith(".gdb")}
    if len(pastas) != 1:
        raise ValueError(f"{zip_.name}: esperava uma pasta .gdb no zip, achei {sorted(pastas)}")
    return f"/vsizip/{zip_.as_posix()}/{pastas.pop()}"


def data_referencia(dist: Distribuidora) -> pd.Timestamp:
    """Data de referência da BDGD, lida do nome do arquivo ("Light_382_2025-12-31_V11_...")."""
    m = re.search(r"_(\d{4}-\d{2}-\d{2})_", Path(arquivo_direto(dist.apelido_bdgd)).name)
    if not m:
        raise ValueError(f"{dist.apelido_bdgd}: nome do arquivo sem data de referência")
    return pd.Timestamp(m.group(1))


def _ler(gdb: str, camada: str, colunas: list[str], geometria: bool = False) -> pd.DataFrame:
    """Uma camada, só com as colunas pedidas. Coluna ausente = erro (BDGD fora do padrão)."""
    existentes = set(pyogrio.read_info(gdb, layer=camada)["fields"])
    faltando = [c for c in colunas if c not in existentes]
    if faltando:
        raise KeyError(f"BDGD {gdb.rsplit('/', 1)[-1]}, camada {camada}: faltam colunas {faltando}")
    df = pyogrio.read_dataframe(gdb, layer=camada, columns=colunas, read_geometry=geometria)
    for c in ("COD_ID", "SUB", "CTMT", "MUN"):
        if c in df.columns:  # chaves sempre como texto sem espaços (a BDGD mistura tipos)
            df[c] = df[c].astype("string").str.strip()
    return df


def _mancha_id(sigla: str, cod: pd.Series) -> pd.Series:
    """"<sigla>:<COD_ID>"; código vazio ou nulo vira NA (nunca um id falso como "LIGHT:").

    A BDGD tem trafos e alimentadores com SUB em branco. Antes eles formavam a mancha "LIGHT:",
    que não existe na camada SUB e estourava na publicação.
    """
    cod = cod.astype("string").str.strip()
    return (sigla + ":" + cod).where(cod.notna() & (cod != ""))


# --------------------------------------------------------------------------- camadas
def subestacoes(dist: Distribuidora) -> gpd.GeoDataFrame:
    """Subestações (polígono) com nome e potência nominal AT/MT (soma dos UNTRAT, MVA)."""
    c, gdb = cfg()["camadas"], caminho_gdb(dist)
    sub = _ler(gdb, c["subestacao"], ["COD_ID", "NOME"], geometria=True)
    trafos = _ler(gdb, c["trafo_subestacao"], ["SUB", "POT_NOM"])
    pot = trafos.groupby("SUB")["POT_NOM"].sum().rename("potencia_nominal_mva")
    sub = sub.merge(pot, left_on="COD_ID", right_index=True, how="left")
    sub["potencia_nominal_mva"] = sub["potencia_nominal_mva"].fillna(0.0)
    sub["mancha_id"] = _mancha_id(dist.sigla, sub["COD_ID"])
    sub["distribuidora"] = dist.nome
    if sub["mancha_id"].duplicated().any():
        raise ValueError(f"{dist.nome}: COD_ID de subestação repetido na BDGD")
    return sub.rename(columns={"COD_ID": "cod_sub", "NOME": "nome"})


def trafos_distribuicao(dist: Distribuidora) -> gpd.GeoDataFrame:
    """Transformadores MT/BT (pontos): subestação, alimentador, município e potência (kVA)."""
    t = _ler(caminho_gdb(dist), cfg()["camadas"]["trafo_distribuicao"], ["SUB", "CTMT", "MUN", "POT_NOM"],
             geometria=True)
    t["POT_NOM"] = t["POT_NOM"].astype(float).fillna(0.0)
    t["mancha_id"] = _mancha_id(dist.sigla, t["SUB"])
    return t


def circuitos(dist: Distribuidora) -> pd.DataFrame:
    """Alimentadores MT: subestação de origem e energia injetada por mês (ENE_01..12, kWh)."""
    cols = ["COD_ID", "SUB", *[f"ENE_{m}" for m in MESES]]
    ct = _ler(caminho_gdb(dist), cfg()["camadas"]["circuito_mt"], cols)
    ct["mancha_id"] = _mancha_id(dist.sigla, ct["SUB"])
    return ct


def consumidores_at(dist: Distribuidora) -> pd.DataFrame:
    """Consumidores AT ligados direto na subestação: energia por mês (ponta + fora ponta, kWh).

    Eles não passam por alimentador MT, então não estão no CTMT; sem isto a carga de uma
    subestação com indústria em AT ficaria subestimada.
    """
    cols = ["SUB", *[f"ENE_P_{m}" for m in MESES], *[f"ENE_F_{m}" for m in MESES]]
    uc = _ler(caminho_gdb(dist), cfg()["camadas"]["consumidor_at"], cols)
    out = pd.DataFrame({"mancha_id": _mancha_id(dist.sigla, uc["SUB"])})
    for m in MESES:
        out[f"ENE_{m}"] = uc[f"ENE_P_{m}"].fillna(0) + uc[f"ENE_F_{m}"].fillna(0)
    return out


def segmentos_at(dist: Distribuidora) -> gpd.GeoDataFrame:
    """Linhas de alta tensão (pontos de conexão PAC_1/PAC_2): base da hierarquia."""
    return _ler(caminho_gdb(dist), cfg()["camadas"]["segmento_at"], ["PAC_1", "PAC_2"], geometria=True)


def eh_mmgd(ceg: pd.Series, padrao: str) -> pd.Series:
    """True para unidade geradora de MMGD: CEG no padrão de GD da ANEEL ("GD.UF.xxx.xxx.xxx").

    Usina grande ligada na rede da distribuidora (UHE, UTE, PCH) também aparece na UGAT/UGMT, com
    CEG de outro formato ou vazio: não é MMGD e não pode entrar na capacidade.
    """
    return ceg.astype("string").str.strip().str.contains(padrao, regex=True, na=False)


def unidades_mmgd(dist: Distribuidora) -> pd.DataFrame:
    """Unidades geradoras de MMGD da BDGD (UGBT, UGMT, UGAT), uma linha por unidade.

    Colunas: ceg, mancha_id, ctmt (alimentador; vazio na UGAT), mun (código IBGE), pot_bdgd_kw,
    ene_01..12 (kWh gerados no mês), camada. Filtro de MMGD pelo padrão do CEG (ver docstring do módulo). A UGAT publica energia
    em ponta/fora ponta (ENE_P/ENE_F): somadas, como no RDX.
    """
    c, gdb = cfg(), caminho_gdb(dist)
    padrao = c["padrao_ceg_mmgd"]
    partes = []
    for camada in c["camadas"]["geracao"]:
        if pyogrio.read_info(gdb, layer=camada)["features"] == 0:
            continue  # a Enel RJ publica a UGAT vazia
        campos = set(pyogrio.read_info(gdb, layer=camada)["fields"])
        at = f"ENE_P_{MESES[0]}" in campos
        energia = ([f"ENE_P_{m}" for m in MESES] + [f"ENE_F_{m}" for m in MESES]) if at else \
            [f"ENE_{m}" for m in MESES]
        # UGAT não tem alimentador MT (liga direto na subestação): ctmt fica vazio
        tem_ctmt = "CTMT" in campos
        ug = _ler(gdb, camada, ["CEG_GD", "SUB", "MUN", "POT_INST", *(["CTMT"] if tem_ctmt else []), *energia])
        ug = ug[eh_mmgd(ug["CEG_GD"], padrao)]
        out = pd.DataFrame({"ceg": ug["CEG_GD"].astype("string").str.strip(),
                            "mancha_id": _mancha_id(dist.sigla, ug["SUB"]),
                            "ctmt": ug["CTMT"] if tem_ctmt else pd.Series(pd.NA, index=ug.index, dtype="string"),
                            "mun": ug["MUN"], "pot_bdgd_kw": ug["POT_INST"].astype(float),
                            "camada": camada})
        for m in MESES:
            out[f"ene_{m}"] = (ug[f"ENE_P_{m}"].fillna(0) + ug[f"ENE_F_{m}"].fillna(0)) if at \
                else ug[f"ENE_{m}"].fillna(0)
        partes.append(out)
    return pd.concat(partes, ignore_index=True)
