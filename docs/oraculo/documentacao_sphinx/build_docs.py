#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Constroi a documentacao do O.R.A.C.U.L.O. com Sphinx.

Existe porque `make` nao esta garantido no ambiente-alvo (Windows, sem
ferramentas GNU) e porque `sphinx-build` pode nao estar no PATH mesmo com o
Sphinx instalado -- invocar `python -m sphinx` resolve os dois casos.

    python build_docs.py            # constroi
    python build_docs.py --open     # constroi e abre no navegador
    python build_docs.py --strict   # trata aviso como erro
    python build_docs.py --clean    # apaga build/ antes
    python build_docs.py --check    # so verifica o ambiente e sai
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import webbrowser
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
FONTE = RAIZ / "source"
SAIDA = RAIZ / "build" / "html"
DOCTREES = RAIZ / "build" / "doctrees"

#: Pacotes exigidos, com o nome de importacao e o de distribuicao.
REQUISITOS = [
    ("sphinx", "sphinx"),
    ("sphinx_rtd_theme", "sphinx-rtd-theme"),
    ("docutils", "docutils"),
    ("jinja2", "jinja2"),
    ("pygments", "pygments"),
]


def verificar_ambiente() -> list[str]:
    """Confere o que falta, sem tentar instalar.

    Nao tenta instalar de proposito: o PyPI esta bloqueado por proxy neste
    ambiente, e uma tentativa de instalacao so produziria um erro de
    certificado confuso em vez da mensagem util que esta funcao imprime.
    """
    faltando = []
    for modulo, dist in REQUISITOS:
        try:
            __import__(modulo)
        except ImportError:
            faltando.append(dist)
    return faltando


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--open", action="store_true", dest="abrir",
                   help="abre o resultado no navegador")
    p.add_argument("--strict", action="store_true",
                   help="trata aviso como erro (-W)")
    p.add_argument("--clean", action="store_true",
                   help="apaga build/ antes de construir")
    p.add_argument("--check", action="store_true",
                   help="apenas verifica o ambiente")
    p.add_argument("--builder", default="html",
                   help="construtor do Sphinx (padrao: html)")
    args = p.parse_args()

    faltando = verificar_ambiente()
    if faltando:
        print("Faltam pacotes para construir a documentacao:", file=sys.stderr)
        for d in faltando:
            print("  -", d, file=sys.stderr)
        print("\nO PyPI esta bloqueado pelo proxy corporativo neste ambiente "
              "(CERTIFICATE_VERIFY_FAILED).\nInstale em uma rede sem "
              "interceptacao de TLS, ou use um espelho interno.",
              file=sys.stderr)
        return 2

    import sphinx  # noqa: E402  (depois da verificacao, de proposito)
    print("Sphinx %s · fonte %s" % (sphinx.__display_version__, FONTE))
    if args.check:
        print("Ambiente completo.")
        return 0

    if args.clean and (RAIZ / "build").exists():
        # `ignore_errors` nao e desleixo: o projeto vive numa pasta do
        # OneDrive, que mantem arquivos abertos enquanto sincroniza e faz o
        # rmtree falhar com WinError 5. O Sphinx reconstroi por cima do que
        # sobrar, e o aviso abaixo diz se algo ficou.
        shutil.rmtree(RAIZ / "build", ignore_errors=True)
        if (RAIZ / "build").exists():
            print("aviso: build/ nao foi removido por completo (arquivo em "
                  "uso, tipico de pasta sincronizada). A construcao segue.")
        else:
            print("build/ removido")

    # As opcoes vao DEPOIS de "sphinx": inseri-las antes faz o Python
    # interpretar `-W` como opcao dele mesmo, e o comando quebra sem
    # mensagem util. Foi o que aconteceu na primeira versao deste script.
    cmd = [sys.executable, "-m", "sphinx", "-b", args.builder]
    if args.strict:
        cmd += ["-W", "--keep-going"]
    cmd += ["-d", str(DOCTREES), str(FONTE), str(SAIDA)]

    env = dict(os.environ)
    env.setdefault("ORACULO_OFFLINE", "1")   # autodoc importa sem tocar a rede

    print("$", " ".join(cmd))
    r = subprocess.run(cmd, env=env)
    if r.returncode != 0:
        print("\nConstrucao falhou (codigo %d)." % r.returncode, file=sys.stderr)
        return r.returncode

    indice = SAIDA / "index.html"
    print("\nPronto: %s" % indice)
    if args.abrir and indice.exists():
        webbrowser.open(indice.as_uri())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
