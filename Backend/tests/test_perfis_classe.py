"""Tabela `perfis_classe` (src/processing/perfis_classe.py): perfis medidos da ANEEL CTR.

As entradas são Parquets MÍNIMOS montados no teste, no formato exato do CTR (inclusive bytes
latin-1), só para verificar as contas. Nenhum sai do teste.

Sem teste de vazamento temporal: a tabela é descritiva (média de campanhas de medição), não há
treino nem previsão.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.processing.perfis_classe import construir_perfis_classe


def _ctr(tmp_path, linhas: list[dict]) -> pd.DataFrame:
    """Grava um Parquet no formato do CTR e devolve a tabela processada."""
    bruto = tmp_path / "ctr.parquet"
    pd.DataFrame(linhas).to_parquet(bruto)
    return construir_perfis_classe(bruto, saida=tmp_path / "perfis.csv")


def _curva(dist, ano, sub, ct, tipo, nivel, forma=None):
    """96 quartos de hora de uma curva: `nivel` x `forma` (24 valores)."""
    forma = np.ones(24) if forma is None else np.asarray(forma, "f8")
    out = []
    for q in range(96):
        h = q // 4
        out.append({"SigCcs": dist, "AnoPrcCal": ano, "NomSubGrupoTarifario": sub,
                    "DscDemandante": ct, "DscTipoDia": tipo,
                    "HorInicial": "%02d:%02d:00" % (h, 15 * (q % 4)),
                    "VlrDmd": nivel * forma[h]})
    return out


def test_perfil_em_pu_do_proprio_dia_util_e_media_simples(tmp_path):
    """Curvas de escalas diferentes pesam igual; sabado e domingo ficam relativos."""
    pico = np.r_[np.ones(18), 3 * np.ones(6)]
    linhas = []
    # duas curvas residenciais com escala 1 e 1000: em p.u. sao identicas
    for ct, nivel in (("CT-001", 1.0), ("CT-002", 1000.0)):
        linhas += _curva("DISTA", 2023, "B1", ct, "Dia Útil", nivel, pico)
        linhas += _curva("DISTA", 2023, "B1", ct, "Sábado", nivel * 0.9, pico)
        linhas += _curva("DISTA", 2023, "B1", ct, "Domingo", nivel * 0.8, pico)
    t = _ctr(tmp_path, linhas)
    util = t[(t.classe == "residencial") & (t.tipo_dia == "util")].sort_values("hora")
    assert util["pu"].mean() == pytest.approx(1.0, abs=1e-4)
    assert util["pu"].iloc[20] / util["pu"].iloc[3] == pytest.approx(3.0, rel=1e-4)
    dom = t[(t.classe == "residencial") & (t.tipo_dia == "domingo_feriado")]
    assert dom["pu"].mean() == pytest.approx(0.8, abs=1e-4)
    assert int(util["n_curvas"].iloc[0]) == 2


def test_so_o_processo_tarifario_mais_recente_de_cada_distribuidora(tmp_path):
    linhas = []
    for tipo in ("Dia Útil", "Sábado", "Domingo"):
        linhas += _curva("DISTA", 2016, "B3", "CT-001", tipo, 1.0, np.r_[np.ones(12), 5 * np.ones(12)])
        linhas += _curva("DISTA", 2023, "B3", "CT-009", tipo, 1.0)
    t = _ctr(tmp_path, linhas)
    b3 = t[t.classe == "comercial_bt"]
    assert set(b3["ano_min"]) == {2023} and set(b3["n_curvas"]) == {1}
    assert b3[b3.tipo_dia == "util"]["pu"].tolist() == pytest.approx([1.0] * 24)


def test_texto_em_bytes_latin1_e_subgrupo_fora_do_yaml(tmp_path):
    """O Parquet da ANEEL traz bytes latin-1; B4 (iluminacao) nao vira classe."""
    linhas = []
    for tipo in ("Dia Útil".encode("latin-1"), b"S\xe1bado", b"Domingo"):
        linhas += _curva(b"DISTA", 2023, b"A4", b"CT-001", tipo, 2.0)
        linhas += _curva(b"DISTA", 2023, b"B4", b"CT-002", tipo, 2.0)
    t = _ctr(tmp_path, linhas)
    assert set(t["classe"]) == {"media_tensao"}
    assert set(t["tipo_dia"]) == {"util", "sabado", "domingo_feriado"}
