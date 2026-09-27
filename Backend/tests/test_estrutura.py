"""A raiz do repositório só tem Backend/, Frontend/ e docs/ (mais arquivos de projeto).

Tudo que é Python (código, config, dados, testes) mora em Backend/.
Ver docs/prompts/prompt_reestruturacao_backend.md.

Sem notebooks Jupyter: o produto é um serviço (ingestão -> processamento -> modelos -> banco ->
FastAPI -> dashboard). Análise exploratória vira código em src/ com relatório em docs/reports/,
que roda no pipeline e no pytest; um .ipynb não é chamado por nada do serviço.
"""
import subprocess
from pathlib import Path

from src.utils.paths import RAIZ, RAIZ_REPO

PASTAS_PERMITIDAS = {"Backend", "Frontend", "docs"}


def test_raiz_do_repositorio_so_tem_as_pastas_permitidas():
    extras = sorted(p.name for p in RAIZ_REPO.iterdir()
                    if p.is_dir() and not p.name.startswith(".") and p.name not in PASTAS_PERMITIDAS)
    assert extras == [], f"pastas fora do lugar na raiz (mova para Backend/): {extras}"


def test_raiz_do_backend_e_a_raiz_de_import():
    assert (RAIZ / "pyproject.toml").exists()
    assert RAIZ.name == "Backend"


# Quem pode tocar o dado bruto (data/raw): só a ingestão (grava) e o processamento (lê), mais
# os utilitários de infraestrutura que definem os caminhos (paths.py, config.py: arquivo_direto)
# e a pasta temporária do DuckDB. A espacialização (Fase 6) é processamento da BDGD, do cadastro
# da ANEEL e da malha do IBGE: só os três módulos dela que leem o bruto entram aqui (os cálculos
# de excedente, que a publicação importa, não). Todo o resto (modelos, previsão, publicação,
# API, orquestrador) usa data/processed e os modelos treinados. Ver docs/Oraculo_planejamento.md §13.1.
# A visão computacional (Luiz) também é ingestão + processamento, só que de IMAGEM: o download de
# satélite grava em data/raw/satelite e a validação/Camada 1 leem essas imagens brutas. A
# auditoria das camadas 2/3 e o teste e2e NÃO entram aqui: consomem só o GeoJSON da Camada 1.
PODEM_LER_BRUTO = ("src/ingestion/", "src/processing/", "src/utils/paths.py",
                   "src/utils/banco_analitico.py", "src/utils/config.py",
                   "src/spatial/bdgd.py", "src/spatial/mmgd.py", "src/spatial/construir.py",
                   "pipeline/download_satelite.py", "pipeline/validar_modelo.py",
                   "pipeline/auditoria_camada1.py", "pipeline/visao_comum.py",
                   # Conciliação de MMGD: as áreas atendidas por transformador leem a BDGD e a malha
                   # do IBGE; a varredura grava os ladrilhos da Esri em data/raw/satelite/esri.
                   # A conciliação em si (src/spatial/conciliacao.py) NÃO entra: usa bdgd.py/mmgd.py.
                   "src/spatial/areas_trafo.py", "pipeline/paineis_por_transformador.py")
# arquivo_direto(: caminho de um arquivo bruto lido da config (BDGD, ANEEL, IBGE). Sem esta marca,
# um módulo qualquer leria o bruto sem escrever "data/raw" em lugar nenhum e o teste não veria.
MARCAS_DO_BRUTO = ("RAW_ONS", "DATA_RAW", "data/raw", "data\\\\raw", "data\\raw", "arquivo_direto(")


def test_so_ingestao_e_processamento_tocam_o_dado_bruto():
    esta = Path(__file__).resolve()
    violacoes = []
    for arq in RAIZ.rglob("*.py"):
        rel = arq.relative_to(RAIZ).as_posix()
        # .venv: terceiros; RDX: legado do hackathon anterior (lê a própria pasta, não data/raw).
        if rel.startswith((".venv/", "RDX/")) or arq.resolve() == esta or rel.startswith(PODEM_LER_BRUTO):
            continue
        texto = arq.read_text(encoding="utf-8", errors="ignore")
        violacoes += [f"{rel}: {m}" for m in MARCAS_DO_BRUTO if m in texto]
    assert violacoes == [], ("só src/ingestion e src/processing podem depender de data/raw; "
                             f"o resto usa data/processed: {violacoes}")


def test_nenhum_notebook_jupyter_versionado():
    # git ls-files (e não glob no disco): olha só o que o time compartilha, ignora .venv e caches.
    arquivos = subprocess.run(["git", "ls-files", "*.ipynb"], cwd=RAIZ_REPO,
                              capture_output=True, text=True, check=True).stdout.split()
    assert arquivos == [], f"notebooks não fazem parte do serviço; migre para src/: {arquivos}"
