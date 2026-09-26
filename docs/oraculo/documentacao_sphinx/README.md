# Documentação do O.R.A.C.U.L.O.

Documentação da aplicação, gerada com **Sphinx**.

**Equipe 24 — LINKFY** · Hackathon IA COPPE/UFRJ 2026

---

## Como construir

```bash
cd 03-DOCUMENTACAO

python build_docs.py --open      # constrói e abre no navegador
python build_docs.py --strict    # trata aviso como erro
python build_docs.py --clean     # reconstrói do zero
python build_docs.py --check     # só verifica o ambiente

make html                        # equivalente, se `make` existir
.\make.bat html                  # equivalente no Windows
```

A saída fica em `build/html/index.html`.

**O `build_docs.py` existe por dois motivos.** `make` não está garantido no
ambiente-alvo (Windows, sem ferramentas GNU), e `sphinx-build` pode não estar
no `PATH` mesmo com o Sphinx instalado — invocar `python -m sphinx` resolve os
dois casos. Ele também verifica o ambiente antes e dá uma mensagem útil se
faltar pacote, em vez de deixar o Sphinx falhar com erro obscuro.

## Construção offline

A documentação constrói **sem rede**:

- `intersphinx` fica deliberadamente de fora — exigiria baixar inventários
  durante a construção, e o proxy corporativo bloqueia;
- o `autodoc` importa o pacote `oraculo` com `ORACULO_OFFLINE=1`, para que a
  leitura das docstrings não dispare ingestão no Portal do ONS.

Estado atual: **build succeeded** em modo estrito (`-W`), **zero avisos**.

## Como está organizada

A navegação **espelha a da aplicação**: os quatro módulos são os quatro grupos
da barra lateral do painel, e cada subseção é uma aba.

```
source/
├── index.rst                 capa, princípio de projeto, mapa dos 11 painéis
├── visao-geral/
│   ├── o-que-e.rst           problema, produtos, escopo e não-escopo
│   ├── como-executar.rst     execução, dependências, os três modos
│   ├── arquitetura.rst       camadas, decisões D1–D8, como se acrescenta painel
│   ├── proveniencia.rst      o envelope obrigatório, campo a campo
│   └── como-ler-os-paineis.rst   a chave de leitura — vale mais que qualquer painel
├── modulos/
│   ├── operacao/             despacho preditivo · risco e excedentes
│   ├── analise/              curtailment · perfis e CLM · triangulação
│   ├── mapa/                 perfis por subestação · visão computacional ·
│   │                         classes de consumo · parametrização CLM
│   └── confianca/            validação · dados abertos
├── api/index.rst             contrato HTTP das 19 rotas
├── referencia/               autodoc do pacote `oraculo`, em 11 grupos
├── limitacoes.rst            L1–L7, R1–R7, C1–C8 e o que resolveria cada uma
└── glossario.rst             termos do setor e do modelo
```

**38 páginas**, sendo **11 de painel** — uma por aba da aplicação — e 12
de referência do código.

## O que cada página de painel contém

Padrão seguido nas onze:

1. **A pergunta que o painel responde**, em uma frase.
2. **Rotas consumidas**, com o que cada uma traz.
3. **Controles**, quando há.
4. **Os KPIs**, um por um, com unidade e como ler.
5. **Cada cartão da tela**, na ordem em que aparece, com o significado de cada
   número e o método por trás.
6. **Os erros encontrados e corrigidos** naquele painel, quando houve — em
   bloco destacado.
7. **Limitações específicas** do painel.
8. **Para aprofundar**, com links à especificação e ao código.

## Relação com os outros diretórios

| Diretório | Papel |
|---|---|
| `01-ESPECIFICACAO/` | **O que se pretende construir** — requisitos, arquitetura, modelos, rastreabilidade ao deck. 12 documentos. |
| `02-PROTOTIPO/` | **O que foi construído** — código, 422 testes, interface. |
| `03-DOCUMENTACAO/` | **Como usar e como ler** o que foi construído. Este diretório. |

A seção `referencia/` não duplica descrição: usa `autodoc` para ler as
**docstrings do próprio código**. Não há duas descrições que possam divergir.

## Embutida na aplicação

Depois de construída, esta documentação é servida pelo próprio serviço em
`/docs`, e a tecla **`F1`** abre, de qualquer painel, a página correspondente
àquele painel. O mapeamento vive em `02-PROTOTIPO/oraculo/api/service_docs.py`
e é verificado por `tests/test_docs.py`.

## Dependências

Já presentes no ambiente: `sphinx` 9.1.0, `sphinx-rtd-theme` 3.1.0,
`docutils`, `jinja2`, `pygments`.

Nada precisa ser instalado. Se algo faltar, `python build_docs.py --check`
diz o quê — e não tenta instalar, porque o PyPI está bloqueado por proxy
neste ambiente (`CERTIFICATE_VERIFY_FAILED`) e a tentativa só produziria um
erro de certificado confuso.
