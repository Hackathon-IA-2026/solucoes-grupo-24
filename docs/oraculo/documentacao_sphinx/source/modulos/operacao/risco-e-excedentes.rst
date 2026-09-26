=============================================
Risco de curtailment e excedentes
=============================================

.. rubric:: Módulo Operação · aba ``#risco``

**Pergunta que responde:** onde há risco de curtailment nas próximas horas,
qual o montante esperado, e por qual razão?

Subtítulo na tela: *localizar · priorizar · explicar e recomendar, com
rastreabilidade*.

Rota consumida
==============

``GET /api/risk?horizon=d1&level=estado&asymmetric=0``

O parâmetro ``level`` controla a agregação territorial; ``horizon`` acompanha
o seletor do painel (30 min, 3 h ou D+1).

Os quatro KPIs
==============

.. list-table::
   :header-rows: 1
   :widths: 34 16 50

   * - KPI
     - Unidade
     - Como ler
   * - **Áreas com risco ≥ 50%**
     - contagem
     - Quantas áreas, do total avaliado, têm probabilidade calibrada de
       restrição acima de 50%.
   * - **Potência esperada de corte**
     - MW
     - Soma de :math:`E[\text{corte}]` sobre as áreas. Não é o pior caso: é
       o valor esperado.
   * - **Predominância de razão energética**
     - contagem de áreas
     - Em quantas áreas a razão **ENE** predomina. É o recorte que o eixo
       (ii) da solução persegue.
   * - **AUC fora da amostra (mediana)**
     - —
     - Desempenho do classificador. Mediana entre as áreas, medida em
       conjunto de teste cronológico.

O montante esperado
===================

.. math::

   E[\text{corte}] = P(\text{restrição}) \times \text{mediana condicional do corte}

Dois fatores independentes: a probabilidade de haver restrição e, **dado que
haja**, a mediana histórica do montante. Multiplicá-los evita o erro de
reportar o pior caso como se fosse o esperado.

Cartão · Mapa esquemático · severidade por área
===============================================

Representação por UF, colorida por severidade. A severidade pondera três
coisas: probabilidade, potência envolvida e criticidade da área.

É **esquemático** de propósito — não é mapa georreferenciado. O mapa
georreferenciado por subestação está em
:doc:`../mapa/perfis-por-subestacao`.

Cartão · Eventos priorizados por severidade
===========================================

Tabela ordenada. Cada linha é um alerta, e cada alerta traz:

* área e horizonte;
* probabilidade calibrada;
* montante esperado, em MW;
* **razão decomposta** — ENE, CNF, REL ou PAR;
* **evidências** que sustentam o alerta;
* **ações recomendadas**.

.. admonition:: Nenhum alerta sem evidência rastreável
   :class: important

   Essa é a metade operacional do princípio de projeto. Um alerta que não
   pode ser auditado até o dado de origem não é acionável — o operador não
   tem como avaliá-lo, e por isso não o usará.

Os códigos de razão
===================

.. list-table::
   :header-rows: 1
   :widths: 12 88

   * - Código
     - Significado
   * - **ENE**
     - Razão **energética** — excedente de geração frente à carga e ao
       intercâmbio. É o alvo declarado do eixo (ii).
   * - **CNF**
     - Confiabilidade.
   * - **REL**
     - Atendimento a requisito de reserva.
   * - **PAR**
     - Restrição por atendimento a pedido de parte.

Os códigos são os do ONS. O dicionário completo aparece no painel
:doc:`../analise/curtailment`.

Cartão · Probabilidade horária · área selecionada
=================================================

Série da probabilidade calibrada hora a hora, para a área escolhida.
Clicar em uma área no mapa esquemático troca a série.

Como o classificador funciona
=============================

Regressão logística regularizada, ajustada por IRLS, sobre os registros
reais de *constrained-off*. A probabilidade é **calibrada** por binning
monotônico, e a AUC é calculada por postos de Mann-Whitney.

Duas decisões que mudaram o resultado
=====================================

.. admonition:: 1. Sem vazamento
   :class: medido

   Uma versão inicial atingiu AUC 0,99 com probabilidade 1,00 — número
   bonito e falso. A causa: usar ``corte_mw`` como alvo colocava a defasagem
   de 1 h do próprio rótulo entre as variáveis. A memória operativa legítima
   é o histórico de restrição defasado em **24 h ou mais**, que é o que o
   operador de fato conhece ao prever D+1.

   Implementado em ``occurrence_memory(y, min_lag=24, window=7*24)``.
   **AUC caiu para 0,902** — e passou a significar algo.

.. admonition:: 2. Só na janela solar
   :class: medido

   Fora da janela solar a resposta é trivialmente "não haverá restrição
   fotovoltaica", e incluir essas horas infla a AUC sem informar nada. Além
   disso, o limiar de rótulo era 2% da capacidade, o que rotulava ruído.

   Correções: limiar de **10%** (``RISK_LABEL_THRESHOLD_FRACTION``) e
   restrição à janela solar (``RISK_DAYLIGHT_ONLY``), ambos versionados em
   ``oraculo/config.py``.

Limitações específicas
======================

.. admonition:: O que este painel não afirma
   :class: limite

   * **O rótulo é a decisão operativa observada**, não o potencial físico de
     geração. A ferramenta aprende quando houve restrição registrada, não
     quanta energia teria sido gerada.
   * A agregação é **por área**, não por usina.
   * O painel **não automatiza despacho**: produz indicador com evidência; a
     decisão é do operador.
   * A severidade embute uma ponderação de criticidade que é **premissa
     declarada**, não medição.

Para aprofundar
===============

* Registros observados de restrição: :doc:`../analise/curtailment`
* Desempenho e calibração: :doc:`../confianca/validacao`
* Código: :doc:`../../referencia/models`
* ONS — FAQ Curtailment: https://www.ons.org.br/Paginas/faq_curtailment.aspx
