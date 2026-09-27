"""Toda biblioteca que o serviço web importa precisa estar em deploy/requirements-api.txt.

Por quê: a imagem de produção (deploy/deploy_ecs.py e deploy/Dockerfile) instala SÓ esse arquivo,
não o pyproject.toml inteiro. Em 2026-09-27 a Triangulação caiu em produção com
"No module named 'pandas'": o import ficava DENTRO da função (import tardio), então subir a API não
acusava nada e o erro só aparecia quando alguém abria a página. Localmente passava, porque o
ambiente de desenvolvimento tem tudo do pyproject.

Como: análise estática (ast), sem importar nada. Parte do main.py e de todo o pacote oraculo/
(o protótipo é montado dentro da API), segue os imports locais (src.*, oraculo.*, relativos)
transitivamente — incluindo os que estão dentro de funções — e junta os módulos de terceiros.
Imports protegidos por `try/except ImportError` são opcionais por decisão de quem escreveu e
ficam de fora.
"""
import ast
import re
import sys
from pathlib import Path

from src.utils.paths import RAIZ

REQUIREMENTS = RAIZ / "deploy" / "requirements-api.txt"

# Nome no pip -> nome no import, só onde os dois diferem.
IMPORT_DO_PACOTE = {"pyyaml": "yaml", "pillow": "PIL", "psycopg": "psycopg"}

# Pacotes locais (raiz de import = Backend/).
LOCAIS = {"src", "oraculo", "main"}

# Exceções conferidas à mão (a análise é por arquivo, não por função). Cada uma com o porquê.
DISPENSADOS = {
    # Dependência obrigatória do fastapi (que está listado): instalar um instala o outro.
    "starlette": "vem com o fastapi",
    # src/utils/torch_windows.py é importado pela API só por carregar_runtime_do_sistema();
    # o `import torch` está em importar_torch(), chamada apenas pelo treino (src/models/*).
    "torch": "só em importar_torch(), usada pelo treino e nunca pela API",
}


def _pacotes_do_requirements() -> set[str]:
    nomes = set()
    for linha in REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        linha = linha.split("#", 1)[0].strip()
        if not linha:
            continue
        # "uvicorn[standard]", "sqlalchemy>=2" -> nome puro
        nome = re.split(r"[\[<>=!~; ]", linha, maxsplit=1)[0].lower().replace("-", "_")
        nomes.add(IMPORT_DO_PACOTE.get(nome, nome))
    return nomes


def _arquivo_do_modulo(modulo: str) -> Path | None:
    base = RAIZ.joinpath(*modulo.split("."))
    for cand in (base.with_suffix(".py"), base / "__init__.py"):
        if cand.exists():
            return cand
    return None


def _modulo_do_arquivo(arq: Path) -> str:
    partes = list(arq.relative_to(RAIZ).with_suffix("").parts)
    if partes[-1] == "__init__":
        partes.pop()
    return ".".join(partes)


def _opcionais(arvore: ast.AST) -> set[int]:
    """ids dos nós de import dentro de `try` que trata ImportError/ModuleNotFoundError."""
    ids = set()
    for no in ast.walk(arvore):
        if not isinstance(no, ast.Try):
            continue
        trata = any(h.type is None or any(
            isinstance(n, ast.Name) and n.id in {"ImportError", "ModuleNotFoundError", "Exception"}
            for n in ast.walk(h.type)) for h in no.handlers)
        if trata:
            ids |= {id(n) for corpo in no.body for n in ast.walk(corpo)
                    if isinstance(n, (ast.Import, ast.ImportFrom))}
    return ids


def _imports(arq: Path) -> list[str]:
    """Módulos importados pelo arquivo (absolutos; relativos já resolvidos), sem os opcionais."""
    arvore = ast.parse(arq.read_text(encoding="utf-8-sig"))  # há arquivos com BOM
    opcionais = _opcionais(arvore)
    pacote = _modulo_do_arquivo(arq)
    if arq.name != "__init__.py":
        pacote = pacote.rpartition(".")[0]
    saida = []
    for no in ast.walk(arvore):
        if id(no) in opcionais:
            continue
        if isinstance(no, ast.Import):
            saida += [a.name for a in no.names]
        elif isinstance(no, ast.ImportFrom):
            if no.level:
                base = pacote.split(".")
                base = base[: len(base) - (no.level - 1)] if no.level > 1 else base
                raiz = ".".join(base + ([no.module] if no.module else []))
            else:
                raiz = no.module
            # `from pkg import sub` pode ser submódulo: inclui os dois candidatos.
            saida.append(raiz)
            saida += [f"{raiz}.{a.name}" for a in no.names]
    return saida


def _terceiros_alcancaveis() -> dict[str, str]:
    """{módulo de terceiros: arquivo local que o importa}, a partir do main.py e de oraculo/."""
    fila = [RAIZ / "main.py", *sorted((RAIZ / "oraculo").rglob("*.py"))]
    vistos: set[Path] = set()
    terceiros: dict[str, str] = {}
    while fila:
        arq = fila.pop()
        if arq in vistos:
            continue
        vistos.add(arq)
        for mod in _imports(arq):
            topo = mod.split(".")[0]
            if topo in LOCAIS:
                # Módulo local: segue, junto com os __init__ dos pacotes no caminho.
                partes = mod.split(".")
                for i in range(1, len(partes) + 1):
                    alvo = _arquivo_do_modulo(".".join(partes[:i]))
                    if alvo is not None and alvo not in vistos:
                        fila.append(alvo)
            elif topo not in sys.stdlib_module_names and topo != "__future__":
                terceiros.setdefault(topo, str(arq.relative_to(RAIZ)))
    return terceiros


def test_todo_import_da_api_esta_no_requirements_de_deploy():
    listados = _pacotes_do_requirements()
    faltando = {m: onde for m, onde in _terceiros_alcancaveis().items()
                if m not in listados and m not in DISPENSADOS}
    assert not faltando, (
        "módulos importados pelo serviço web e ausentes de deploy/requirements-api.txt "
        f"(em produção dão 'No module named ...'): {faltando}")
