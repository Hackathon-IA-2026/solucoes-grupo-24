# -*- coding: utf-8 -*-
"""Imagem de satélite real (oraculo.vision.satelite_real), sem rede: ladrilho falso no lugar da Esri."""
import numpy as np
import pytest

from oraculo.vision import satelite_real as SR


def test_gsd_no_rio_e_proximo_de_0_28m():
    # Web Mercator no zoom 19 a 22,9° S: ~0,275 m/pixel (a resolução do banco de ensaio é 0,3 m)
    assert SR.gsd_m(-22.9) == pytest.approx(0.2749, abs=5e-4)


def test_pixel_global_na_origem_e_no_centro():
    n = SR.LADRILHO_PX * 2 ** SR.ZOOM
    x, y = SR.pixel_global(0.0, 0.0)
    assert (x, y) == (pytest.approx(n / 2), pytest.approx(n / 2))


def test_mosaico_recorta_o_quadrado_centrado_no_ponto(monkeypatch):
    # cada ladrilho falso tem uma cor por (x, y): o recorte tem de sair do tamanho pedido
    monkeypatch.setattr(SR, "_ladrilho", lambda cliente, z, x, y: np.full((256, 256, 3), (x + y) % 255, dtype="u1"))
    monkeypatch.setattr(SR.config, "FORCE_OFFLINE", True)
    rgb, geo, fonte = SR.mosaico(-22.9, -43.2, lado_m=230.4)
    lado_px = rgb.shape[0]
    assert rgb.shape == (lado_px, lado_px, 3)
    assert lado_px * geo.gsd_m == pytest.approx(230.4, abs=2 * geo.gsd_m)
    # o centro da imagem georreferencia de volta no ponto pedido
    lat, lon = geo.to_latlon(geo.width_px / 2, geo.height_px / 2)
    assert (lat, lon) == (pytest.approx(-22.9, abs=1e-7), pytest.approx(-43.2, abs=1e-7))
    assert fonte["fonte"] == "Esri World Imagery" and fonte["ladrilhos"] >= 4


def test_ponto_fora_do_brasil_e_recusado():
    with pytest.raises(ValueError):
        SR.analisar(40.7, -74.0)
