"""Peças B e C: regras do histórico mensal, dos episódios de corte e do lead time.

Casos pequenos montados à mão, com a resposta conhecida (não são dados do projeto: testam as regras).
"""
import pandas as pd
import pytest

from src.analise import episodios as ep
from src.analise import historico as hi

T0 = pd.Timestamp("2026-01-01 00:00")
P = pd.Timedelta("30min")


# --------------------------------------------------------------------------- Peça B
def test_corte_mensal_e_resposta():
    cm = pd.DataFrame({
        "mes": ["2025-03-01"] * 3 + ["2025-04-01"] * 3 + ["2025-05-01"] * 3,
        "razao": ["ENE", "CNF", "REL"] * 3,
        "energia_cortada_gwh": [1, 8, 1, 6, 3, 1, 2, 7, 1],
    })
    t = hi.corte_mensal(cm)
    assert list(t["dominante"]) == ["CNF", "ENE", "CNF"]
    assert t.loc["2025-04-01", "pct_ENE"] == pytest.approx(60)
    r = hi.resposta(t, pd.Timestamp("2025-04-01"))
    assert r["meses_desde_marco"] == 2 and r["meses_ene_dominante"] == 1
    assert r["meses_outra_dominante"] == ["05/2025 (CNF)"]
    assert r["pct_ene_desde_marco"] == pytest.approx(100 * 8 / 20)
    assert r["pct_ene_antes_marco"] == pytest.approx(10)


def test_mmgd_no_fim_do_mes_soma_ufs_com_o_ultimo_valor_conhecido():
    cap = pd.DataFrame({"uf": ["RJ", "SP", "RJ"], "data": ["2025-01-10", "2025-01-20", "2025-02-05"],
                        "potencia_acumulada_mw": [100.0, 300.0, 150.0]})
    meses = pd.DatetimeIndex(["2025-01-01", "2025-02-01"])
    gw = hi.mmgd_mensal(cap, meses)
    assert gw.tolist() == pytest.approx([0.4, 0.45])  # fev: RJ 150 + SP 300 (valor de jan mantido)


# --------------------------------------------------------------------------- Peça C
def _cortes(chave, passos):
    return pd.DataFrame({"chave": chave, "fonte": "eolica", "subsistema": "NE",
                         "timestamp": [T0 + k * P for k in passos], "mw": 10.0})


def test_episodios_tolerancia_e_folga():
    # u1: cortes em 20,21 | 23 (1 passo sem corte: mesmo episódio com tolerância 2) | 40 (novo)
    # u2: corte em 3, só 3 passos depois do início da base: não é INÍCIO (folga < 12)
    cortes = pd.concat([_cortes("u1", [20, 21, 23, 40]), _cortes("u2", [3])])
    inicio_base = pd.Series({"u1": T0, "u2": T0})
    e = ep.episodios(cortes, inicio_base, tolerancia=2, folga_minima=12).set_index(["chave", "inicio"])
    assert len(e) == 3
    a = e.loc[("u1", T0 + 20 * P)]
    assert a["semihoras_com_corte"] == 3 and a["duracao_h"] == 2.0 and a["energia_mwh"] == 15.0
    assert a["folga_antes_passos"] == 20 and a["eh_inicio"]
    b = e.loc[("u1", T0 + 40 * P)]
    assert b["folga_antes_passos"] == 40 - 23 - 1 and b["eh_inicio"]
    assert not e.loc[("u2", T0 + 3 * P), "eh_inicio"]


def test_lead_time_maior_antecedencia_com_aviso():
    h = {"30min": 1, "3h": 6, "D+1": 48}
    av = pd.DataFrame({
        "chave": ["a"] * 3 + ["b"] * 3 + ["c"] * 3,
        "alvo": [T0] * 9,
        "horizonte": ["30min", "3h", "D+1"] * 3,
        "p": [0.9, 0.7, 0.6,    # a: avisou já na véspera
              0.8, 0.2, 0.1,    # b: só 30 min antes
              0.1, 0.1, 0.1],   # c: nunca
        "persistencia": [0.0] * 9,
    })
    por_h, dist = ep.lead_time(av, h, 0.5)
    assert por_h.set_index("horizonte").loc["30min", "pct_avisados"] == pytest.approx(200 / 3)
    assert por_h.set_index("horizonte").loc["D+1", "pct_avisados"] == pytest.approx(100 / 3)
    d = dist.set_index("maior_antecedencia_com_aviso")["pct_inicios"]
    assert d["D+1"] == pytest.approx(100 / 3) and d["30min"] == pytest.approx(100 / 3)
    assert d["sem aviso"] == pytest.approx(100 / 3)
    assert list(dist["maior_antecedencia_com_aviso"]) == ["D+1", "30min", "sem aviso"]
