=======================================
Perfis representativos e insumos ao CLM
=======================================

.. rubric:: Módulo Análise · aba ``#perfis``

**Pergunta que responde:** qual é a forma típica da carga e da MMGD por
dia-tipo, e que grandezas agregadas isso oferece à modelagem de carga?

Subtítulo na tela: *eixo 1 — caracterizar perfis de consumo e a presença da
geração distribuída*.

Rota consumida
==============

``GET /api/profiles?area=SE``

.. admonition:: Este painel e o de parametrização do CLM
   :class: important

   Este painel caracteriza **perfis agregados por subsistema** e propõe
   grandezas de entrada. O painel :doc:`../mapa/parametrizacao-clm` emite o
   **cartão de parâmetros do CMPLDW**, campo a campo, com procedência. Este é
   o insumo; aquele é o produto.

Os quatro KPIs
==============

.. list-table::
   :header-rows: 1
   :widths: 30 14 56

   * - KPI
     - Unidade
     - Como ler
   * - **Fator de carga**
     - —
     - Razão entre carga média e carga de pico. Quanto mais próximo de 1,
       mais plana a curva — assinatura de predominância industrial.
   * - **Penetração solar no pico**
     - %
     - Participação da geração solar no instante de maior carga. Distingue a
       área onde a solar alivia a ponta daquela onde ela já saiu.
   * - **Âncora noturna**
     - MWmed
     - Nível de carga na madrugada, quando a MMGD é nula por construção. É a
       referência que separa carga de geração distribuída.
   * - **Rampa máxima**
     - MW/h
     - Maior variação horária no perfil típico. Dimensiona a exigência de
       flexibilidade.

Cartão · Perfis por dia-tipo, com quantis
=========================================

Curvas de 24 h por dia-tipo — útil, sábado, domingo e feriado — com banda de
quantis em torno da mediana.

.. admonition:: Por que dia-tipo e não média
   :class: premissa

   A média de todos os dias produz uma curva que não corresponde a nenhum dia
   real: mistura o platô de expediente com o fim de semana. Os dias-tipo
   preservam a forma.

   Os feriados nacionais móveis são calculados pelo algoritmo de
   Meeus/Butcher para a Páscoa, em ``oraculo/core/calendar_br.py``, e os
   fixos por tabela. Feriado tratado como dia útil distorceria o perfil
   comercial.

Cartão · Perfil de MMGD estimada por dia-tipo
=============================================

A mesma decomposição, restrita à parcela estimada de geração distribuída.
A forma é governada pela geometria solar; a amplitude, pela capacidade
instalada e pelo fator de nebulosidade.

.. admonition:: Um erro grande que este cartão expôs
   :class: medido

   A primeira versão estimava a MMGD por extrapolação ancorada na noite. O
   resultado dava pico de **8,1 GW** no Sudeste — implausível. A causa é
   estrutural: a extrapolação ancorada na noite é mal condicionada, porque as
   harmônicas diárias são identificadas fora do suporte em que a geração
   existe.

   A substituição pelo **método do envelope** — percentil 90 da carga por
   mês, dia-tipo e hora — levou o pico a **12,5 GW**, com participação de
   **23%**, compatível com a capacidade instalada declarada.

Cartão · Insumos agregados propostos
====================================

Lista de estatísticas com as grandezas que a caracterização oferece à
modelagem de carga: fator de carga, participação da MMGD, âncora noturna,
amplitude diária, rampa.

.. admonition:: O que estes números são, e o que não são
   :class: limite

   São **grandezas observadas** que o especialista usa ao escolher a
   composição do modelo de carga. **Não são parâmetros prontos para
   simulação.** A distinção está escrita no próprio payload, no campo
   ``aviso``, e é a mesma disciplina do painel
   :doc:`../mapa/parametrizacao-clm`.

Decomposição da carga
=====================

A identidade verificada por teste, com resíduo nulo:

.. math::

   \text{carga global} = \text{carga supervisionada} + \text{MMGD estimada}

Derivados publicados: participação máxima da MMGD, mínima supervisionada e a
hora em que ocorre, amplitude diária, maior rampa.

Limitações específicas
======================

.. admonition:: O que este painel não afirma
   :class: limite

   * A MMGD é **estimada**, com viés conservador declarado — um piso.
   * Os perfis são **por subsistema**. Não existe curva de carga por
     subestação em dado aberto; essa limitação percorre todo o Mapa
     Inteligente e está registrada como R3 na especificação do desafio.
   * Os quantis descrevem a **variabilidade histórica** da forma, não
     incerteza de previsão. A incerteza preditiva está em
     :doc:`../operacao/despacho-preditivo`.

Para aprofundar
===============

* Decomposição em classes de consumo: :doc:`../mapa/classes-de-consumo`
* Cartão de parâmetros do CMPLDW: :doc:`../mapa/parametrizacao-clm`
* Modelos: ``01-ESPECIFICACAO/06-modelos-analiticos.md``
* Código: :doc:`../../referencia/models`
