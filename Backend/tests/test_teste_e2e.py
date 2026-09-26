"""Testes do harness ponta a ponta (pipeline/teste_e2e.py, Prompt 12).

O status de cada etapa é LIDO dos dados: os testes provam que um registro adulterado ou uma
flag mock mudam o relatório, sem nenhuma chave de config para "declarar" real/mock.
"""
import copy

import pandas as pd
import pytest

from pipeline import teste_e2e as e2e
from src.utils.config import carregar


@pytest.fixture(scope="module")
def recursos_mock():
    return e2e.mocks_do_dashboard()


def test_contrato_dos_mocks_e_lido_como_mock(recursos_mock):
    etapa = e2e.etapa_contrato(recursos_mock, "mocks")
    assert etapa.status == "mock"
    assert len(etapa.detalhes) == len(recursos_mock)


def test_um_recurso_real_vira_parcial(recursos_mock):
    r = copy.deepcopy(recursos_mock)
    r["carga"]["mock"] = False
    assert e2e.etapa_contrato(r, "x").status == "parcial"


def test_dashboard_valida_o_contrato(recursos_mock):
    assert e2e.etapa_dashboard(recursos_mock).status == "ok"


def test_dashboard_acusa_registro_fora_do_contrato_e_alerta_orfao(recursos_mock):
    r = copy.deepcopy(recursos_mock)
    r["riscos"][0]["probabilidadePct"] = 180          # fora de 0–100
    r["alertas"][0]["riscoUsinaId"] = "nao-existe"
    etapa = e2e.etapa_dashboard(r)
    assert etapa.status == "erro"
    assert any("riscos[0]" in d for d in etapa.detalhes)
    assert any("sem risco correspondente" in d for d in etapa.detalhes)


def test_alerta_incoerente_com_o_risco_e_erro(recursos_mock):
    assert e2e.etapa_alerta(recursos_mock).status == "mock"
    r = copy.deepcopy(recursos_mock)
    alvo = r["alertas"][0]["riscoUsinaId"]
    next(x for x in r["riscos"] if x["id"] == alvo)["probabilidadePct"] = 3
    assert e2e.etapa_alerta(r).status == "erro"


def _cenario():
    return carregar("e2e")["cenarios"]["dia_dos_pais_2024"]


def test_dia_dos_pais_sem_dados_so_mostra_referencia(tmp_path):
    res = e2e.cenario_dia_dos_pais(_cenario(), tmp_path / "nao.csv", tmp_path / "nao.parquet")
    assert res["status"].startswith("indisponível")
    assert res["real"] == {}
    assert any("39.024" in l for l in res["linhas"])
    assert any("in-sample" in l for l in res["linhas"])  # 2024-08-11 está no treino do classificador


def test_dia_dos_pais_extrai_do_dado(tmp_path):
    # FIXTURE sintética de teste (não é dado do ONS): 4 subsistemas × 3 semi-horas no dia
    ts = pd.to_datetime(["2024-08-11 12:00", "2024-08-11 12:30", "2024-08-11 13:00"])
    linhas = [{"subsistema": s, "timestamp": t, "carga_supervisionada": base + k * 100, "mmgd_estimada": 1000}
              for s, base in [("SE", 20000), ("S", 8000), ("NE", 7000), ("N", 5000)]
              for k, t in enumerate(ts)]
    linhas.append({"subsistema": "SE", "timestamp": pd.Timestamp("2024-08-12 00:00"),
                   "carga_supervisionada": 1, "mmgd_estimada": 0})  # outro dia: ignorado
    carga = tmp_path / "carga.csv"
    pd.DataFrame(linhas).to_csv(carga, index=False)

    rot = pd.DataFrame({
        "chave": ["eolica:A", "eolica:B", "solar:C"] * 2,
        "timestamp": [ts[0]] * 3 + [ts[1]] * 3,
        "flag_ENE": [True, True, True, True, False, False],
        "flag_CNF": [False] * 6,
        "corte_MW_ENE": [10.0, 20.0, 30.0, 5.0, 0.0, 0.0],
        "corte_MW_CNF": [0.0] * 6,
    })
    parquet = tmp_path / "rot.parquet"
    rot.to_parquet(parquet)

    res = e2e.cenario_dia_dos_pais(_cenario(), carga, parquet)
    assert res["status"] == "real"
    assert res["real"]["carga_supervisionada_minima_mw"] == 40000   # 20000+8000+7000+5000 às 12:00
    assert res["real"]["instante_minimo"] == "12:00"
    assert res["real"]["fracao_maxima_usinas_cortadas"] == 1.0
    assert res["real"]["semi_horas_restricao_generalizada"] == 1    # só 12:00 passa de 80%
    assert res["real"]["corte_MW_ENE_max"] == 60.0
