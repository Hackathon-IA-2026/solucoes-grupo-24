======================
Perfis por subestação
======================

.. rubric:: Módulo Mapa Inteligente · aba ``#mapa``

**Pergunta que responde:** para cada subestação georreferenciada, qual o
perfil predominante de consumo da área atendida e existe presença relevante
de geração distribuída no entorno?

São as duas perguntas literais do enunciado do desafio Radix + AXIA + Cepel.

Rotas consumidas
================

.. list-table::
   :header-rows: 1
   :widths: 46 54

   * - Rota
     - O que traz
   * - ``GET /api/mapa/substations``
     - lote de subestações com classe, MMGD e resumo do detector
   * - ``GET /api/mapa/substations/{sub_id}``
     - detalhe de uma subestação, com detecções e insumo ao CLM
   * - ``GET /api/mapa/scene/{sub_id}.png``
     - ortoimagem da amostra, com as detecções desenhadas

A entrada, real
===============

O ONS publica exatamente o insumo que o desafio pede, no conjunto
``subestacao``:

.. code-block:: text

   id_subsistema;nom_subsistema;id_estado;nom_estado;nom_agente_principal;
   id_subestacao;nom_subestacao;val_niveltensao;id_estacao;num_barra;
   val_latitude;val_longitude

Resultado da ingestão real:

.. list-table::
   :header-rows: 1
   :widths: 62 38

   * - Grandeza
     - Valor
   * - Registros lidos
     - 1.689
   * - Descartados por coordenada ausente ou fora do território
     - 9
   * - Subestações únicas
     - **909**, em 27 UF
   * - Com capacidade de transformação associada
     - 600
   * - **Com transformação de fronteira com a distribuição**
     - **522**

.. admonition:: Por que "fronteira" e não "subestação de distribuição"
   :class: premissa

   O conjunto ``subestacao`` cobre a **rede de operação** — transmissão. A
   subestação de distribuição propriamente dita está na BDGD, que não é dado
   aberto de acesso direto.

   A **fronteira T–D**, porém, está no dado público: identificamos as
   transformações cujo lado secundário é de tensão de distribuição
   (≤ 138 kV, campo ``val_tensaosecundario_kv`` de
   ``capacidade-transformacao``). É onde o problema de observabilidade se
   manifesta, e é o recorte honesto possível com base aberta.

A área de influência
====================

Dimensionada pela capacidade que **efetivamente desce** para a distribuição,
não pela capacidade total — um transformador 765/500 kV não atende carga,
apenas interliga transmissão.

.. math::

   \text{área}_{km^2} = \frac{MVA_{\text{fronteira}}}{9}
   \qquad
   r_{km} = \sqrt{\frac{\text{área}}{\pi}},\ \ \text{limitado a } [0{,}8;\ 6{,}0]

Raio resultante nas 522 de fronteira: mínimo 0,80 km, **mediana 3,34 km**,
máximo 6,00 km. A mediana reaparece como âncora da escala de impedância do
alimentador em :doc:`parametrizacao-clm`.

Os quatro KPIs
==============

.. list-table::
   :header-rows: 1
   :widths: 32 14 54

   * - KPI
     - Unidade
     - Como ler
   * - **Subestações de fronteira**
     - contagem
     - Universo analisável: 522 das 909.
   * - **Classe dominante no lote**
     - rótulo
     - Classe predominante no conjunto carregado.
   * - **Penetração de MMGD**
     - nível
     - Distribuição dos três níveis no lote.
   * - **Qualidade da detecção**
     - F1
     - F1 médio do detector nas amostras analisadas. Está no cabeçalho de
       propósito: a classificação vale o que vale o detector.

Cartão · Subestações analisadas
===============================

Tabela principal. Cada linha é uma subestação, e **clicar abre o detalhe**.
Colunas:

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Coluna
     - Significado
   * - nome, UF, subsistema
     - identificação
   * - tensão / secundário
     - nível de tensão e menor secundário — é o secundário que caracteriza a
       fronteira
   * - MVA de fronteira
     - capacidade que desce para a distribuição
   * - raio, área
     - área de influência estimada
   * - classe dominante e rótulo
     - resposta à pergunta 1, com percentual por classe
   * - confiança da classe
     - quão separada é a classe dominante das demais
   * - desvio em relação ao subsistema
     - **onde esta área difere do seu subsistema** — ver nota abaixo
   * - nível de MMGD
     - resposta à pergunta 2: baixa, média ou alta
   * - kWp e kWp/km²
     - potência distribuída estimada, absoluta e por área
   * - painéis detectados
     - contagem na amostra
   * - Tipo III da UF
     - conferência cruzada com dado real de usinas conectadas à distribuição

Pergunta 1 — perfil predominante de consumo
===========================================

Duas evidências, com pesos declarados.

Evidência local: morfologia construída (75%)
--------------------------------------------

Distribuição de área dos telhados na amostra, **ponderada por área e não por
contagem**:

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Classe
     - Área de telhado
   * - Residencial
     - até 220 m²
   * - Comercial
     - 220 a 1.200 m²
   * - Industrial
     - acima de 1.200 m²

.. admonition:: Por que ponderar por área
   :class: premissa

   Um galpão de 5.000 m² pesa muito mais na carga do que uma casa de 120 m²,
   ainda que conte como uma edificação. Ponderar por contagem daria o
   resultado errado em qualquer área mista.

Prior regional: forma da curva de carga (25%)
---------------------------------------------

Decomposição da curva verificada do subsistema nos perfis canônicos das
classes, por mínimos quadrados não negativos. Detalhado em
:doc:`classes-de-consumo`.

.. admonition:: A nota metodológica que reestruturou este painel
   :class: medido

   **O prior regional não é uma segunda medida da mesma grandeza.**

   Numa versão anterior, comparar a curva agregada do subsistema de igual
   para igual com a morfologia local produzia "Misto / DIVERGEM" em
   **todas** as subestações — divergência por construção, porque o
   subsistema agrega todas as classes.

   O que se reporta agora é o **desvio da área em relação à média
   regional**, que é a informação útil: *onde esta área difere do seu
   subsistema* e, portanto, onde vale aprofundar o estudo.

Pergunta 2 — presença de geração distribuída
============================================

Da detecção ao indicador:

.. code-block:: text

   pixel → lat/lon (geo-transformação local plana)
   área conexa × área do pixel  → m² de painel
   × calibração de área (1,19, medida)  → m² corrigido
   × 200 W/m² de módulo                 → kWp
   ÷ área amostrada                     → kWp/km² → nível

Faixas do indicador
-------------------

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Nível
     - kWp/km²
   * - Baixa
     - < 200
   * - Média
     - 200 a 800
   * - Alta
     - > 800

Ancoragem: uma unidade com MMGD tem tipicamente 5 kWp; a densidade construída
urbana fica entre 800 e 2.000 telhados por km²; a penetração média brasileira
é da ordem de 3% das unidades consumidoras, chegando a 8–10% nos municípios
mais avançados.

.. admonition:: Amostragem, não cobertura total
   :class: premissa

   Ortoimagem de 30 cm sobre 113 km² por subestação é inviável. A detecção
   roda em **2 janelas de 230 m de lado a 0,30 m/pixel** (0,106 km² no
   total), e a densidade medida é extrapolada para a área de influência
   aplicando a **fração construída** típica da morfologia identificada
   (comercial 0,80 · residencial 0,60 · industrial 0,40 · misto 0,55).

   **O nível usa a densidade medida, sem extrapolação.** Só o total absoluto
   é extrapolado.

Cartões do detalhe da subestação
================================

Ao clicar em uma linha, abrem-se:

.. list-table::
   :header-rows: 1
   :widths: 38 62

   * - Cartão
     - Conteúdo
   * - **Ortoimagem com as detecções**
     - A cena amostrada, com as caixas desenhadas. Alternáveis: verdade
       fundamental, grade de ladrilhos e canais de característica.
   * - **Desempenho do detector nesta amostra**
     - Precisão, revocação, F1 e IoU **nesta cena** — não a média global.
   * - **Desvio em relação ao subsistema**
     - Comparação da composição local com o prior regional, e o desvio.
   * - **Insumo proposto ao Modelo de Carga Composta**
     - Composição por classe, fração de motor estimada, sinalização de GD e
       confiança. Ver o aviso abaixo.
   * - **Detecções georreferenciadas**
     - Tabela com lat/lon, área e confiança de cada detecção.

Insumo ao modelo de carga
=========================

.. list-table::
   :header-rows: 1
   :widths: 34 66

   * - Campo
     - Significado
   * - ``composicao_classe``
     - fração por classe de consumo
   * - ``fracao_motor_estimada``
     - fração de carga motora, combinando as classes com premissas
       declaradas (residencial 0,22 · comercial 0,38 · industrial 0,62 ·
       rural 0,55)
   * - ``mmgd_kwp_na_area``
     - potência distribuída estimada
   * - ``distributed_generation_flag``
     - se o modelo deve representar GD explicitamente
   * - ``confianca``
     - confiança da classificação

.. admonition:: Não são parâmetros prontos para simulação
   :class: limite

   São as grandezas observadas que o especialista usa ao escolher a
   composição do modelo de carga. A distinção está no próprio payload, no
   campo ``aviso``. O cartão de parâmetros do CMPLDW, campo a campo e com
   procedência, está em :doc:`parametrizacao-clm` — e a fração de motor
   acima reaparece lá, com teste que exige desvio zero entre as duas telas.

Cartão · Pipeline replicável
============================

Lista das etapas, na ordem em que executam. Atende ao requisito do enunciado:
sempre que as bases forem atualizadas, a metodologia reproduz o mapa.

Cartão · Faixas do indicador de MMGD
====================================

As três faixas, a ancoragem que as justifica, a fração construída por classe
urbana e os parâmetros de amostragem.

Limitações específicas
======================

.. admonition:: O que este painel não afirma
   :class: limite

   * **R1 — a ortoimagem é sintética.** O detector é o mesmo que roda em
     imagem real e as métricas são medições reais dele; a imagem é de
     demonstração. Em imagem real, esperar degradação.
   * **R2 — subestação de distribuição exige BDGD.** O recorte usado é a
     fronteira T–D.
   * **R3 — não existe curva de carga por subestação em dado aberto.** A
     decomposição roda por subsistema e entra como prior regional.
   * **R4 — industrial não é afirmado pelo cadastro.** Exige base de classe
     de consumo (BDGD ou Pesquisa de Posse e Hábitos de Consumo do IBGE,
     citada no enunciado). O rótulo industrial vem só da morfologia.
   * **R5 — variância de amostragem alta** onde as edificações são poucas e
     grandes. O payload reporta ``sample_adequacy`` (boa / limitada /
     insuficiente).

Dois erros corrigidos neste painel
==================================

.. admonition:: Heurística urbana circular
   :class: medido

   A densidade de carga era calculada como :math:`MVA/(\pi r^2)` com
   :math:`r=\sqrt{MVA/9\pi}` — o que dá **9 MVA/km² constante, por
   construção**. Substituída por sinais independentes: tensão secundária,
   MVA de fronteira e agente de distribuição.

.. admonition:: 225 MW de MMGD por subestação
   :class: medido

   A taxa de painel por telhado estava em 0,35–0,45, contra os ~3% reais do
   Brasil. Corrigida para 0,015–0,10, e as três faixas recalibradas.

Para aprofundar
===============

* Desempenho do detector: :doc:`visao-computacional`
* Perfis canônicos e NNLS: :doc:`classes-de-consumo`
* Cartão de parâmetros: :doc:`parametrizacao-clm`
* Especificação: ``01-ESPECIFICACAO/11-desafio-radix-mapa-inteligente.md``
* Código: :doc:`../../referencia/substations`
