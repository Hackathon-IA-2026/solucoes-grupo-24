"""Único ponto de definição de caminhos do projeto.

Estrutura (ver docs/prompts/prompt_reestruturacao_backend.md):
    <repo>/Backend/   código Python, config, dados, testes            -> RAIZ
    <repo>/Frontend/  dashboard
    <repo>/docs/      documentação e relatórios                        -> RAIZ_REPO / "docs"

Decisão: dados, config e saídas são relativos a RAIZ (= Backend/), inclusive os caminhos
gravados no manifesto de download; assim mover o repositório inteiro não quebra nada.
Nenhum outro módulo deve montar caminhos "na mão" a partir de strings soltas.
"""
from pathlib import Path

# Raiz do backend: Backend/src/utils/paths.py -> parents[2]
RAIZ = Path(__file__).resolve().parents[2]
BACKEND = RAIZ
# Raiz do repositório git (onde ficam Backend/, Frontend/ e docs/)
RAIZ_REPO = RAIZ.parent

CONFIG = RAIZ / "config"
DATA = RAIZ / "data"
DATA_RAW = DATA / "raw"
DATA_PROCESSED = DATA / "processed"
OUTPUT = RAIZ / "output"
# Modelos treinados e previsões do replay (etapas 3 e 4 do run_heavywork.py; fora do git)
MODELOS = DATA / "modelos"
TESTS = RAIZ / "tests"

DOCS = RAIZ_REPO / "docs"
DOCS_REPORTS = DOCS / "reports"
FRONTEND = RAIZ_REPO / "Frontend"
# Mocks do dashboard (o pipeline gera alertas.json aqui; ver pipeline/gerar_alertas_mock.py)
DASHBOARD_MOCK = FRONTEND / "oraculo-dashboard" / "src" / "data" / "mock"

# Bases brutas do ONS (Parquet particionado, fora do git)
RAW_ONS = DATA_RAW / "ons"

# Estado e trava do run_heavywork.py (locais de cada máquina, fora do git). Ficam em data/ e não
# em data/raw: o orquestrador não tem nada a ver com o dado bruto (só ingestão e processamento têm).
ESTADO_HEAVYWORK = DATA / "_estado_heavywork.json"
TRAVA_HEAVYWORK = DATA / "_heavywork.lock"


def ensure(path: Path) -> Path:
    """Cria o diretório (e pais) se não existir e devolve o próprio path."""
    path.mkdir(parents=True, exist_ok=True)
    return path


if __name__ == "__main__":
    # Auto-checagem rápida: o backend tem o pyproject.toml e o repositório tem o .git
    assert (RAIZ / "pyproject.toml").exists(), f"raiz do backend inesperada: {RAIZ}"
    assert (RAIZ_REPO / ".git").exists(), f"raiz do repositório inesperada: {RAIZ_REPO}"
    for nome, valor in sorted(globals().items()):
        if isinstance(valor, Path):
            print(f"{nome:15s} {valor}")
