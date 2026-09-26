# -*- coding: utf-8 -*-
"""Visao computacional: geo-transformacao, NMS, detector e avaliacao.

O detector e medido contra verdade fundamental conhecida: os limites destes
testes sao compromissos de desempenho, nao formalidade. Se o detector
degradar, a suite reprova.
"""
from __future__ import annotations

import numpy as np
import pytest

from oraculo.vision import detector as D
from oraculo.vision import evaluate as EV
from oraculo.vision import nms as N
from oraculo.vision import render as R
from oraculo.vision import tiles as T


# ============================================================ geo
def test_pixel_e_latlon_sao_inversos():
    geo = T.GeoTransform(-22.9, -43.2, 0.30, 768, 768)
    for lat, lon in ((-22.9, -43.2), (-22.895, -43.205), (-22.905, -43.19)):
        px, py = geo.to_pixel(lat, lon)
        la, lo = geo.to_latlon(px, py)
        assert la == pytest.approx(lat, abs=1e-6)
        assert lo == pytest.approx(lon, abs=1e-6)


def test_centro_da_imagem_e_o_centro_geografico():
    geo = T.GeoTransform(-15.8, -47.9, 0.5, 400, 400)
    px, py = geo.to_pixel(-15.8, -47.9)
    assert px == pytest.approx(200.0)
    assert py == pytest.approx(200.0)


def test_norte_esta_para_cima():
    geo = T.GeoTransform(-22.9, -43.2, 0.30, 500, 500)
    _, py_norte = geo.to_pixel(-22.89, -43.2)     # latitude maior = mais ao norte
    _, py_sul = geo.to_pixel(-22.91, -43.2)
    assert py_norte < py_sul, "latitude maior deve ter pixel y menor"


def test_area_do_pixel_e_o_quadrado_do_gsd():
    assert T.GeoTransform(0, 0, 0.30).pixel_area_m2() == pytest.approx(0.09)


def test_extensao_em_metros_e_km2():
    geo = T.GeoTransform(-22.9, -43.2, 0.30, 768, 768)
    w, h = geo.extent_m
    assert w == pytest.approx(230.4)
    assert geo.to_dict()["extent_km2"] == pytest.approx(0.0531, abs=1e-3)


# ============================================================ ladrilhos
def test_grade_cobre_a_imagem_com_sobreposicao():
    grid = T.tile_grid(768, 768, tile=256, overlap=32)
    assert len(grid) >= 9
    assert all(t.x1 <= 768 and t.y1 <= 768 for t in grid)
    # cobertura: todo pixel pertence a pelo menos um ladrilho
    cover = np.zeros((768, 768), dtype=bool)
    for t in grid:
        cover[t.y0:t.y1, t.x0:t.x1] = True
    assert cover.all(), "a grade deixou pixel descoberto"


def test_ladrilhos_tem_indice_unico():
    grid = T.tile_grid(600, 400, tile=200, overlap=40)
    assert len({t.index for t in grid}) == len(grid)


# ============================================================ IoU e NMS
def test_iou_de_caixas_identicas_e_um():
    b = np.array([[0.0, 0.0, 10.0, 10.0]])
    assert N.iou_matrix(b, b)[0, 0] == pytest.approx(1.0)


def test_iou_de_caixas_disjuntas_e_zero():
    a = np.array([[0.0, 0.0, 5.0, 5.0]])
    b = np.array([[10.0, 10.0, 15.0, 15.0]])
    assert N.iou_matrix(a, b)[0, 0] == pytest.approx(0.0)


def test_iou_de_sobreposicao_conhecida():
    a = np.array([[0.0, 0.0, 10.0, 10.0]])       # area 100
    b = np.array([[5.0, 0.0, 15.0, 10.0]])       # area 100, intersecao 50
    assert N.iou_matrix(a, b)[0, 0] == pytest.approx(50.0 / 150.0)


def test_nms_mantem_a_de_maior_pontuacao():
    boxes = np.array([[0, 0, 10, 10], [1, 1, 11, 11], [50, 50, 60, 60]], dtype="f8")
    keep = N.nms(boxes, np.array([0.9, 0.8, 0.7]), 0.4)
    assert set(keep.tolist()) == {0, 2}


def test_nms_preserva_caixas_distantes():
    boxes = np.array([[0, 0, 5, 5], [20, 20, 25, 25], [40, 40, 45, 45]], dtype="f8")
    keep = N.nms(boxes, np.array([0.5, 0.6, 0.7]), 0.3)
    assert len(keep) == 3


def test_nms_vazio_nao_quebra():
    assert len(N.nms(np.zeros((0, 4)), np.zeros(0))) == 0


def test_dedupe_remove_caixa_contida_em_outra():
    """Na costura entre ladrilhos, o mesmo painel aparece recortado e completo:
    IoU baixo, contencao alta. So a NMS classica nao resolve."""
    boxes = np.array([[0, 0, 20, 20], [0, 0, 20, 6]], dtype="f8")
    iou = N.iou_matrix(boxes[:1], boxes[1:])[0, 0]
    assert iou < 0.35, "o caso de teste precisa ter IoU baixo"
    keep = N.soft_dedupe(boxes, np.array([0.9, 0.8]))
    assert keep.tolist() == [0], "a caixa contida deveria ser suprimida"


def test_dedupe_nao_remove_paineis_vizinhos_legitimos():
    boxes = np.array([[0, 0, 10, 10], [12, 0, 22, 10]], dtype="f8")
    keep = N.soft_dedupe(boxes, np.array([0.9, 0.9]))
    assert len(keep) == 2


# ============================================ letterbox (contrato YOLO)
def test_letterbox_preserva_proporcao():
    scale, dx, dy = N.letterbox_params(1280, 640, 640)
    assert scale == pytest.approx(0.5)
    assert dx == pytest.approx(0.0)
    assert dy == pytest.approx(160.0)


def test_undo_letterbox_e_inverso_do_ajuste():
    src_w, src_h, dst = 1000, 500, 640
    scale, dx, dy = N.letterbox_params(src_w, src_h, dst)
    orig = np.array([[100.0, 50.0, 300.0, 200.0]])
    fwd = orig.copy()
    fwd[:, [0, 2]] = orig[:, [0, 2]] * scale + dx
    fwd[:, [1, 3]] = orig[:, [1, 3]] * scale + dy
    back = N.undo_letterbox(fwd, src_w, src_h, dst)
    assert np.allclose(back, orig, atol=1e-6)


def test_conversao_xywh_e_xyxy_e_reversivel():
    xywh = np.array([[50.0, 60.0, 20.0, 10.0]])
    assert np.allclose(N.xyxy_to_xywh(N.xywh_to_xyxy(xywh)), xywh)


def test_xywh_para_xyxy_usa_o_centro():
    out = N.xywh_to_xyxy(np.array([[10.0, 10.0, 4.0, 6.0]]))
    assert out.tolist() == [[8.0, 7.0, 12.0, 13.0]]


# ============================================================ cena
@pytest.fixture(scope="module")
def scene():
    return T.synth_scene(-22.9, -43.2, size_px=768, urban_class="misto",
                         panel_rate=0.25, seed=11)


def test_cena_tem_verdade_fundamental(scene):
    assert scene.rgb.shape == (768, 768, 3)
    assert scene.rgb.dtype == np.uint8
    assert scene.truth_count() > 0
    assert scene.panel_mask.shape == (768, 768)
    assert scene.panel_mask.sum() > 0


def test_cena_e_deterministica():
    a = T.synth_scene(-22.9, -43.2, size_px=256, seed=7)
    b = T.synth_scene(-22.9, -43.2, size_px=256, seed=7)
    assert np.array_equal(a.rgb, b.rgb)
    assert np.array_equal(a.panel_boxes, b.panel_boxes)


def test_classe_urbana_muda_a_morfologia():
    res = T.synth_scene(-22.9, -43.2, size_px=512, urban_class="residencial", seed=3)
    ind = T.synth_scene(-22.9, -43.2, size_px=512, urban_class="industrial", seed=3)
    ar_res = res.roof_area_m2()
    ar_ind = ind.roof_area_m2()
    assert ar_res["residencial"] > 0
    assert ar_ind["industrial"] > ar_res["industrial"]
    # industrial tem menos telhados, porem muito maiores
    assert len(ind.roof_boxes) < len(res.roof_boxes)


def test_painel_e_mais_azul_e_mais_escuro_que_asfalto(scene):
    """A separabilidade espectral e a premissa do detector classico."""
    f = D.ClassicalPanelDetector.features(scene.rgb)
    m = scene.panel_mask
    assert m.any()
    blue_panel = float(f["blue_raw"][m].mean())
    blue_fora = float(f["blue_raw"][~m].mean())
    lum_panel = float(f["luminance_raw"][m].mean())
    lum_fora = float(f["luminance_raw"][~m].mean())
    assert blue_panel > blue_fora + 0.05
    assert lum_panel < lum_fora


# ============================================================ detector
@pytest.fixture(scope="module")
def scan(scene):
    return D.scan_scene(scene.rgb, scene.geo, D.ClassicalPanelDetector())


def test_detector_classico_esta_disponivel():
    info = D.ClassicalPanelDetector().info()
    assert info.available is True
    assert info.kind == "classico"


def test_deteccoes_estao_georreferenciadas(scan):
    assert scan.detections
    for d in scan.detections:
        assert d.lat is not None and d.lon is not None
        assert -34.0 <= d.lat <= 6.0
        assert -74.0 <= d.lon <= -34.0
        assert d.area_m2 > 0 and d.kwp > 0


def test_area_calibrada_e_maior_que_a_bruta(scan):
    for d in scan.detections[:10]:
        assert d.area_m2 == pytest.approx(d.area_raw_m2 * D.AREA_CALIBRATION)


def test_conversao_area_para_potencia():
    assert D.area_to_kwp(100.0) == pytest.approx(20.0)


def test_deduplicacao_remove_repetidas_na_costura(scan):
    assert scan.raw_count >= scan.kept_count
    assert scan.kept_count == len(scan.detections)


def test_deteccoes_ficam_dentro_da_imagem(scan, scene):
    h, w = scene.rgb.shape[:2]
    for d in scan.detections:
        assert 0 <= d.box[0] <= w and 0 <= d.box[2] <= w
        assert 0 <= d.box[1] <= h and 0 <= d.box[3] <= h


def test_desempenho_do_detector_atende_o_compromisso(scan, scene):
    """Limites de desempenho. Se degradar, a suite reprova."""
    ev = EV.evaluate_scene(scan, scene)
    m = ev["match"]
    assert m["precision"] >= 0.85, ev
    assert m["recall"] >= 0.85, ev
    assert m["f1"] >= 0.85, ev
    assert ev["mask_iou"] >= 0.60, ev
    assert abs(ev["area"]["rel_error"]) <= 0.25, ev


@pytest.mark.parametrize("urban", ["residencial", "comercial", "industrial", "misto"])
def test_detector_funciona_nas_quatro_classes_urbanas(urban):
    sc = T.synth_scene(-22.9, -43.2, size_px=768, urban_class=urban,
                       panel_rate=0.30, seed=11)
    if sc.truth_count() == 0:
        pytest.skip("cena sem painel")
    res = D.scan_scene(sc.rgb, sc.geo, D.ClassicalPanelDetector())
    ev = EV.evaluate_scene(res, sc)
    assert ev["match"]["f1"] >= 0.70, (urban, ev)


def test_calibracao_de_area_reduz_o_vies():
    """A calibracao e medida; este teste guarda o ganho que ela entrega."""
    raws, cals = [], []
    for urban in ("residencial", "comercial", "misto"):
        sc = T.synth_scene(-22.9, -43.2, size_px=768, urban_class=urban,
                           panel_rate=0.28, seed=23)
        if sc.truth_count() == 0:
            continue
        res = D.scan_scene(sc.rgb, sc.geo, D.ClassicalPanelDetector())
        ev = EV.evaluate_scene(res, sc)
        if ev["area"]["rel_error"] is None:
            continue
        raws.append(abs(ev["area_raw"]["rel_error"]))
        cals.append(abs(ev["area"]["rel_error"]))
    assert raws and cals
    assert float(np.mean(cals)) < float(np.mean(raws)), (cals, raws)


def test_refinamento_melhora_a_area():
    sc = T.synth_scene(-22.9, -43.2, size_px=768, urban_class="misto",
                       panel_rate=0.28, seed=11)
    sem = D.ClassicalPanelDetector(D.ClassicalParams(refine=False))
    com = D.ClassicalPanelDetector(D.ClassicalParams(refine=True))
    ev_sem = EV.evaluate_scene(D.scan_scene(sc.rgb, sc.geo, sem), sc)
    ev_com = EV.evaluate_scene(D.scan_scene(sc.rgb, sc.geo, com), sc)
    assert ev_com["mask_iou"] > ev_sem["mask_iou"], (ev_com, ev_sem)


# ============================================================ YOLO
def test_adaptador_yolo_declara_a_ausencia_do_runtime():
    """Nunca apresentar o YOLO como ativo quando ele nao esta."""
    info = D.YoloSegAdapter().info()
    if not info.available:
        assert info.reason, "a indisponibilidade precisa ser explicada"
        assert "PyPI" in info.reason or "runtime" in info.reason.lower()
        assert info.runtime == "indisponível"


def test_backend_ativo_cai_para_o_classico_sem_runtime():
    det = D.build_detector()
    assert det.info().available is True
    if not D.YoloSegAdapter().info().available:
        assert det.info().kind == "classico"


def test_backends_status_lista_os_dois():
    st = D.backends_status()
    assert {b["kind"] for b in st} == {"classico", "yolo"}


def test_preprocessamento_do_yolo_produz_nchw_normalizado():
    y = D.YoloSegAdapter()
    rgb = np.full((400, 800, 3), 200, dtype="uint8")
    x, (scale, dx, dy) = y.preprocess(rgb)
    assert x.shape == (1, 3, y.p.imgsz, y.p.imgsz)
    assert 0.0 <= float(x.min()) and float(x.max()) <= 1.0
    assert scale == pytest.approx(0.8)


def test_decodificacao_do_yolo_aplica_limiar_e_nms():
    y = D.YoloSegAdapter(D.YoloParams(conf=0.5, iou=0.4, imgsz=640))
    # duas caixas sobrepostas com confianca alta e uma abaixo do limiar
    raw = np.array([[
        [320.0, 320.0, 64.0, 64.0, 0.9],
        [326.0, 322.0, 64.0, 64.0, 0.8],
        [100.0, 100.0, 20.0, 20.0, 0.2],
    ]]).transpose(0, 2, 1)
    boxes, scores = y.decode(raw, 640, 640)
    assert len(boxes) == 1, "NMS deveria fundir as duas e o limiar cortar a terceira"
    assert scores[0] == pytest.approx(0.9)


def test_decodificacao_sem_deteccao_devolve_vazio():
    y = D.YoloSegAdapter(D.YoloParams(conf=0.9))
    raw = np.array([[[320.0, 320.0, 20.0, 20.0, 0.1]]]).transpose(0, 2, 1)
    boxes, scores = y.decode(raw, 640, 640)
    assert len(boxes) == 0 and len(scores) == 0


def test_mascara_por_prototipos_respeita_a_caixa():
    protos = np.ones((2, 32, 32), dtype="f4") * 4.0
    coeffs = np.array([1.0, 1.0], dtype="f4")
    m = D.YoloSegAdapter.mask_from_prototypes(coeffs, protos, (10, 10, 30, 30),
                                              64, 64)
    assert m.shape == (64, 64)
    assert m[20, 20]              # dentro da caixa, prototipo positivo
    assert not m[5, 5]            # fora da caixa


def test_yolo_sem_sessao_nao_detecta():
    assert D.YoloSegAdapter().detect_tile(np.zeros((64, 64, 3), "uint8")) == []


# ============================================================ avaliacao
def test_casamento_perfeito():
    b = np.array([[0, 0, 10, 10], [20, 20, 30, 30]], dtype="f8")
    m = EV.match(b, b)
    assert m.tp == 2 and m.fp == 0 and m.fn == 0
    assert m.precision == pytest.approx(1.0)
    assert m.f1 == pytest.approx(1.0)


def test_casamento_e_um_para_um():
    """Duas deteccoes sobre a mesma verdade: uma casa, a outra e falso positivo."""
    truth = np.array([[0, 0, 10, 10]], dtype="f8")
    pred = np.array([[0, 0, 10, 10], [1, 1, 11, 11]], dtype="f8")
    m = EV.match(pred, truth)
    assert m.tp == 1 and m.fp == 1 and m.fn == 0


def test_falso_negativo_quando_nada_e_detectado():
    m = EV.match(np.zeros((0, 4)), np.array([[0, 0, 5, 5]], dtype="f8"))
    assert m.tp == 0 and m.fn == 1
    assert m.recall == pytest.approx(0.0)


def test_iou_de_mascara():
    a = np.zeros((10, 10), dtype=bool); a[:5, :] = True
    b = np.zeros((10, 10), dtype=bool); b[:5, :] = True
    assert EV.mask_iou(a, b) == pytest.approx(1.0)
    c = np.zeros((10, 10), dtype=bool); c[5:, :] = True
    assert EV.mask_iou(a, c) == pytest.approx(0.0)


def test_erro_de_area_relativo():
    e = EV.area_error(110.0, 100.0)
    assert e["rel_error"] == pytest.approx(0.10)
    assert e["abs_error_m2"] == pytest.approx(10.0)


def test_curva_pr_e_monotona_em_n():
    sc = T.synth_scene(-22.9, -43.2, size_px=512, panel_rate=0.3, seed=5)
    res = D.scan_scene(sc.rgb, sc.geo, D.ClassicalPanelDetector())
    pred = np.array([d.box for d in res.detections]).reshape(-1, 4)
    scores = np.array([d.score for d in res.detections])
    curve = EV.pr_curve(pred, scores, sc.panel_boxes)
    ns = [c["n_pred"] for c in curve]
    assert ns == sorted(ns, reverse=True), "elevar o limiar nao pode aumentar n"


# ============================================================ render
def test_png_e_gerado_com_assinatura_valida(scene, scan):
    if not R.available():
        pytest.skip("Pillow indisponível")
    png = R.scene_png(scene.rgb, detections=scan.detections,
                      truth_boxes=scene.panel_boxes, tiles=scan.tiles)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(png) > 1000


def test_png_de_canal_de_caracteristica(scene):
    if not R.available():
        pytest.skip("Pillow indisponível")
    f = D.ClassicalPanelDetector.features(scene.rgb)
    png = R.feature_png(f["blue_excess"], cmap="teal")
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
