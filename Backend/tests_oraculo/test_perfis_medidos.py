# -*- coding: utf-8 -*-
"""Composicao real por subsistema e montagem da curva (oraculo/profiles/medidos.py).

As entradas aqui sao tabelas MINIMAS montadas no teste, no formato exato da
base da fronteira, so para verificar as contas. Nenhuma sai do teste. A
construcao dos perfis a partir do CTR e testada em tests/test_perfis_classe.py.

Sem teste de vazamento temporal: o modulo e descritivo (media de campanhas de
medicao e soma de energia faturada), nao ha treino nem previsao.
"""
from __future__ import annotations

import numpy as np
import pytest

from oraculo.profiles import medidos as M


def _sed(n_mt, n_at, kwh):
    return {"n_mt": n_mt, "n_at": n_at, "e_class": {"industrial": kwh}}


def test_composicao_por_tensao_e_subsistema():
    seds = [_sed(3, 0, 100.0), _sed(0, 2, 300.0), _sed(1, 1, 50.0)]
    per = [
        {"subsystem": "SE", "sed_idx": [0, 1, 2],
         "e_bt_class_kwh": {"residencial": 400.0, "industrial": 100.0, "rural": 50.0}},
        {"subsystem": "S", "sed_idx": [], "e_bt_class_kwh": {}},   # sem energia: some
    ]
    c = M.composicao_subsistemas(per, seds)
    assert set(c) == {"SE"}
    k = c["SE"]["kwh"]
    assert k["media_tensao"] == 150.0          # so-MT + mista (regra do YAML)
    assert k["alta_tensao"] == 300.0
    assert k["comercial_bt"] == 100.0          # industrial de BT vai para o B3
    assert k["residencial"] == 400.0 and k["rural"] == 50.0
    assert sum(c["SE"]["pesos"].values()) == pytest.approx(1.0, abs=5e-4)
    assert c["SE"]["fracao_sed_mista"] == pytest.approx(50 / 1000, abs=1e-4)


def _perfis_fake():
    plano = [1.0] * 24
    noturno = [0.5] * 18 + [2.5] * 6
    return {
        "residencial": {"util": noturno, "sabado": noturno, "domingo_feriado": noturno},
        "alta_tensao": {"util": plano, "sabado": [0.5] * 24, "domingo_feriado": [0.5] * 24},
    }


def test_montagem_de_uma_classe_so_devolve_a_forma_dela():
    p = _perfis_fake()
    m = M.montar({"residencial": 1.0}, p)
    esperado = np.asarray(p["residencial"]["util"]) / sum(p["residencial"]["util"])
    assert m["shape"] == pytest.approx(esperado)
    assert m["weekend_ratio"] == pytest.approx(1.0)
    assert M.r2(esperado, m["shape"]) == pytest.approx(1.0)


def test_peso_do_dia_util_corrige_o_fim_de_semana_de_cada_classe():
    """Mesma energia anual: a classe que some no fim de semana pesa mais no dia util."""
    p = _perfis_fake()
    m = M.montar({"residencial": 0.5, "alta_tensao": 0.5}, p)
    # dia util: residencial 0.5/7, alta 0.5/6 -> alta pesa 7/13
    w_at = (0.5 / 6) / (0.5 / 7 + 0.5 / 6)
    assert m["weekend_ratio"] == pytest.approx((1 - w_at) * 1.0 + w_at * 0.5)
    assert sum(m["shape"]) == pytest.approx(1.0)


def test_qualidade_segue_limiares_do_yaml():
    q = M.cfg()["qualidade_r2"]
    assert M.qualidade(q["bom"]) == "bom"
    assert M.qualidade(q["moderado"]) == "moderado"
    assert M.qualidade(q["moderado"] - 0.01) == "fraco"
