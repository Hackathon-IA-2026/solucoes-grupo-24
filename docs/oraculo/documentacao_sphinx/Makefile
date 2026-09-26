# Makefile da documentacao do O.R.A.C.U.L.O.
#
# Em Windows sem ferramentas GNU, use `python build_docs.py` ou `make.bat`.

SPHINXBUILD   ?= python -m sphinx
SOURCEDIR     = source
BUILDDIR      = build
SPHINXOPTS    ?=

export ORACULO_OFFLINE = 1

.PHONY: help html strict clean linkcheck open

help:
	@$(SPHINXBUILD) -M help "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS)

html:
	@$(SPHINXBUILD) -b html -d "$(BUILDDIR)/doctrees" "$(SOURCEDIR)" "$(BUILDDIR)/html" $(SPHINXOPTS)
	@echo "Pronto: $(BUILDDIR)/html/index.html"

strict:
	@$(SPHINXBUILD) -b html -W --keep-going -d "$(BUILDDIR)/doctrees" "$(SOURCEDIR)" "$(BUILDDIR)/html" $(SPHINXOPTS)

clean:
	@rm -rf "$(BUILDDIR)"

open: html
	@python -c "import webbrowser,pathlib; webbrowser.open(pathlib.Path(\"$(BUILDDIR)/html/index.html\").resolve().as_uri())"
