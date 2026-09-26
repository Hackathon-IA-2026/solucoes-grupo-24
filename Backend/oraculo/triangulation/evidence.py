# -*- coding: utf-8 -*-
"""Triangulacao de evidencias e fator de correcao de capacidade.

Tres camadas independentes, com cadencias diferentes. O valor nao esta em
nenhuma camada isolada, e sim no cruzamento: sem o desempate diario, defasagem
administrativa e instalacao irregular seriam tratadas como a mesma coisa, e o
fator de correcao de capacidade -- que alimenta o estimador de MMGD -- sairia
enviesado.

Matriz de desempate::

                       | Consta na ANEEL              | Nao consta
    -------------------+------------------------------+--------------------------
    Detectado          | confirmada; se ausente na    | nao_homologada
    no satelite        | BDGD -> lag_de_sistema       | (excecao escalada)
    -------------------+------------------------------+--------------------------
    Nao detectado      | cadastro_sem_evidencia       | sem_evidencia
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..config import RANDOM_SEED

# Classificacoes possiveis de uma unidade
CONFIRMADA = "confirmada"
LAG_DE_SISTEMA = "lag_de_sistema"
NAO_HOMOLOGADA = "nao_homologada"
CADASTRO_SEM_EVIDENCIA = "cadastro_sem_evidencia"
SEM_EVIDENCIA = "sem_evidencia"

CLASSES = (CONFIRMADA, LAG_DE_SISTEMA, NAO_HOMOLOGADA,
           CADASTRO_SEM_EVIDENCIA, SEM_EVIDENCIA)

CLASS_LABELS = {
    CONFIRMADA: "MMGD confirmada",
    LAG_DE_SISTEMA: "Defasagem de sistema",
    NAO_HOMOLOGADA: "Não homologada",
    CADASTRO_SEM_EVIDENCIA: "Cadastro sem evidência",
    SEM_EVIDENCIA: "Sem evidência",
}

CLASS_NOTES = {
    CONFIRMADA: "Três camadas concordam. Entra no fator de correção.",
    LAG_DE_SISTEMA: "Homologada na ANEEL e ausente na BDGD: defasagem "
                    "administrativa, MMGD legítima. Entra no fator de correção.",
    NAO_HOMOLOGADA: "Presente e gerando sem registro de homologação. Escalada "
                    "como exceção; NÃO entra no fator de correção.",
    CADASTRO_SEM_EVIDENCIA: "Registro sem evidência física: imagem defasada ou "
                            "obra não concluída. Revisar captura.",
    SEM_EVIDENCIA: "Nenhuma evidência em nenhuma camada. Nada a corrigir.",
}

LAYERS = [
    {
        "layer": 1,
        "name": "Realidade física",
        "source": "Imagens de satélite + visão computacional",
        "question": "O ativo existe fisicamente e onde está?",
        "cadence": "mensal / trimestral",
        "limitation": "A data de captura pode ter meses: é evidência periódica, "
                      "não de tempo real.",
    },
    {
        "layer": 2,
        "name": "Topologia",
        "source": "BDGD — Base de Dados Geográfica da Distribuidora (ANEEL)",
        "question": "A que alimentador e transformador a unidade está conectada?",
        "cadence": "anual",
        "limitation": "Periodicidade anual e nomenclaturas divergentes entre "
                      "distribuidoras.",
    },
    {
        "layer": 3,
        "name": "Cadastro",
        "source": "Empreendimentos de Geração Distribuída (ANEEL)",
        "question": "O empreendimento foi homologado, e quando?",
        "cadence": "diária",
        "limitation": "Atualização diária, porém não localiza a unidade na malha.",
    },
]


# --------------------------------------------------------------- desempate
def classify(detected: bool, in_bdgd: bool, in_aneel: bool) -> str:
    """Aplica a matriz de desempate a uma unidade."""
    if detected and in_aneel:
        return CONFIRMADA if in_bdgd else LAG_DE_SISTEMA
    if detected and not in_aneel:
        return NAO_HOMOLOGADA
    if not detected and in_aneel:
        return CADASTRO_SEM_EVIDENCIA
    return SEM_EVIDENCIA


def counts_in_correction(cls: str) -> bool:
    """Somente evidencia legitima entra no fator de correcao."""
    return cls in (CONFIRMADA, LAG_DE_SISTEMA)


# --------------------------------------------------------------- unidades
@dataclass
class Unit:
    unit_id: str
    area: str
    capacity_kwp: float
    detected: bool
    in_bdgd: bool
    in_aneel: bool
    homologated_at: str = ""

    @property
    def classification(self) -> str:
        return classify(self.detected, self.in_bdgd, self.in_aneel)

    def to_dict(self) -> dict:
        c = self.classification
        return {
            "unit_id": self.unit_id,
            "area": self.area,
            "capacity_kwp": round(self.capacity_kwp, 2),
            "detected": self.detected,
            "in_bdgd": self.in_bdgd,
            "in_aneel": self.in_aneel,
            "homologated_at": self.homologated_at,
            "classification": c,
            "label": CLASS_LABELS[c],
            "note": CLASS_NOTES[c],
            "counts_in_correction": counts_in_correction(c),
        }


@dataclass
class AreaResult:
    area: str
    units_total: int
    matrix: dict[str, int] = field(default_factory=dict)
    capacity_declared_mw: float = 0.0
    capacity_corrected_mw: float = 0.0
    capacity_unhomologated_mw: float = 0.0
    coverage: float = 0.0

    @property
    def correction_factor(self) -> float:
        if self.capacity_declared_mw <= 0:
            return 1.0
        return round(self.capacity_corrected_mw / self.capacity_declared_mw, 4)

    def to_dict(self) -> dict:
        return {
            "area": self.area,
            "units_total": self.units_total,
            "matrix": {k: int(self.matrix.get(k, 0)) for k in CLASSES},
            "capacity_declared_mw": round(self.capacity_declared_mw, 2),
            "capacity_corrected_mw": round(self.capacity_corrected_mw, 2),
            "capacity_unhomologated_mw": round(self.capacity_unhomologated_mw, 2),
            "correction_factor": self.correction_factor,
            "coverage": round(self.coverage, 4),
        }


def aggregate(units: list[Unit]) -> list[dict]:
    """Agrega unidades por area, produzindo o fator de correcao."""
    by_area: dict[str, list[Unit]] = {}
    for u in units:
        by_area.setdefault(u.area, []).append(u)

    out: list[AreaResult] = []
    for area, group in sorted(by_area.items()):
        res = AreaResult(area=area, units_total=len(group))
        declared = 0.0
        corrected = 0.0
        unhom = 0.0
        with_all = 0
        for u in group:
            c = u.classification
            res.matrix[c] = res.matrix.get(c, 0) + 1
            mw = u.capacity_kwp / 1000.0
            # "Declarada" e o que a BDGD conhece hoje.
            if u.in_bdgd:
                declared += mw
            if counts_in_correction(c):
                corrected += mw
            if c == NAO_HOMOLOGADA:
                unhom += mw
            if u.detected is not None and u.in_bdgd is not None and u.in_aneel is not None:
                with_all += 1
        res.capacity_declared_mw = declared
        res.capacity_corrected_mw = corrected
        res.capacity_unhomologated_mw = unhom
        res.coverage = with_all / len(group) if group else 0.0
        out.append(res)
    return [r.to_dict() for r in out]


# --------------------------------------------------------------- demo
def demo_units(areas: list[str], per_area: int = 220,
               seed: int = RANDOM_SEED) -> list[Unit]:
    """Conjunto demonstrativo com os campos e as proporcoes reais do problema.

    As proporcoes refletem o padrao descrito pelo Operador: a maior parte das
    unidades e consistente, uma fracao relevante esta em defasagem
    administrativa e uma fracao pequena aparece sem homologacao.
    """
    rng = np.random.default_rng(seed)
    units: list[Unit] = []
    for area in areas:
        for i in range(per_area):
            r = rng.random()
            if r < 0.62:
                det, bdgd, aneel = True, True, True
            elif r < 0.80:
                det, bdgd, aneel = True, False, True     # lag de sistema
            elif r < 0.86:
                det, bdgd, aneel = True, False, False    # nao homologada
            elif r < 0.94:
                det, bdgd, aneel = False, True, True     # cadastro sem evidencia
            else:
                det, bdgd, aneel = False, False, False
            cap = float(np.clip(rng.lognormal(mean=3.1, sigma=0.8), 2.0, 4000.0))
            units.append(Unit(
                unit_id="%s-%05d" % (area, i + 1),
                area=area,
                capacity_kwp=cap,
                detected=det,
                in_bdgd=bdgd,
                in_aneel=aneel,
                homologated_at="2025-%02d-%02d" % (
                    int(rng.integers(1, 13)), int(rng.integers(1, 28))
                ) if aneel else "",
            ))
    return units


def matrix_cells() -> list[dict]:
    """Descricao das quatro celulas, para a interface."""
    return [
        {"row": "Detectado no satélite", "col": "Consta na ANEEL",
         "classification": CONFIRMADA, "label": CLASS_LABELS[CONFIRMADA],
         "note": CLASS_NOTES[CONFIRMADA] + " Se ausente na BDGD, é classificada "
                 "como defasagem de sistema."},
        {"row": "Detectado no satélite", "col": "Não consta",
         "classification": NAO_HOMOLOGADA, "label": CLASS_LABELS[NAO_HOMOLOGADA],
         "note": CLASS_NOTES[NAO_HOMOLOGADA]},
        {"row": "Não detectado", "col": "Consta na ANEEL",
         "classification": CADASTRO_SEM_EVIDENCIA,
         "label": CLASS_LABELS[CADASTRO_SEM_EVIDENCIA],
         "note": CLASS_NOTES[CADASTRO_SEM_EVIDENCIA]},
        {"row": "Não detectado", "col": "Não consta",
         "classification": SEM_EVIDENCIA, "label": CLASS_LABELS[SEM_EVIDENCIA],
         "note": CLASS_NOTES[SEM_EVIDENCIA]},
    ]
