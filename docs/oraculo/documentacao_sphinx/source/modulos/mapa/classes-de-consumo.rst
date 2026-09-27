============================================
Classes de consumo e assinatura da curva
============================================

.. rubric:: Módulo Mapa Inteligente · aba ``#classes``

**Pergunta que responde:** como cada classe de consumo usa energia ao longo do
dia, quanto cada classe pesa em cada subsistema, e isso explica a curva que o
ONS observa?

Subtítulo na tela: *perfis medidos por classe (ANEEL CTR) e composição real
por subsistema (BDGD + SAMP), validados contra a curva do ONS*.

Rota consumida
==============

``GET /api/mapa/classes`` — com proveniência própria: ONS (validação), ANEEL e
IBGE da base da fronteira T–D (composição) e ANEEL CTR (forma).

Três peças, todas de dado real
==============================

.. list-table::
   :header-rows: 1
   :widths: 16 40 44

   * - Peça
     - Fonte
     - O que dá
   * - **Forma**
     - ANEEL · *CTR – Curva de Carga Consumidor Tipo*
     - curva de 15 min de cada classe, medida nas campanhas das revisões
       tarifárias (dia útil, sábado, domingo)
   * - **Composição**
     - BDGD (UCMT/UCAT por SED) + SAMP (BT por distribuidora), já associadas
       às SEs de fronteira em :doc:`../fronteira/index`
     - energia faturada por classe em cada subsistema
   * - **Validação**
     - ONS · carga **global** do subsistema
     - a curva real contra a qual a curva montada é comparada

A curva montada do dia útil é

.. math::

   \text{curva}(h) = \sum_c e_c \cdot \text{forma}_c(h),
   \qquad e_c \propto \frac{E_c}{5 + \text{sáb}_c + \text{dom}_c}

em que :math:`E_c` é a energia anual faturada da classe e sáb/dom são a
energia medida do sábado e do domingo em relação ao dia útil da própria classe.
A correção existe porque a energia é anual e a forma é de dia útil: uma classe
que some no fim de semana pesa mais no dia útil. A razão domingo/dia útil
montada sai da mesma conta.

.. admonition:: A curva do ONS deixou de ser a fonte da composição
   :class: medido

   Até setembro de 2026 esta tela adivinhava a composição encaixando a curva
   do ONS em quatro perfis **desenhados à mão**, por mínimos quadrados não
   negativos. O perfil "rural" desenhado (bombeamento de madrugada) tinha
   correlação **negativa** com o rural medido, e o ajuste chegava a atribuir
   35 % do Sudeste ao rural, contra 2 % na energia faturada. Agora a
   composição vem da energia faturada e a curva do ONS só **valida**.

As classes seguem o que a ANEEL mede
====================================

.. list-table::
   :header-rows: 1
   :widths: 30 18 52

   * - Classe
     - Subgrupos
     - Assinatura medida
   * - **Residencial**
     - B1
     - ponta às 19h, vale de madrugada; domingo ≈ dia útil
   * - **Rural**
     - B2
     - pico também às 19h
   * - **Comercial, serviços e demais BT**
     - B3
     - platô 9h–16h, domingo ~0,70 do dia útil
   * - **Média tensão**
     - A4, AS
     - platô diurno, domingo ~0,64
   * - **Alta tensão**
     - A1, A2, A3, A3a
     - quase plana; grande indústria

.. admonition:: Por que não "comercial × industrial"
   :class: premissa

   A ANEEL mede por **subgrupo tarifário**. O B3 junta comércio, serviços e
   pequena indústria de baixa tensão; separá-los exigiria um critério que o
   dado não traz. A indústria aparece pela tensão (MT e AT).

Como os perfis são calculados
=============================

#. Só o processo tarifário **mais recente** de cada distribuidora
   (campanhas de 2016 a 2026, 62 distribuidoras).
#. Cada curva (distribuidora × subgrupo × CT) vira média horária e é dividida
   pela **sua própria** média de dia útil (p.u.).
#. O perfil da classe é a média **simples** das curvas: o arquivo não diz
   quantos consumidores cada curva representa, então não há peso honesto a
   aplicar.
#. Domingo do CTR = dia-tipo domingo/feriado do projeto.

Download: apelido ``aneel_ctr_consumidor_tipo`` em
``Backend/config/fontes_ons.yaml``. Parâmetros:
``Backend/config/perfis_classe.yaml``. Código:
``Backend/oraculo/profiles/medidos.py`` (``python -m oraculo.profiles.medidos``
reconstrói a tabela; a API também a constrói sozinha se só o bruto existir).

Composição
==========

* **Baixa tensão** (SAMP, rateado para as SEs de fronteira): residencial → B1,
  rural → B2, comercial e industrial → B3.
* **MT/AT** (BDGD): SED só com UCs de MT → média tensão; só com UCs de AT →
  alta tensão; com as duas → média tensão (a base agregada soma a energia e
  não separa). A fração dessas SEDs aparece na tabela como *SED mista*.

Validação
=========

.. admonition:: Por que a carga GLOBAL e não a supervisionada
   :class: important

   O CTR mede **consumo**. A carga supervisionada desconta a MMGD, o que
   achata o meio-dia: comparar com ela faria a curva montada "errar" por um
   efeito que não é de classe. Com a carga global, o R² sobe de 0,57 para
   0,93 no Sul e de 0,32 para 0,77 no Sudeste/Centro-Oeste.

A qualidade é classificada pelo R² da forma do dia útil (limiares em
``perfis_classe.yaml``: bom ≥ 0,70; moderado ≥ 0,50).

.. admonition:: Quando não valida: cobertura
   :class: limite

   A **cobertura** é a energia da distribuição associada às SEs de fronteira
   dividida pela energia do ONS no mesmo ano. No Norte ela é ~39 % e no
   Nordeste ~62 %: o restante são consumidores ligados direto na rede básica
   (eletrointensivos) e perdas, carga quase plana que não está na composição.
   Ali a curva montada sai mais ondulada que a observada e o R² é negativo. A
   tela mostra isso com aviso em vez de ajustar pesos para esconder.

Cartões
=======

* **Perfis medidos por classe** — dia útil em p.u.
* **Fim de semana e amostra** — sábado e domingo relativos ao dia útil,
  número de curvas, distribuidoras e anos dos processos.
* **Cartões por subsistema** — carga global do ONS × curva montada, R²,
  qualidade, cobertura e barras da composição.
* **Composição por subsistema** — participações, GWh/ano, cobertura, SED
  mista, R² e domingo/dia útil observado × montado.
* **Limiares de área de telhado · PREMISSA** — residencial até 220 m²,
  comercial 220–1.200 m², industrial acima. Não é medição: são os limiares da
  evidência morfológica de :doc:`perfis-por-subestacao`.
* **O que cada classe cobre** — subgrupos e assinatura medida.

Limitações específicas
======================

.. admonition:: O que este painel não afirma
   :class: limite

   * **Perfis nacionais.** O CTR não traz subsistema, e mapear distribuidora
     → subsistema pelas siglas antigas do arquivo seria frágil.
   * **Iluminação pública (B4)** não é classe própria: no SAMP ela já soma na
     comercial.
   * **Sem base da fronteira** (modo demonstrativo ou construção em
     andamento), a composição não é mostrada — nunca é estimada por outro
     caminho.
   * O prior regional de :doc:`perfis-por-subestacao` ainda usa a
     decomposição NNLS sobre os perfis estilizados de
     ``oraculo/profiles/classes.py``.

Para aprofundar
===============

* Composição por SE de fronteira: :doc:`../fronteira/index`
* Uso como prior regional: :doc:`perfis-por-subestacao`
* Código: :doc:`../../referencia/profiles`
