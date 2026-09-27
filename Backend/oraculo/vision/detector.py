# -*- coding: utf-8 -*-
"""Detectores de paineis fotovoltaicos em ortoimagem.

Dois backends com a MESMA interface:

  ``ClassicalPanelDetector``  — ativo. Visao computacional em scipy.ndimage:
     indice espectral de excesso de azul, luminancia, densidade de borda por
     Sobel, morfologia binaria, componentes conexas e filtro de forma. Roda
     agora, em qualquer imagem, e e avaliado contra verdade fundamental.

  ``YoloSegAdapter``          — pronto, sem pesos. Implementa TODO o
     pre e pos-processamento do YOLOv8-seg: letterbox, ladrilhamento,
     decodificacao das saidas, limiar de confianca, NMS, upsample de mascara e
     transformacao ladrilho -> imagem -> coordenada. Falta apenas o runtime de
     inferencia.

HONESTIDADE SOBRE O YOLO: ``torch``, ``onnxruntime`` e ``ultralytics`` NAO
podem ser instalados neste ambiente — o proxy corporativo bloqueia o PyPI com
certificado proprio. O adaptador detecta a ausencia do runtime, declara isso na
API e cede o lugar ao detector classico. Quando houver pesos e runtime, trocar
o backend e uma linha; nada mais no pipeline muda, porque o ladrilhamento, a
NMS, a deduplicacao entre ladrilhos e a georreferencia sao compartilhados e
testados.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

import numpy as np

try:
    from scipy import ndimage as ndi
except ImportError:  # pragma: no cover
    ndi = None  # type: ignore

from . import nms as NMS
from .tiles import DEFAULT_OVERLAP_PX, DEFAULT_TILE_PX, GeoTransform, Tile, tile_grid


# ------------------------------------------------------------------ tipos
@dataclass
class Detection:
    """Uma deteccao de painel, em pixel da imagem completa."""

    box: tuple[float, float, float, float]        # x0, y0, x1, y1
    score: float
    area_px: float
    tile_index: int = -1
    lat: float | None = None
    lon: float | None = None
    area_m2: float | None = None          # calibrada
    area_raw_m2: float | None = None      # bruta, sem calibracao
    kwp: float | None = None
    rectangularity: float | None = None
    blue_index: float | None = None
    edge_density: float | None = None

    def to_dict(self) -> dict:
        return {
            "box": [round(float(v), 1) for v in self.box],
            "score": round(float(self.score), 4),
            "area_px": round(float(self.area_px), 1),
            "tile_index": int(self.tile_index),
            "lat": None if self.lat is None else round(self.lat, 6),
            "lon": None if self.lon is None else round(self.lon, 6),
            "area_m2": None if self.area_m2 is None else round(self.area_m2, 2),
            "area_raw_m2": None if self.area_raw_m2 is None
                           else round(self.area_raw_m2, 2),
            "kwp": None if self.kwp is None else round(self.kwp, 3),
            "rectangularity": None if self.rectangularity is None
                              else round(self.rectangularity, 3),
            "blue_index": None if self.blue_index is None
                          else round(self.blue_index, 4),
            "edge_density": None if self.edge_density is None
                            else round(self.edge_density, 4),
        }


@dataclass
class DetectorInfo:
    name: str
    kind: str                 # "classico" | "yolo"
    available: bool
    reason: str = ""
    params: dict = field(default_factory=dict)
    runtime: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name, "kind": self.kind, "available": self.available,
            "reason": self.reason, "params": self.params, "runtime": self.runtime,
        }


class Detector(Protocol):
    """Contrato comum aos backends."""

    def info(self) -> DetectorInfo: ...

    def detect_tile(self, rgb: np.ndarray) -> list[Detection]: ...


# ------------------------------------------- conversao area -> potencia
# Modulos comerciais entregam da ordem de 200 W por metro quadrado de area de
# modulo. E premissa de negocio: fica visivel e versionada.
WATT_PER_M2 = 200.0

# Janela de suavizacao dos indices espectrais, em pixels (~1,5 m a 30 cm/px).
SMOOTH_PX = 5

# Calibracao de area, MEDIDA contra verdade fundamental na cena de referencia.
# Mesmo apos o refinamento em duas etapas, o detector subestima a area em torno
# de 16%: a borda do painel e um gradiente, nao um degrau, e qualquer limiar
# corta parte dela. O vies e sistematico e consistente entre classes urbanas
# (-12% a -21%), portanto e corrigivel. O valor bruto continua disponivel para
# auditoria, e o teste de regressao exige erro calibrado abaixo de 8%.
#
# LIMITE: a calibracao foi medida em ortoimagem SINTETICA. Em imagem real ela
# precisa ser remedida contra um conjunto rotulado. Ver 08-limitacoes.md.
AREA_CALIBRATION = 1.19
AREA_CALIBRATION_SOURCE = (
    "medida contra verdade fundamental da cena sintética de referência "
    "(erro bruto médio de -16%)"
)


def area_to_kwp(area_m2: float) -> float:
    return area_m2 * WATT_PER_M2 / 1000.0


# =================================================== detector classico
@dataclass
class ClassicalParams:
    # Assinatura dos materiais em ortoimagem, medida na cena de referencia:
    #   painel   -> excesso de azul 0,21   luminancia  56
    #   asfalto  -> excesso de azul 0,021  luminancia  80
    #   telhado  -> excesso de azul -0,14  luminancia 131
    #   vegetacao-> excesso de azul -0,13  luminancia  90
    # O limiar de azul e o que separa painel de asfalto; sem ele, a malha
    # viaria inteira entra como deteccao.
    blue_excess_min: float = 0.090
    luminance_max: float = 74.0
    edge_density_min: float = 0.050    # modulos criam borda periodica
    min_area_px: int = 30
    max_area_frac: float = 0.75        # um painel industrial domina o ladrilho
    rectangularity_min: float = 0.50
    aspect_max: float = 6.0
    open_iter: int = 1
    close_iter: int = 2
    score_min: float = 0.30
    # Refinamento em duas etapas. A suavizacao espectral e a abertura
    # morfologica erodem cerca de 2 a 3 px de cada borda -- perda que, num
    # painel residencial de 12 px, chega a 40% da area e propaga direto para o
    # kWp estimado. A segunda etapa redelimita a deteccao sobre o indice CRU,
    # com limiar relaxado, dentro de uma vizinhanca dilatada.
    refine: bool = True
    refine_pad: int = 5
    refine_relax: float = 0.55

    def to_dict(self) -> dict:
        return dict(self.__dict__)


class ClassicalPanelDetector:
    """Deteccao de paineis por indice espectral, textura e forma.

    Sequencia, toda em scipy.ndimage:

    1. indice de excesso de azul  b = (B - (R+G)/2) / (R+G+B)
    2. luminancia  L = 0,299R + 0,587G + 0,114B   (painel e escuro)
    3. densidade de borda por magnitude de Sobel, suavizada em janela local
    4. mascara = (b alto) E (L baixa) E (borda alta)
    5. abertura e fechamento binarios para remover sal-e-pimenta e fechar vaos
    6. componentes conexas + filtro de area, retangularidade e alongamento
    7. pontuacao continua combinando os tres sinais
    """

    def __init__(self, params: ClassicalParams | None = None) -> None:
        self.p = params or ClassicalParams()

    def info(self) -> DetectorInfo:
        return DetectorInfo(
            name="Detector clássico de painéis (índice espectral + textura + forma)",
            kind="classico",
            available=ndi is not None,
            reason="" if ndi is not None else "scipy.ndimage indisponível",
            params=self.p.to_dict(),
            runtime="numpy + scipy.ndimage",
        )

    # ---------------------------------------------------------- features
    @staticmethod
    def features(rgb: np.ndarray) -> dict[str, np.ndarray]:
        a = np.asarray(rgb, dtype="f4")
        r, g, b = a[..., 0], a[..., 1], a[..., 2]
        total = r + g + b + 1e-6
        blue_raw = (b - (r + g) / 2.0) / total
        lum_raw = 0.299 * r + 0.587 * g + 0.114 * b
        if ndi is not None:
            # O gradiente e calculado na luminancia CRUA: a textura dos modulos
            # e justamente o sinal que se quer medir aqui.
            gx = ndi.sobel(lum_raw, axis=1, mode="reflect")
            gy = ndi.sobel(lum_raw, axis=0, mode="reflect")
            grad = np.hypot(gx, gy)
            thr = float(np.percentile(grad, 70)) if grad.size else 0.0
            edges = (grad > max(thr, 1e-6)).astype("f4")
            edge_density = ndi.uniform_filter(edges, size=9, mode="reflect")
            # Os indices espectrais, ao contrario, sao suavizados: o limiar deve
            # decidir sobre a mancha, nao sobre o vao entre dois modulos.
            blue_excess = ndi.uniform_filter(blue_raw, size=SMOOTH_PX, mode="reflect")
            lum = ndi.uniform_filter(lum_raw, size=SMOOTH_PX, mode="reflect")
        else:  # pragma: no cover
            grad = np.zeros_like(lum_raw)
            edge_density = np.zeros_like(lum_raw)
            blue_excess, lum = blue_raw, lum_raw
        return {"blue_excess": blue_excess, "luminance": lum,
                "blue_raw": blue_raw, "luminance_raw": lum_raw,
                "gradient": grad, "edge_density": edge_density}

    # ---------------------------------------------------------- detect
    def detect_tile(self, rgb: np.ndarray) -> list[Detection]:
        if ndi is None:  # pragma: no cover
            return []
        h, w = rgb.shape[:2]
        f = self.features(rgb)
        p = self.p

        mask = ((f["blue_excess"] > p.blue_excess_min) &
                (f["luminance"] < p.luminance_max) &
                (f["edge_density"] > p.edge_density_min))
        if p.close_iter:
            mask = ndi.binary_closing(mask, structure=np.ones((3, 3)),
                                      iterations=p.close_iter)
        if p.open_iter:
            mask = ndi.binary_opening(mask, structure=np.ones((3, 3)),
                                      iterations=p.open_iter)
        mask = ndi.binary_fill_holes(mask)

        labels, n = ndi.label(mask)
        if n == 0:
            return []
        max_area = p.max_area_frac * h * w
        out: list[Detection] = []
        for i, sl in enumerate(ndi.find_objects(labels), start=1):
            if sl is None:
                continue
            comp = labels[sl] == i
            area = float(comp.sum())
            if area < p.min_area_px or area > max_area:
                continue
            y0, y1 = sl[0].start, sl[0].stop
            x0, x1 = sl[1].start, sl[1].stop
            bw, bh = float(x1 - x0), float(y1 - y0)
            if bw <= 0 or bh <= 0:
                continue
            rect = area / (bw * bh)
            if rect < p.rectangularity_min:
                continue
            aspect = max(bw / bh, bh / bw)
            if aspect > p.aspect_max:
                continue

            be = float(f["blue_excess"][sl][comp].mean())
            ed = float(f["edge_density"][sl][comp].mean())
            lm = float(f["luminance"][sl][comp].mean())

            if p.refine:
                ref = self._refine(f, (x0, y0, x1, y1), h, w)
                if ref is not None:
                    x0, y0, x1, y1, area = ref
                    bw, bh = float(x1 - x0), float(y1 - y0)
                    if bw <= 0 or bh <= 0:
                        continue
                    rect = area / (bw * bh)

            s_blue = _ramp(be, p.blue_excess_min, p.blue_excess_min * 4.0)
            s_edge = _ramp(ed, p.edge_density_min, p.edge_density_min * 3.0)
            s_dark = _ramp(p.luminance_max - lm, 0.0, 60.0)
            s_rect = _ramp(rect, p.rectangularity_min, 0.95)
            score = 0.34 * s_blue + 0.26 * s_edge + 0.20 * s_dark + 0.20 * s_rect
            if score < p.score_min:
                continue
            out.append(Detection(
                box=(float(x0), float(y0), float(x1), float(y1)),
                score=float(score), area_px=area,
                rectangularity=rect, blue_index=be, edge_density=ed,
            ))
        return out


    # ---------------------------------------------------------- refino
    def _refine(self, f: dict, box: tuple[int, int, int, int],
                h: int, w: int) -> tuple[int, int, int, int, float] | None:
        """Redelimita a deteccao no indice cru, com limiar relaxado.

        Detectar no indice suavizado e correto (decide sobre a mancha, nao
        sobre o vao entre modulos), mas a mancha suavizada e menor que o
        painel. Esta etapa recupera a extensao verdadeira sem reintroduzir os
        falsos positivos que o limiar frouxo causaria se aplicado a imagem
        inteira: ela so atua DENTRO de uma vizinhanca ja aceita.
        """
        if ndi is None:  # pragma: no cover
            return None
        p = self.p
        pad = p.refine_pad
        rx0, ry0 = max(0, box[0] - pad), max(0, box[1] - pad)
        rx1, ry1 = min(w, box[2] + pad), min(h, box[3] + pad)
        if rx1 - rx0 < 3 or ry1 - ry0 < 3:
            return None
        sub_b = f["blue_raw"][ry0:ry1, rx0:rx1]
        sub_l = f["luminance_raw"][ry0:ry1, rx0:rx1]
        loose = ((sub_b > p.blue_excess_min * p.refine_relax) &
                 (sub_l < p.luminance_max * (2.0 - p.refine_relax)))
        loose = ndi.binary_closing(loose, structure=np.ones((3, 3)), iterations=2)
        loose = ndi.binary_fill_holes(loose)
        lab, k = ndi.label(loose)
        if k == 0:
            return None
        # componente que contem o centro da deteccao original
        cy = int(round((box[1] + box[3]) / 2.0)) - ry0
        cx = int(round((box[0] + box[2]) / 2.0)) - rx0
        cy = int(np.clip(cy, 0, loose.shape[0] - 1))
        cx = int(np.clip(cx, 0, loose.shape[1] - 1))
        target = int(lab[cy, cx])
        if target == 0:
            sizes = ndi.sum(loose, lab, index=range(1, k + 1))
            target = int(np.argmax(sizes)) + 1
        comp = lab == target
        area = float(comp.sum())
        if area <= 0:
            return None
        ys, xs = np.nonzero(comp)
        return (int(xs.min()) + rx0, int(ys.min()) + ry0,
                int(xs.max()) + 1 + rx0, int(ys.max()) + 1 + ry0, area)


def _ramp(v: float, lo: float, hi: float) -> float:
    if hi <= lo:
        return 0.0
    return float(np.clip((v - lo) / (hi - lo), 0.0, 1.0))


# =================================================== adaptador YOLOv8-seg
@dataclass
class YoloParams:
    imgsz: int = 640
    conf: float = 0.25
    iou: float = 0.45
    max_det: int = 300
    weights: str = "yolov8n-seg-pv.pt"
    class_id: int = 0
    class_name: str = "painel_fotovoltaico"
    # Numero de classes do cabecalho. A saida do YOLOv8 tem 4 + nc canais
    # (mais nm coeficientes de mascara na variante -seg). Saber esse numero
    # torna a leitura da orientacao do tensor DETERMINISTICA, em vez de
    # depender de comparar as dimensoes -- heuristica que falha quando o
    # numero de ancoras e pequeno.
    nc: int = 1
    nm: int = 0

    def to_dict(self) -> dict:
        return dict(self.__dict__)


class YoloSegAdapter:
    """Pipeline completo do YOLOv8-seg, sem o runtime de inferencia.

    O que esta implementado e testado aqui: letterbox e sua inversa,
    decodificacao das saidas (xywh -> xyxy, confianca por classe), limiar,
    NMS, recorte de mascara pelo prototipo e reamostragem para o ladrilho.

    O que falta: ``torch`` ou ``onnxruntime`` para executar os pesos. A
    ausencia e declarada em ``info()`` e propagada para a API, de modo que a
    interface nunca apresenta o YOLO como ativo quando ele nao esta.
    """

    def __init__(self, params: YoloParams | None = None, session=None) -> None:
        self.p = params or YoloParams()
        self.session = session
        self._runtime, self._reason = _probe_runtime()

    # ------------------------------------------------------------- info
    def info(self) -> DetectorInfo:
        # Disponivel = ha sessao de inferencia com os pesos carregados. So o runtime
        # (torch instalado como dependencia de outra parte do projeto) nao basta: sem
        # sessao, detect_tile devolve vazio e o YOLO "ativo" zeraria a MMGD do mapa.
        ok = self.session is not None
        if ok:
            reason = ""
        elif self._runtime:
            reason = ("Runtime %s presente, mas os pesos %s não estão carregados: "
                      "sem sessão de inferência o adaptador não detecta nada, então "
                      "o detector clássico segue ativo." % (self._runtime, self.p.weights))
        else:
            reason = self._reason
        return DetectorInfo(
            name="YOLOv8-seg (segmentação de instâncias) — %s" % self.p.weights,
            kind="yolo",
            available=ok,
            reason=reason,
            params=self.p.to_dict(),
            runtime=self._runtime or "indisponível",
        )

    # ------------------------------------------------------- pre-process
    def preprocess(self, rgb: np.ndarray) -> tuple[np.ndarray, tuple[float, float, float]]:
        """Letterbox para imgsz x imgsz, normalizado, em NCHW."""
        h, w = rgb.shape[:2]
        dst = self.p.imgsz
        scale, dx, dy = NMS.letterbox_params(w, h, dst)
        new_w, new_h = max(1, int(round(w * scale))), max(1, int(round(h * scale)))
        canvas = np.full((dst, dst, 3), 114, dtype="uint8")
        resized = _resize_nearest(rgb, new_w, new_h)
        oy, ox = int(round(dy)), int(round(dx))
        canvas[oy:oy + new_h, ox:ox + new_w] = resized
        x = canvas.astype("f4").transpose(2, 0, 1)[None] / 255.0
        return x, (scale, dx, dy)

    # ------------------------------------------------------ post-process
    def decode(self, raw: np.ndarray, src_w: int, src_h: int
               ) -> tuple[np.ndarray, np.ndarray]:
        """Decodifica a saida crua (1, 4+nc[+nm], N) em caixas e escores.

        Formato do YOLOv8: as quatro primeiras linhas sao xywh no espaco do
        letterbox; as seguintes, logits por classe.
        """
        arr = np.asarray(raw, dtype="f8")
        if arr.ndim == 3:
            arr = arr[0]
        if arr.ndim != 2:
            return np.zeros((0, 4)), np.zeros(0)
        # Orientacao determinada pelo numero de canais esperado, nao por
        # comparacao de dimensoes: (C, N) e o formato nativo do YOLOv8.
        expected_c = 4 + self.p.nc + self.p.nm
        if arr.shape[0] == expected_c:
            pred = arr.T                     # (N, C)
        elif arr.shape[1] == expected_c:
            pred = arr
        else:
            # Cabecalho desconhecido: assume o eixo menor como canais.
            pred = arr.T if arr.shape[0] <= arr.shape[1] else arr
        if pred.shape[1] < 5:
            return np.zeros((0, 4)), np.zeros(0)
        boxes_xywh = pred[:, :4]
        cls_scores = pred[:, 4:]
        scores = cls_scores[:, self.p.class_id] if cls_scores.shape[1] > self.p.class_id \
            else cls_scores.max(axis=1)
        keep = scores >= self.p.conf
        boxes = NMS.xywh_to_xyxy(boxes_xywh[keep])
        scores = scores[keep]
        if not len(boxes):
            return np.zeros((0, 4)), np.zeros(0)
        boxes = NMS.undo_letterbox(boxes, src_w, src_h, self.p.imgsz)
        idx = NMS.nms(boxes, scores, self.p.iou)[: self.p.max_det]
        return boxes[idx], scores[idx]

    @staticmethod
    def mask_from_prototypes(coeffs: np.ndarray, protos: np.ndarray,
                             box: tuple[float, float, float, float],
                             src_w: int, src_h: int) -> np.ndarray:
        """Mascara de instancia: sigmoide(coef @ protos), recortada pela caixa."""
        c = np.asarray(coeffs, dtype="f4").ravel()
        p = np.asarray(protos, dtype="f4")
        if p.ndim == 3:
            nm, mh, mw = p.shape
            flat = p.reshape(nm, mh * mw)
        else:  # pragma: no cover
            return np.zeros((src_h, src_w), dtype=bool)
        n = min(len(c), flat.shape[0])
        m = 1.0 / (1.0 + np.exp(-(c[:n] @ flat[:n])))
        m = m.reshape(mh, mw)
        m = _resize_nearest(m[..., None], src_w, src_h)[..., 0]
        out = np.zeros((src_h, src_w), dtype=bool)
        x0, y0, x1, y1 = [int(round(v)) for v in box]
        x0, y0 = max(0, x0), max(0, y0)
        x1, y1 = min(src_w, x1), min(src_h, y1)
        if x1 > x0 and y1 > y0:
            out[y0:y1, x0:x1] = m[y0:y1, x0:x1] > 0.5
        return out

    def detect_tile(self, rgb: np.ndarray) -> list[Detection]:
        """Executa a inferencia, se houver runtime. Sem runtime, devolve vazio."""
        if self.session is None:
            return []
        h, w = rgb.shape[:2]
        x, _ = self.preprocess(rgb)
        raw = self.session.run(x)            # contrato minimo do runtime
        boxes, scores = self.decode(raw, w, h)
        return [Detection(box=tuple(b), score=float(s),
                          area_px=float((b[2] - b[0]) * (b[3] - b[1])))
                for b, s in zip(boxes, scores)]


def _probe_runtime() -> tuple[str, str]:
    # No Windows com Python do Anaconda, `import torch` falha com OSError (WinError 1114) por
    # causa do runtime do Visual C++ antigo do Anaconda. O carregamento do runtime do sistema
    # mora num lugar so (src/utils/torch_windows.py); aqui so chamamos antes da sondagem.
    from src.utils.torch_windows import carregar_runtime_do_sistema

    carregar_runtime_do_sistema()
    for mod in ("torch", "onnxruntime"):
        try:
            __import__(mod)
            return mod, ""
        except (ImportError, OSError):  # OSError: DLL presente mas que nao inicializa
            continue
    return "", ("Runtime de inferência ausente: torch e onnxruntime não podem "
                "ser instalados neste ambiente (proxy corporativo bloqueia o "
                "PyPI). O pipeline de pré e pós-processamento está implementado "
                "e testado; falta apenas carregar os pesos.")


def _resize_nearest(img: np.ndarray, new_w: int, new_h: int) -> np.ndarray:
    """Reamostragem por vizinho mais proximo, sem dependencia externa."""
    a = np.asarray(img)
    h, w = a.shape[:2]
    yi = np.clip((np.arange(new_h) * (h / float(new_h))).astype("i8"), 0, h - 1)
    xi = np.clip((np.arange(new_w) * (w / float(new_w))).astype("i8"), 0, w - 1)
    return a[yi][:, xi]


# =================================================== varredura completa
@dataclass
class ScanResult:
    detections: list[Detection]
    tiles: list[Tile]
    detector: DetectorInfo
    raw_count: int
    kept_count: int
    geo: GeoTransform

    def total_area_m2(self) -> float:
        """Area calibrada, que e a usada no indicador de MMGD."""
        return float(sum(d.area_m2 or 0.0 for d in self.detections))

    def total_area_raw_m2(self) -> float:
        """Area bruta, sem calibracao, mantida para auditoria."""
        return float(sum(d.area_raw_m2 or 0.0 for d in self.detections))

    def total_kwp(self) -> float:
        return float(sum(d.kwp or 0.0 for d in self.detections))

    def to_dict(self, max_detections: int = 400) -> dict:
        return {
            "detector": self.detector.to_dict(),
            "tiles": len(self.tiles),
            "tile_grid": [t.to_dict() for t in self.tiles],
            "raw_count": self.raw_count,
            "kept_count": self.kept_count,
            "duplicates_removed": self.raw_count - self.kept_count,
            "total_area_m2": round(self.total_area_m2(), 1),
            "total_area_raw_m2": round(self.total_area_raw_m2(), 1),
            "area_calibration": AREA_CALIBRATION,
            "area_calibration_source": AREA_CALIBRATION_SOURCE,
            "watt_per_m2": WATT_PER_M2,
            "total_kwp": round(self.total_kwp(), 2),
            "geo": self.geo.to_dict(),
            "detections": [d.to_dict() for d in self.detections[:max_detections]],
        }


def scan_scene(rgb: np.ndarray, geo: GeoTransform, detector: Detector, *,
               tile: int = DEFAULT_TILE_PX, overlap: int = DEFAULT_OVERLAP_PX,
               dedupe_iou: float = 0.30) -> ScanResult:
    """Varre a imagem por ladrilhos, deduplicando na costura e georreferenciando.

    E o mesmo caminho para os dois backends: o que muda e apenas quem responde
    `detect_tile`.
    """
    h, w = rgb.shape[:2]
    grid = tile_grid(w, h, tile, overlap)
    all_det: list[Detection] = []
    for t in grid:
        patch = rgb[t.y0:t.y1, t.x0:t.x1]
        for d in detector.detect_tile(patch):
            x0, y0, x1, y1 = d.box
            all_det.append(Detection(
                box=(x0 + t.x0, y0 + t.y0, x1 + t.x0, y1 + t.y0),
                score=d.score, area_px=d.area_px, tile_index=t.index,
                rectangularity=d.rectangularity, blue_index=d.blue_index,
                edge_density=d.edge_density,
            ))

    raw = len(all_det)
    if all_det:
        boxes = np.array([d.box for d in all_det], dtype="f8")
        scores = np.array([d.score for d in all_det], dtype="f8")
        keep = NMS.soft_dedupe(boxes, scores, iou_threshold=dedupe_iou)
        all_det = [all_det[i] for i in keep]

    for d in all_det:
        cx = (d.box[0] + d.box[2]) / 2.0
        cy = (d.box[1] + d.box[3]) / 2.0
        d.lat, d.lon = geo.to_latlon(cx, cy)
        # A area do painel e a area conexa detectada, nao a da caixa: o
        # retangulo envolvente superestima paineis levemente rotacionados.
        d.area_raw_m2 = float(d.area_px * geo.pixel_area_m2())
        d.area_m2 = d.area_raw_m2 * AREA_CALIBRATION
        d.kwp = area_to_kwp(d.area_m2)

    all_det.sort(key=lambda d: -d.score)
    return ScanResult(all_det, grid, detector.info(), raw, len(all_det), geo)


def build_detector(prefer: str = "auto") -> Detector:
    """Escolhe o backend. `prefer`: "auto" | "classico" | "yolo"."""
    if prefer == "yolo":
        return YoloSegAdapter()
    if prefer == "classico":
        return ClassicalPanelDetector()
    y = YoloSegAdapter()
    return y if y.info().available else ClassicalPanelDetector()


def backends_status() -> list[dict]:
    """Estado dos dois backends, para a interface mostrar sem enfeite."""
    return [ClassicalPanelDetector().info().to_dict(),
            YoloSegAdapter().info().to_dict()]
