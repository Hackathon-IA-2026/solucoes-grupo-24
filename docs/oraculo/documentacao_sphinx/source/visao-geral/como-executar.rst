==============
Como executar
==============

Requisitos
==========

Nenhuma instalação é necessária no ambiente-alvo. O protótipo usa apenas
``numpy``, ``scipy``, ``starlette``, ``uvicorn``, ``httpx``, ``pydantic`` e
``pytest``.

.. admonition:: Por que não pandas, scikit-learn ou biblioteca de gráficos
   :class: premissa

   A rede corporativa tem proxy com certificado próprio, o que bloqueia o
   PyPI (``CERTIFICATE_VERIFY_FAILED``). **A solução precisa rodar onde o
   problema existe.** Consequências deliberadas:

   .. list-table::
      :header-rows: 1
      :widths: 28 40 32

      * - Em vez de
        - Usamos
        - Onde
      * - ``pandas``
        - tabela colunar própria sobre ``numpy``
        - ``oraculo/core/frame.py``
      * - ``scikit-learn``
        - regressão quantílica e logística em ``numpy``/``scipy``
        - ``oraculo/models/``
      * - biblioteca de gráficos
        - primitivos SVG em JavaScript puro
        - ``web/js/charts.js``
      * - ``fastapi``
        - ``starlette`` (mesma base ASGI)
        - ``oraculo/api/app.py``

   Ganho colateral: a **perda assimétrica por patamar** — o diferencial
   declarado da solução — não existe pronta em biblioteca alguma. Escrevê-la
   foi necessário de todo modo.

Subir a aplicação
=================

.. code-block:: bash

   cd Backend
   python main.py                       # serviço único: dashboard React + APIs + esta ajuda

   # (opcional) só o serviço do protótipo, com a interface original em HTML/JS
   python run_oraculo_legado.py --open --port 9000

A interface fica em http://127.0.0.1:8000/ (dashboard React; compile antes com
``npm run build`` em ``Frontend/oraculo-dashboard``). A interface original do
protótipo continua em http://127.0.0.1:8000/legado.

Execução em lote, sem interface
===============================

.. code-block:: bash

   python run_pipeline.py --area SE      # relatório completo no terminal
   python run_pipeline.py --demo         # força o modo demonstrativo
   python run_pipeline.py --json         # imprime os payloads brutos

Testes
======

.. code-block:: bash

   python -m pytest                  # 404 testes
   python -m pytest -m network       # inclui o teste que fala com o Portal

Os três modos de operação
=========================

O campo ``mode`` declara, em **toda** resposta da API, de onde veio o número.

.. list-table::
   :header-rows: 1
   :widths: 14 36 50

   * - Modo
     - Origem
     - Quando ocorre
   * - ``live``
     - Portal de Dados Abertos do ONS, agora
     - rede disponível
   * - ``cache``
     - ``.cache/`` local, com hash SHA-256 registrado
     - sem rede, com extração anterior
   * - ``demo``
     - gerador determinístico
     - sem rede e sem cache, ou ``ORACULO_OFFLINE=1``

.. code-block:: bash

   ORACULO_OFFLINE=1 python main.py

Todos os painéis carregam com dados sintéticos determinísticos, rotulados com
o selo ``DADOS DEMONSTRATIVOS``. Útil para apresentar sem rede.

.. admonition:: Degradação graciosa
   :class: important

   A aplicação nunca fica fora do ar. Sem rede, cai para o cache; sem cache,
   para o gerador determinístico. O que **não** acontece em nenhum caso é
   exibir número sem dizer de onde ele veio.
