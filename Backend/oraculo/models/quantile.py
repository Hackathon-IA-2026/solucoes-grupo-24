# -*- coding: utf-8 -*-
"""Regressao quantilica com perda assimetrica por patamar horario.

Este e o diferencial declarado no deck e nao existe pronto em biblioteca: na
curva de carga o erro nao tem peso uniforme. Subestimar a ponta noturna pode
significar acionamento emergencial; superestimar a minima diurna significa
termica cara ligada a toa.

Formulacao (ver 06-modelos-analiticos.md, secao 6.4):

    L(b) = sum_t  w(patamar_t, sinal_do_erro) * rho_tau( y_t - x_t' b )

com rho_tau a perda pinball. O peso e aplicado dentro da pinball, o que preserva
a interpretacao de quantil e desloca o ajuste na direcao operacionalmente
segura.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

try:
    from scipy.optimize import minimize
except ImportError:  # pragma: no cover
    minimize = None  # type: ignore

from ..config import ASYMMETRIC_WEIGHTS, L2_PENALTY, QUANTILES


# --------------------------------------------------------------- perdas
def pinball(residual: np.ndarray, tau: float,
            w_under: np.ndarray | float = 1.0,
            w_over: np.ndarray | float = 1.0) -> np.ndarray:
    """Perda pinball ponderada, elemento a elemento.

    `residual = y - y_hat`. residual > 0 significa que o modelo subestimou.
    """
    r = np.asarray(residual, dtype="f8")
    under = np.where(r >= 0, r * tau, 0.0) * np.asarray(w_under, dtype="f8")
    over = np.where(r < 0, r * (tau - 1.0), 0.0) * np.asarray(w_over, dtype="f8")
    return under + over


def _smooth_pinball(r: np.ndarray, tau: float, w_u, w_o, eps: float) -> np.ndarray:
    """Versao suavizada (Huber em torno de zero) para o otimizador."""
    r = np.asarray(r, dtype="f8")
    absr = np.abs(r)
    soft = np.where(absr < eps, r * r / (2.0 * eps), absr - eps / 2.0)
    # Reparte a magnitude suavizada entre os dois lados com os pesos devidos.
    side = np.where(r >= 0, tau * np.asarray(w_u, dtype="f8"),
                    (1.0 - tau) * np.asarray(w_o, dtype="f8"))
    return soft * side


def patamar_weights(patamar: np.ndarray,
                    weights: dict[str, tuple[float, float]] | None = None,
                    asymmetric: bool = True) -> tuple[np.ndarray, np.ndarray]:
    """Vetores (peso_subestimacao, peso_superestimacao) por linha."""
    table = weights or ASYMMETRIC_WEIGHTS
    n = len(patamar)
    if not asymmetric:
        return np.ones(n), np.ones(n)
    w_u = np.ones(n)
    w_o = np.ones(n)
    for i, p in enumerate(patamar):
        pu, po = table.get(str(p), table.get("base", (1.0, 1.0)))
        w_u[i], w_o[i] = pu, po
    return w_u, w_o


# --------------------------------------------------------------- modelo
@dataclass
class QuantileModel:
    quantiles: tuple[float, ...] = QUANTILES
    asymmetric: bool = True
    l2: float = L2_PENALTY
    coef: dict[float, np.ndarray] = field(default_factory=dict)
    names: list[str] = field(default_factory=list)
    y_scale: float = 1.0
    y_center: float = 0.0
    fit_info: dict = field(default_factory=dict)

    # ------------------------------------------------------------- fit
    def fit(self, X: np.ndarray, y: np.ndarray, patamar: np.ndarray,
            names: list[str] | None = None) -> "QuantileModel":
        X = np.asarray(X, dtype="f8")
        y = np.asarray(y, dtype="f8")
        ok = np.isfinite(y) & np.all(np.isfinite(X), axis=1)
        Xf, yf, pf = X[ok], y[ok], np.asarray(patamar, dtype=object)[ok]
        if len(yf) < X.shape[1] + 5:
            raise ValueError(
                "amostra insuficiente: %d linhas para %d variaveis"
                % (len(yf), X.shape[1])
            )

        self.names = list(names or [])
        self.y_center = float(np.mean(yf))
        self.y_scale = float(np.std(yf)) or 1.0
        yz = (yf - self.y_center) / self.y_scale

        w_u, w_o = patamar_weights(pf, asymmetric=self.asymmetric)
        eps = 0.02  # em unidades de desvio padrao do alvo

        p = Xf.shape[1]
        # Inicializa em minimos quadrados regularizados: convergencia rapida.
        lam = self.l2 * float(np.trace(Xf.T @ Xf)) / p
        beta0 = np.linalg.solve(Xf.T @ Xf + lam * np.eye(p), Xf.T @ yz)

        info: dict = {"rows": int(len(yf)), "features": p, "iterations": {}}
        for tau in self.quantiles:
            beta = self._solve(Xf, yz, tau, w_u, w_o, beta0, lam, eps, info)
            self.coef[tau] = beta
        self.fit_info = info
        return self

    def _solve(self, X, y, tau, w_u, w_o, beta0, lam, eps, info):
        n = len(y)

        def obj(b):
            r = y - X @ b
            loss = _smooth_pinball(r, tau, w_u, w_o, eps).sum() / n
            return loss + lam / n * float(b @ b)

        def grad(b):
            r = y - X @ b
            absr = np.abs(r)
            # d/dr da parte suavizada
            dsoft = np.where(absr < eps, r / eps, np.sign(r))
            side = np.where(r >= 0, tau * w_u, (1.0 - tau) * w_o)
            g = -(X.T @ (dsoft * side)) / n
            return g + 2.0 * lam / n * b

        if minimize is None:  # pragma: no cover - scipy presente no ambiente
            return self._gd(X, y, tau, w_u, w_o, beta0, lam, eps)
        res = minimize(obj, beta0, jac=grad, method="L-BFGS-B",
                       options={"maxiter": 400, "ftol": 1e-10})
        info["iterations"][str(tau)] = int(res.nit)
        return np.asarray(res.x, dtype="f8")

    def _gd(self, X, y, tau, w_u, w_o, beta0, lam, eps, iters: int = 3000):
        b = np.array(beta0, dtype="f8")
        n = len(y)
        lr = 0.5
        for _ in range(iters):
            r = y - X @ b
            dsoft = np.where(np.abs(r) < eps, r / eps, np.sign(r))
            side = np.where(r >= 0, tau * w_u, (1.0 - tau) * w_o)
            g = -(X.T @ (dsoft * side)) / n + 2.0 * lam / n * b
            b -= lr * g
        return b

    # ---------------------------------------------------------- predict
    def predict(self, X: np.ndarray) -> dict[float, np.ndarray]:
        X = np.asarray(X, dtype="f8")
        out: dict[float, np.ndarray] = {}
        for tau, beta in sorted(self.coef.items()):
            out[tau] = X @ beta * self.y_scale + self.y_center
        return self._enforce_monotonic(out)

    @staticmethod
    def _enforce_monotonic(pred: dict[float, np.ndarray]) -> dict[float, np.ndarray]:
        """Garante P10 <= P50 <= P90 por ordenacao pontual.

        Cruzamento de quantis e artefato conhecido da estimacao independente;
        ordenar e a correcao padrao e preserva a cobertura marginal.
        """
        taus = sorted(pred.keys())
        stack = np.vstack([pred[t] for t in taus])
        stack = np.sort(stack, axis=0)
        return {t: stack[i] for i, t in enumerate(taus)}

    def drivers(self, feature_matrix) -> list[dict]:
        """Importancia por grupo de variavel, para a mediana."""
        med = self.coef.get(0.50)
        if med is None or feature_matrix is None:
            return []
        return feature_matrix.group_weights(med)

    def describe(self) -> dict:
        return {
            "kind": "regressao_quantilica_linear",
            "loss": "pinball_assimetrico_por_patamar" if self.asymmetric
                    else "pinball_simetrico",
            "quantiles": list(self.quantiles),
            "weights_by_patamar": {
                k: {"subestimacao": v[0], "superestimacao": v[1]}
                for k, v in ASYMMETRIC_WEIGHTS.items()
            } if self.asymmetric else {},
            "l2": self.l2,
            "fit": self.fit_info,
        }


# --------------------------------------------------- regressao quantilica simples
def fit_median(X: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Mediana condicional (tau=0,5), usada no montante esperado de corte."""
    m = QuantileModel(quantiles=(0.50,), asymmetric=False)
    pat = np.array(["base"] * len(y), dtype=object)
    m.fit(X, y, pat)
    return m.coef[0.50]
