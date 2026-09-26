================
Fronteira T–D
================

A seção que **liga as duas pontas da fronteira transmissão–distribuição**: as
subestações de fronteira da rede básica, publicadas pelo ONS, e as
subestações de distribuição (SED), que estão na BDGD da ANEEL. O objetivo é
levar ao modelo de carga de cada SE de fronteira a carga e a MMGD que
**de fato** passam por ela, com dado faturado real em vez de estimativa
morfológica.

.. toctree::
   :maxdepth: 2

   se-x-distribuicao
   qualidade-da-correlacao

Por que esta seção existe
=========================

O Mapa Inteligente responde, para cada SE de fronteira, qual o perfil de
consumo da área e a presença de GD, a partir de ortoimagem e do prior do
subsistema. As duas evidências são **indiretas**. A ANEEL publica, em dado
aberto, as unidades consumidoras de média e alta tensão com o código da SED
que as atende, 12 meses de energia e demanda e o vínculo com a GD. Com isso a
composição da carga deixa de ser inferida da forma dos telhados e passa a ser
**medida no faturamento**.

.. code-block:: text

   SE de fronteira (ONS)           SED (ANEEL · BDGD)
   subestacao + capacidade-  ←──── UCMT / UCAT: SUB, classe,
   transformacao, sec ≤ 138 kV     energia, demanda, CEG_GD
            │                            │
            │     modelo gravitacional   │
            └─────────────┬──────────────┘
                          ▼
         carga por classe + MMGD por SE de fronteira
         (MT/AT medida · BT do SAMP rateada · GD do cadastro)
                          │
                          ▼
         cartão do Modelo de Carga Composta (fonte = BDGD)

Fontes, todas abertas
=====================

.. list-table::
   :header-rows: 1
   :widths: 30 40 30

   * - Conjunto
     - Uso
     - Granularidade
   * - ONS ``subestacao`` + ``capacidade-transformacao``
     - SE de fronteira: posição, agente, MVA de fronteira
     - por subestação
   * - ANEEL · BDGD ``UCMT_PJ`` e ``UCAT_PJ``
     - reconstrução da SED; energia e demanda por classe
     - por unidade consumidora (pessoa jurídica)
   * - ANEEL · Relação de empreendimentos de MMGD
     - MMGD por município e, pelo ``CEG_GD``, por SED
     - por empreendimento
   * - ANEEL · SAMP
     - energia de baixa tensão por distribuidora e classe
     - por distribuidora, mensal
   * - IBGE · SIDRA 6579 e malha municipal
     - rateio da baixa tensão; centroide do município
     - por município

.. admonition:: O limite mais importante desta seção
   :class: limite

   **A associação SED → SE de fronteira é inferida.** A topologia de
   subtransmissão (qual SED é alimentada por qual SE) está no cadastro interno
   da distribuidora, não em dado aberto. Cada vínculo sai com probabilidade e
   alternativas, e o painel de qualidade mostra onde a inferência é frágil.
