# -*- coding: utf-8 -*-
"""Ajuda sensivel ao contexto: a documentacao Sphinx servida pelo proprio app.

Mixin proprio, pelo mesmo motivo dos anteriores (decisao D7): acrescentar
ajuda nao pode alterar nada que ja funciona.

A ideia e simples e vale o trabalho: quem esta olhando um painel e tem uma
duvida nao deve precisar sair da aplicacao, procurar um diretorio e abrir um
arquivo. Aperta F1 e cai **na pagina daquele painel**.

O mapeamento painel -> pagina vive aqui, no servidor, e nao no JavaScript.
Assim ha um unico lugar a corrigir quando uma pagina e renomeada, e o teste
pode exigir que **todo** painel tenha pagina e que **todo** arquivo apontado
exista de fato.
"""
from __future__ import annotations

from .. import config

#: Painel da interface -> pagina da documentacao, relativa a raiz do HTML.
#:
#: As chaves sao exatamente os `id` do NAV em `web/js/app.js`. Ha teste que
#: exige a igualdade dos dois conjuntos: painel novo sem pagina de ajuda
#: reprova a suite, o que e o comportamento desejado.
DOC_MAP = {
    "operacao": "modulos/operacao/despacho-preditivo.html",
    "risco": "modulos/operacao/risco-e-excedentes.html",
    "pato": "modulos/operacao/curva-do-pato-tempo.html",
    "curtailment": "modulos/analise/curtailment.html",
    "perfis": "modulos/analise/perfis-e-clm.html",
    "triangulacao": "modulos/analise/triangulacao.html",
    "mapa": "modulos/mapa/perfis-por-subestacao.html",
    "visao": "modulos/mapa/visao-computacional.html",
    "classes": "modulos/mapa/classes-de-consumo.html",
    "clm": "modulos/mapa/parametrizacao-clm.html",
    "fronteira": "modulos/fronteira/se-x-distribuicao.html",
    "correlacao": "modulos/fronteira/qualidade-da-correlacao.html",
    "bess": "modulos/investimento/alocacao-de-bess.html",
    "bessmetodo": "modulos/investimento/metodo-e-sensibilidade.html",
    "projecao": "modulos/investimento/projecao-do-corte-ene.html",
    "validacao": "modulos/confianca/validacao.html",
    "dados": "modulos/confianca/dados-abertos.html",
}

#: Paginas de contexto geral, alcancaveis pela propria ajuda.
DOC_GERAL = {
    "inicio": "index.html",
    "como_ler": "visao-geral/como-ler-os-paineis.html",
    "proveniencia": "visao-geral/proveniencia.html",
    "arquitetura": "visao-geral/arquitetura.html",
    "limitacoes": "limitacoes.html",
    "glossario": "glossario.html",
    "api": "api/index.html",
    "referencia": "referencia/index.html",
}

#: Como construir, quando a documentacao ainda nao existe.
COMO_CONSTRUIR = "cd docs/oraculo/documentacao_sphinx && python build_docs.py"


class DocsMixin:
    """Estado da documentacao embutida."""

    def docs_payload(self) -> dict:
        """O que a interface precisa saber para abrir a ajuda.

        Inclui o mapeamento completo e, crucialmente, **se a documentacao foi
        construida**. Sem isso a tecla F1 abriria um quadro em branco e o
        usuario nao teria como saber por que -- o mesmo raciocinio da
        degradacao graciosa da ingestao: nunca falhar em silencio.
        """
        raiz = config.DOCS_DIR
        indice = raiz / "index.html"
        construida = indice.exists()

        faltando = []
        if construida:
            for painel, rel in DOC_MAP.items():
                if not (raiz / rel).exists():
                    faltando.append({"painel": painel, "pagina": rel})

        return {
            "disponivel": construida and not faltando,
            "construida": construida,
            "prefixo": config.DOCS_URL_PREFIX,
            "paineis": DOC_MAP,
            "geral": DOC_GERAL,
            "paginas_faltando": faltando,
            "diretorio": str(raiz),
            "como_construir": COMO_CONSTRUIR,
            "atalho": "F1",
            "nota": ("Documentacao Sphinx servida pela propria aplicacao. F1 "
                     "abre a pagina do painel corrente; Esc fecha."
                     if construida else
                     "Documentacao ainda nao construida. Execute: %s"
                     % COMO_CONSTRUIR),
        }

    @staticmethod
    def doc_url_for(panel_id: str) -> str:
        """URL da pagina de ajuda de um painel, com recuo para a capa."""
        rel = DOC_MAP.get(panel_id) or DOC_GERAL["inicio"]
        return "%s/%s" % (config.DOCS_URL_PREFIX.rstrip("/"), rel)
