===========================
Proveniência de cada número
===========================

A regra
=======

.. admonition:: Obrigatório, não opcional
   :class: important

   **Toda** resposta da API carrega o envelope ``provenance``. Ele é montado
   pela camada de API, não pelo autor da rota — não há como publicar número
   sem origem.

Forma do envelope
=================

.. code-block:: json

   {
     "ok": true,
     "mode": "live",
     "data": { "...": "o conteúdo da rota" },
     "provenance": [
       {
         "dataset": "balanco-energia-subsistema",
         "resource": "BALANCO_ENERGIA_SUBSISTEMA_2026_09.csv",
         "mode": "live",
         "rows": 17544,
         "bytes_read": 2841600,
         "fetched_at": "2026-09-14T11:22:05Z",
         "lag_note": "publicação com defasagem típica de 1 dia"
       }
     ],
     "notes": ["..."]
   }

Campo por campo
===============

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Campo
     - O que significa
   * - ``dataset``
     - Identificador do conjunto no Portal de Dados Abertos do ONS.
   * - ``resource``
     - Recurso específico — em geral o CSV de um ano/mês.
   * - ``mode``
     - ``live``, ``cache`` ou ``demo``, **por recurso**. Uma resposta pode
       misturar: carga do cache e restrição ao vivo.
   * - ``rows``
     - Linhas efetivamente lidas. Uma queda brusca aqui é o primeiro sinal
       de que a publicação mudou de formato.
   * - ``bytes_read``
     - Volume lido. O protótipo usa requisições ``Range`` para não baixar
       arquivos inteiros quando só precisa do trecho recente.
   * - ``fetched_at``
     - Instante da extração, em UTC.
   * - ``lag_note``
     - **Defasagem conhecida da publicação.** É o campo que impede confundir
       "o dado não existe" com "o dado ainda não foi publicado".

Onde a proveniência aparece na tela
===================================

Ao pé de **cada** painel há um bloco recolhível *Proveniência e notas*, com
uma linha por recurso usado naquela tela. O painel
:doc:`../modulos/confianca/dados-abertos` traz a auditoria completa,
incluindo o manifesto de cache.

O manifesto de cache
====================

Todo recurso baixado entra em ``.cache/`` e é registrado em
``manifest.json`` com:

* **hash SHA-256** do conteúdo;
* tamanho em bytes;
* instante de extração;
* URL de origem.

.. admonition:: Por que o hash importa
   :class: medido

   Permite responder a uma pergunta que costuma ficar sem resposta: *este
   número mudou porque o modelo mudou, ou porque o dado mudou?* Se o hash do
   recurso é o mesmo, o dado é o mesmo — e a diferença está no código.

Os conjuntos usados
===================

.. list-table::
   :header-rows: 1
   :widths: 34 24 42

   * - Conjunto
     - Granularidade
     - Uso
   * - ``balanco-energia-subsistema``
     - horária, por subsistema
     - carga verificada e geração por fonte — espinha dorsal
   * - ``curva-carga``
     - horária, por subsistema
     - conferência cruzada da carga
   * - ``restricao_coff_fotovoltaica``
     - semi-horária, por usina
     - rótulo do risco de curtailment
   * - ``restricao_coff_eolica_usi``
     - semi-horária, por usina
     - rótulo, fonte eólica
   * - ``subestacao``
     - cadastral, por subestação
     - subestações georreferenciadas — entrada do Mapa Inteligente
   * - ``capacidade-transformacao``
     - cadastral, por transformador
     - área de influência e identificação da fronteira T–D
   * - ``modalidade-usina``
     - cadastral, por usina
     - usinas Tipo III conectadas à distribuição

Os 85 conjuntos do Portal são navegáveis no painel
:doc:`../modulos/confianca/dados-abertos`.
