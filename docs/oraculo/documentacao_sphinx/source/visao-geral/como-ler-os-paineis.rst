=====================
Como ler os painéis
=====================

Esta página é a chave de leitura. Vale mais do que qualquer painel isolado,
porque os elementos abaixo repetem-se em todos os onze.

Anatomia de um painel
=====================

.. code-block:: text

   ┌─ título e subtítulo ──────────────────────────────────────┐
   │  o que o painel responde, em uma frase                    │
   ├───────────────────────────────────────────────────────────┤
   │  faixa de nota (quando há)                                │
   │  o aviso que muda a leitura de tudo o que vem abaixo      │
   ├──────────┬──────────┬──────────┬──────────────────────────┤
   │   KPI    │   KPI    │   KPI    │   KPI                    │
   │  número de cabeceira, com unidade e rodapé explicativo    │
   ├──────────┴──────────┴──────────┴──────────────────────────┤
   │  cartões: gráfico, tabela ou lista de estatísticas        │
   │  cada um com dica (canto direito) e nota (ao pé)          │
   ├───────────────────────────────────────────────────────────┤
   │  ▸ Proveniência e notas (N)                               │
   └───────────────────────────────────────────────────────────┘

Os elementos, e o que cada um significa
=======================================

KPI
---

Número de cabeceira. Traz **rótulo**, **valor**, **unidade** e um **rodapé**
que explica a origem ou o contexto. Quando acentuado em cor, a cor tem
significado — âmbar para atenção, vermelho para desfavorável, verde para
medição favorável.

Dica do cartão
--------------

Texto curto no canto direito do cabeçalho do cartão. Em geral traz o
**método** ou o **parâmetro** usado: ``método: NNLS``, ``R² 0,91``,
``procedência campo a campo``.

Nota do cartão
--------------

Texto ao pé do cartão. É onde está a **advertência metodológica** — por que
o número é o que é, ou o que ele não significa. É a parte da tela que
costuma ser ignorada e que mais protege de conclusão errada.

Faixa de nota
-------------

Barra no topo do painel, com borda à esquerda. Quando **âmbar**, contém uma
ressalva que altera a leitura de todo o painel.

Chips
-----

Rótulos clicáveis ou informativos. Cores usadas de forma consistente:

.. list-table::
   :header-rows: 1
   :widths: 18 82

   * - Cor
     - Significado
   * - verde
     - medido, confere, favorável, baixa penetração
   * - âmbar
     - premissa declarada, atenção, média penetração
   * - vermelho
     - não afirmado, falha, alta penetração, desfavorável
   * - azul-petróleo
     - normativo, vindo de fonte externa

Bloco de proveniência
---------------------

Recolhível, ao pé de cada painel. Uma linha por recurso de dado usado
naquela tela. Ver :doc:`proveniencia`.

As quatro convenções que evitam erro de leitura
===============================================

1. Todo número tem procedência declarada
----------------------------------------

Nos painéis do Mapa Inteligente e do CLM, a procedência é explícita em
rótulo:

.. list-table::
   :header-rows: 1
   :widths: 18 82

   * - Rótulo
     - Significado
   * - **derivado**
     - Calculado com dado que a ferramenta observa.
   * - **premissa**
     - Hipótese versionada no código, com o motivo escrito.
   * - **WECC** / **referência**
     - Vem de fonte externa normativa ou publicada.
   * - **a calibrar**
     - **Não afirmado.** Exibido com o valor de referência apenas; exige
       ensaio, medição de campo ou base cadastral.

2. Estimativa nunca é apresentada como medição
----------------------------------------------

A MMGD é **estimada**, e o viés é declarado como conservador. A ortoimagem do
Mapa Inteligente é **sintética**, e isso está na tela. O detector é real e
suas métricas são medições reais dele — a distinção é feita em cada cartão.

3. Modelo aparece sempre ao lado do baseline
--------------------------------------------

Nenhum desempenho é publicado sozinho. Persistência e sazonal-ingênuo estão
no mesmo conjunto de teste, e o *skill score* negativo **aparece em
vermelho** em vez de ser omitido.

4. O modo de dados está sempre visível
--------------------------------------

O selo ``live``, ``cache`` ou ``demo`` acompanha a tela. Em modo
demonstrativo, o selo ``DADOS DEMONSTRATIVOS`` é ostensivo: nenhum número
daquela sessão deve ser citado como resultado.

Convenções de unidade e tempo
=============================

.. list-table::
   :header-rows: 1
   :widths: 24 76

   * - Convenção
     - Detalhe
   * - Potência
     - ``MWmed`` para média horária, ``MW`` para instantânea, ``MW/h`` para
       rampa, ``MWp``/``kWp`` para capacidade fotovoltaica instalada.
   * - Tempo
     - Hora local brasileira nos painéis; **UTC** nos campos de
       proveniência (``fetched_at``).
   * - Dia-tipo
     - Útil, sábado, domingo e feriado nacional. Feriados móveis calculados
       por Meeus/Butcher em ``oraculo/core/calendar_br.py``.
   * - Patamar operativo
     - Mínima diurna (09–15 h), rampa (16–19 h), ponta noturna (18–22 h),
       base (o restante). As faixas se sobrepõem de propósito: a rampa e a
       ponta compartilham horas, e o peso aplicado é o do patamar mais
       crítico.
   * - Quantis
     - P10, P50 (mediana) e P90. A banda no gráfico é P10–P90.

Ajuda contextual: a tecla F1
============================

Esta documentação está **embutida na própria aplicação**. Em qualquer painel:

.. list-table::
   :header-rows: 1
   :widths: 22 78

   * - Atalho
     - O que faz
   * - :kbd:`F1`
     - Abre a página desta documentação **correspondente ao painel aberto**.
       Pressionar de novo fecha.
   * - :kbd:`Esc`
     - Fecha a ajuda.
   * - Botão ``?``
     - O mesmo que :kbd:`F1`, na barra superior.

O quadro de ajuda traz atalhos para as páginas de contexto geral — *Como ler
os painéis*, *Proveniência*, *Limitações*, *Glossário*, *API* e *Código* — e um
botão para abrir a página em aba separada, quando se quer ler e operar ao
mesmo tempo.

.. admonition:: O mapeamento painel → página vive no servidor
   :class: important

   Em ``oraculo/api/service_docs.py``, não no JavaScript. Há um único lugar a
   corrigir quando uma página é renomeada, e o teste
   ``test_todo_painel_tem_pagina_de_ajuda`` exige **igualdade** entre os
   painéis do NAV e as páginas mapeadas: painel novo sem ajuda reprova a
   suíte, e página de ajuda órfã também.

   A alternativa seria descobrir o furo quando alguém aperta F1 durante a
   apresentação.

.. admonition:: Se a documentação não foi construída
   :class: premissa

   A ajuda é gerada sob demanda, e o diretório ``docs/oraculo/documentacao_sphinx/build/`` pode
   não existir. Nesse caso, ``F1`` **não abre um quadro em branco**: mostra o
   comando que produz a documentação.

   .. code-block:: bash

      cd docs/oraculo/documentacao_sphinx && python build_docs.py

   É a mesma disciplina da ingestão de dados — degradar, mas explicando. E a
   montagem de ``/docs`` é condicional de propósito: ``StaticFiles`` valida o
   diretório na criação, e montar um caminho ausente derrubaria a aplicação
   inteira na subida. A ajuda é acessório; o painel é o essencial.

Um aviso sobre a primeira carga
===============================

O primeiro acesso a um painel pode demorar: é a ingestão real no Portal de
Dados Abertos do ONS. As respostas seguintes vêm do cache. Se o painel
demorar mais do que o esperado, o campo ``mode`` no bloco de proveniência
dirá se a origem foi ``live`` ou ``cache``.
