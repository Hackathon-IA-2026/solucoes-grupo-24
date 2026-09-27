"""Config e caminhos da conciliação de MMGD (config/conciliacao.yaml), num módulo sem lógica.

Mesmo motivo de src/spatial/saidas.py: quem só LÊ as saídas (a rota da API, o pipeline de visão)
importa daqui, sem puxar geopandas nem o código que calcula a conciliação.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from src.utils.config import carregar
from src.utils.paths import DOCS_REPORTS, RAIZ


def cfg() -> dict[str, Any]:
    return carregar("conciliacao")


def piloto() -> dict[str, list[str]]:
    """{sigla da distribuidora: [códigos IBGE dos municípios]} da área piloto."""
    out: dict[str, list[str]] = {}
    for item in cfg()["piloto"]:
        out.setdefault(item["distribuidora"], []).extend(str(m) for m in item["municipios"])
    return out


def saida(nome: str) -> Path:
    """Caminho absoluto de uma saída (chave de `saidas` na config). O relatório vai para docs/reports/."""
    valor = cfg()["saidas"][nome]
    return DOCS_REPORTS / valor if nome == "relatorio" else RAIZ / valor


def caminho(relativo_backend: str) -> Path:
    """Caminho da config (relativo a Backend/) -> absoluto."""
    return RAIZ / relativo_backend
