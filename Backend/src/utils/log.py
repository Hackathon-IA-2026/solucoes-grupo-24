"""Configuração de log compartilhada pelos scripts do trabalho pesado.

Um lugar só: o download e o run_heavywork.py usam o mesmo formato, e chamar de novo
não duplica handlers (cada linha sairia duas vezes no terminal).
"""
import logging
from pathlib import Path

FORMATO = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def configurar(arquivo: Path | None = None) -> None:
    raiz = logging.getLogger()
    if not raiz.handlers:
        logging.basicConfig(level=logging.INFO, format=FORMATO)
    if arquivo is not None:
        alvo = str(Path(arquivo).resolve())
        if not any(isinstance(h, logging.FileHandler) and h.baseFilename == alvo for h in raiz.handlers):
            Path(arquivo).parent.mkdir(parents=True, exist_ok=True)
            h = logging.FileHandler(arquivo, encoding="utf-8")
            h.setFormatter(logging.Formatter(FORMATO))
            raiz.addHandler(h)


def console_utf8() -> None:
    """Saída do terminal em UTF-8 (acentos e "·" legíveis no console do Windows, que usa cp1252).

    Chamado no main() dos scripts que imprimem relatório. Sem efeito onde o console já é UTF-8;
    `errors="replace"` garante que um caractere fora do código de página nunca derruba o script.
    """
    import sys

    for fluxo in (sys.stdout, sys.stderr):
        if hasattr(fluxo, "reconfigure"):
            fluxo.reconfigure(encoding="utf-8", errors="replace")
