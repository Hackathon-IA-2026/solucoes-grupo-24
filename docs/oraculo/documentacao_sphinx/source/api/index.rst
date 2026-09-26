=================
Contrato HTTP
=================

Serviço ASGI em Starlette. **Dezenove rotas de API**, todas devolvendo o
envelope de proveniência descrito em :doc:`../visao-geral/proveniencia`.

Convenções
==========

.. list-table::
   :header-rows: 1
   :widths: 24 76

   * - Convenção
     - Detalhe
   * - Base
     - ``http://127.0.0.1:8000``
   * - Tipo
     - ``application/json; charset=utf-8``, exceto as rotas de imagem
   * - Cache
     - ``Cache-Control: no-store`` — o cache é do lado do servidor, com
       manifesto auditável
   * - Erro
     - ``{"ok": false, "erro": "..."}`` com código HTTP apropriado;
       ``404`` para recurso inexistente
   * - Escrita
     - apenas ``POST /api/ingest``

Serviço e metadados
===================

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Rota
     - O que faz
   * - ``GET /api/health``
     - estado do serviço, modo corrente e disponibilidade de rede
   * - ``GET /api/meta``
     - versões, premissas versionadas e áreas disponíveis
   * - ``GET /api/provenance``
     - auditoria completa: relatórios de ingestão e manifesto de cache

Catálogo
========

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Rota
     - O que faz
   * - ``GET /api/catalog``
     - catálogo do Portal, conjuntos curados, fontes externas
   * - ``GET /api/catalog/{pkg}``
     - detalhe de um conjunto, com dicionário e recursos
   * - ``POST /api/ingest``
     - dispara ingestão · corpo ``{"force": false}``

Séries e modelos
================

.. list-table::
   :header-rows: 1
   :widths: 46 54

   * - Rota
     - O que faz
   * - ``GET /api/series?area=SE``
     - séries operativas ingeridas
   * - ``GET /api/decomposition?area=SE&hours=72``
     - carga global, supervisionada e MMGD estimada
   * - ``GET /api/forecast?area=SE&horizon=3h&asymmetric=1``
     - previsão quantílica com banda e desempenho no teste
   * - ``GET /api/profiles?area=SE``
     - perfis por dia-tipo e insumos agregados
   * - ``GET /api/risk?horizon=d1&level=estado&asymmetric=0``
     - probabilidade calibrada, montante esperado, razão e severidade
   * - ``GET /api/validation?area=SE&asymmetric=1``
     - backtest, baselines, métricas por patamar, calibração
   * - ``GET /api/triangulation``
     - três camadas, matriz de desempate, fator de correção

Parâmetros comuns
-----------------

.. list-table::
   :header-rows: 1
   :widths: 20 20 60

   * - Parâmetro
     - Valores
     - Efeito
   * - ``area``
     - ``SE``, ``S``, ``NE``, ``N``
     - subsistema
   * - ``horizon``
     - ``30min``, ``3h``, ``d1``
     - horizonte de previsão
   * - ``asymmetric``
     - ``0``, ``1``
     - liga a perda assimétrica por patamar
   * - ``level``
     - ``estado``, ``subsistema``
     - agregação territorial do risco

Mapa Inteligente
================

.. list-table::
   :header-rows: 1
   :widths: 46 54

   * - Rota
     - O que faz
   * - ``GET /api/mapa/substations``
     - lote de subestações de fronteira, com classe, MMGD e resumo do
       detector. Aceita ``limit``, ``offset``, ``uf``, ``subsystem``.
   * - ``GET /api/mapa/substations/{sub_id}``
     - detalhe, com detecções georreferenciadas e insumo ao CLM
   * - ``GET /api/mapa/scene/{sub_id}.png``
     - ortoimagem da amostra. Aceita ``overlay``, ``truth``, ``tiles``,
       ``channel``.
   * - ``GET /api/mapa/bench.png``
     - cena de referência do banco de ensaio
   * - ``GET /api/mapa/vision``
     - backends, banco de ensaio, curva P×R, calibração de área
   * - ``GET /api/mapa/classes``
     - perfis canônicos e decomposição NNLS por subsistema

.. admonition:: A lista de subestações vem em `rows`
   :class: important

   O payload de ``/api/mapa/substations`` entrega as linhas no campo
   ``rows``, não ``substations``. A primeira versão do painel de
   parametrização do CLM leu a chave errada e o seletor ficava vazio **sem
   erro visível** — há hoje um teste de contrato que amarra isso.

Modelo de Carga Composta
========================

.. list-table::
   :header-rows: 1
   :widths: 46 54

   * - Rota
     - O que faz
   * - ``GET /api/clm/spec``
     - estrutura, registro de 124 parâmetros, cobertura por procedência,
       critérios de aplicabilidade
   * - ``GET /api/clm/cartao``
     - cartão de parâmetros. Aceita ``sub_id``, ``ac_factor`` e a composição
       livre (``residencial``, ``comercial``, ``industrial``, ``rural``).
   * - ``GET /api/clm/curvas``
     - características estáticas amostradas. Aceita ``vstall``, ``rstall``,
       ``xstall``, ``vd1``, ``vd2``, ``frcel``, ``comppf``, ``p1c``,
       ``p1e``, ``p2c``, ``p2e``.
   * - ``GET /api/clm/validacao``
     - exemplo publicado do WECC, conferências independentes e limites

Ajuda contextual
================

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Rota
     - O que faz
   * - ``GET /api/docs/status``
     - estado da documentação embutida: se foi construída, o mapeamento
       painel → página, as páginas gerais e o comando de construção
   * - ``GET /docs/...``
     - a documentação Sphinx, servida pela própria aplicação. Montado apenas
       se ``docs/oraculo/documentacao_sphinx/build/html`` existir; caso contrário a rota
       explica como construí-la.

O diretório pode ser redirecionado pela variável ``ORACULO_DOCS``.

Estáticos
=========

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Rota
     - O que faz
   * - ``GET /``
     - a interface
   * - ``GET /css/*``, ``GET /js/*``
     - assets, servidos sem CDN

Exemplo de resposta
===================

.. code-block:: bash

   curl -s "http://127.0.0.1:8000/api/clm/validacao" | python -m json.tool

.. code-block:: json

   {
     "ok": true,
     "mode": "live",
     "data": {
       "exemplo_wecc": {
         "confere": true,
         "desvio_maximo": 0.0,
         "total_calculado": 0.36,
         "total_publicado": 0.36
       }
     },
     "provenance": [ "..." ],
     "notes": [ "..." ]
   }

Para aprofundar
===============

* Contrato detalhado: ``01-ESPECIFICACAO/05-api.md``
* Código: :doc:`../referencia/api`
