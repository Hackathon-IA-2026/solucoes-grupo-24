===================
Despacho preditivo
===================

.. rubric:: Módulo Operação · aba ``#operacao``

**Pergunta que responde:** quanto de carga o ONS vai enxergar nas próximas
horas, e quanto a MMGD está escondendo agora?

Subtítulo na tela: *carga medida − MMGD estimada = carga supervisionada, com
banda P10/P90*.

Rotas consumidas
================

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Rota
     - O que traz
   * - ``GET /api/decomposition?area=SE&hours=72``
     - decomposição da carga nas últimas 72 h
   * - ``GET /api/forecast?area=SE&horizon=3h&asymmetric=1``
     - previsão com banda e desempenho no conjunto de teste

Controles
=========

* **Área** — subsistema (SE, S, NE, N).
* **Horizonte** — 30 min, 3 h ou D+1.
* **Assimetria** — liga e desliga a perda assimétrica por patamar. É o
  controle que transforma o argumento da solução em evidência: com ele
  desligado, o mesmo conjunto de teste mostra o desempenho sem os pesos.

Os quatro KPIs
==============

.. list-table::
   :header-rows: 1
   :widths: 34 16 50

   * - KPI
     - Unidade
     - Como ler
   * - **Carga supervisionada (último ponto)**
     - MWmed
     - O que o ONS mede. É a carga global **menos** a MMGD estimada.
   * - **MMGD estimada — pico na janela**
     - MWmed
     - Maior valor estimado da geração distribuída nas 72 h. Ocorre perto do
       meio-dia solar. **É estimativa, com viés conservador declarado.**
   * - **Mínima supervisionada**
     - MWmed
     - O vale da carga supervisionada, e a hora em que ocorreu. Em áreas de
       alta penetração esse vale migrou da madrugada para o meio-dia — é a
       assinatura da MMGD.
   * - **Maior rampa horária**
     - MW/h
     - Maior variação entre horas consecutivas. Dimensiona a exigência de
       flexibilidade no fim da tarde.

Cartão · Decomposição da carga · últimas 72 h
=============================================

Gráfico de área empilhada: **carga supervisionada** e **MMGD estimada**,
somando a carga global.

A identidade que sustenta o gráfico:

.. math::

   \text{carga global} = \text{carga supervisionada} + \text{MMGD estimada}

Há teste que verifica resíduo nulo nessa identidade — ela não é aproximada, é
exata por construção.

.. admonition:: Como a MMGD é estimada
   :class: premissa

   A MMGD **não existe** como série horária por área no Portal. O estimador
   combina três coisas:

   #. **Geometria solar** — declinação e equação do tempo de Spencer (1971),
      céu claro de Haurwitz. Dá a forma da curva de irradiância para a
      latitude e o dia.
   #. **Capacidade instalada declarada** por área.
   #. **Fator de nebulosidade pelo método do envelope** — o percentil 90 da
      carga em horas comparáveis do mês aproxima a carga global, porque *o
      dia de maior carga observada é o dia de menor geração distribuída*.

   **Viés declarado:** mesmo os dias de maior carga contêm alguma geração
   distribuída. A estimativa é **um piso, não um valor central**.

Cartão · Fator de nebulosidade e irradiância
============================================

Duas séries no mesmo eixo: a irradiância de céu claro calculada e o fator de
nebulosidade estimado pelo envelope. Serve para inspecionar se a estimativa
está se comportando — fator próximo de 1 em dia claro, deprimido em dia
encoberto.

Cartão · Previsão da carga supervisionada
=========================================

Série observada, mediana prevista (P50) e **banda P10–P90**.

.. admonition:: A banda não é enfeite
   :class: important

   Uma previsão pontual esconde a informação que o operador precisa. A banda
   P10–P90 diz **quanto** o valor pode se afastar, e é produzida por três
   regressões quantílicas independentes — não por um intervalo simétrico
   suposto em torno da média.

Cartão · Desempenho no teste
============================

Lista de estatísticas com MAE, RMSE, cobertura da banda e *skill score*
contra o melhor baseline, no conjunto de teste **fora da amostra**.

*Skill score* positivo significa erro menor que o baseline; negativo
significa que o baseline ganhou, e nesse caso o número aparece em vermelho.

Cartão · Erro por patamar operativo
===================================

Tabela com o erro decomposto pelos quatro patamares. É aqui que a perda
assimétrica se justifica, ou não.

.. list-table::
   :header-rows: 1
   :widths: 30 18 18 34

   * - Patamar
     - Subestimar
     - Superestimar
     - Por que o peso é assim
   * - Mínima diurna (09–15 h)
     - 1,0
     - **2,2**
     - Superestimar a carga no vale diurno leva a subestimar o excedente
       renovável — o erro que produz curtailment inesperado.
   * - Rampa (16–19 h)
     - **2,0**
     - 1,2
     - Subestimar a rampa deixa o sistema sem flexibilidade contratada no
       momento em que a solar sai.
   * - Ponta noturna (18–22 h)
     - **2,8**
     - 1,0
     - O erro mais caro: subestimar a ponta é risco de atendimento.
   * - Base
     - 1,0
     - 1,0
     - Sem assimetria: nenhuma direção é mais custosa.

Implementação em ``oraculo/models/quantile.py``: perda *pinball* assimétrica
suavizada por Huber, otimizada por L-BFGS-B. Os pesos estão versionados em
``oraculo/config.py`` (``ASYMMETRIC_WEIGHTS``).

Cartão · Peso por grupo de variável
===================================

Barras com a importância relativa de cada grupo de variáveis — calendário,
defasagens, geometria solar, meteorologia, memória operativa.

.. admonition:: Um erro que este cartão revelou
   :class: medido

   Em uma versão anterior todos os pesos vinham nulos. A causa: ``np.std``
   propagava ``NaN`` a partir das colunas de defasagem, e o resultado inteiro
   virava ``None``. A correção foi ``np.nanstd`` com ``nan_to_num``, e há
   teste de regressão para isso. O cartão é útil justamente porque um peso
   obviamente errado salta aos olhos.

Limitações específicas
======================

.. admonition:: O que este painel não afirma
   :class: limite

   * A MMGD é **estimada**, não medida, e o viés é conservador por
     construção.
   * A previsão é da **carga supervisionada**, não da carga global.
   * O painel **não substitui o PREVCARGA**: é camada complementar focada na
     parcela não supervisionada.
   * O desempenho exibido é do conjunto de teste cronológico corrente. A
     auditoria completa do procedimento está em
     :doc:`../confianca/validacao`.

Para aprofundar
===============

* Modelos: ``01-ESPECIFICACAO/06-modelos-analiticos.md``
* Código: :doc:`../../referencia/models`
* Validação do método: :doc:`../confianca/validacao`
