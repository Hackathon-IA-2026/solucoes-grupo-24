"""Download de imagem de satélite da área piloto via Google Earth Engine, por bounding box.

Uso (de dentro de Backend/):
    python -m pipeline.download_satelite                       # bbox de config/visao.yaml
    python -m pipeline.download_satelite --bbox -43.33 -15.82 -43.29 -15.78 [--dry-run]

TODO (Tiago): a área piloto ainda é provisória (config/projeto.yaml). Quando for confirmada,
preencher `satelite.bbox` em config/visao.yaml; até lá, sem --bbox o script para e avisa.

Saída: GeoTIFF composto (mediana do período, filtro de nuvens) em satelite.saida, pronto para
auditoria_camada1.py (o GeoTIFF traz a própria georreferência).

Decisões:
- `earthengine-api` é import tardio (extra `pip install -e ".[visao]"`) e a autenticação é a
  do usuário (`earthengine authenticate`); o id do projeto Cloud vem de satelite.gee_projeto.
- TRAVA DE RESOLUÇÃO: a escala pedida (m/pixel) é comparada com modelo.gsd_maximo_m. Acima
  dela o download é recusado sem --forcar: com Sentinel-2 (10 m) um painel residencial não
  ocupa nem um pixel, e o modelo devolveria "zero painéis" — um falso negativo que pareceria
  resultado. Para a auditoria de verdade, trocar a coleção por imagem submétrica.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from pipeline import visao_comum as vc
from src.utils.paths import ensure


class ErroDownload(vc.ErroVisao):
    """Parâmetro de download inválido ou ausente."""


def validar_bbox(bbox: Any) -> tuple[float, float, float, float]:
    """[lon_min, lat_min, lon_max, lat_max] dentro do Brasil e com min < max."""
    if bbox is None:
        raise ErroDownload("área piloto sem bounding box: preencha satelite.bbox em config/visao.yaml "
                           "(TODO Tiago) ou passe --bbox LON_MIN LAT_MIN LON_MAX LAT_MAX")
    if len(bbox) != 4:
        raise ErroDownload(f"bbox precisa de 4 números, veio {bbox}")
    lon_min, lat_min, lon_max, lat_max = (float(v) for v in bbox)
    if not (lon_min < lon_max and lat_min < lat_max):
        raise ErroDownload(f"bbox com mínimo ≥ máximo: {bbox}")
    # mesma caixa do Brasil que o contrato do dashboard usa (lat/lon trocados caem fora)
    if not (-74 <= lon_min and lon_max <= -28 and -34 <= lat_min and lat_max <= 6):
        raise ErroDownload(f"bbox fora do Brasil (lat/lon trocados?): {bbox}")
    return lon_min, lat_min, lon_max, lat_max


def checar_resolucao(escala_m: float, gsd_maximo_m: float, forcar: bool) -> str | None:
    """Recusa (ou só avisa, com --forcar) imagem grossa demais para painel residencial."""
    if escala_m <= gsd_maximo_m:
        return None
    msg = (f"escala de {escala_m} m/pixel > {gsd_maximo_m} m (modelo.gsd_maximo_m): painel residencial "
           "não aparece nessa resolução. Use uma coleção submétrica ou --forcar só para testar o fluxo.")
    if not forcar:
        raise ErroDownload(msg)
    return msg


def baixar(bbox: tuple[float, float, float, float], cfg: dict[str, Any], destino: Path) -> Path:  # pragma: no cover - rede/GEE
    """Composto mediano da coleção no período, recortado no bbox, salvo como GeoTIFF."""
    try:
        import ee
    except ImportError as e:
        raise ErroDownload('earthengine-api não instalado: pip install -e ".[visao]"') from e
    if not cfg["gee_projeto"]:
        raise ErroDownload("satelite.gee_projeto vazio em config/visao.yaml (projeto Cloud do Earth Engine)")
    import requests

    ee.Initialize(project=cfg["gee_projeto"])
    regiao = ee.Geometry.Rectangle(list(bbox))
    imagem = (ee.ImageCollection(cfg["colecao"])
              .filterBounds(regiao)
              .filterDate(cfg["data_inicio"], cfg["data_fim"])
              .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", cfg["max_nuvens_pct"]))
              .median()
              .select(cfg["bandas"]))
    url = imagem.getDownloadURL({"region": regiao, "scale": cfg["escala_m"], "format": "GEO_TIFF",
                                 "crs": "EPSG:4326"})
    resp = requests.get(url, timeout=300)
    resp.raise_for_status()
    ensure(destino.parent)
    destino.write_bytes(resp.content)
    return destino


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Imagem de satélite da área piloto (Google Earth Engine).")
    ap.add_argument("--bbox", nargs=4, type=float, metavar=("LON_MIN", "LAT_MIN", "LON_MAX", "LAT_MAX"))
    ap.add_argument("--dry-run", action="store_true", help="só valida parâmetros, não baixa")
    ap.add_argument("--forcar", action="store_true", help="baixa mesmo com resolução grossa demais")
    args = ap.parse_args(argv)
    cfg_vis = vc.config()
    cfg = cfg_vis["satelite"]
    try:
        bbox = validar_bbox(args.bbox or cfg["bbox"])
        aviso = checar_resolucao(cfg["escala_m"], cfg_vis["modelo"]["gsd_maximo_m"], args.forcar)
        if aviso:
            print(f"AVISO: {aviso}")
        nome = "_".join(f"{v:.4f}" for v in bbox) + f"_{cfg['data_inicio']}_{cfg['data_fim']}.tif"
        destino = vc.caminho(cfg["saida"]) / nome
        if args.dry_run:
            print(f"ok (dry-run): {cfg['colecao']} · bbox {bbox} · {cfg['escala_m']} m -> {destino}")
            return 0
        print(f"baixado: {baixar(bbox, cfg, destino)}")
    except ErroDownload as e:
        print(f"ERRO: {e}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
