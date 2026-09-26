# -*- coding: utf-8 -*-
"""Configuracao do Sphinx para a documentacao do O.R.A.C.U.L.O.

Duas decisoes que valem explicacao:

* **`default_role = "literal"`.** As docstrings do prototipo usam crase
  simples para nomes de campo e de funcao (`Fma`, `build_card`). Com o papel
  padrao do Sphinx isso viraria referencia de titulo; com `literal`, vira
  codigo, que e o que se quer. Ou seja: as docstrings ja escritas renderizam
  bem sem serem reescritas.

* **`ORACULO_OFFLINE = 1`.** O `autodoc` importa os modulos para ler as
  docstrings. Sem essa variavel, a importacao poderia disparar ingestao no
  Portal do ONS e tornar a construcao da documentacao dependente de rede.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# O pacote `oraculo` vive em Backend/ do repositorio (docs/oraculo/documentacao_sphinx/source
# -> parents[4] = raiz do repositorio).
ROOT = Path(__file__).resolve().parents[4]
PROTOTIPO = ROOT / "Backend"
sys.path.insert(0, str(PROTOTIPO))

# Construcao sempre offline e deterministica.
os.environ.setdefault("ORACULO_OFFLINE", "1")

# ---------------------------------------------------------------- projeto

project = "O.R.A.C.U.L.O."
author = "Equipe 24 — LINKFY"
copyright = "2026, Equipe 24 — LINKFY · Hackathon IA COPPE/UFRJ"
version = "1.0"
release = "1.0"
language = "pt_BR"

# ------------------------------------------------------------- extensoes

extensions = [
    "sphinx.ext.autodoc",       # docstrings do pacote `oraculo`
    "sphinx.ext.napoleon",      # secoes de docstring em prosa
    "sphinx.ext.viewcode",      # link do simbolo para o codigo-fonte
    "sphinx.ext.autosummary",   # tabelas-resumo de modulo
    "sphinx.ext.mathjax",       # equacoes do CLM e dos modelos
    "sphinx.ext.todo",
]

# `intersphinx` fica deliberadamente de fora: exigiria rede na construcao, e
# o proxy corporativo a bloqueia. A documentacao constroi offline.

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

default_role = "literal"
primary_domain = "py"
numfig = True
today_fmt = "%d/%m/%Y"

# --------------------------------------------------------------- autodoc

autodoc_default_options = {
    "members": True,
    "undoc-members": False,
    "show-inheritance": True,
    "member-order": "bysource",
}
autodoc_typehints = "description"
autodoc_preserve_defaults = True
autosummary_generate = False

napoleon_google_docstring = True
napoleon_numpy_docstring = True
napoleon_include_init_with_doc = True

# ------------------------------------------------------------------ HTML

html_theme = "sphinx_rtd_theme"
html_title = "O.R.A.C.U.L.O. — documentação"
html_short_title = "O.R.A.C.U.L.O."
html_static_path = ["_static"]
html_css_files = ["oraculo.css"]
html_show_sourcelink = True
html_copy_source = False

html_theme_options = {
    "navigation_depth": 4,
    "collapse_navigation": False,
    "sticky_navigation": True,
    "titles_only": False,
    "style_external_links": True,
}

html_context = {"display_github": False}

# ------------------------------------------------------------------ TODO

todo_include_todos = True
