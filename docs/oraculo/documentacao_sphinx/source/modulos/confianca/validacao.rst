===================
Validação do método
===================

.. rubric:: Módulo Confiança · aba ``#validacao``

**Pergunta que responde:** o método supera os baselines? Onde ele erra?

Subtítulo na tela: *backtest cronológico, baselines obrigatórios, métricas por
patamar e calibração probabilística*.

Rota consumida
==============

``GET /api/validation?area=SE&asymmetric=1``

.. admonition:: Por que este painel existe
   :class: important

   Em um hackathon é fácil mostrar um gráfico bonito. O que distingue uma
   solução operável é ter resposta para *qual o desempenho fora da amostra,
   contra um baseline honesto*. Este painel é a resposta, e inclui os casos
   em que o modelo perde.

Os quatro KPIs
==============

.. list-table::
   :header-rows: 1
   :widths: 28 16 56

   * - KPI
     - Valor
     - Como ler
   * - **Corte cronológico**
     - sim / não
     - Se o conjunto de teste é **estritamente posterior** ao de treino.
       Verificado por teste automatizado, não afirmado por confiança.
   * - **Instante do corte**
     - data e hora
     - Onde treino termina e teste começa. Explicitá-lo permite auditar.
   * - **Melhor MAE**
     - MW
     - Menor erro absoluto médio entre os horizontes.
   * - **Função de perda**
     - assimétrica / simétrica
     - Reflete o estado do seletor. É o controle que transforma o argumento
       em evidência.

Cartão · Desempenho por horizonte
=================================

Tabela com, para cada horizonte (30 min, 3 h, D+1): MAE, RMSE, cobertura da
banda P10–P90 e *skill score* contra o melhor baseline.

.. admonition:: Skill score negativo aparece em vermelho
   :class: important

   Não é omitido. Esconder o caso em que o modelo perde do baseline tornaria
   o resto da tela inútil — quem lê passaria a desconfiar de tudo.

Cartão · Métricas por patamar operativo
=======================================

O erro decomposto pelos quatro patamares, por horizonte. É onde se verifica
se a perda assimétrica entregou o que promete: erro menor **na direção que
importa** em cada patamar, ainda que o erro médio total não melhore.

Cartão · Calibração probabilística
==================================

Gráfico de confiabilidade: probabilidade prevista no eixo horizontal,
frequência observada no vertical. A diagonal é a calibração perfeita.

.. admonition:: Por que calibração e não só AUC
   :class: important

   Um classificador pode ordenar bem (AUC alta) e ainda assim dizer "70% de
   chance" em situações que ocorrem 30% das vezes. Para uso operativo, o
   **valor** da probabilidade tem de significar algo — e isso é calibração,
   não discriminação.

   A calibração usa binning monotônico; a AUC, postos de Mann-Whitney.

Cartão · Efeito da perda assimétrica (3 h)
==========================================

Comparação lado a lado, **no mesmo conjunto de teste**, com e sem os pesos
assimétricos. A tabela mostra o erro por direção em cada patamar.

.. list-table::
   :header-rows: 1
   :widths: 32 20 20 28

   * - Patamar
     - Subestimar
     - Superestimar
     - Erro que se quer evitar
   * - Mínima diurna (09–15 h)
     - 1,0
     - **2,2**
     - subestimar o excedente renovável
   * - Rampa (16–19 h)
     - **2,0**
     - 1,2
     - ficar sem flexibilidade quando a solar sai
   * - Ponta noturna (18–22 h)
     - **2,8**
     - 1,0
     - risco de atendimento
   * - Base
     - 1,0
     - 1,0
     - nenhuma direção é mais custosa

Cartão · Série de teste · horizonte 3 h
=======================================

Observado, previsto e banda, ao longo de todo o conjunto de teste. Permite
ver **onde** o modelo erra, e não apenas quanto — informação que nenhuma
métrica agregada carrega.

Cartão · Baselines avaliados no mesmo conjunto de teste
=======================================================

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Baseline
     - Definição
   * - **Persistência**
     - o próximo valor é igual ao último observado
   * - **Sazonal-ingênuo diário**
     - o valor de ontem, na mesma hora
   * - **Sazonal-ingênuo semanal**
     - o valor da semana passada, no mesmo dia-tipo e hora

.. admonition:: Baselines não são formalidade
   :class: important

   Em série de carga, o sazonal-ingênuo semanal é **difícil de superar**: a
   carga tem estrutura semanal forte. Um modelo que não o supera não deve ser
   promovido, e é essa a regra do projeto.

O procedimento de backtest
==========================

* **Corte estritamente cronológico**, com **embargo** entre treino e teste
  para impedir vazamento por defasagens que cruzem a fronteira.
* Baselines avaliados **no mesmo conjunto de teste**, nunca em outro.
* Métricas por horizonte e por patamar.
* Verificação automatizada da ausência de vazamento.

Dois erros que este painel revelou
==================================

.. admonition:: Sazonalidade anual não identificada
   :class: medido

   O *skill score* veio **−0,49** no horizonte de 30 min. A causa: o treino
   usava um recorte parcial de 2026, e a sazonalidade anual não era
   identificável naquele suporte.

   Correção: carregar **dois anos**. O *skill score* passou a **+0,575**.

   Registre-se o que aconteceu aqui: o painel de validação **reprovou o
   modelo**, e isso levou à correção. Se o *skill* negativo estivesse
   escondido, o erro teria ido para a apresentação.

.. admonition:: Vazamento no classificador de risco
   :class: medido

   AUC 0,99 com probabilidade 1,00 — porque o alvo ``corte_mw`` colocava a
   defasagem de 1 h do próprio rótulo entre as variáveis. Corrigido com
   ``occurrence_memory(min_lag=24)``: **AUC 0,902**, e agora significa algo.

Limitações específicas
======================

.. admonition:: O que este painel não afirma
   :class: limite

   * O desempenho é do **conjunto de teste corrente**, com a janela de dados
     carregada. Janela diferente, número diferente.
   * A cobertura da banda é medida **no agregado**; cobertura correta no
     total pode conviver com cobertura ruim em um patamar específico — por
     isso a tabela por patamar existe.
   * A validação cobre os modelos de carga e de risco. O detector de visão
     computacional tem validação própria, em
     :doc:`../mapa/visao-computacional`, e o CLM tem a sua em
     :doc:`../mapa/parametrizacao-clm`.

Para aprofundar
===============

* Procedimento: ``01-ESPECIFICACAO/07-validacao.md``
* Código: :doc:`../../referencia/validation`
