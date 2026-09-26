# -*- coding: utf-8 -*-
"""Testes da ajuda contextual (tecla F1).

O teste que mais importa aqui e
`test_todo_painel_tem_pagina_de_ajuda`: ele amarra o NAV da interface ao
mapeamento do servidor. Painel novo sem pagina de ajuda reprova a suite, que
e exatamente o comportamento desejado -- a alternativa e descobrir o furo
quando alguem aperta F1 durante a apresentacao.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from oraculo import config
from oraculo.api import service_docs as SD
from oraculo.api.service import SERVICE

WEB_DIR = config.WEB_DIR


# ---------------------------------------------------------------------------
# Mapeamento
# ---------------------------------------------------------------------------

def _nav_ids() -> set[str]:
    """Os `id` de painel declarados no NAV da interface."""
    src = (WEB_DIR / "js" / "app.js").read_text(encoding="utf-8")
    bloco = re.search(r"const NAV = \[(.*?)\];", src, re.S)
    assert bloco, "NAV nao encontrado em app.js"
    return set(re.findall(r'\{\s*id:\s*"([a-z]+)"', bloco.group(1)))


def test_todo_painel_tem_pagina_de_ajuda():
    """O mapeamento cobre exatamente os paineis do NAV.

    Igualdade, nao inclusao: pagina de ajuda para painel que nao existe e
    tao ruim quanto painel sem ajuda -- indica que uma das duas pontas ficou
    para tras numa renomeacao.
    """
    nav = _nav_ids()
    mapeados = set(SD.DOC_MAP)
    assert nav == mapeados, {
        "sem ajuda": sorted(nav - mapeados),
        "ajuda orfa": sorted(mapeados - nav),
    }


def test_mapeamento_aponta_para_html_dentro_da_arvore():
    """Nenhum caminho absoluto, nenhuma subida de diretorio."""
    for painel, rel in SD.DOC_MAP.items():
        assert rel.endswith(".html"), (painel, rel)
        assert not rel.startswith("/"), (painel, rel)
        assert ".." not in rel, (painel, rel)


def test_paginas_gerais_tambem_sao_relativas():
    for chave, rel in SD.DOC_GERAL.items():
        assert rel.endswith(".html"), (chave, rel)
        assert not rel.startswith("/") and ".." not in rel, (chave, rel)
    assert "inicio" in SD.DOC_GERAL


def test_url_de_painel_desconhecido_cai_na_capa():
    """Recuo silencioso, mas para algo util -- nunca para um 404."""
    url = SERVICE.doc_url_for("painel-que-nao-existe")
    assert url == config.DOCS_URL_PREFIX + "/" + SD.DOC_GERAL["inicio"]


def test_url_de_painel_conhecido():
    url = SERVICE.doc_url_for("clm")
    assert url == config.DOCS_URL_PREFIX + "/" + SD.DOC_MAP["clm"]
    assert url.startswith("/docs/")


# ---------------------------------------------------------------------------
# Payload
# ---------------------------------------------------------------------------

def test_payload_declara_o_estado_da_documentacao():
    d = SERVICE.docs_payload()
    for chave in ("disponivel", "construida", "prefixo", "paineis", "geral",
                  "paginas_faltando", "diretorio", "como_construir",
                  "atalho", "nota"):
        assert chave in d, chave
    assert d["atalho"] == "F1"
    assert isinstance(d["construida"], bool)
    assert d["paineis"] == SD.DOC_MAP


def test_payload_nunca_falha_em_silencio():
    """Sem documentacao construida, a nota diz como construi-la.

    E a mesma disciplina da ingestao: degradar, mas explicando. Um quadro de
    ajuda em branco seria pior do que nao ter ajuda.
    """
    d = SERVICE.docs_payload()
    if not d["construida"]:
        assert SD.COMO_CONSTRUIR in d["nota"]
        assert not d["disponivel"]
    else:
        assert "F1" in d["nota"]


@pytest.mark.skipif(not (config.DOCS_DIR / "index.html").exists(),
                    reason="documentacao nao construida neste ambiente")
def test_quando_construida_todas_as_paginas_existem():
    """Cada caminho mapeado corresponde a um arquivo real."""
    d = SERVICE.docs_payload()
    assert d["paginas_faltando"] == [], d["paginas_faltando"]
    assert d["disponivel"]
    for rel in list(SD.DOC_MAP.values()) + list(SD.DOC_GERAL.values()):
        assert (config.DOCS_DIR / rel).exists(), rel


# ---------------------------------------------------------------------------
# Rota e montagem
# ---------------------------------------------------------------------------

def test_rota_de_estado_responde_com_envelope(client):
    r = client.get("/api/docs/status")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert "provenance" in body
    assert body["data"]["atalho"] == "F1"


@pytest.mark.skipif(not (config.DOCS_DIR / "index.html").exists(),
                    reason="documentacao nao construida neste ambiente")
def test_documentacao_e_servida_pelo_proprio_app(client):
    r = client.get("/docs/index.html")
    assert r.status_code == 200
    assert "html" in r.headers.get("content-type", "")


@pytest.mark.skipif(not (config.DOCS_DIR / "index.html").exists(),
                    reason="documentacao nao construida neste ambiente")
def test_pagina_do_painel_clm_e_alcancavel(client):
    r = client.get(SERVICE.doc_url_for("clm"))
    assert r.status_code == 200
    assert "CMPLDW" in r.text or "Carga Composta" in r.text


def test_montar_docs_nunca_derruba_as_rotas_existentes(client):
    """A ajuda e acessorio; o painel e o essencial.

    `StaticFiles` valida o diretorio na criacao, e montar um caminho ausente
    derrubaria a aplicacao inteira na subida. Este teste confirma que as
    rotas centrais seguem de pe seja qual for o estado da documentacao.
    """
    for rota in ("/api/health", "/api/meta", "/legado"):
        assert client.get(rota).status_code == 200


# ---------------------------------------------------------------------------
# Contrato da interface
# ---------------------------------------------------------------------------

def test_app_js_liga_f1_e_escape():
    src = (WEB_DIR / "js" / "app.js").read_text(encoding="utf-8")
    assert 'ev.key === "F1"' in src
    assert 'ev.key === "Escape"' in src
    # Sem preventDefault o navegador abre a propria ajuda e o usuario perde o
    # contexto -- o motivo de o atalho existir.
    assert "ev.preventDefault()" in src
    assert "bindHelpKeys()" in src


def test_app_js_consulta_o_mapeamento_no_servidor():
    """O mapeamento nao pode estar duplicado no cliente."""
    src = (WEB_DIR / "js" / "app.js").read_text(encoding="utf-8")
    assert 'Api.get("docs/status")' in src
    # Nenhum caminho de pagina escrito a mao no JavaScript.
    for rel in SD.DOC_MAP.values():
        assert rel not in src, rel


def test_app_js_tem_botao_de_ajuda_na_barra():
    src = (WEB_DIR / "js" / "app.js").read_text(encoding="utf-8")
    assert 'id="btn-help"' in src
    assert "F1" in src


def test_css_tem_o_painel_de_ajuda():
    css = (WEB_DIR / "css" / "oraculo.css").read_text(encoding="utf-8")
    for classe in (".help-overlay", ".help-panel", ".help-foot",
                   "body.help-locked"):
        assert classe in css, classe


def test_ajuda_exportada_no_objeto_app():
    src = (WEB_DIR / "js" / "app.js").read_text(encoding="utf-8")
    for nome in ("openHelp", "closeHelp", "toggleHelp"):
        assert nome in src, nome


def test_config_tem_diretorio_da_documentacao():
    assert isinstance(config.DOCS_DIR, Path)
    assert config.DOCS_URL_PREFIX == "/docs"
    # Fora de ROOT de proposito: e um diretorio irmao, com ciclo de vida
    # proprio. Se estivesse dentro, um `--clean` da documentacao poderia
    # alcancar o prototipo.
    assert config.ROOT not in config.DOCS_DIR.parents
