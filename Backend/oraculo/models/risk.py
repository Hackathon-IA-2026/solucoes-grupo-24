# -*- coding: utf-8 -*-
"""Risco de curtailment por razao energetica.

Rotulo extraido dos registros reais de constrained-off: para area `a` e hora `t`,

    corte_mw(a,t)  = soma de max(0, val_geracaoreferencia - val_geracao)
    restricao(a,t) = corte_mw(a,t) > limiar(a)

LIMITE CONCEITUAL DECLARADO: o rotulo reflete a decisao operativa observada,
nao o potencial fisico de geracao. O modelo aprende a decisao, nao um
contrafactual.

Modelo: regressao logistica regularizada ajustada por IRLS em numpy, com
calibracao por binning e montante esperado E[corte] = P(restricao) *
E[corte | restricao].
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..config import (L2_PENALTY, RISK_LABEL_THRESHOLD_FRACTION,
                      RISK_SEVERITY_WEIGHTS, criticality_of, patamar_of_hour)
from ..core.frame import Frame
from ..core.timeutils import hour_of_day, reindex_hourly
from ..ons.catalog import RAZOES

REASONS = ("ENE", "CNF", "REL", "PAR")


# ----------------------------------------------------------- rotulagem
@dataclass
class CurtailmentLabels:
    index: np.ndarray            # datetime64[s], grade horaria
    area: str
    corte_mw: np.ndarray         # montante restringido, MWmed
    disponibilidade_mw: np.ndarray
    ocorreu: np.ndarray          # bool
    by_reason: dict[str, np.ndarray] = field(default_factory=dict)
    threshold_mw: float = 0.0

    def reason_shares(self) -> dict[str, float]:
        tot = float(np.nansum(self.corte_mw)) or 1.0
        return {
            r: round(float(np.nansum(v)) / tot, 4)
            for r, v in self.by_reason.items()
        }

    def summary(self) -> dict:
        occ = float(np.mean(self.ocorreu)) if len(self.ocorreu) else 0.0
        return {
            "area": self.area,
            "hours": int(len(self.index)),
            "occurrence_rate": round(occ, 4),
            "total_cut_gwh": round(float(np.nansum(self.corte_mw)) / 1000.0, 2),
            "peak_cut_mw": round(float(np.nanmax(self.corte_mw)), 1) if len(self.corte_mw) else 0.0,
            "threshold_mw": round(self.threshold_mw, 1),
            "reason_shares": self.reason_shares(),
        }


def build_labels(coff: Frame, area_field: str, area: str) -> CurtailmentLabels:
    """Agrega o constrained-off semi-horario para a grade horaria da area."""
    sel = coff.eq(area_field, area) if area_field in coff else coff
    if len(sel) == 0:
        empty = np.array([], dtype="datetime64[s]")
        return CurtailmentLabels(empty, area, np.array([]), np.array([]),
                                 np.array([], dtype=bool))

    ref = sel["val_geracaoreferencia"]
    ger = sel["val_geracao"]
    cut = np.where(np.isfinite(ref) & np.isfinite(ger), np.maximum(ref - ger, 0.0), 0.0)
    disp = np.where(np.isfinite(sel["val_disponibilidade"]),
                    sel["val_disponibilidade"], 0.0)

    ts = sel["din_instante"].astype("datetime64[s]")
    hour_bucket = ts.astype("datetime64[h]").astype("datetime64[s]")

    grid = np.unique(hour_bucket)
    lut = {int(t.astype("i8")): i for i, t in enumerate(grid)}
    pos = np.array([lut[int(t.astype("i8"))] for t in hour_bucket], dtype="i8")

    corte = np.zeros(len(grid))
    dispo = np.zeros(len(grid))
    # Media dentro da hora (dois registros semi-horarios por hora).
    counts = np.zeros(len(grid))
    np.add.at(corte, pos, cut)
    np.add.at(dispo, pos, disp)
    np.add.at(counts, pos, 1.0)
    counts[counts == 0] = 1.0
    # Passo semi-horario: soma de usinas, media temporal dentro da hora.
    n_plants = max(1, len(np.unique(sel["nom_usina"]))) if "nom_usina" in sel else 1
    corte = corte / np.maximum(counts / n_plants, 1.0)
    dispo = dispo / np.maximum(counts / n_plants, 1.0)

    by_reason: dict[str, np.ndarray] = {}
    if "cod_razaorestricao" in sel:
        reasons = sel["cod_razaorestricao"]
        for r in REASONS:
            acc = np.zeros(len(grid))
            m = reasons == r
            if m.any():
                np.add.at(acc, pos[m], cut[m])
            by_reason[r] = acc / np.maximum(counts / n_plants, 1.0)

    cap_proxy = float(np.nanpercentile(dispo, 95)) if len(dispo) else 0.0
    thr = max(cap_proxy * RISK_LABEL_THRESHOLD_FRACTION, 1.0)

    return CurtailmentLabels(
        index=grid,
        area=area,
        corte_mw=corte,
        disponibilidade_mw=dispo,
        ocorreu=corte > thr,
        by_reason=by_reason,
        threshold_mw=thr,
    )


# ----------------------------------------------------------- logistica
@dataclass
class LogisticModel:
    coef: np.ndarray | None = None
    l2: float = L2_PENALTY
    calib: list[tuple[float, float]] = field(default_factory=list)
    info: dict = field(default_factory=dict)

    def fit(self, X: np.ndarray, y: np.ndarray, iters: int = 60) -> "LogisticModel":
        X = np.asarray(X, dtype="f8")
        y = np.asarray(y, dtype="f8")
        ok = np.isfinite(y) & np.all(np.isfinite(X), axis=1)
        X, y = X[ok], y[ok]
        n, p = X.shape
        if n < p + 10 or y.sum() < 5 or (n - y.sum()) < 5:
            raise ValueError("amostra insuficiente ou sem variacao no rotulo")
        beta = np.zeros(p)
        lam = self.l2 * n
        for _ in range(iters):
            eta = np.clip(X @ beta, -30, 30)
            mu = 1.0 / (1.0 + np.exp(-eta))
            w = np.clip(mu * (1 - mu), 1e-6, None)
            z = eta + (y - mu) / w
            WX = X * w[:, None]
            H = X.T @ WX + lam * np.eye(p)
            g = X.T @ (w * z)
            new = np.linalg.solve(H, g)
            if np.max(np.abs(new - beta)) < 1e-8:
                beta = new
                break
            beta = new
        self.coef = beta
        self.info = {"rows": int(n), "features": int(p),
                     "positive_rate": round(float(y.mean()), 4)}
        return self

    def raw_probability(self, X: np.ndarray) -> np.ndarray:
        if self.coef is None:
            return np.full(len(X), np.nan)
        eta = np.clip(np.asarray(X, dtype="f8") @ self.coef, -30, 30)
        return 1.0 / (1.0 + np.exp(-eta))

    def calibrate(self, X: np.ndarray, y: np.ndarray, bins: int = 10) -> "LogisticModel":
        """Calibracao por binning monotonico sobre o conjunto de validacao."""
        p = self.raw_probability(X)
        y = np.asarray(y, dtype="f8")
        ok = np.isfinite(p) & np.isfinite(y)
        p, y = p[ok], y[ok]
        if len(p) < bins * 4:
            self.calib = []
            return self
        edges = np.quantile(p, np.linspace(0, 1, bins + 1))
        pairs: list[tuple[float, float]] = []
        for i in range(bins):
            lo, hi = edges[i], edges[i + 1]
            sel = (p >= lo) & (p <= hi) if i == bins - 1 else (p >= lo) & (p < hi)
            if sel.sum() >= 3:
                pairs.append((float(np.mean(p[sel])), float(np.mean(y[sel]))))
        # impoe monotonicidade (pool adjacent violators simplificado)
        for i in range(1, len(pairs)):
            if pairs[i][1] < pairs[i - 1][1]:
                avg = (pairs[i][1] + pairs[i - 1][1]) / 2.0
                pairs[i - 1] = (pairs[i - 1][0], avg)
                pairs[i] = (pairs[i][0], avg)
        self.calib = pairs
        return self

    def probability(self, X: np.ndarray) -> np.ndarray:
        p = self.raw_probability(X)
        if not self.calib:
            return p
        xs = np.array([a for a, _ in self.calib])
        ys = np.array([b for _, b in self.calib])
        return np.clip(np.interp(p, xs, ys), 0.0, 1.0)


def occurrence_memory(occurred: np.ndarray, *, min_lag: int = 24,
                      window: int = 7 * 24) -> np.ndarray:
    """Fracao de horas com restricao na janela recente, defasada.

    Somente informacao que o operador realmente possui ao prever: a janela
    termina `min_lag` horas antes do instante alvo. Defasagem menor que o
    horizonte seria vazamento.
    """
    y = np.asarray(occurred, dtype="f8")
    n = len(y)
    out = np.zeros(n)
    csum = np.concatenate(([0.0], np.cumsum(np.nan_to_num(y))))
    for i in range(n):
        hi = max(0, i - min_lag + 1)
        lo = max(0, hi - window)
        k = hi - lo
        out[i] = (csum[hi] - csum[lo]) / k if k > 0 else 0.0
    return out


# ----------------------------------------------------------- motivo
def reason_weights(labels: CurtailmentLabels, hours: np.ndarray,
                   energy_signal: float, electric_signal: float) -> dict[str, float]:
    """Decomposicao do motivo provavel, normalizada para somar 1.

    Combina tres evidencias: frequencia historica por razao na area, sinal
    energetico corrente (excedente projetado) e sinal eletrico corrente
    (intercambio proximo do limite).
    """
    hist = labels.reason_shares() if labels.by_reason else {}
    base = {r: float(hist.get(r, 0.0)) for r in REASONS}
    if sum(base.values()) <= 0:
        base = {"ENE": 0.5, "CNF": 0.3, "REL": 0.15, "PAR": 0.05}
    out = dict(base)
    out["ENE"] = out.get("ENE", 0.0) + 0.60 * max(0.0, energy_signal)
    out["CNF"] = out.get("CNF", 0.0) + 0.40 * max(0.0, electric_signal)
    total = sum(out.values()) or 1.0
    return {k: round(v / total, 4) for k, v in out.items()}


def dominant_reason(weights: dict[str, float]) -> str:
    return max(weights.items(), key=lambda kv: kv[1])[0] if weights else "ENE"


def reason_label(code: str) -> str:
    return RAZOES.get(code, code)


# ----------------------------------------------------------- severidade
def severity(probability: float, expected_mw: float, area: str,
             mw_reference: float = 1000.0) -> float:
    w = RISK_SEVERITY_WEIGHTS
    norm_mw = min(1.0, max(0.0, expected_mw / max(mw_reference, 1.0)))
    return round(
        w["probability"] * probability
        + w["expected_mw"] * norm_mw
        + w["criticality"] * criticality_of(area),
        4,
    )


def expected_cut(probability: np.ndarray, conditional_mw: float) -> np.ndarray:
    """E[corte] = P(restricao) * E[corte | restricao]."""
    return np.asarray(probability, dtype="f8") * float(conditional_mw)


def conditional_mean_cut(labels: CurtailmentLabels) -> float:
    if not len(labels.corte_mw):
        return 0.0
    sel = labels.ocorreu
    if not sel.any():
        return 0.0
    return float(np.median(labels.corte_mw[sel]))


# ----------------------------------------------------------- acoes
def recommended_actions(reason: str, expected_mw: float, patamar: str) -> list[str]:
    """Apoio a decisao humana. Nao e comando operativo."""
    acts: list[str] = []
    if reason == "ENE":
        acts.append("Avaliar deslocamento de carga e resposta da demanda na janela.")
        acts.append("Verificar margem das fontes controláveis até o mínimo técnico.")
        if expected_mw > 200:
            acts.append("Acionar o plano de excedentes na rede de distribuição "
                        "com antecedência, evitando regime emergencial.")
        acts.append("Comunicar a distribuidora da área sobre a janela prevista.")
    elif reason == "CNF":
        acts.append("Revisar limites de exportação do subsistema no horizonte.")
        acts.append("Avaliar redespacho e coordenação de intercâmbio.")
        acts.append("Conferir manobras programadas no período.")
    elif reason == "REL":
        acts.append("Confirmar indisponibilidades externas programadas.")
        acts.append("Checar o estado das instalações a montante da usina.")
    else:
        acts.append("Revisar condições do parecer de acesso aplicáveis.")
    if patamar == "minima_diurna":
        acts.append("Atenção: patamar de mínima diurna — menor margem de absorção.")
    elif patamar in ("rampa", "ponta_noturna"):
        acts.append("Atenção: proximidade da rampa vespertina.")
    return acts


def evidence_items(*, probability: float, expected_mw: float,
                   ghi_norm: float, margin_mw: float, reason: str,
                   reason_weights_: dict[str, float],
                   provenance_dataset: str) -> list[dict]:
    """Evidencias que sustentam o alerta, com a fonte de cada peca."""
    return [
        {"label": "Probabilidade de restrição",
         "value": "%.0f%%" % (probability * 100.0),
         "source": "modelo logístico calibrado (%s)" % provenance_dataset},
        {"label": "Montante esperado",
         "value": "%.0f MW" % expected_mw,
         "source": "E[corte] = P × mediana histórica condicional"},
        {"label": "Irradiância de céu claro (normalizada)",
         "value": "%.2f" % ghi_norm,
         "source": "geometria solar + Haurwitz"},
        {"label": "Margem das fontes controláveis",
         "value": "%.0f MW" % margin_mw,
         "source": "balanço de energia (hidráulica + térmica)"},
        {"label": "Razão predominante",
         "value": "%s — %s" % (reason, reason_label(reason)),
         "source": "histórico por razão + sinais correntes %s" % reason_weights_},
    ]
