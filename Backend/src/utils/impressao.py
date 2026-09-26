"""Impressões digitais (hashes) de entradas, para saber se uma etapa precisa rodar de novo.

O run_heavywork.py pula uma etapa quando a impressão digital das entradas dela é igual à
da última execução bem-sucedida. Os dois tipos de entrada que importam:
- dados/estado (ex.: o manifesto do download)  -> de_objeto()
- arquivos de código e de configuração          -> de_arquivos()
Incluir o CÓDIGO na impressão faz uma correção de bug no processamento refazer as tabelas
sozinha: "consertei a regra mas esqueci de reprocessar" deixa de ser possível.
"""
import hashlib
import json
from pathlib import Path
from typing import Iterable


def de_objeto(obj) -> str:
    """sha256 de um objeto JSON-serializável, estável entre execuções (chaves ordenadas)."""
    texto = json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def de_arquivos(caminhos: Iterable[Path], base: Path) -> str:
    """sha256 do conteúdo de arquivos e pastas (pastas: todos os .py e .yaml dentro, recursivo).

    O caminho relativo a `base` entra no hash junto com o conteúdo: renomear ou mover um
    arquivo também muda a impressão. __pycache__ fica de fora (muda sem o código mudar).
    """
    arquivos: set[Path] = set()
    for c in caminhos:
        c = Path(c)
        if c.is_dir():
            arquivos.update(p for p in c.rglob("*") if p.suffix in (".py", ".yaml")
                            and "__pycache__" not in p.parts)
        elif c.exists():
            arquivos.add(c)
        else:
            raise FileNotFoundError(f"entrada da impressão digital não existe: {c}")
    h = hashlib.sha256()
    for p in sorted(arquivos):
        h.update(p.resolve().relative_to(base.resolve()).as_posix().encode())
        # Normaliza fim de linha: o mesmo arquivo com CRLF (Windows) e LF (git) é o mesmo código.
        h.update(p.read_bytes().replace(b"\r\n", b"\n"))
    return h.hexdigest()


def codigo_de(modulo: str, raiz: Path) -> list[Path]:
    """Arquivos de código de `modulo` e de TUDO que ele importa do projeto (fecho transitivo).

    Lê os `import`/`from ... import` de cada arquivo (AST, sem executar nada) e segue os que
    começam por um pacote do projeto (src, pipeline). Serve de entrada da impressão digital de
    uma etapa: a lista de dependências nunca é escrita à mão, então não dá para esquecer um
    import (etapa que não refaz) nem incluir código alheio (etapa que refaz à toa, ex.: mexer
    no classificador de curtailment retreinar a carga).
    """
    import ast

    pacotes = ("src", "pipeline")

    def arquivo(nome: str) -> Path | None:
        base = raiz.joinpath(*nome.split("."))
        for p in (base.with_suffix(".py"), base / "__init__.py"):
            if p.exists():
                return p
        return None

    vistos: set[Path] = set()
    fila = [modulo]
    while fila:
        nome = fila.pop()
        p = arquivo(nome)
        if p is None or p in vistos:
            continue
        vistos.add(p)
        # pacotes pais (__init__.py) também rodam no import
        partes = nome.split(".")
        fila += [".".join(partes[:i]) for i in range(1, len(partes))]
        for no in ast.walk(ast.parse(p.read_text(encoding="utf-8-sig"))):
            if isinstance(no, ast.Import):
                fila += [a.name for a in no.names]
            elif isinstance(no, ast.ImportFrom) and no.module and no.level == 0:
                fila.append(no.module)
                fila += [f"{no.module}.{a.name}" for a in no.names]  # "from pacote import modulo"
        fila = [n for n in fila if n.split(".")[0] in pacotes]
    return sorted(vistos)
