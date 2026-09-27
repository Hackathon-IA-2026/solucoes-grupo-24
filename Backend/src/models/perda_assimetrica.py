"""Perda pinball assimétrica por patamar (Fase 5): o diferencial do TFT.

Na curva de carga o erro não custa igual em toda hora nem nos dois sentidos. Subestimar a ponta
noturna pode levar a acionamento emergencial; superestimar a mínima diurna liga térmica cara à
toa. A perda multiplica a pinball de cada quantil por um peso que depende do PATAMAR do
instante-alvo e do SINAL do erro:

    e = real − previsto_q
    L = w_sub[patamar] · q · e          se e >= 0   (subestimou)
        w_sup[patamar] · (q − 1) · e    se e <  0   (superestimou)

Com todos os pesos = 1 é exatamente a pinball (teste). Pesos em config/modelos_tft.yaml,
indexados pelo código de patamar de src/features/carga.py::CODIGO_PATAMAR (um só mapa
nome -> código no projeto).

Integração com a pytorch-forecasting: a coluna de peso do TimeSeriesDataSet chega à loss por
passo do decoder. Usamos essa coluna para levar o CÓDIGO do patamar do alvo (e não um peso
multiplicativo), porque o peso aqui depende do sinal do erro, que só se conhece dentro da loss.
Por isso `update` é sobrescrito: a biblioteca multiplicaria a perda pela coluna de peso.
"""
from __future__ import annotations

from src.features.carga import CODIGO_PATAMAR
from src.utils.torch_windows import importar_torch

torch = importar_torch()

from pytorch_forecasting.metrics import QuantileLoss  # noqa: E402  (depois do torch)
from pytorch_forecasting.utils import unpack_sequence  # noqa: E402
from torch.nn.utils import rnn  # noqa: E402


def tabela_pesos(pesos_cfg: dict[str, list[float]]) -> tuple[list[float], list[float]]:
    """Config {patamar: [sub, sup]} -> listas indexadas pelo código do patamar.

    Recusa config incompleta ou com patamar desconhecido: um patamar sem peso viraria peso 0
    (aquele horário deixaria de ensinar o modelo) sem ninguém perceber.
    """
    faltam = set(CODIGO_PATAMAR) - set(pesos_cfg)
    sobram = set(pesos_cfg) - set(CODIGO_PATAMAR)
    if faltam or sobram:
        raise ValueError(f"pesos da perda: faltam {sorted(faltam)}, desconhecidos {sorted(sobram)}")
    n = len(CODIGO_PATAMAR)
    sub, sup = [0.0] * n, [0.0] * n
    for nome, codigo in CODIGO_PATAMAR.items():
        sub[codigo], sup[codigo] = (float(v) for v in pesos_cfg[nome])
    if min(sub + sup) <= 0:
        raise ValueError("pesos da perda precisam ser positivos")
    return sub, sup


def pinball_assimetrica(previsto, real, codigo, quantis, peso_sub, peso_sup):
    """Perda por elemento (lote × passo × quantil).

    previsto: (B, T, Q) · real: (B, T) · codigo: (B, T) inteiro (patamar do alvo)
    quantis, peso_sub, peso_sup: tensores 1-D (Q) e (n_patamares).
    """
    erro = real.unsqueeze(-1) - previsto                  # (B, T, Q); > 0 = subestimou
    c = codigo.long()
    w_sub = peso_sub[c].unsqueeze(-1)                     # (B, T, 1)
    w_sup = peso_sup[c].unsqueeze(-1)
    return torch.where(erro >= 0, w_sub * quantis * erro, w_sup * (quantis - 1) * erro)


class PinballAssimetrica(QuantileLoss):
    """QuantileLoss da pytorch-forecasting com os pesos assimétricos por patamar."""

    def __init__(self, quantiles: list[float], pesos_sub: list[float], pesos_sup: list[float], **kwargs):
        super().__init__(quantiles=quantiles, **kwargs)
        # Guardados como listas (hiperparâmetros serializáveis no checkpoint); os tensores são
        # criados no device da previsão a cada chamada (custo desprezível: poucos números).
        self.pesos_sub = list(pesos_sub)
        self.pesos_sup = list(pesos_sup)

    def _tensores(self, ref):
        como = {"device": ref.device, "dtype": ref.dtype}
        return (torch.tensor(self.quantiles, **como), torch.tensor(self.pesos_sub, **como),
                torch.tensor(self.pesos_sup, **como))

    def update(self, y_pred, target):
        # A coluna de peso do dataset traz o código do patamar (ver o docstring do módulo).
        if not isinstance(target, (list, tuple)) or target[1] is None:
            raise ValueError("PinballAssimetrica precisa do código do patamar na coluna de peso do dataset")
        target, codigo = target
        if isinstance(target, rnn.PackedSequence):
            target, lengths = unpack_sequence(target)
        else:
            lengths = torch.full((target.size(0),), fill_value=target.size(1), dtype=torch.long,
                                 device=target.device)
        q, w_sub, w_sup = self._tensores(y_pred)
        losses = pinball_assimetrica(y_pred, target, codigo, q, w_sub, w_sup)
        self._update_losses_and_lengths(losses, lengths)
