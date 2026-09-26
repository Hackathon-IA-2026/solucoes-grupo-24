"""Peças comuns da visão computacional (validar_modelo.py e auditoria_camada1.py).

Um lugar só para: ler config/visao.yaml, carregar o YOLO, descobrir se ele é de detecção ou
segmentação, listar imagens, georreferenciar pixels e medir área em m². Os dois scripts
chamam estas funções — o jeito de converter pixel em coordenada não pode divergir entre a
validação e a auditoria.

Decisões:
- `ultralytics` (e o torch que vem com ele) é importado só dentro de carregar_modelo(): o modo
  --mock, os testes e a auditoria das camadas 2/3 rodam sem ele. Instalação:
  `pip install -e ".[visao]"`.
- O tipo do modelo vem de `model.task` (ultralytics), nunca de suposição pelo nome do arquivo.
- Georreferência: world file (.pgw/.jgw/.tfw, formato ESRI) sem dependência extra; GeoTIFF via
  rasterio (import tardio). Imagem sem georreferência é RECUSADA com mensagem: inventar
  coordenada para ela quebraria a regra "nunca inventar dados".
- Área em m² pela geodésica do elipsoide WGS84 (pyproj.Geod), não em graus².
"""
from __future__ import annotations

import json
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.utils.config import carregar
from src.utils.paths import RAIZ, ensure

# Tarefas do ultralytics que a auditoria sabe transformar em geometria.
TAREFAS_SUPORTADAS = ("segment", "detect")


class ErroVisao(RuntimeError):
    """Problema de entrada da visão computacional (a mensagem diz o que fazer)."""


def config() -> dict[str, Any]:
    """config/visao.yaml (único ponto de parâmetros da visão computacional)."""
    return carregar("visao")


def caminho(relativo_backend: str | Path) -> Path:
    """Caminho da config (relativo a Backend/) -> absoluto. Absoluto passa direto."""
    p = Path(relativo_backend)
    return p if p.is_absolute() else RAIZ / p


# --------------------------------------------------------------------------- modelo
def resolver_caminho_modelo(cli: str | None) -> Path:
    """Linha de comando > config. Sem nenhum dos dois, erro explicando onde preencher."""
    valor = cli or config()["modelo"]["caminho"]
    if not valor:
        raise ErroVisao("caminho do modelo YOLO não informado: use --modelo ou preencha "
                        "modelo.caminho em config/visao.yaml")
    p = caminho(valor)
    if not p.exists():
        raise ErroVisao(f"modelo YOLO não encontrado: {p}")
    return p


def carregar_modelo(arquivo: Path) -> Any:
    """YOLO do ultralytics (import tardio: só quem roda o modelo precisa do torch)."""
    try:
        from ultralytics import YOLO
    except ImportError as e:  # pragma: no cover - depende do ambiente
        raise ErroVisao('ultralytics não instalado: pip install -e ".[visao]"') from e
    return YOLO(str(arquivo))


def tarefa_do_modelo(modelo: Any) -> str:
    """'segment' (máscara) ou 'detect' (caixa), lido de model.task. Outra tarefa -> erro."""
    tarefa = getattr(modelo, "task", None)
    if tarefa not in TAREFAS_SUPORTADAS:
        raise ErroVisao(f"tarefa do modelo = {tarefa!r}; a auditoria só sabe usar {TAREFAS_SUPORTADAS}")
    return tarefa


def metadados_modelo(modelo: Any) -> dict[str, Any]:
    """O que o checkpoint conta sobre o treino (data, versão, dataset, imgsz), se disponível."""
    ck = getattr(modelo, "ckpt", None) or {}
    args = ck.get("train_args") or {}
    return {
        "classes": dict(getattr(modelo, "names", {}) or {}),
        "data_treino": ck.get("date"),
        "versao_ultralytics_treino": ck.get("version"),
        "dataset_treino": args.get("data"),
        "imgsz": args.get("imgsz"),
        "epocas": args.get("epochs"),
    }


def listar_imagens(pasta: Path, extensoes: Sequence[str] | None = None) -> list[Path]:
    """Imagens da pasta (ordem alfabética, determinística). Pasta vazia/inexistente -> erro."""
    if not pasta.is_dir():
        raise ErroVisao(f"pasta de imagens não encontrada: {pasta}")
    exts = {e.lower() for e in (extensoes or config()["imagens"]["extensoes"])}
    imagens = sorted(p for p in pasta.iterdir() if p.suffix.lower() in exts)
    if not imagens:
        raise ErroVisao(f"nenhuma imagem ({', '.join(sorted(exts))}) em {pasta}")
    return imagens


# --------------------------------------------------------------------------- saída do YOLO
@dataclass(frozen=True)
class DeteccaoPixel:
    """Uma detecção em coordenadas de PIXEL (x = coluna, y = linha, origem no canto superior esquerdo)."""
    poligono: list[tuple[float, float]]
    confianca: float
    classe: str


def deteccoes_do_resultado(resultado: Any, tarefa: str) -> list[DeteccaoPixel]:
    """Resultado do ultralytics -> polígonos em pixel.

    segment: contorno da máscara (`masks.xy`); detect: retângulo da caixa (`boxes.xyxy`).
    """
    nomes = getattr(resultado, "names", {}) or {}
    caixas = resultado.boxes
    if caixas is None or len(caixas) == 0:
        return []
    confs = [float(c) for c in caixas.conf.tolist()]
    classes = [nomes.get(int(c), str(int(c))) for c in caixas.cls.tolist()]
    if tarefa == "segment" and resultado.masks is not None:
        poligonos = [[(float(x), float(y)) for x, y in m.tolist()] for m in resultado.masks.xy]
    else:
        poligonos = [[(x1, y1), (x2, y1), (x2, y2), (x1, y2)] for x1, y1, x2, y2 in caixas.xyxy.tolist()]
    return [DeteccaoPixel(p, c, k) for p, c, k in zip(poligonos, confs, classes) if len(p) >= 3]


# --------------------------------------------------------------------------- georreferência
@dataclass(frozen=True)
class Georreferencia:
    """Transformação afim pixel -> coordenada do mapa (convenção de CANTO do pixel) + CRS.

    x_mapa = a·col + b·lin + c ;  y_mapa = d·col + e·lin + f   (col/lin contínuos, 0 = borda)
    """
    a: float
    b: float
    c: float
    d: float
    e: float
    f: float
    crs: str

    def para_mapa(self, col: float, lin: float) -> tuple[float, float]:
        return (self.a * col + self.b * lin + self.c, self.d * col + self.e * lin + self.f)

    @property
    def gsd_m(self) -> float | None:
        """Tamanho do pixel em metros (só quando o CRS é métrico ou geográfico conhecido)."""
        from pyproj import CRS

        crs = CRS.from_user_input(self.crs)
        passo = (self.a ** 2 + self.d ** 2) ** 0.5
        if crs.is_geographic:
            return passo * 111_320.0  # grau de latitude ≈ 111,32 km (escala, não geometria)
        return passo if crs.axis_info[0].unit_name in ("metre", "meter") else None


# Extensão do world file para cada extensão de imagem (ESRI): .png -> .pgw, .jpg -> .jgw...
_WORLD = {".png": ".pgw", ".jpg": ".jgw", ".jpeg": ".jgw", ".tif": ".tfw", ".tiff": ".tfw"}


def ler_world_file(arquivo: Path, crs: str) -> Georreferencia:
    """World file ESRI: 6 linhas A, D, B, E, C, F; (C, F) = CENTRO do pixel superior esquerdo.

    Convertido para a convenção de CANTO (a mesma do rasterio), para um vértice de máscara em
    (col, lin) contínuos cair no lugar certo: canto = centro − meio pixel em cada eixo.
    """
    valores = [float(v) for v in arquivo.read_text(encoding="utf-8").split()]
    if len(valores) != 6:
        raise ErroVisao(f"world file com {len(valores)} valores (esperado 6): {arquivo}")
    a, d, b, e, c, f = valores
    return Georreferencia(a, b, c - a / 2 - b / 2, d, e, f - d / 2 - e / 2, crs)


def georreferencia_da_imagem(imagem: Path, crs_world_file: str | None = None) -> Georreferencia:
    """World file ao lado da imagem ou, para GeoTIFF, a transformação do próprio arquivo."""
    world = imagem.with_suffix(_WORLD.get(imagem.suffix.lower(), ".wld"))
    if world.exists():
        return ler_world_file(world, crs_world_file or config()["imagens"]["crs_world_file"])
    if imagem.suffix.lower() in (".tif", ".tiff"):
        try:
            import rasterio
        except ImportError as e:
            raise ErroVisao(f"{imagem.name}: GeoTIFF sem world file e rasterio não instalado") from e
        with rasterio.open(imagem) as src:
            t = src.transform
            if src.crs is None:
                raise ErroVisao(f"{imagem.name}: GeoTIFF sem CRS")
            return Georreferencia(t.a, t.b, t.c, t.d, t.e, t.f, src.crs.to_string())
    raise ErroVisao(f"{imagem.name}: sem georreferência (world file {world.name} ou GeoTIFF). "
                    "Não é possível saber onde está o painel — imagem recusada.")


def poligono_lonlat(pixels: Sequence[tuple[float, float]], geo: Georreferencia) -> list[tuple[float, float]]:
    """Vértices em pixel -> (lon, lat) WGS84 (EPSG:4326), anel fechado."""
    from pyproj import Transformer

    pts = [geo.para_mapa(x, y) for x, y in pixels]
    if geo.crs.upper() not in ("EPSG:4326", "OGC:CRS84"):
        tr = Transformer.from_crs(geo.crs, "EPSG:4326", always_xy=True)
        pts = [tr.transform(x, y) for x, y in pts]
    if pts[0] != pts[-1]:
        pts.append(pts[0])
    return pts


def area_m2(anel_lonlat: Sequence[tuple[float, float]]) -> float:
    """Área geodésica (m²) de um anel lon/lat no elipsoide WGS84."""
    from pyproj import Geod

    lons, lats = zip(*anel_lonlat)
    area, _ = Geod(ellps="WGS84").polygon_area_perimeter(lons, lats)
    return abs(area)


def retangulo_lonlat(lat: float, lon: float, largura_m: float, altura_m: float) -> list[tuple[float, float]]:
    """Retângulo (anel fechado lon/lat) centrado em (lat, lon) com lados em metros (E-O × N-S)."""
    from pyproj import Geod

    g = Geod(ellps="WGS84")
    lon_l, _, _ = g.fwd(lon, lat, 270, largura_m / 2)
    lon_r, _, _ = g.fwd(lon, lat, 90, largura_m / 2)
    _, lat_n, _ = g.fwd(lon, lat, 0, altura_m / 2)
    _, lat_s, _ = g.fwd(lon, lat, 180, altura_m / 2)
    return [(lon_l, lat_s), (lon_r, lat_s), (lon_r, lat_n), (lon_l, lat_n), (lon_l, lat_s)]


def distancia_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distância geodésica (m) entre dois pontos WGS84."""
    from pyproj import Geod

    _, _, d = Geod(ellps="WGS84").inv(lon1, lat1, lon2, lat2)
    return d


def centroide(anel_lonlat: Sequence[tuple[float, float]]) -> tuple[float, float]:
    """Centroide (lat, lon) do polígono (shapely, planar em graus: ok na escala de um telhado)."""
    from shapely.geometry import Polygon

    c = Polygon(anel_lonlat).centroid
    return (c.y, c.x)


# --------------------------------------------------------------------------- GeoJSON
def escrever_geojson(features: list[dict[str, Any]], destino: Path, propriedades: dict[str, Any]) -> Path:
    """FeatureCollection (EPSG:4326) com propriedades de nível superior (ex.: is_mock)."""
    ensure(destino.parent)
    colecao = {"type": "FeatureCollection", "properties": propriedades, "features": features}
    destino.write_text(json.dumps(colecao, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return destino


def ler_geojson(origem: Path) -> dict[str, Any]:
    dados = json.loads(origem.read_text(encoding="utf-8"))
    if dados.get("type") != "FeatureCollection":
        raise ErroVisao(f"{origem}: esperado um GeoJSON FeatureCollection")
    return dados


def iterar_features(colecao: dict[str, Any]) -> Iterator[dict[str, Any]]:
    yield from colecao.get("features", [])
