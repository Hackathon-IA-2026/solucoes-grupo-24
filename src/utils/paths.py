"""Caminhos do projeto, derivados da raiz do repositório (nada hardcoded)."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

DATA = ROOT / "data"
DATA_RAW = DATA / "raw"
DATA_PROCESSED = DATA / "processed"
CONFIG = ROOT / "config"
DOCS = ROOT / "docs"
NOTEBOOKS = ROOT / "notebooks"
REPORTS = ROOT / "reports"
OUTPUT = ROOT / "output"


def ensure(path: Path) -> Path:
    """Cria o diretório (e pais) se não existir e devolve o próprio path."""
    path.mkdir(parents=True, exist_ok=True)
    return path


if __name__ == "__main__":
    assert (ROOT / "pyproject.toml").is_file(), f"raiz errada: {ROOT}"
    assert DATA_RAW == ROOT / "data" / "raw"
    print(ROOT)
