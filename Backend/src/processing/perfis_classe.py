"""Perfis horários de consumo por classe, MEDIDOS pela ANEEL (tabela `perfis_classe`).

Fonte: ANEEL "CTR - Curva de Carga Consumidor Tipo" (apelido `aneel_ctr_consumidor_tipo` em
config/fontes_ons.yaml): curvas de demanda de 15 min medidas pelas distribuidoras nas campanhas
das revisões tarifárias periódicas, por subgrupo tarifário e tipo de dia.

Saída: `saida` de config/perfis_classe.yaml (data/processed/perfis_classe_ctr.csv), uma linha
por classe × dia-tipo × hora, com a amostra (curvas, distribuidoras, anos) e a proveniência do
bruto (URL, data do download). Quem lê: oraculo/profiles/medidos.py (página Classes de consumo).
Só este módulo toca o bruto (regra de tests/test_estrutura.py).

Rodar sozinho:  python -m src.processing.tabelas perfis_classe
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from src.utils.config import arquivo_direto, carregar
from src.utils.paths import RAIZ

APELIDO_ANEEL_CTR = "aneel_ctr_consumidor_tipo"
HORAS = range(24)
# Mesmos rótulos de dia-tipo do resto do projeto (oraculo/core/calendar_br.py).
UTIL, SABADO, DOMINGO = "util", "sabado", "domingo_feriado"
DIAS_TIPO = (UTIL, SABADO, DOMINGO)


def _texto(v) -> str:
    """O Parquet da ANEEL mistura str e bytes latin-1 na mesma coluna."""
    return v.decode("latin-1") if isinstance(v, bytes) else str(v)


def _dia_tipo(s: str) -> str:
    """'Dia útil' / 'Sábado' / 'Domingo' -> dia-tipo do projeto.

    Compara só o prefixo ASCII: o acento vem corrompido em parte das linhas. Domingo vira
    `domingo_feriado`, como no resto do projeto (feriado tratado como domingo).
    """
    s = s.strip().upper()
    if s.startswith("DIA"):
        return UTIL
    if s.startswith("DOM"):
        return DOMINGO
    return SABADO


def construir_perfis_classe(bruto: Path | None = None, saida: Path | None = None) -> pd.DataFrame:
    """Lê o CTR bruto e grava a tabela de perfis por classe e dia-tipo.

    Método, por classe:
      1. uma "curva" = distribuidora × subgrupo × demandante (CT-nnn);
      2. média dos 4 quartos de hora -> 24 valores por dia-tipo;
      3. cada curva é dividida pela SUA média de dia útil (p.u.): o CTR vem em unidades
         absolutas diferentes por CT; em p.u. elas se comparam e sábado/domingo ficam relativos
         ao dia útil da mesma curva;
      4. perfil da classe = média simples das curvas em p.u.

    Decisão: média SIMPLES entre curvas. O arquivo não traz quantos consumidores cada CT
    representa, então não há peso honesto a aplicar — e isso é declarado na página.
    `bruto` e `saida` só são passados pelos testes (tabelas mínimas em pasta temporária).
    """
    cfg = carregar("perfis_classe")
    bruto = bruto or arquivo_direto(APELIDO_ANEEL_CTR)
    if not bruto.exists():
        raise FileNotFoundError(f"CTR da ANEEL ausente em {bruto}. Rode: python -m "
                                f"src.ingestion.download --diretos {APELIDO_ANEEL_CTR}")
    cols = ["SigCcs", "AnoPrcCal", "NomSubGrupoTarifario", "DscDemandante", "DscTipoDia",
            "HorInicial", "VlrDmd"]
    d = pd.read_parquet(bruto, columns=cols)
    # decodifica pelos valores ÚNICOS (2,9 mi linhas, poucas centenas de valores distintos)
    for col in ("SigCcs", "NomSubGrupoTarifario", "DscDemandante", "DscTipoDia", "HorInicial"):
        d[col] = d[col].map({v: _texto(v) for v in d[col].unique()})
    d["tipo_dia"] = d["DscTipoDia"].map({v: _dia_tipo(v) for v in d["DscTipoDia"].unique()})
    d["hora"] = d["HorInicial"].str[:2].astype(int)

    # Um processo por revisão tarifária: fica só o mais recente de cada distribuidora (misturar
    # revisões contaria a mesma distribuidora várias vezes na média).
    if cfg["selecao"]["processo_mais_recente"]:
        d = d[d["AnoPrcCal"] == d.groupby("SigCcs")["AnoPrcCal"].transform("max")]

    # subgrupo -> classe da página (subgrupo fora do YAML, ex. B4, sai aqui)
    sub2cls = {sg: k for k, v in cfg["classes"].items() for sg in v["subgrupos"]}
    d["classe"] = d["NomSubGrupoTarifario"].map(sub2cls)
    d = d[d["classe"].notna()]

    chave = ["classe", "SigCcs", "NomSubGrupoTarifario", "DscDemandante"]
    horario = d.groupby(chave + ["tipo_dia", "hora"])["VlrDmd"].mean().unstack("hora")
    util = horario.xs(UTIL, level="tipo_dia").mean(axis=1)
    util = util[util > cfg["selecao"]["media_minima_dia_util"]]

    # proveniência do bruto, repetida em cada linha: quem lê a tabela processada (a API) não
    # precisa tocar o bruto para dizer de onde o dado veio
    url = next(a["url"] for a in carregar("fontes_ons")["arquivos_diretos"]
               if a["apelido"] == APELIDO_ANEEL_CTR)
    baixado = datetime.fromtimestamp(bruto.stat().st_mtime, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    linhas = []
    for classe in cfg["classes"]:
        base = util[util.index.get_level_values("classe") == classe]
        if base.empty:
            continue
        dist = base.index.get_level_values("SigCcs")
        anos = d.loc[d["SigCcs"].isin(set(dist)) & (d["classe"] == classe), "AnoPrcCal"]
        for td in DIAS_TIPO:
            pu = horario.xs(td, level="tipo_dia").reindex(base.index).div(base, axis=0).dropna()
            perfil = pu.mean()
            for h in HORAS:
                linhas.append({
                    "classe": classe, "tipo_dia": td, "hora": h,
                    "pu": round(float(perfil.get(h, np.nan)), 5),
                    "n_curvas": int(len(pu)), "n_distribuidoras": int(dist.nunique()),
                    "ano_min": int(anos.min()), "ano_max": int(anos.max()),
                    "fonte_url": url, "fonte_arquivo": bruto.name, "fonte_baixado_em": baixado,
                    "fonte_bytes": int(bruto.stat().st_size),
                })
    out = pd.DataFrame(linhas)
    saida = saida or RAIZ / cfg["saida"]
    saida.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(saida, index=False)
    return out
