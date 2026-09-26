===========
Arquitetura
===========

Camadas
=======

.. code-block:: text

   ┌──────────────────────────────────────────────────────────────┐
   │  web/           interface: 11 painéis, SVG em JS puro        │
   │                 index.html · charts.js · api.js · app.js     │
   │                 views/{operacao,analise,confianca,mapa,clm}  │
   └───────────────────────────┬──────────────────────────────────┘
                               │  HTTP, envelope com proveniência
   ┌───────────────────────────▼──────────────────────────────────┐
   │  oraculo/api/   ASGI Starlette · 19 rotas                    │
   │                 app.py · service.py · service_mapa.py        │
   │                 service_clm.py · service_docs.py · envelope.py                 │
   └───────────────────────────┬──────────────────────────────────┘
   ┌───────────────────────────▼──────────────────────────────────┐
   │  modelos e análise                                           │
   │  models/        solar · mmgd · quantile · risk · baselines   │
   │                 decomposition                                │
   │  features/      construção de variáveis e pesos por grupo    │
   │  validation/    backtest cronológico · métricas              │
   │  triangulation/ três camadas e matriz de desempate           │
   │  vision/        ladrilhos · NMS · detectores · avaliação     │
   │  profiles/      classes de consumo · NNLS                    │
   │  substations/   registro georreferenciado · Mapa Inteligente │
   │  clm/           Modelo de Carga Composta: teoria e parâmetros│
   └───────────────────────────┬──────────────────────────────────┘
   ┌───────────────────────────▼──────────────────────────────────┐
   │  ingestão                                                    │
   │  ons/           ckan · csvio · cache (SHA-256) · catalog     │
   │  core/          frame (tabela colunar) · calendar_br         │
   └───────────────────────────┬──────────────────────────────────┘
                               ▼
              Portal de Dados Abertos do ONS (CKAN + CSV em S3)

Decisões de engenharia
======================

As oito decisões estão em ``01-ESPECIFICACAO/03-arquitetura.md`` (D1 a D8).
As de maior consequência:

.. list-table::
   :header-rows: 1
   :widths: 8 34 58

   * - #
     - Decisão
     - Porquê
   * - D1
     - Tabela colunar própria sobre ``numpy``, em vez de ``pandas``
     - PyPI bloqueado no ambiente-alvo. O ``Frame`` carrega ``Provenance``
       imutável junto com os dados, o que o ``pandas`` não faria de graça.
   * - D2
     - Cache com manifesto SHA-256
     - Auditoria: o mesmo recurso baixado duas vezes tem de ter o mesmo
       hash, ou o número mudou e isso precisa aparecer.
   * - D4
     - ``starlette`` em vez de ``fastapi``
     - Mesma base ASGI, presente no ambiente.
   * - D6
     - Envelope de proveniência **obrigatório** em toda resposta
     - Torna impossível publicar número sem origem: o envelope é montado
       pela camada de API, não pelo autor da rota.
   * - D7
     - Mixins para os módulos novos (``MapaMixin``, ``ClmMixin``,
       ``DocsMixin``)
     - Acrescentar painel não pode alterar o ``Service`` existente. As abas
       que já funcionavam continuam idênticas, e há teste que exige isso.
   * - D8
     - Gráficos em SVG escrito à mão
     - Sem CDN e sem biblioteca. Consequência: cada gráfico faz exatamente o
       que a análise pede, incluindo a banda P10/P90 e o marcador de
       ``Vstallbrk``.

Estrutura de diretórios
=======================

.. code-block:: text

   solucoes-grupo-24/
   ├── Backend/
   │   ├── oraculo/                 pacote Python do protótipo (API em /api/...)
   │   │   └── web_legado/          interface original em HTML/JS (servida em /legado)
   │   ├── tests_oraculo/           testes do protótipo
   │   ├── main.py                  sobe o serviço único (contrato + protótipo + docs + dashboard)
   │   ├── run_oraculo_legado.py    sobe só o serviço Starlette do protótipo
   │   └── run_oraculo_pipeline.py  execução em lote
   ├── Frontend/oraculo-dashboard/  dashboard React (telas do protótipo em src/oraculo/)
   └── docs/oraculo/
       ├── especificacao/           documentos rastreáveis ao deck
       └── documentacao_sphinx/     esta documentação (Sphinx)

Como um painel novo é acrescentado
==================================

O procedimento seguido nos quatro painéis mais recentes, e que a suíte de
testes protege:

#. **Módulo de domínio** em ``oraculo/<area>/`` — a lógica, com testes
   próprios.
#. **Mixin de fachada** em ``oraculo/api/service_<area>.py`` — não se toca no
   ``Service``; acrescenta-se à sua lista de bases.
#. **Rotas** em ``oraculo/api/app.py``, acrescentadas ao fim da lista.
#. **View** em ``web/js/views/<area>.js``, registrada em ``window.App.VIEWS``.
#. **Entrada no NAV** e ``<script>`` no ``index.html``.
#. **Teste de contrato** em ``tests/test_ui_contract.py``, que exige que as
   views originais continuem registradas nos seus arquivos de origem.

.. admonition:: O teste que impede regressão de interface
   :class: medido

   ``test_paineis_novos_nao_quebram_os_antigos`` fixa qual arquivo registra
   qual painel. Quando a aba de parametrização do CLM foi acrescentada, esse
   teste falhou primeiro — o que é exatamente o seu trabalho.
