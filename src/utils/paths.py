"""Único ponto de definição de caminhos do projeto.

Decisão: tudo é relativo à raiz do repositório (dois níveis acima deste arquivo),
para que scripts, notebooks e testes funcionem de qualquer diretório de trabalho.
Nenhum outro módulo deve montar caminhos "na mão" a partir de strings soltas.
"""
from pathlib import Path

# Raiz do repositório: src/utils/paths.py -> parents[2]
RAIZ = Path(__file__).resolve().parents[2]

CONFIG = RAIZ / "config"
DATA = RAIZ / "data"
DATA_RAW = DATA / "raw"
DATA_PROCESSED = DATA / "processed"
DOCS = RAIZ / "docs"
DOCS_REPORTS = DOCS / "reports"
NOTEBOOKS = RAIZ / "notebooks"
OUTPUT = RAIZ / "output"
BACKEND = RAIZ / "Backend"
TESTS = RAIZ / "tests"

# Bases brutas do ONS (Parquet particionado, fora do git)
RAW_ONS = DATA_RAW / "ons"


def ensure(path: Path) -> Path:
    """Cria o diretório (e pais) se não existir e devolve o próprio path."""
    path.mkdir(parents=True, exist_ok=True)
    return path


if __name__ == "__main__":
    # Auto-checagem rápida: a raiz precisa conter o pyproject.toml
    assert (RAIZ / "pyproject.toml").exists(), f"raiz inesperada: {RAIZ}"
    for nome, valor in sorted(globals().items()):
        if isinstance(valor, Path):
            print(f"{nome:15s} {valor}")
