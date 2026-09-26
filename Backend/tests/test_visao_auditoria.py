"""Testes da visão computacional e da auditoria da MMGD em 3 camadas (Prompts 10 e 11).

Nenhum teste precisa do ultralytics/torch: a geometria, o modo --mock, o desempate e o
diagnóstico do modelo são funções puras. O YOLO real é exercitado à mão (docs/STATUS.md).
"""
import copy
import json
from datetime import date
from pathlib import Path

import pytest

from pipeline import auditoria_camada1, auditoria_camadas_2_3 as aud, download_satelite, validar_modelo
from pipeline import visao_comum as vc

MOCK = Path(__file__).resolve().parents[1] / "pipeline" / "mock"


@pytest.fixture
def cfg_tmp(tmp_path, monkeypatch):
    """config/visao.yaml com as SAÍDAS apontando para tmp (teste nunca grava em output/)."""
    cfg = copy.deepcopy(vc.config())
    cfg["camada1"]["saida_mock"] = str(tmp_path / "c1_mock.geojson")
    cfg["camada1"]["saida"] = str(tmp_path / "c1.geojson")
    cfg["auditoria"]["mock"]["saida"] = str(tmp_path / "aud_mock.json")
    cfg["auditoria"]["saida"] = str(tmp_path / "aud.json")
    monkeypatch.setattr(vc, "config", lambda: cfg)
    return cfg


# --------------------------------------------------------------------------- geometria
def test_world_file_convencao_de_canto(tmp_path):
    img = tmp_path / "tile.png"
    img.write_bytes(b"")
    # pixel de 0,5° ; (C, F) = CENTRO do pixel superior esquerdo -> canto em (-43.0, -15.0)
    (tmp_path / "tile.pgw").write_text("0.5\n0\n0\n-0.5\n-42.75\n-15.25\n", encoding="utf-8")
    geo = vc.georreferencia_da_imagem(img, "EPSG:4326")
    assert geo.para_mapa(0, 0) == pytest.approx((-43.0, -15.0))
    assert geo.para_mapa(2, 2) == pytest.approx((-42.0, -16.0))


def test_imagem_sem_georreferencia_e_recusada(tmp_path):
    img = tmp_path / "sem_geo.jpg"
    img.write_bytes(b"")
    with pytest.raises(vc.ErroVisao, match="sem georreferência"):
        vc.georreferencia_da_imagem(img, "EPSG:4326")


def test_area_geodesica_de_um_retangulo_em_metros():
    anel = vc.retangulo_lonlat(-15.8, -43.3, largura_m=10, altura_m=5)
    assert vc.area_m2(anel) == pytest.approx(50, rel=0.01)
    assert vc.centroide(anel) == pytest.approx((-15.8, -43.3), abs=1e-6)


# --------------------------------------------------------------------------- camada 1
def test_camada1_mock_marca_tudo_como_mock(cfg_tmp):
    destino = auditoria_camada1.executar(mock=True)
    col = vc.ler_geojson(destino)
    assert col["properties"]["is_mock"] is True
    assert len(col["features"]) == 12
    assert all(f["properties"]["is_mock"] and f["properties"]["area_m2"] > 0 for f in col["features"])


def test_mock_sem_flag_e_recusado(tmp_path):
    dados = json.loads((MOCK / "camada1_paineis_mock.json").read_text(encoding="utf-8"))
    dados["mock"] = False
    arq = tmp_path / "sem_flag.json"
    arq.write_text(json.dumps(dados), encoding="utf-8")
    with pytest.raises(vc.ErroVisao, match="mock"):
        auditoria_camada1.deteccoes_mock(arq)


# --------------------------------------------------------------------------- camadas 2 e 3
REF = date(2025, 12, 31)


@pytest.mark.parametrize("tem_bdgd, homologacao, esperado", [
    (True, None, aud.CADASTRADA),
    (True, date(2026, 5, 1), aud.CADASTRADA),        # na BDGD: a ANEEL não muda nada
    (False, date(2026, 1, 1), aud.LAG),              # homologado depois da BDGD
    (False, REF, aud.DIVERGENCIA),                   # no mesmo dia NÃO é depois: não é lag
    (False, date(2024, 1, 1), aud.DIVERGENCIA),
    (False, None, aud.NAO_HOMOLOGADA),
])
def test_regra_do_desempate(tem_bdgd, homologacao, esperado):
    assert aud.classificar(tem_bdgd, homologacao, REF) == esperado


def test_auditoria_dos_mocks_classifica_e_exclui_nao_homologadas_do_fator(cfg_tmp):
    r = json.loads(aud.executar(mock=True).read_text(encoding="utf-8"))
    assert r["is_mock"] is True
    classe = {d["id"]: d["classificacao"] for d in r["deteccoes"]}
    assert classe == {
        **{f"D0{i}": aud.CADASTRADA for i in range(1, 6)},
        "D06": aud.LAG, "D07": aud.LAG, "D08": aud.LAG,
        "D09": aud.DIVERGENCIA,
        "D10": aud.NAO_HOMOLOGADA, "D11": aud.NAO_HOMOLOGADA, "D12": aud.NAO_HOMOLOGADA,
    }
    assert r["excecoes_nao_homologadas"] == ["D10", "D11", "D12"]
    for m in r["manchas"]:
        dets = [d for d in r["deteccoes"] if d["mancha"] == m["mancha"]]
        auditada = sum(d["capacidade_estimada_kw"] for d in dets if d["classificacao"] != aud.NAO_HOMOLOGADA)
        assert m["capacidade_auditada_kw"] == pytest.approx(auditada)
        assert m["fator_correcao"] == pytest.approx(auditada / m["capacidade_cadastrada_bdgd_kw"], abs=1e-4)


def _painel(id_, lat, lon, area=20.0):
    return aud.Painel(id_, lat, lon, area, True)


def test_casamento_um_para_um():
    # dois painéis a ~5 m do mesmo cadastro: só o mais próximo casa
    registros = [{"id": "B1", "lat": -15.8, "lon": -43.3}]
    ps = [_painel("perto", -15.80003, -43.3), _painel("longe", -15.80008, -43.3)]
    casados = aud.casar(ps, registros, raio_m=25, chave="id")
    assert list(casados) == ["perto"]


def test_mancha_sem_capacidade_cadastrada_nao_inventa_fator():
    bdgd = {"data_referencia": "2025-12-31", "unidades": [
        {"id": "B1", "lat": -15.8, "lon": -43.3, "potencia_kw": 0.0, "transformador": "T", "alimentador": "AL-1"}]}
    aneel = {"empreendimentos": [{"codigo": "A1", "lat": -15.8, "lon": -43.3, "potencia_kw": 4, "data_homologacao": "2026-03-01"}]}
    r = aud.auditar([_painel("D1", -15.8, -43.3)], bdgd, aneel, 25, 0.18, "alimentador")
    assert r["manchas"][0]["fator_correcao"] is None
    assert "sem capacidade" in r["manchas"][0]["motivo_sem_fator"]


def test_entrada_mock_nunca_vai_para_a_saida_real(cfg_tmp):
    auditoria_camada1.executar(mock=True)
    with pytest.raises(vc.ErroVisao, match="mock"):
        aud.executar(mock=False, deteccoes=cfg_tmp["camada1"]["saida_mock"],
                     bdgd=str(MOCK / "bdgd_mock.json"), aneel=str(MOCK / "aneel_cadastro_diario_mock.json"))


def test_registro_com_chave_repetida_e_recusado():
    regs = [{"id": "B1", "lat": -15.8, "lon": -43.3}, {"id": "B1", "lat": -15.9, "lon": -43.3}]
    with pytest.raises(vc.ErroVisao, match="repetido"):
        aud.casar([_painel("D1", -15.8, -43.3)], regs, 25, "id")


# --------------------------------------------------------------------------- download
def test_bbox_ausente_ou_invertido_e_recusado():
    with pytest.raises(download_satelite.ErroDownload, match="TODO Tiago"):
        download_satelite.validar_bbox(None)
    with pytest.raises(download_satelite.ErroDownload, match="fora do Brasil"):
        download_satelite.validar_bbox([-15.8, -43.3, -15.7, -43.2])  # lat/lon trocados


def test_trava_de_resolucao():
    assert download_satelite.checar_resolucao(0.3, 0.5, forcar=False) is None
    with pytest.raises(download_satelite.ErroDownload, match="m/pixel"):
        download_satelite.checar_resolucao(10, 0.5, forcar=False)
    assert "m/pixel" in download_satelite.checar_resolucao(10, 0.5, forcar=True)


def test_download_dry_run_respeita_a_trava():
    bbox = ["--bbox", "-43.33", "-15.82", "-43.29", "-15.78", "--dry-run"]
    assert download_satelite.main(bbox) == 2              # Sentinel-2 (10 m) recusado
    assert download_satelite.main(bbox + ["--forcar"]) == 0


# --------------------------------------------------------------------------- diagnóstico do modelo
def _img(nome, n, conf=0.8, esperado=None, geo=True):
    return validar_modelo.ResultadoImagem(nome, n, conf if n else None, 0.3 if geo else None,
                                          None if geo else "sem georreferência", esperado)


def test_sem_gabarito_nunca_diz_adequado():
    v = validar_modelo.Validacao("m.pt", "segment", {"classes": {0: "solar-panel"}}, [_img("a.tif", 2)])
    v.avisos = validar_modelo.diagnosticar(v.tarefa, v.metadados, v.imagens, 0.5)
    assert v.avisos == []
    assert v.veredito == "sanidade_ok_sem_gabarito"


def test_falso_positivo_com_gabarito():
    imgs = [_img("onibus.jpg", 3, esperado=0), _img("telhado.tif", 2, esperado=2)]
    avisos = validar_modelo.diagnosticar("segment", {"classes": {0: "solar-panel"}}, imgs, 0.5)
    assert any("falso positivo" in a for a in avisos)


def test_avisos_de_classe_tarefa_e_georreferencia():
    avisos = validar_modelo.diagnosticar("detect", {"classes": {0: "person"}}, [_img("x.jpg", 1, geo=False)], 0.5)
    texto = " | ".join(avisos)
    assert "painel solar" in texto and "DETECÇÃO" in texto and "georreferência" in texto
