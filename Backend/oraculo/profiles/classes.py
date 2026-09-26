# -*- coding: utf-8 -*-
"""Classes de consumo: perfis canonicos e decomposicao da carga observada.

Responde a primeira pergunta do desafio Radix: **qual e o perfil predominante
de consumo da area atendida por cada subestacao**, com indicador de percentual.

Duas fontes de sinal, combinadas:

1. **Forma da curva de carga** (dado real do ONS). Cada classe tem assinatura
   propria: a residencial tem ponta noturna acentuada; a comercial, plato em
   horario de expediente e queda no fim de semana; a industrial e quase plana e
   pouco sensivel ao dia da semana; a rural/irrigacao bombeia de madrugada.
   A composicao e obtida por minimos quadrados NAO NEGATIVOS sobre os perfis
   canonicos, com soma unitaria:

       carga_norm(t)  ~  soma_c  w_c * perfil_c(t),    w_c >= 0,  soma w_c = 1

2. **Morfologia construida** (imagem). Muitos telhados pequenos e densos
   indicam residencial; poucos galpoes muito grandes indicam industrial. Entra
   como evidencia independente, e a divergencia entre as duas fontes e
   reportada em vez de escondida.

Os perfis canonicos sao ESTILIZADOS, construidos a partir das caracteristicas
documentadas de cada classe, nao medidos em campo. E premissa, fica versionada
e visivel. Ver 08-limitacoes.md.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

try:
    from scipy.optimize import nnls
except ImportError:  # pragma: no cover
    nnls = None  # type: ignore

from ..core.calendar_br import typeday_array
from ..core.timeutils import hour_of_day

CLASSES = ("residencial", "comercial", "industrial", "rural")

CLASS_LABELS = {
    "residencial": "Residencial",
    "comercial": "Comercial / serviços",
    "industrial": "Industrial",
    "rural": "Rural / irrigação",
}

CLASS_NOTES = {
    "residencial": "Ponta noturna acentuada, vale de madrugada, pouca "
                   "diferença entre dias úteis e fim de semana.",
    "comercial": "Platô em horário de expediente, queda acentuada no fim de "
                 "semana e à noite.",
    "industrial": "Perfil quase plano nas 24 horas, baixa sensibilidade ao dia "
                  "da semana; fator de carga alto.",
    "rural": "Bombeamento noturno e de madrugada, sazonalidade de safra.",
}


# ------------------------------------------------------ perfis canonicos
def _norm(v: np.ndarray) -> np.ndarray:
    v = np.asarray(v, dtype="f8")
    s = v.sum()
    return v / s if s > 0 else v


# Perfis horarios estilizados (24 valores), normalizados para somar 1.
CANONICAL: dict[str, np.ndarray] = {
    "residencial": _norm(np.array([
        0.55, 0.48, 0.44, 0.42, 0.42, 0.46, 0.58, 0.70, 0.72, 0.70,
        0.68, 0.70, 0.74, 0.72, 0.70, 0.72, 0.80, 0.96, 1.30, 1.45,
        1.34, 1.12, 0.88, 0.68])),
    "comercial": _norm(np.array([
        0.30, 0.28, 0.27, 0.27, 0.28, 0.32, 0.46, 0.72, 1.05, 1.24,
        1.32, 1.34, 1.26, 1.30, 1.34, 1.32, 1.24, 1.08, 0.86, 0.64,
        0.50, 0.42, 0.36, 0.32])),
    "industrial": _norm(np.array([
        0.92, 0.90, 0.89, 0.89, 0.90, 0.93, 0.98, 1.04, 1.08, 1.10,
        1.10, 1.08, 1.05, 1.08, 1.10, 1.10, 1.08, 1.04, 1.00, 0.98,
        0.96, 0.95, 0.94, 0.93])),
    "rural": _norm(np.array([
        1.28, 1.34, 1.36, 1.32, 1.22, 1.06, 0.88, 0.74, 0.64, 0.58,
        0.56, 0.56, 0.58, 0.58, 0.58, 0.60, 0.66, 0.78, 0.94, 1.06,
        1.14, 1.22, 1.26, 1.28])),
}

# Razao entre a carga media de fim de semana e de dia util, por classe.
# Segunda assinatura, independente da forma horaria: e o que separa comercial
# de industrial quando as duas tem plato diurno.
WEEKEND_RATIO: dict[str, float] = {
    "residencial": 0.98,
    "comercial": 0.62,
    "industrial": 0.90,
    "rural": 1.00,
}


# ------------------------------------------------------ decomposicao
@dataclass
class ClassMix:
    weights: dict[str, float]
    dominant: str
    residual: float                    # norma do residuo do ajuste
    r2: float
    observed: np.ndarray = field(default_factory=lambda: np.zeros(24))
    fitted: np.ndarray = field(default_factory=lambda: np.zeros(24))
    weekend_ratio: float = float("nan")
    samples: int = 0
    method: str = "nnls_perfis_canonicos"

    @property
    def is_mixed(self) -> bool:
        """Misto quando nenhuma classe passa de 50%."""
        return max(self.weights.values()) < 0.50 if self.weights else True

    def label(self) -> str:
        if self.is_mixed:
            top = sorted(self.weights.items(), key=lambda kv: -kv[1])[:2]
            return "Misto (%s)" % " + ".join(CLASS_LABELS[k] for k, _ in top)
        return CLASS_LABELS[self.dominant]

    def to_dict(self) -> dict:
        return {
            "weights": {k: round(v, 4) for k, v in self.weights.items()},
            "dominant": self.dominant,
            "label": self.label(),
            "is_mixed": self.is_mixed,
            "confidence": round(max(self.weights.values()), 4) if self.weights else 0.0,
            "r2": round(self.r2, 4),
            "residual": round(self.residual, 5),
            "weekend_ratio": None if not np.isfinite(self.weekend_ratio)
                             else round(self.weekend_ratio, 3),
            "samples": int(self.samples),
            "method": self.method,
            "observed": [round(float(v), 5) for v in self.observed],
            "fitted": [round(float(v), 5) for v in self.fitted],
            "hours": list(range(24)),
        }


def hourly_shape(index: np.ndarray, load: np.ndarray,
                 typeday: str = "util") -> tuple[np.ndarray, int]:
    """Perfil horario medio normalizado, para um dia-tipo."""
    index = np.asarray(index, dtype="datetime64[s]")
    load = np.asarray(load, dtype="f8")
    hod = hour_of_day(index)
    kinds = typeday_array(index)
    sel_kind = kinds == typeday if typeday else np.ones(len(index), dtype=bool)
    prof = np.full(24, np.nan)
    n = 0
    for h in range(24):
        v = load[sel_kind & (hod == h)]
        v = v[np.isfinite(v)]
        if len(v):
            prof[h] = float(np.mean(v))
            n += len(v)
    if not np.isfinite(prof).all():
        good = np.isfinite(prof)
        if not good.any():
            return np.zeros(24), 0
        prof = np.interp(np.arange(24), np.flatnonzero(good), prof[good])
    return _norm(prof), n


def weekend_weekday_ratio(index: np.ndarray, load: np.ndarray) -> float:
    """Razao entre a carga media de domingo/feriado e de dia util."""
    index = np.asarray(index, dtype="datetime64[s]")
    load = np.asarray(load, dtype="f8")
    kinds = typeday_array(index)
    wd = load[(kinds == "util") & np.isfinite(load)]
    we = load[(kinds == "domingo_feriado") & np.isfinite(load)]
    if not len(wd) or not len(we) or np.mean(wd) <= 0:
        return float("nan")
    return float(np.mean(we) / np.mean(wd))


def decompose(index: np.ndarray, load: np.ndarray, *,
              use_weekend: bool = True) -> ClassMix:
    """Decompoe a forma da carga observada nos perfis canonicos por NNLS.

    A restricao de soma unitaria e imposta por uma linha extra no sistema, com
    peso alto: e o truque padrao para transformar NNLS em NNLS com simplexo,
    sem precisar de um solucionador de programacao quadratica.
    """
    shape, n = hourly_shape(index, load, "util")
    ratio = weekend_weekday_ratio(index, load) if use_weekend else float("nan")

    cols = [CANONICAL[c] for c in CLASSES]
    A = np.column_stack(cols)                      # (24, 4)
    b = shape.copy()

    rows_A = [A]
    rows_b = [b]
    # soma unitaria
    W_SUM = 6.0
    rows_A.append(np.full((1, len(CLASSES)), W_SUM))
    rows_b.append(np.array([W_SUM]))
    # assinatura de fim de semana como equacao adicional
    if use_weekend and np.isfinite(ratio):
        W_WE = 2.2
        rows_A.append(np.array([[WEEKEND_RATIO[c] * W_WE for c in CLASSES]]))
        rows_b.append(np.array([ratio * W_WE]))

    Aa = np.vstack(rows_A)
    bb = np.concatenate(rows_b)

    if nnls is not None:
        w, res = nnls(Aa, bb)
    else:  # pragma: no cover
        w, *_ = np.linalg.lstsq(Aa, bb, rcond=None)
        w = np.clip(w, 0, None)
        res = float(np.linalg.norm(Aa @ w - bb))

    total = float(w.sum())
    if total <= 0:
        weights = {c: 1.0 / len(CLASSES) for c in CLASSES}
        w = np.array([weights[c] for c in CLASSES])
    else:
        w = w / total
        weights = {c: float(x) for c, x in zip(CLASSES, w)}

    fitted = A @ w
    ss_res = float(np.sum((shape - fitted) ** 2))
    ss_tot = float(np.sum((shape - shape.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    dominant = max(weights.items(), key=lambda kv: kv[1])[0]
    return ClassMix(weights=weights, dominant=dominant,
                    residual=float(np.sqrt(ss_res)), r2=r2,
                    observed=shape, fitted=fitted, weekend_ratio=ratio,
                    samples=n)


# ------------------------------------------------------ morfologia
@dataclass
class MorphologyMix:
    weights: dict[str, float]
    dominant: str
    counts: dict[str, int]
    area_m2: dict[str, float]
    mean_footprint_m2: float
    density_per_km2: float
    method: str = "morfologia_construida"

    def to_dict(self) -> dict:
        return {
            "weights": {k: round(v, 4) for k, v in self.weights.items()},
            "dominant": self.dominant,
            "label": CLASS_LABELS.get(self.dominant, self.dominant),
            "counts": self.counts,
            "area_m2": {k: round(v, 1) for k, v in self.area_m2.items()},
            "mean_footprint_m2": round(self.mean_footprint_m2, 1),
            "density_per_km2": round(self.density_per_km2, 1),
            "method": self.method,
        }


# Limiares de area de telhado, em metros quadrados. Sao premissa de negocio.
FOOTPRINT_RESIDENTIAL_MAX = 220.0
FOOTPRINT_COMMERCIAL_MAX = 1200.0


def classify_footprint(area_m2: float) -> str:
    if area_m2 <= FOOTPRINT_RESIDENTIAL_MAX:
        return "residencial"
    if area_m2 <= FOOTPRINT_COMMERCIAL_MAX:
        return "comercial"
    return "industrial"


def from_morphology(roof_areas_m2: np.ndarray, extent_km2: float
                    ) -> MorphologyMix:
    """Composicao pela morfologia: distribuicao de area dos telhados.

    A ponderacao e por AREA, nao por contagem: um galpao industrial de
    5.000 m2 pesa muito mais na carga do que uma casa de 120 m2, ainda que
    conte como uma unica edificacao.
    """
    a = np.asarray(roof_areas_m2, dtype="f8")
    a = a[np.isfinite(a) & (a > 0)]
    counts = {c: 0 for c in CLASSES}
    area = {c: 0.0 for c in CLASSES}
    for v in a:
        c = classify_footprint(float(v))
        counts[c] += 1
        area[c] += float(v)
    total_area = sum(area.values())
    if total_area <= 0:
        weights = {c: 0.0 for c in CLASSES}
        weights["residencial"] = 1.0
        dominant = "residencial"
    else:
        weights = {c: area[c] / total_area for c in CLASSES}
        dominant = max(weights.items(), key=lambda kv: kv[1])[0]
    return MorphologyMix(
        weights=weights, dominant=dominant, counts=counts, area_m2=area,
        mean_footprint_m2=float(a.mean()) if a.size else 0.0,
        density_per_km2=float(len(a) / extent_km2) if extent_km2 > 0 else 0.0,
    )


# ------------------------------------------------------ combinacao
def combine(load_mix: ClassMix, morph: MorphologyMix,
            w_load: float = 0.6) -> dict:
    """Funde as duas evidencias e REPORTA a divergencia.

    Concordancia entre curva de carga e morfologia e o melhor sinal de que a
    classificacao esta certa. Divergencia nao e erro a esconder: e informacao
    sobre onde vale aprofundar o estudo, que e exatamente o que o desafio pede.
    """
    w_morph = 1.0 - w_load
    fused = {c: w_load * load_mix.weights.get(c, 0.0) +
                w_morph * morph.weights.get(c, 0.0) for c in CLASSES}
    total = sum(fused.values()) or 1.0
    fused = {c: v / total for c, v in fused.items()}
    dominant = max(fused.items(), key=lambda kv: kv[1])[0]
    agree = load_mix.dominant == morph.dominant
    # distancia L1 entre as duas composicoes, em [0, 2] -> normalizada
    divergence = sum(abs(load_mix.weights.get(c, 0.0) - morph.weights.get(c, 0.0))
                     for c in CLASSES) / 2.0
    confidence = max(fused.values()) * (1.0 - 0.35 * divergence)
    is_mixed = max(fused.values()) < 0.50
    if is_mixed:
        top = sorted(fused.items(), key=lambda kv: -kv[1])[:2]
        label = "Misto (%s)" % " + ".join(CLASS_LABELS[k] for k, _ in top)
    else:
        label = CLASS_LABELS[dominant]
    return {
        "weights": {c: round(v, 4) for c, v in fused.items()},
        "dominant": dominant,
        "label": label,
        "is_mixed": is_mixed,
        "confidence": round(float(np.clip(confidence, 0.0, 1.0)), 4),
        "sources_agree": bool(agree),
        "divergence": round(float(divergence), 4),
        "weight_load": w_load,
        "weight_morphology": round(w_morph, 3),
        "from_load": load_mix.to_dict(),
        "from_morphology": morph.to_dict(),
    }


def canonical_payload() -> dict:
    """Perfis canonicos para a interface desenhar."""
    return {
        "hours": list(range(24)),
        "classes": [
            {"key": c, "label": CLASS_LABELS[c], "note": CLASS_NOTES[c],
             "profile": [round(float(v), 5) for v in CANONICAL[c]],
             "weekend_ratio": WEEKEND_RATIO[c]}
            for c in CLASSES
        ],
        "note": ("Perfis estilizados a partir das características documentadas "
                 "de cada classe. São premissa versionada, não medição de campo."),
        "footprint_thresholds_m2": {
            "residencial_max": FOOTPRINT_RESIDENTIAL_MAX,
            "comercial_max": FOOTPRINT_COMMERCIAL_MAX,
        },
    }
