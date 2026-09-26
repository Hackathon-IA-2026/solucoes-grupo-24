=====================
Curtailment observado
=====================

.. rubric:: Módulo Análise · aba ``#curtailment``

**Pergunta que responde:** quanto foi efetivamente restringido, em que área e
por qual razão?

Subtítulo na tela: *montante, razão e origem da restrição, a partir dos
registros de constrained-off*.

Rota consumida
==============

``GET /api/risk?horizon=d1&level=estado&asymmetric=0``

O mesmo payload que alimenta o painel de risco, lido pelo lado do
**registro observado** em vez do lado preditivo.

.. admonition:: A diferença em relação ao painel de risco
   :class: important

   :doc:`../operacao/risco-e-excedentes` olha para frente e produz alerta.
   Este painel olha para o registro de *constrained-off* já publicado pelo
   ONS. Mesma fonte, perguntas opostas no tempo.

Os quatro KPIs
==============

.. list-table::
   :header-rows: 1
   :widths: 34 16 50

   * - KPI
     - Unidade
     - Como ler
   * - **Energia restringida na janela**
     - GWh
     - Integral do corte no período carregado. É a grandeza que dimensiona o
       custo do problema.
   * - **Maior corte horário**
     - MWmed
     - Pico de restrição observado — o pior instante da janela.
   * - **Taxa média de ocorrência**
     - %
     - Fração das horas com restrição registrada. Diferencia o evento raro e
       intenso do evento crônico e moderado.
   * - **Participação da razão ENE**
     - %
     - Quanto do total restringido teve **razão energética**. É o recorte que
       a solução persegue, e a justificativa de existir o eixo (ii).

Cartão · Montante restringido por área e razão
==============================================

Barras empilhadas: cada área no eixo, cada razão como segmento. Mostra de uma
vez onde a restrição se concentra e se a natureza é energética ou de rede.

Cartão · Probabilidade horária por área
=======================================

Séries por área ao longo do dia. A forma revela a assinatura do problema:
restrição fotovoltaica concentrada no meio do dia, restrição eólica com
padrão distinto, tipicamente noturno no Nordeste.

Cartão · Histórico por área
===========================

Tabela com, por área: horas com registro, energia restringida, maior corte,
taxa de ocorrência e razão predominante.

Cartão · Códigos de razão
=========================

Dicionário do ONS, com o código e a descrição de cada razão.

.. list-table::
   :header-rows: 1
   :widths: 12 88

   * - Código
     - Significado
   * - **ENE**
     - Razão energética — excedente frente à carga e ao intercâmbio
   * - **CNF**
     - Confiabilidade
   * - **REL**
     - Atendimento a requisito de reserva
   * - **PAR**
     - Restrição por atendimento a pedido de parte

Cartão · Códigos de origem
==========================

Dicionário de origem da restrição, também do ONS. Separa a restrição
determinada pelo Operador da originada em outros processos.

.. admonition:: Por que os dois dicionários estão na tela
   :class: important

   Não são enfeite: um número de corte sem o código de razão não é
   interpretável. A mesma restrição de 100 MW significa coisas diferentes se
   é **ENE** (há energia sobrando e falta escoamento ou carga) ou **CNF**
   (a rede não suporta). Sem essa distinção, a solução estaria somando
   grandezas de naturezas distintas.

Fonte dos dados
===============

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Conjunto
     - Conteúdo
   * - ``restricao_coff_fotovoltaica``
     - restrição semi-horária, por usina fotovoltaica
   * - ``restricao_coff_eolica_usi``
     - restrição semi-horária, por usina eólica

Esquemas verificados por inspeção direta dos CSV publicados. A leitura usa
requisições ``Range`` para não baixar arquivos inteiros.

Limitações específicas
======================

.. admonition:: O que este painel não afirma
   :class: limite

   * **O registro é a decisão operativa**, não o potencial físico. Não
     responde "quanta energia teria sido gerada sem a restrição" — responde
     "quanto foi determinado como restrição".
   * A granularidade publicada é **por usina**; a agregação por área é
     nossa.
   * A janela carregada é a recente. Séries longas exigem ingestão de mais
     recursos, disponível pela rota ``POST /api/ingest``.

Para aprofundar
===============

* Antecipação do mesmo fenômeno: :doc:`../operacao/risco-e-excedentes`
* Proveniência e cache: :doc:`../confianca/dados-abertos`
* ONS — FAQ Curtailment: https://www.ons.org.br/Paginas/faq_curtailment.aspx
