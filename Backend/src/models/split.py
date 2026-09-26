"""Split cronológico ÚNICO do projeto (carga e curtailment usam o mesmo código).

    treino: ALVOS em [inicio_treino, fim_treino]
    teste:  EMISSÕES (alvo − h) a partir de inicio_teste

Como fim_treino < inicio_teste (validado ao montar), nenhum alvo de treino é posterior a uma
emissão de teste: o modelo nunca aprendeu com algo que, na hora de prever o teste, ainda não
tinha acontecido. Split aleatório não existe no projeto (regra do CLAUDE.md).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.utils.tempo import PASSO


@dataclass(frozen=True)
class Split:
    inicio_treino: pd.Timestamp
    fim_treino: pd.Timestamp
    inicio_teste: pd.Timestamp

    @classmethod
    def de(cls, cfg_split: dict) -> "Split":
        """A partir da seção `split` de uma config (datas em texto, horário local do projeto)."""
        sp = cls(**{k: pd.Timestamp(v) for k, v in cfg_split.items()})
        if not sp.inicio_treino < sp.fim_treino < sp.inicio_teste:
            raise ValueError(f"split inválido (precisa inicio_treino < fim_treino < inicio_teste): {sp}")
        return sp

    def treino(self, alvos: pd.DatetimeIndex) -> np.ndarray:
        """Linhas de treino: ALVO dentro de [inicio_treino, fim_treino]."""
        return np.asarray((alvos >= self.inicio_treino) & (alvos <= self.fim_treino))

    def teste(self, alvos: pd.DatetimeIndex, horizonte: int) -> np.ndarray:
        """Linhas de teste: EMISSÃO (alvo − h) a partir de inicio_teste."""
        return np.asarray(alvos - horizonte * PASSO >= self.inicio_teste)
