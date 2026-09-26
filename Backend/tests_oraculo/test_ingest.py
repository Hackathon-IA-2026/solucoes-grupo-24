# -*- coding: utf-8 -*-
"""Leitor CSV, catalogo, cache e degradacao graciosa."""
from __future__ import annotations

import numpy as np
import pytest

from oraculo.core.frame import Provenance
from oraculo.ons import cache, catalog, ckan, csvio
from oraculo.pipeline import ingest

BALANCO_CSV = (
    b"id_subsistema;nom_subsistema;din_instante;val_gerhidraulica;val_gertermica;"
    b"val_gereolica;val_gersolar;val_carga;val_intercambio\n"
    b"NE;NORDESTE;2025-01-01 00:00:00;2219.28;415.15;16070.65;0.0;12251.18;6453.90\n"
    b"SIN;SISTEMA INTERLIGADO NACIONAL;2025-01-01 00:00:00;40778.71;6835.33;"
    b"17662.51;1.0;65277.57;0.0\n"
    b"SE;SUDESTE;data-invalida;1.0;2.0;3.0;4.0;5.0;6.0\n"
    b"S;SUL;2025-01-01 01:00:00;100.0;;;;10554.60;0.0\n"
)


# ================================================================ csvio
def test_le_csv_do_ons_com_delimitador_ponto_e_virgula():
    f, rep = csvio.read_csv(BALANCO_CSV, schema=catalog.SCHEMA_BALANCO)
    assert rep.rows == 3, "a linha com instante invalido deve ser descartada"
    assert rep.discarded_bad_time == 1
    assert sorted(f.unique("id_subsistema").tolist()) == ["NE", "S", "SIN"]


def test_campo_numerico_vazio_vira_nan_nao_zero():
    f, _ = csvio.read_csv(BALANCO_CSV, schema=catalog.SCHEMA_BALANCO)
    s = f.eq("id_subsistema", "S")
    assert np.isnan(s["val_gertermica"][0])
    assert np.isnan(s["val_gereolica"][0])
    assert s["val_carga"][0] == pytest.approx(10554.60)


def test_instante_e_convertido_para_datetime64():
    f, _ = csvio.read_csv(BALANCO_CSV, schema=catalog.SCHEMA_BALANCO)
    assert f["din_instante"].dtype == np.dtype("datetime64[s]")
    assert str(f.eq("id_subsistema", "SIN")["din_instante"][0]) == "2025-01-01T00:00:00"


def test_truncamento_descarta_a_ultima_linha():
    """Um download por Range termina no meio de uma linha, que deve cair."""
    cortado = BALANCO_CSV + b"SE;SUDESTE;2025-01-01 02:00:0"
    f_full, _ = csvio.read_csv(cortado, schema=catalog.SCHEMA_BALANCO)
    f_trunc, rep = csvio.read_csv(cortado, schema=catalog.SCHEMA_BALANCO,
                                  truncated=True)
    assert rep.truncated_tail is True
    # a linha parcial entra como "linha curta" na leitura completa e desaparece
    # por inteiro quando o truncamento e declarado
    assert len(f_trunc) == 3
    assert len(f_full) == 3


def test_arquivo_completo_com_nova_linha_final_nao_perde_registro():
    f_full, _ = csvio.read_csv(BALANCO_CSV, schema=catalog.SCHEMA_BALANCO)
    f_trunc, _ = csvio.read_csv(BALANCO_CSV, schema=catalog.SCHEMA_BALANCO,
                                truncated=True)
    assert len(f_trunc) == len(f_full)


def test_payload_vazio_devolve_frame_vazio():
    f, rep = csvio.read_csv(b"", schema=catalog.SCHEMA_BALANCO)
    assert len(f) == 0 and rep.rows == 0


def test_filtro_descarta_antes_de_materializar():
    f, _ = csvio.read_csv(BALANCO_CSV, schema=catalog.SCHEMA_BALANCO,
                          filter_fn=lambda r: r["id_subsistema"] == "SIN")
    assert len(f) == 1


def test_sniff_header_lista_as_colunas():
    cols = csvio.sniff_header(BALANCO_CSV)
    assert "val_carga" in cols and "din_instante" in cols


def test_relatorio_de_leitura_e_serializavel():
    _, rep = csvio.read_csv(BALANCO_CSV, schema=catalog.SCHEMA_BALANCO)
    d = rep.to_dict()
    for k in ("rows", "discarded_bad_time", "duplicates", "columns"):
        assert k in d


def test_proveniencia_acompanha_o_frame():
    prov = Provenance("ds", "res.csv", "http://x", "2026-01-01T00:00:00Z",
                      0, 100, "live", "nota")
    f, _ = csvio.read_csv(BALANCO_CSV, schema=catalog.SCHEMA_BALANCO,
                          provenance=prov)
    assert f.provenance_dicts()[0]["dataset"] == "ds"


# ================================================================ catalogo
def test_url_de_recurso_anual_e_mensal():
    u = catalog.resource_url("balanco", 2025)
    assert u.endswith("BALANCO_ENERGIA_SUBSISTEMA_2025.csv")
    m = catalog.resource_url("coff_fv", 2025, 8)
    assert m.endswith("RESTRICAO_COFF_FOTOVOLTAICA_2025_08.csv")


def test_recurso_mensal_exige_mes():
    with pytest.raises(ValueError):
        catalog.resource_url("coff_fv", 2025)


def test_resumo_curado_descreve_papel_e_esquema():
    for c in catalog.curated_summary():
        assert c["role"] and c["granularity"] and c["lag_note"]
        assert len(c["fields"]) >= 3


def test_razoes_e_origens_documentadas():
    assert set(catalog.RAZOES) == {"REL", "CNF", "ENE", "PAR"}
    assert set(catalog.ORIGENS) == {"LOC", "SIS"}


def test_periodo_extraido_do_nome_do_recurso():
    assert ckan.resource_period("RESTRICAO_COFF_EOLICA_2026_09.csv") == (2026, 9)
    assert ckan.resource_period("CURVA_CARGA_2025.csv") == (2025, None)
    assert ckan.resource_period("DicionarioDados.pdf") == (None, None)


# ================================================================ cache
def test_cache_grava_le_e_registra_manifesto(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)
    url = "https://exemplo/teste.csv"
    entry = cache.write(url, b"abc", dataset="ds", resource="teste.csv")
    assert entry["bytes"] == 3 and entry["sha256"]
    assert cache.read(url) == b"abc"
    assert cache.entry_for(url)["dataset"] == "ds"
    st = cache.stats()
    assert st["entries"] == 1 and st["bytes"] == 3


def test_cache_isola_por_sufixo_de_truncamento(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)
    url = "https://exemplo/grande.csv"
    cache.write(url, b"completo", suffix="")
    cache.write(url, b"trunc", suffix="#100")
    assert cache.read(url, "") == b"completo"
    assert cache.read(url, "#100") == b"trunc"


def test_cache_clear_remove_arquivos(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)
    cache.write("https://a/1.csv", b"x")
    assert cache.clear() >= 1
    assert cache.stats()["entries"] == 0


# ======================================================= degradacao graciosa
def test_modo_demo_carrega_tudo_sem_rede():
    b = ingest.load_bundle(force_demo=True)
    assert b.mode == "demo"
    assert len(b.balanco) > 1000
    assert len(b.coff) > 100
    assert b.provenance(), "o modo demo tambem precisa declarar proveniencia"
    for p in b.provenance():
        assert p["mode"] == "demo"


def test_series_da_area_vem_em_grade_horaria_completa():
    b = ingest.load_bundle(force_demo=True)
    ser = ingest.area_series(b.balanco, "SE")
    ts = ser["index"]
    deltas = np.unique(np.diff(ts).astype("i8"))
    assert deltas.tolist() == [3600], "a grade precisa ser estritamente horaria"
    assert "margem_controlavel" in ser


def test_area_inexistente_devolve_vazio():
    b = ingest.load_bundle(force_demo=True)
    assert ingest.area_series(b.balanco, "XX") == {}


def test_relatorio_de_ingestao_e_serializavel():
    b = ingest.load_bundle(force_demo=True)
    for r in b.reports_dicts():
        for k in ("dataset", "resource", "mode", "rows"):
            assert k in r


def test_ckan_offline_nao_levanta_excecao(monkeypatch):
    monkeypatch.setattr(ckan, "FORCE_OFFLINE", True)
    res = ckan.fetch_resource("https://inexistente/nada.csv")
    assert res.ok is False
    assert res.mode == "demo"
    assert res.error


def test_gerador_demo_e_deterministico():
    from oraculo.demo.synthetic import balanco_frame
    a = balanco_frame(days=10, areas=["SE"])
    b = balanco_frame(days=10, areas=["SE"])
    assert np.allclose(a["val_carga"], b["val_carga"])


def test_demo_respeita_a_forma_do_problema():
    """Vale diurno e pico noturno precisam existir, senao o painel mente."""
    from oraculo.core.timeutils import hour_of_day
    from oraculo.demo.synthetic import balanco_frame
    f = balanco_frame(days=30, areas=["SE"])
    ts, load = f["din_instante"], f["val_carga"]
    hod = hour_of_day(ts)
    meio_dia = float(np.nanmean(load[(hod >= 11) & (hod <= 14)]))
    noite = float(np.nanmean(load[(hod >= 18) & (hod <= 21)]))
    assert noite > meio_dia, "a ponta noturna deve superar a barriga diurna"


# ================================================================ rede real
@pytest.mark.network
def test_api_real_do_ons_responde():
    """Exercita o Portal de Dados Abertos. Ignorado sem conectividade."""
    if not ckan.network_available():
        pytest.skip("sem acesso ao Portal do ONS")
    names, mode = ckan.package_list()
    assert len(names) > 50, "o Portal publica dezenas de conjuntos"
    assert "balanco-energia-subsistema" in names
    assert mode in ("live", "cache")
