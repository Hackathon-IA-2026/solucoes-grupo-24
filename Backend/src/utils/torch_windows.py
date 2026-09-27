"""Importa o torch no Windows mesmo quando o Python vem do Anaconda (ponto único de import).

Problema (diagnosticado em 2026-09-26): `import torch` falhava com
`OSError: [WinError 1114] ... c10.dll`. O .venv foi criado a partir do Python do Anaconda, que
traz na PRÓPRIA pasta o runtime do Visual C++ 14.27 (2020): `vcruntime140.dll`,
`vcruntime140_1.dll` e `msvcp140.dll`. O `python.exe` carrega essas DLLs antigas antes das do
sistema (14.51 em C:\\Windows\\System32), e o torch 2.x exige um runtime mais novo: a rotina de
inicialização da `c10.dll` falha. Com as DLLs do sistema carregadas ANTES do torch, o Windows
reaproveita as já carregadas e o import funciona (conferido: torch 2.14.0+cpu).

Decisão: corrigir no código, e não mandar cada pessoa do time trocar de Python. Fora do Windows,
ou se as DLLs do sistema não existirem, a função não faz nada (o comportamento é o padrão).
Alternativa definitiva, sem este desvio: recriar o .venv com o Python do python.org.

Uso: todo módulo do projeto que precisa do torch faz `torch = importar_torch()` em vez de
`import torch` (inclusive antes de importar pytorch_forecasting / lightning, que importam o torch).
"""
from __future__ import annotations

import ctypes
import os
import sys
from pathlib import Path

# Ordem importa: vcruntime antes de msvcp (a msvcp depende da vcruntime).
_DLLS_RUNTIME = ("vcruntime140.dll", "vcruntime140_1.dll", "msvcp140.dll")


_JA_CARREGADO = False


def carregar_runtime_do_sistema() -> list[str]:
    """Carrega o runtime do Visual C++ do System32 (só no Windows). Devolve as DLLs carregadas.

    PRECISA rodar antes de QUALQUER extensão em C++ (LightGBM, pandas, scikit-learn...): a
    primeira que pedir `msvcp140.dll` fixa a versão para o processo inteiro, e se for a do
    Anaconda o torch não inicializa mais (achado no run_heavywork.py: o treino do LightGBM
    rodava antes do TFT). Por isso a chamada mora no `__init__` dos pacotes `src` e `oraculo`,
    executado antes de qualquer outro import deles; aqui ela só é repetida por segurança.
    """
    global _JA_CARREGADO
    if sys.platform != "win32" or _JA_CARREGADO or "torch" in sys.modules:
        return []  # fora do Windows não se aplica; torch já importado = tarde demais, nada a fazer
    system32 = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32"
    carregadas = []
    for nome in _DLLS_RUNTIME:
        caminho = system32 / nome
        if caminho.exists():
            ctypes.WinDLL(str(caminho))
            carregadas.append(nome)
    _JA_CARREGADO = True
    return carregadas


def importar_torch():
    """`import torch` à prova do runtime antigo do Anaconda. Devolve o módulo torch."""
    carregar_runtime_do_sistema()
    import torch

    return torch
