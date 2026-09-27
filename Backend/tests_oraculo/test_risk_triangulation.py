# -*- coding: utf-8 -*-
"""Risco de curtailment e triangulacao de evidencias."""
from __future__ import annotations

import numpy as np
import pytest

from oraculo import config
from oraculo.models import risk
from oraculo.triangulation import evidence as E


# ================================================================ rotulagem
@pytest.fixture(scope="module")
def coff():
    from oraculo.demo.synthetic import coff_frame
    return coff_frame(days=60)


def test_rotulo_agrega_para_grade_horaria(coff):
    lab = risk.build_labels(coff, "id_estado", "BA")
    assert len(lab.index) > 100
    # grade horaria: nenhum instante repetido
    assert len(np.unique(lab.index)) == len(lab.index)
    assert lab.corte_mw.min() >= 0.0


def test_rotulo_usa_geracao_de_referencia_menos_verificada(coff):
    lab = risk.build_labels(coff, "id_estado", "BA")
    assert lab.ocorreu.dtype == bool
    assert lab.threshold_mw > 0
    assert lab.ocorreu.sum() > 0, "a amostra demo precisa conter eventos"


def test_limiar_evita_rotular_ruido_de_apuracao(coff):
    lab = risk.build_labels(coff, "id_estado", "BA")
    # nenhuma hora abaixo do limiar pode estar marcada como ocorrencia
    assert not np.any(lab.ocorreu & (lab.corte_mw <= lab.threshold_mw))


def test_area_inexistente_devolve_rotulo_vazio(coff):
    lab = risk.build_labels(coff, "id_estado", "ZZ")
    assert len(lab.index) == 0


def test_composicao_por_razao_soma_um_quando_ha_corte(coff):
    lab = risk.build_labels(coff, "id_estado", "BA")
    sh = lab.reason_shares()
    total = sum(sh.values())
    assert total == pytest.approx(1.0, abs=0.02)


def test_resumo_do_historico_traz_campos_esperados(coff):
    s = risk.build_labels(coff, "id_estado", "BA").summary()
    for k in ("hours", "occurrence_rate", "total_cut_gwh", "peak_cut_mw",
              "threshold_mw", "reason_shares"):
        assert k in s


# ================================================= memoria sem vazamento
def test_memoria_de_ocorrencia_nao_usa_o_presente():
    y = np.zeros(60)
    y[30] = 1.0
    mem = risk.occurrence_memory(y, min_lag=24, window=48)
    assert mem[30] == 0.0, "a janela nao pode conter o proprio instante"
    assert mem[53] == 0.0, "ainda dentro da defasagem de 24 h"
    assert mem[54] > 0.0, "apos 24 h o evento pode ser conhecido"


def test_memoria_e_fracao_entre_zero_e_um():
    rng = np.random.default_rng(2)
    y = (rng.random(400) < 0.3).astype(float)
    mem = risk.occurrence_memory(y)
    assert mem.min() >= 0.0 and mem.max() <= 1.0


# ================================================================ logistica
def test_logistica_aprende_separacao_linear():
    rng = np.random.default_rng(4)
    n = 1500
    x = rng.normal(0, 1, n)
    p = 1.0 / (1.0 + np.exp(-(1.5 * x - 0.3)))
    y = (rng.random(n) < p).astype(float)
    X = np.column_stack([np.ones(n), x])
    m = risk.LogisticModel().fit(X, y)
    from oraculo.validation.metrics import roc_auc
    assert roc_auc(y, m.raw_probability(X)) > 0.75


def test_logistica_rejeita_rotulo_sem_variacao():
    X = np.column_stack([np.ones(50), np.arange(50.0)])
    with pytest.raises(ValueError):
        risk.LogisticModel().fit(X, np.zeros(50))


def test_probabilidade_fica_no_intervalo_unitario():
    rng = np.random.default_rng(6)
    n = 800
    X = np.column_stack([np.ones(n), rng.normal(0, 1, n)])
    y = (rng.random(n) < 0.4).astype(float)
    m = risk.LogisticModel().fit(X, y).calibrate(X, y)
    p = m.probability(X)
    assert p.min() >= 0.0 and p.max() <= 1.0


def test_calibracao_e_monotonica():
    rng = np.random.default_rng(8)
    n = 1200
    X = np.column_stack([np.ones(n), rng.normal(0, 1, n)])
    y = (rng.random(n) < 1.0 / (1.0 + np.exp(-X[:, 1]))).astype(float)
    m = risk.LogisticModel().fit(X, y).calibrate(X, y)
    ys = [b for _, b in m.calib]
    assert all(ys[i] <= ys[i + 1] + 1e-9 for i in range(len(ys) - 1))


# ================================================================ severidade
def test_severidade_cresce_com_probabilidade_e_potencia():
    a = risk.severity(0.2, 100.0, "BA", mw_reference=1000.0)
    b = risk.severity(0.9, 100.0, "BA", mw_reference=1000.0)
    c = risk.severity(0.9, 900.0, "BA", mw_reference=1000.0)
    assert a < b < c


def test_severidade_pondera_criticidade_da_area():
    mt = risk.severity(0.5, 100.0, "MT")   # criticidade 1,00
    pb = risk.severity(0.5, 100.0, "PB")   # criticidade 0,66
    assert mt > pb


def test_severidade_fica_entre_zero_e_um():
    for p in (0.0, 0.5, 1.0):
        for mw in (0.0, 500.0, 5000.0):
            s = risk.severity(p, mw, "MT", mw_reference=1000.0)
            assert 0.0 <= s <= 1.0


def test_montante_esperado_e_probabilidade_vezes_condicional():
    p = np.array([0.0, 0.5, 1.0])
    assert risk.expected_cut(p, 200.0).tolist() == [0.0, 100.0, 200.0]


# ================================================================ motivo
def test_pesos_de_razao_somam_um(coff):
    lab = risk.build_labels(coff, "id_estado", "BA")
    w = risk.reason_weights(lab, np.arange(24), 0.8, 0.2)
    assert sum(w.values()) == pytest.approx(1.0, abs=1e-6)


def test_sinal_energetico_eleva_o_peso_da_razao_ene(coff):
    lab = risk.build_labels(coff, "id_estado", "BA")
    baixo = risk.reason_weights(lab, np.arange(24), 0.0, 0.0)
    alto = risk.reason_weights(lab, np.arange(24), 1.0, 0.0)
    assert alto["ENE"] > baixo["ENE"]


def test_razao_dominante_e_a_de_maior_peso():
    assert risk.dominant_reason({"ENE": 0.6, "CNF": 0.4}) == "ENE"
    assert risk.dominant_reason({"ENE": 0.2, "CNF": 0.8}) == "CNF"


def test_acoes_recomendadas_dependem_da_razao():
    ene = " ".join(risk.recommended_actions("ENE", 500.0, "minima_diurna")).lower()
    cnf = " ".join(risk.recommended_actions("CNF", 500.0, "rampa")).lower()
    assert "excedentes" in ene
    assert "exporta" in cnf or "intercâmbio" in cnf


def test_evidencias_declaram_a_fonte_de_cada_peca():
    items = risk.evidence_items(
        probability=0.8, expected_mw=120.0, ghi_norm=0.7, margin_mw=4000.0,
        reason="ENE", reason_weights_={"ENE": 1.0}, provenance_dataset="coff")
    assert len(items) >= 4
    for it in items:
        assert it["source"], "toda evidencia precisa declarar a fonte"


# ============================================================ triangulacao
def test_matriz_de_desempate_cobre_as_quatro_celulas():
    assert E.classify(True, True, True) == E.CONFIRMADA
    assert E.classify(True, False, True) == E.LAG_DE_SISTEMA
    assert E.classify(True, False, False) == E.NAO_HOMOLOGADA
    assert E.classify(True, True, False) == E.NAO_HOMOLOGADA
    assert E.classify(False, True, True) == E.CADASTRO_SEM_EVIDENCIA
    assert E.classify(False, False, False) == E.SEM_EVIDENCIA


def test_nao_homologada_nao_entra_no_fator_de_correcao():
    assert E.counts_in_correction(E.NAO_HOMOLOGADA) is False
    assert E.counts_in_correction(E.CONFIRMADA) is True
    assert E.counts_in_correction(E.LAG_DE_SISTEMA) is True
    assert E.counts_in_correction(E.CADASTRO_SEM_EVIDENCIA) is False


def test_defasagem_de_sistema_entra_no_fator_e_eleva_a_capacidade():
    units = [
        E.Unit("u1", "SE", 1000.0, True, True, True),    # confirmada
        E.Unit("u2", "SE", 1000.0, True, False, True),   # lag de sistema
    ]
    agg = E.aggregate(units)[0]
    assert agg["capacity_declared_mw"] == pytest.approx(1.0)
    assert agg["capacity_corrected_mw"] == pytest.approx(2.0)
    assert agg["correction_factor"] == pytest.approx(2.0)


def test_unidade_irregular_e_reportada_em_separado():
    units = [
        E.Unit("u1", "NE", 500.0, True, True, True),
        E.Unit("u2", "NE", 300.0, True, False, False),   # nao homologada
    ]
    agg = E.aggregate(units)[0]
    assert agg["capacity_unhomologated_mw"] == pytest.approx(0.3)
    assert agg["capacity_corrected_mw"] == pytest.approx(0.5)
    assert agg["matrix"]["nao_homologada"] == 1


def test_agregacao_por_area_separa_os_grupos():
    units = E.demo_units(["SE", "NE"], per_area=40)
    agg = E.aggregate(units)
    assert {a["area"] for a in agg} == {"SE", "NE"}
    for a in agg:
        assert a["units_total"] == 40
        assert sum(a["matrix"].values()) == 40
        assert 0.0 <= a["coverage"] <= 1.0


def test_unidades_demo_sao_deterministicas():
    a = E.demo_units(["SE"], per_area=30)
    b = E.demo_units(["SE"], per_area=30)
    assert [u.classification for u in a] == [u.classification for u in b]


def test_camadas_declaram_cadencia_e_limitacao():
    assert len(E.LAYERS) == 3
    for l in E.LAYERS:
        assert l["cadence"] and l["limitation"] and l["question"]


def test_celulas_da_matriz_descrevem_as_quatro_combinacoes():
    cells = E.matrix_cells()
    assert len(cells) == 4
    for c in cells:
        assert c["label"] and c["note"]


def test_horizonte_muda_o_modelo_de_risco(client):
    # Antes o horizonte so trocava o rotulo: agora a memoria de restricao
    # termina `lag` horas antes do alvo (config.HORIZONS) e o modelo muda.
    from oraculo.api.service import SERVICE
    r30 = SERVICE.risk_payload("30min")
    rd1 = SERVICE.risk_payload("d1")
    assert r30["model"]["memory_lag_h"] == config.HORIZONS["30min"]
    assert rd1["model"]["memory_lag_h"] == config.HORIZONS["d1"]
    assert r30["horizon"] == "30min" and rd1["horizon"] == "d1"
    assert r30 is not rd1


# ================================================= desempate com dado real (camada 1 ausente)
def test_sem_satelite_o_desempate_e_bdgd_por_aneel():
    assert E.classify(None, True, True) == E.CADASTRAL
    assert E.classify(None, False, True) == E.LAG_DE_SISTEMA
    assert E.classify(None, True, False) == E.NAO_HOMOLOGADA
    assert E.counts_in_correction(E.CADASTRAL)
    assert not E.counts_in_correction(E.NAO_HOMOLOGADA)


def _empreendimentos():
    import pandas as pd
    return pd.DataFrame({
        "ceg": ["GD1", "GD2", "GD3", "GD4"],
        "categoria": ["bdgd_e_aneel", "bdgd_e_aneel", "lag_sistema", "bdgd_sem_homologacao"],
        "distribuidora": ["LIGHT"] * 4,
        "pot_aneel_kw": [100.0, 300.0, 50.0, float("nan")],
        "pot_bdgd_kw": [90.0, 280.0, float("nan"), 7.0],
        "data": pd.to_datetime(["2024-01-01", "2024-02-01", "2026-03-01", None]),
    })


def test_empreendimentos_reais_viram_unidades_sem_deteccao_presumida():
    units = E.units_from_empreendimentos(_empreendimentos())
    assert all(u.detected is None for u in units)
    assert [u.classification for u in units] == [E.CADASTRAL, E.CADASTRAL, E.LAG_DE_SISTEMA,
                                                 E.NAO_HOMOLOGADA]
    # potencia = ANEEL; so-BDGD usa a da BDGD
    assert [u.capacity_kwp for u in units] == [100.0, 300.0, 50.0, 7.0]
    a = E.aggregate(units)[0]
    # declarada = o que a BDGD conhece (100+300+7); corrigida = cadastral + lag (100+300+50)
    assert a["capacity_declared_mw"] == pytest.approx(0.41, abs=1e-3)
    assert a["capacity_corrected_mw"] == pytest.approx(0.45, abs=1e-3)
    assert a["capacity_unhomologated_mw"] == pytest.approx(0.01, abs=1e-3)
    assert a["coverage"] == 0.0            # nenhuma unidade com as tres camadas


def test_amostra_mostra_um_exemplo_de_cada_classificacao():
    units = E.units_from_empreendimentos(_empreendimentos())
    s = E.sample_units(units, n=3)
    assert {u.classification for u in s} == {E.CADASTRAL, E.LAG_DE_SISTEMA, E.NAO_HOMOLOGADA}
