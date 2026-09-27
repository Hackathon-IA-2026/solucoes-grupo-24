# -*- coding: utf-8 -*-
"""Perfis de consumo por classe MEDIDOS e composicao real por subsistema.

Substitui, na pagina "Classes de consumo", os perfis estilizados de
`classes.py` (desenhados a mao) por dado real, em duas pecas independentes:

1. **Forma horaria de cada classe** -- ANEEL "CTR - Curva de Carga Consumidor
   Tipo": curvas de 15 min medidas pelas distribuidoras nas campanhas das
   revisoes tarifarias, por subgrupo tarifario e tipo de dia.
2. **Composicao de cada subsistema** -- energia faturada real da base da
   Fronteira T-D (BDGD MT/AT por SED + SAMP BT por distribuidora), ja
   associada as SEs de fronteira do ONS e, por elas, ao subsistema.

A curva montada (composicao x forma) e comparada com a curva verificada do
ONS. A curva do ONS deixa de ser a FONTE da composicao (o NNLS antigo
adivinhava a mistura encaixando a curva em perfis inventados) e passa a ser a
VALIDACAO dela.

Parametros (classes, subgrupos, regras de composicao, caminhos) em
`config/perfis_classe.yaml`. Este modulo so LE a tabela processada; quem le o
bruto do CTR e `src/processing/perfis_classe.py` (regra do projeto: so a
ingestao e o processamento tocam o dado bruto). Construcao::

    python -m src.processing.tabelas perfis_classe
"""
from __future__ import annotations

from collections import defaultdict
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from src.utils.config import carregar
from src.utils.paths import RAIZ

from ..core.calendar_br import TYPEDAY_SATURDAY, TYPEDAY_SUNHOL, TYPEDAY_UTIL, TYPEDAYS

HOURS = list(range(24))


def cfg() -> dict:
    return carregar("perfis_classe")


def classes() -> list[str]:
    """Chaves das classes, na ordem do YAML (e a ordem da tela)."""
    return list(cfg()["classes"])


def caminho_saida() -> Path:
    return RAIZ / cfg()["saida"]


# ------------------------------------------------------------ perfis
@lru_cache(maxsize=4)
def _ler(caminho: str, mtime: float) -> dict:
    """Tabela processada -> {classe: {dia-tipo: [24 p.u.], meta...}}.

    O `mtime` entra na chave do cache: reconstruir a tabela invalida sozinho.
    """
    t = pd.read_csv(caminho)
    out = {}
    for classe, g in t.groupby("classe", sort=False):
        item = {td: g[g["tipo_dia"] == td].sort_values("hora")["pu"].tolist()
                for td in TYPEDAYS}
        m = g.iloc[0]
        item.update({"n_curvas": int(m["n_curvas"]),
                     "n_distribuidoras": int(m["n_distribuidoras"]),
                     "ano_min": int(m["ano_min"]), "ano_max": int(m["ano_max"])})
        out[classe] = item
    # proveniencia do bruto, gravada pelo processamento em cada linha
    m = t.iloc[0]
    out["_fonte"] = {"url": m["fonte_url"], "arquivo": m["fonte_arquivo"],
                     "baixado_em": m["fonte_baixado_em"], "bytes": int(m["fonte_bytes"]),
                     "linhas": int(len(t))}
    return out


def perfis() -> dict:
    """Perfis medidos da tabela processada. Sem ela: erro dizendo como construir."""
    saida = caminho_saida()
    if not saida.exists():
        raise FileNotFoundError(
            "tabela de perfis medidos ausente (%s). Rode `python -m src.ingestion.download "
            "--diretos aneel_ctr_consumidor_tipo` e depois `python -m src.processing.tabelas "
            "perfis_classe` (ou o run_heavywork.py)." % saida.name)
    return _ler(str(saida), saida.stat().st_mtime)


def fracao_sabado_domingo(p: dict) -> tuple[float, float]:
    """Energia de sabado e de domingo em relacao ao dia util (p.u. medio)."""
    return float(np.mean(p[TYPEDAY_SATURDAY])), float(np.mean(p[TYPEDAY_SUNHOL]))


def proveniencia() -> dict:
    """Envelope de proveniencia do CTR, no formato de `core.frame.Provenance`."""
    f = perfis()["_fonte"]
    return {
        "dataset": "ctr-curva-de-carga (ANEEL)", "resource": f["arquivo"], "url": f["url"],
        "fetched_at": f["baixado_em"], "rows": f["linhas"], "bytes_read": f["bytes"],
        "mode": "cache",
        "lag_note": "Campanhas de medição das revisões tarifárias: cada "
                    "distribuidora mede a cada ~4-5 anos (ano do processo na página).",
    }


def payload_perfis() -> dict:
    """Perfis medidos para a interface desenhar."""
    c = cfg()["classes"]
    p = perfis()
    out = []
    for k in classes():
        if k not in p:
            continue
        sab, dom = fracao_sabado_domingo(p[k])
        out.append({
            "key": k, "label": c[k]["rotulo"], "note": c[k]["nota"],
            "subgrupos": c[k]["subgrupos"],
            # forma do dia util somando 1 (comparavel com a curva do ONS)
            "profile": [round(v / sum(p[k][TYPEDAY_UTIL]), 5) for v in p[k][TYPEDAY_UTIL]],
            "profile_pu": {td: p[k][td] for td in TYPEDAYS},
            "saturday_ratio": round(sab, 3), "weekend_ratio": round(dom, 3),
            "n_curvas": p[k]["n_curvas"], "n_distribuidoras": p[k]["n_distribuidoras"],
            "ano_min": p[k]["ano_min"], "ano_max": p[k]["ano_max"],
        })
    return {"hours": HOURS, "classes": out}


# ------------------------------------------------------------ composicao
def composicao_subsistemas(per_frontier: list[dict], seds: list[dict]) -> dict:
    """Energia real por classe da pagina, somada por subsistema.

    Entrada: o resultado da correlacao fronteira T-D (`fronteira.correlacao`).
    Cada SE de fronteira do ONS tem subsistema, a BT do SAMP rateada para ela
    (`e_bt_class_kwh`) e as SEDs da BDGD associadas (`sed_idx`), cada uma com
    a energia MT/AT por classe e a contagem de UCs de MT e de AT.
    So entra o que foi associado a alguma SE de fronteira: o resto nao tem
    subsistema conhecido (a cobertura contra o ONS e reportada a parte).
    """
    regra = cfg()["composicao"]
    acc: dict[str, dict] = defaultdict(lambda: {"kwh": defaultdict(float), "kwh_mista": 0.0})
    for f in per_frontier:
        a = acc[f["subsystem"]]
        for cls_bt, v in (f.get("e_bt_class_kwh") or {}).items():
            a["kwh"][regra["bt"].get(cls_bt, "comercial_bt")] += float(v)
        for i in f.get("sed_idx", []):
            s = seds[i]
            e = float(sum(s["e_class"].values()))
            if s["n_at"] == 0:
                alvo = regra["sed_so_mt"]
            elif s["n_mt"] == 0:
                alvo = regra["sed_so_at"]
            else:
                alvo = regra["sed_mista"]
                a["kwh_mista"] += e
            a["kwh"][alvo] += e
    out = {}
    for ss, a in acc.items():
        tot = sum(a["kwh"].values())
        if tot <= 0:
            continue
        out[ss] = {
            "kwh": {k: round(a["kwh"].get(k, 0.0), 0) for k in classes()},
            "pesos": {k: round(a["kwh"].get(k, 0.0) / tot, 4) for k in classes()},
            "total_gwh": round(tot / 1e6, 1),
            "fracao_sed_mista": round(a["kwh_mista"] / tot, 4),
        }
    return out


# ------------------------------------------------------------ montagem
def montar(pesos: dict[str, float], p: dict) -> dict:
    """Curva do dia util montada = soma das formas medidas, pesadas pela energia.

    `pesos` e fracao da energia ANUAL. A forma e de DIA UTIL, entao o peso de
    cada classe no dia util e corrigido pelo fim de semana medido dela:
    energia semanal ~ 5 + sab + dom (em p.u. de dia util), logo a energia de
    um dia util da classe c e proporcional a  w_c / (5 + sab_c + dom_c).
    A razao domingo/dia util montada sai da mesma conta.
    """
    w_util, dom = {}, {}
    for k, w in pesos.items():
        if k not in p or w <= 0:
            continue
        sab_k, dom_k = fracao_sabado_domingo(p[k])
        w_util[k] = w / (5.0 + sab_k + dom_k)
        dom[k] = dom_k
    tot = sum(w_util.values())
    if tot <= 0:
        return {"shape": [0.0] * 24, "weekend_ratio": None}
    curva = np.zeros(24)
    for k, w in w_util.items():
        pu = np.asarray(p[k][TYPEDAY_UTIL], dtype="f8")
        curva += (w / tot) * pu / pu.sum()      # forma da classe somando 1
    return {"shape": curva / curva.sum(),
            "weekend_ratio": sum(w_util[k] * dom[k] for k in w_util) / tot}


def r2(observada: np.ndarray, montada: np.ndarray) -> float:
    """R² da forma montada contra a observada (mesma conta do NNLS antigo)."""
    o, m = np.asarray(observada, "f8"), np.asarray(montada, "f8")
    ss_tot = float(np.sum((o - o.mean()) ** 2))
    return 1.0 - float(np.sum((o - m) ** 2)) / ss_tot if ss_tot > 0 else 0.0


def qualidade(valor_r2: float) -> str:
    q = cfg()["qualidade_r2"]
    return "bom" if valor_r2 >= q["bom"] else "moderado" if valor_r2 >= q["moderado"] else "fraco"
