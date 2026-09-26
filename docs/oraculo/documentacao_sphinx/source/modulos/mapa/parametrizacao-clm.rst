==========================================
Parametrização do Modelo de Carga Composta
==========================================

.. rubric:: Módulo Mapa Inteligente · aba ``#clm``

**Pergunta que responde:** que parâmetros usar no Modelo de Carga Composta
para esta subestação — e em quais deles é possível confiar?

Destino: **parametrização do CLM no ORGANON**. O cartão é **neutro**, porque
os campos do CMPLDW são os mesmos em PSS/E (``CMLDxxU2``), PSLF (``cmpldw``),
PowerWorld, DSATools e ORGANON.

Rotas consumidas
================

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Rota
     - O que traz
   * - ``GET /api/clm/spec``
     - estrutura, registro de 124 parâmetros, cobertura por procedência
   * - ``GET /api/clm/cartao``
     - cartão para uma subestação ou para composição livre
   * - ``GET /api/clm/curvas``
     - as características estáticas, amostradas
   * - ``GET /api/clm/validacao``
     - o exemplo publicado do WECC e as conferências independentes

Duas fontes, e só duas
======================

.. list-table::
   :header-rows: 1
   :widths: 14 86

   * - Rótulo
     - Fonte
   * - **WECC**
     - *WECC Composite Load Model Specification*, Modeling and Validation
       Subcommittee, abril de 2021 (aprovada em 27/01/2015). Define
       estrutura, nomes de campo, equações, o exemplo numérico resolvido e os
       poucos números que o texto fixa.
   * - **REF**
     - Q. Huang, S. Jin, R. Diao, B. Palmer et al., *A Reference
       Implementation of WECC Composite Load Model in Matlab and GridPACK*,
       arXiv:1708.00939, apêndice — conjunto completo em formato PSLF DYD,
       barra 90 do IEEE 300 barras. **Todo** valor numérico de referência
       vem daqui.

Os rótulos de procedência
=========================

.. list-table::
   :header-rows: 1
   :widths: 18 82

   * - Rótulo
     - Significado
   * - **derivado**
     - Calculado com dado que esta ferramenta observa.
   * - **premissa**
     - Hipótese versionada no repositório, com o motivo escrito.
   * - **WECC** / **referência**
     - Vem das duas fontes acima.
   * - **a calibrar**
     - **Não afirmado.** Exibido com o valor de referência e o rótulo; exige
       ensaio, medição de campo ou base cadastral.

.. admonition:: A regra que organiza o módulo
   :class: important

   **Nenhum número sem procedência.** O CMPLDW tem mais de cem campos e quase
   nenhum é observável a partir de dado aberto — é exatamente onde a tentação
   de inventar é maior.

.. admonition:: Uma fonte que ficou de fora, e por quê
   :class: limite

   O *Reliability Guideline — Developing Load Model Composition Data* (NERC
   Load Modeling Task Force, março de 2017) é a fonte certa para substituir a
   premissa de composição por classe por dado. **Não foi consultada nesta
   versão**: o servidor da NERC nega acesso automatizado (HTTP 403,
   verificado). Consta como próximo passo e como referência declarada na
   API — não como base de número algum.

Os quatro KPIs
==============

.. list-table::
   :header-rows: 1
   :widths: 32 14 54

   * - KPI
     - Valor
     - Como ler
   * - **Campos do modelo**
     - **124**
     - Tamanho do registro completo do CMPLDW.
   * - **Derivados de dado nosso**
     - 5 a 6
     - As cinco frações e, havendo subestação real, a base MVA.
   * - **Premissa versionada**
     - 2
     - ``Rfdr`` e ``Xfdr``, escalados pelo comprimento equivalente.
   * - **A calibrar**
     - **29**
     - **Não afirmados.** É o número mais honesto da tela.

Dado aberto brasileiro não determina nem um quinto do CMPLDW. O painel existe
para deixar essa fronteira explícita, não para escondê-la.

Cartão · Estrutura do modelo
============================

Diagrama da cadeia entre o barramento de transmissão e o uso final.

.. code-block:: text

   Barramento          Barramento              Barramento
   do sistema           de baixa                de carga
       │                   │                       │
       ├── jXxf, 1:T ──────┤── Rfdr + jXfdr ───────┤── M  Motor A   3φ
       │     (LTC)         │                       │── M  Motor B   3φ
       │                   ⊥ Bss                   │── M  Motor C   3φ
       │                   ⊥ Fb·Bfdr  (1−Fb)·Bfdr ⊥│── M  Motor D   1φ
       │                                           │── ▭  Eletrônica
     UVLS                                          │── ▭  Estática
     UFLS                                          └── Pdg + jQdg (MMGD)

Os barramentos **de baixa** e **de carga** não existem no fluxo de potência:
são criados na inicialização do modelo.

.. admonition:: O ponto que costuma passar em branco
   :class: important

   Metade do efeito dinâmico do CLM vem da **rede entre** o barramento de
   transmissão e o uso final. É a impedância do transformador e do
   alimentador que faz a tensão no uso final cair mais do que a tensão medida
   na subestação — e é isso que leva o compressor a travar.

   A especificação observa que as ferramentas **reajustam** ``Rfdr`` e
   ``Xfdr`` na inicialização para manter o barramento de carga acima de
   **0,95 pu**.

Cartão · Composição da carga
============================

Seletor de subestação (as 522 de fronteira) ou composição livre, mais o
cursor do motor D. Devolve as cinco frações e a estática, com a tabela de
**contribuição por classe** — quanto cada classe de consumo aportou a cada
fração.

A repartição por classe
-----------------------

.. list-table::
   :header-rows: 1
   :widths: 20 11 11 11 11 11 13 12

   * - Classe
     - Fma
     - Fmb
     - Fmc
     - Fmd
     - Fel
     - estática
     - motora
   * - Residencial
     - 0,05
     - 0,03
     - 0,02
     - **0,12**
     - 0,20
     - 0,58
     - 0,22
   * - Comercial
     - 0,12
     - 0,10
     - 0,06
     - 0,10
     - 0,22
     - 0,40
     - 0,38
   * - Industrial
     - 0,20
     - 0,12
     - **0,28**
     - 0,02
     - 0,10
     - 0,28
     - 0,62
   * - Rural
     - 0,06
     - 0,04
     - **0,43**
     - 0,02
     - 0,08
     - 0,37
     - 0,55

O raciocínio, classe por classe:

* **Residencial** — carga motora pequena e quase toda monofásica: compressor
  de refrigerador e de ar condicionado, que é o motor D. Carga eletrônica
  alta e crescente. O resto é resistivo — chuveiro, no Brasil, é parcela
  relevante e puramente estática.
* **Comercial** — climatização central reparte entre compressores de
  conjugado constante (A) e ventilação forçada (B).
* **Industrial** — predomínio de bombas e alta inércia (C), pouca carga
  monofásica.
* **Rural** — irrigação e bombeamento, praticamente tudo C.

.. admonition:: A coluna "motora" não é coincidência
   :class: medido

   Ela reproduz **exatamente** a fração motora que
   :doc:`perfis-por-subestacao` já publica, e há teste que exige desvio
   **zero**. Duas telas que discordassem sobre a mesma grandeza destruiriam a
   credibilidade das duas.

O cursor do motor D
-------------------

.. admonition:: O parâmetro que expusemos em vez de fixar
   :class: premissa

   A **penetração de ar condicionado no Brasil não é a do sudoeste
   norte-americano** de onde vem o modelo do motor D — e o motor D é
   justamente o componente que governa a recuperação lenta de tensão. Não
   temos esse dado.

   O cursor escala ``Fmd``, e o delta volta para a carga estática, de modo
   que a soma continua fechando em 1 (há teste que exige soma exata).
   **Expor a sensibilidade é mais honesto do que fixar um número que não
   temos.**

Cartão · Contexto e aplicabilidade
==================================

Contexto da subestação — MVA de fronteira, secundário, raio, escala do
alimentador, confiança da classe, adequação da amostra — e os três critérios
de aplicabilidade:

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Critério
     - Limite
   * - Carga
     - > 5 MW
   * - Tensão
     - > 0,98 pu
   * - Relação P/Q
     - > 1,61

O CLM não deve ser aplicado a qualquer barra: abaixo desses valores a
inicialização falha. O painel reporta **qual** critério reprovou.

A escala do alimentador
-----------------------

.. math::

   \text{escala} = \frac{r_{km}}{3{,}34}, \quad
   \text{limitada a } [0{,}35;\ 2{,}20]
   \qquad
   Rfdr = Xfdr = 0{,}04 \times \text{escala}

A impedância série é proporcional ao comprimento; o raio de influência é o
único proxy de comprimento em dado aberto, e a subestação **mediana** recebe
exatamente o valor de referência. Premissa de primeira ordem, e ponto de
partida apenas.

Cartão · Cartão de parâmetros
=============================

Os 124 campos, navegáveis por bloco: transformador, alimentador, frações,
estática, eletrônica e os quatro motores. Cada linha traz valor sugerido,
valor de referência, unidade, **procedência** e o que o campo significa.

Cartão · Motor A, B e C — o que de fato os distingue
====================================================

.. list-table::
   :header-rows: 1
   :widths: 12 12 24 26 26

   * - Motor
     - H
     - Etrq
     - Desligamento por subtensão
     - Leitura convencional
   * - A
     - 0,3 s
     - 0 — conjugado constante
     - não
     - compressores, conjugado constante
   * - B
     - 0,5 s
     - 2 — ∝ velocidade²
     - 0,80 pu / 2 s · 0,60 pu / 0,16 s
     - ventiladores
   * - C
     - 1,0 s
     - 2 — ∝ velocidade²
     - idem B
     - bombas, alta inércia

.. admonition:: Não existe campo "tipo de equipamento" no CMPLDW
   :class: important

   A diferença entre os três motores trifásicos está **inteiramente** em
   ``H`` e ``Etrq``, que o conjunto de referência fixa. A leitura de
   equipamento é a convencional da literatura de modelagem de carga, e está
   **rotulada como tal** na tela — não é dado.

Conjugado mecânico: :math:`T_m = T_{mo}\,\omega^{Etrq}`.

Cartão · Carga estática
=======================

.. math::

   P = P_o (P1c\,V^{P1e} + P2c\,V^{P2e} + P3)(1 + Pfrq\,\Delta f),
   \quad P3 = 1 - P1c - P2c

Em :math:`V = 1` e :math:`\Delta f = 0` o fator é **exatamente 1**, qualquer
que seja a repartição ZIP. Se não fosse, o CLM deslocaria o ponto de operação
na inicialização — o modelo passaria a mentir sobre a própria carga inicial.
Há teste para isso.

Cartão · Motor D — compressor monofásico
========================================

As duas características de potência ativa no mesmo eixo, com o ponto de
cruzamento marcado, mais a característica de reativo.

.. math::

   \begin{aligned}
   V > 0{,}86:\quad & P = P_o (1 + \Delta f) \\
                    & Q = [Q'_o + 6 (V - 0{,}86)^2](1 - 3{,}3\,\Delta f) \\[4pt]
   V'_{stall} < V < 0{,}86:\quad & P = [P_o + 12 (0{,}86 - V)^{3,2}](1 + \Delta f) \\
                    & Q = [Q'_o + 11 (0{,}86 - V)^{2,5}](1 - 3{,}3\,\Delta f) \\[4pt]
   V < V'_{stall}:\quad & P = G_{stall} V^2 \\
                    & Q = -B_{stall} V^2
   \end{aligned}

com :math:`Q'_o = P_o \tan(\arccos(CompPF)) - 6(1 - 0{,}86)^2` e
:math:`G_{stall} + jB_{stall} = 1/(R_{stall} + jX_{stall})` invertido.
:math:`\Delta f` é :math:`f - 1`, negativo em subfrequência.

``Vstallbrk``
-------------

O ponto onde a curva de rotor bloqueado cruza a de regime. A especificação
publica o laço que o encontra a 0,01 pu:

.. code-block:: text

   for (V = 0,4; V < Vstall; V += 0,01)
       pst    = Gstall · V²
       p_comp = Po + 12 (0,86 − V)^3,2
       if (p_comp <= pst) { V'stall = V; break }

Implementamos o laço publicado **e** uma bissecção independente, e exigimos
que concordem dentro de um passo. Com o conjunto de referência: laço
**0,5500 pu**, bissecção **0,544942 pu**.

.. admonition:: A posição relativa importa, não só o valor
   :class: important

   Se ``Vstall`` for menor que ``Vstallbrk``, o compressor trava **antes** de
   a curva de regime encontrar a de rotor bloqueado. É o que as figuras 6 a 8
   da especificação mostram, e o que o cursor do painel reproduz.

   Travado, o compressor é um rotor bloqueado: absorve reativo em vez de
   produzir trabalho. É esse salto que **retém a tensão deprimida** depois de
   uma falta — o fenômeno que motivou o modelo.

Cartão · Carga eletrônica — descida ≠ subida
============================================

Duas curvas: a rampa descendente e a recuperação seguinte.

A variável interna ``Vmin`` guarda a menor tensão já vista. Consequência:
com ``Frcel = 0``, a carga desligada **não volta sozinha**. É esse laço, e
não o valor de ``Vd1``, o que costuma surpreender em estudo.

.. admonition:: Um erro corrigido aqui
   :class: medido

   A primeira versão varria a malha de tensão em ordem crescente. O modelo
   tem memória, e percorrê-lo na ordem errada produzia uma curva sem sentido
   físico. A varredura tem de começar no topo.

Cartão · Proteções agregadas
============================

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Proteção
     - Caracterização
   * - Térmica
     - unitária até ``Th1t``, decrescente até zero em ``Th2t``; temperatura
       de :math:`I^2 R_{stall}` filtrada por :math:`1/(T_{th}s + 1)`
   * - Contatores
     - histerese ``Vc1off``/``Vc2off`` na descida, ``Vc2on``/``Vc1on`` na
       subida — é o laço que impede religamento instantâneo e oscilação
       numérica na fronteira

Cartão · O que prova que a implementação está correta
=====================================================

A especificação resolve um exemplo numérico de 100 MW e **publica a tabela de
resultado** (seção *Handling of extra vars due to end-use load tripping*,
páginas 19 e 20).

.. list-table::
   :header-rows: 1
   :widths: 16 9 10 9 12 12 11 11 10

   * - Componente
     - MW
     - Mvar
     - peso
     - B calc.
     - B publ.
     - em serviço
     - rem. calc.
     - rem. publ.
   * - Motor A
     - 40
     - 9
     - 0,40
     - 0,1440
     - 0,144
     - 0,20
     - 0,0288
     - 0,0288
   * - Motor B
     - 20
     - 6
     - 0,20
     - 0,0720
     - 0,072
     - 0,70
     - 0,0504
     - 0,0504
   * - Motor C
     - 5
     - 4
     - 0,05
     - 0,0180
     - 0,018
     - 0,40
     - 0,0072
     - 0,0072
   * - Motor D
     - 15
     - 1
     - 0,15
     - 0,0540
     - 0,054
     - 1,00
     - 0,0540
     - 0,0540
   * - Eletrônica
     - 10
     - −2
     - 0,10
     - 0,0360
     - 0,036
     - 0,80
     - 0,0288
     - 0,0288
   * - Estática
     - 10
     - −2
     - 0,10
     - 0,0360
     - 0,036
     - 1,00
     - 0,0360
     - 0,0360
   * - **total**
     - 100
     - 16
     -
     - **0,3600**
     - 0,360
     -
     - **0,2052**
     - 0,2052

.. admonition:: Desvio máximo nas 12 comparações: 0,0
   :class: medido

   Reproduzir a tabela publicada é a única forma de mostrar que a
   implementação está **correta**, e não apenas plausível.

.. admonition:: Um detalhe que quase virou erro
   :class: medido

   Os reativos extras do exemplo são **−36 Mvar**, enquanto a soma dos
   reativos dos componentes é **+16**. Os dois números não são o mesmo: o
   montante vem do **balanço de rede da inicialização** — transformador,
   alimentador, shunts e a própria geração distribuída.

   Derivar um do outro seria errado, e a primeira versão deste código fazia
   exatamente isso. Há teste nomeado
   (``test_reativos_extras_nao_sao_a_soma_dos_componentes``) para impedir que
   a simplificação volte.

Cartão · Conferências independentes
===================================

.. list-table::
   :header-rows: 1
   :widths: 46 54

   * - Conferência
     - Por que importa
   * - Carga estática devolve fator 1,000000 em 1 pu
     - se não, o CLM desloca o ponto de operação
   * - ``Vstallbrk`` por laço publicado e por bissecção concordam
     - um valida o outro
   * - Normalização das frações quando somam mais de 1
     - regra explícita da especificação
   * - Admitância de rotor bloqueado
     - a especificação usa ``Gstall``/``Bstall`` sem escrevê-los em função de
       ``Rstall``/``Xstall``

Cartão · Coerência com o Mapa Inteligente
=========================================

Tabela por classe, comparando a fração motora deste painel com a que
:doc:`perfis-por-subestacao` publica. Desvio exigido: **zero**.

Cartão · Geração distribuída no CLM
===================================

A MMGD estimada na área, e onde ela entra.

**Entra como:** injeção :math:`P_{dg} + jQ_{dg}` no barramento de carga, como
na figura de inicialização da especificação.

.. admonition:: O que o CMPLDW não faz
   :class: limite

   **Dinâmica de inversor.** Resposta a subtensão, resposta a frequência e
   anti-ilhamento exigem modelo próprio de recurso distribuído (família
   DER_A), em paralelo ao CLM. Dizê-lo é mais útil do que sugerir que o CLM
   resolve.

Cartão · Cartão em texto
========================

O cartão completo em formato de texto, com a procedência em cada linha,
pronto para copiar.

.. admonition:: Neutro de propósito
   :class: important

   Emitir a sintaxe de uma ferramenta específica daria a impressão de um caso
   pronto para rodar, que **não é o que isto é**.

Limitações específicas
======================

.. admonition:: O que este painel não afirma
   :class: limite

   * **C1 — nada aqui simula o CLM no tempo.** São as relações algébricas e a
     lógica de proteção. A resposta transitória é do ORGANON.
   * **C2 — a composição por classe é premissa versionada**, não medição de
     uso final.
   * **C3 — 29 campos não são afirmados.** Aparecem com o valor de
     referência e o rótulo *a calibrar*.
   * **C4 — a penetração de ar condicionado brasileira é desconhecida
     aqui.**
   * **C5 — ``Rfdr``/``Xfdr`` saem de um proxy de comprimento**, não de
     cadastro de alimentador.
   * **C8 — o cartão não é caso pronto para simulação.** Está escrito no
     próprio cartão, na tela e no payload.

Próximos passos
===============

#. **Guia de composição de carga da NERC** — substitui a premissa de
   repartição por classe por base reconhecida.
#. **Pesquisa de Posse e Hábitos de Consumo** — penetração de ar
   condicionado e uso final por classe no Brasil.
#. **BDGD de distribuidora piloto** — cadastro de alimentador para
   ``Rfdr``/``Xfdr`` reais.
#. **Oscilografia de perturbação real** — ajuste dos parâmetros hoje em *a
   calibrar*. A perturbação de 15/08/2023, citada no enunciado da Radix, é o
   caso natural.
#. **DER_A em paralelo** — fecha a lacuna de dinâmica de inversor.

Para aprofundar
===============

* Especificação: ``01-ESPECIFICACAO/12-modelo-clm-parametrizacao.md``
* Composição de classe: :doc:`classes-de-consumo`
* Código: :doc:`../../referencia/clm`
