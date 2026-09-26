============================================
Classes de consumo e assinatura da curva
============================================

.. rubric:: Módulo Mapa Inteligente · aba ``#classes``

**Pergunta que responde:** como a curva de carga verificada se decompõe nas
classes de consumo, e que assinatura distingue uma classe da outra?

Subtítulo na tela: *perfis canônicos e decomposição da curva de carga
verificada por mínimos quadrados não negativos*.

Rota consumida
==============

``GET /api/mapa/classes``

O método
========

A decomposição resolve, para cada subsistema:

.. math::

   \text{carga}_{\text{norm}}(t) \approx \sum_c w_c \cdot \text{perfil}_c(t),
   \qquad w_c \ge 0, \qquad \sum_c w_c = 1

por **mínimos quadrados não negativos** (``scipy.optimize.nnls``).

.. admonition:: Por que não negativos
   :class: important

   Um peso negativo não tem interpretação: significaria uma classe que
   *consome negativamente*. Restringir a não negatividade é o que faz os
   pesos serem legíveis como participação.

Duas restrições extras
----------------------

#. **Soma unitária** — entra como equação adicional com peso alto (6,0), para
   que os pesos sejam participações e não escalas livres.
#. **Razão fim de semana / dia útil** — entra como segunda equação, com peso
   2,2.

.. admonition:: A segunda assinatura é o que resolve a ambiguidade
   :class: medido

   Comercial e industrial têm ambos **platô diurno**. Só pela forma horária,
   os dois são quase indistinguíveis, e o NNLS distribui o peso de modo
   arbitrário entre eles.

   A razão fim de semana / dia útil é uma assinatura **independente da forma
   horária**: comercial 0,62, industrial 0,90. É ela que separa os dois.

Cartão · Perfis canônicos por classe
====================================

As quatro curvas de 24 h, normalizadas.

.. list-table::
   :header-rows: 1
   :widths: 24 76

   * - Classe
     - Assinatura
   * - **Residencial**
     - ponta noturna acentuada, vale de madrugada
   * - **Comercial**
     - platô de expediente, queda no fim de semana
   * - **Industrial**
     - quase plano nas 24 h, fator de carga alto
   * - **Rural / irrigação**
     - bombeamento noturno e de madrugada

.. admonition:: Os perfis canônicos são premissa, não medição
   :class: premissa

   São **estilizados a partir das características documentadas de cada
   classe** — premissa versionada em ``oraculo/profiles/classes.py``, não
   medição de campo.

   Calibrá-los com medição exige base de classe de consumo: BDGD ou a
   Pesquisa de Posse e Hábitos de Consumo do IBGE, citada no próprio
   enunciado do desafio. Consta como próximo passo.

Cartão · Assinatura de fim de semana
====================================

Tabela com a razão fim de semana / dia útil de cada classe canônica. É a
segunda equação do sistema, e a razão de ela existir está explicada acima.

Cartão · Composição por subsistema
==================================

Por subsistema: os pesos resultantes por classe, o rótulo resumido, o **R²**
do ajuste e uma qualificação em texto da qualidade do ajuste.

.. admonition:: Quando o R² é baixo
   :class: important

   Um ajuste ruim aparece com aviso no próprio cartão. Não é escondido, e a
   razão é simples: um R² baixo significa que a curva real **não** é
   combinação linear dos quatro perfis canônicos, e nesse caso os pesos não
   devem ser lidos como participação de classe. É informação sobre o limite
   do método, não um defeito a ocultar.

Cartões por subsistema
======================

Um cartão para cada subsistema, com a curva real sobreposta à curva
reconstruída pela combinação dos perfis, mais as barras de peso por classe.
A comparação visual mostra **onde** o ajuste falha — em geral no fim de tarde,
quando a MMGD deforma a curva de um modo que nenhuma classe reproduz.

Cartão · Limiares de área de telhado
====================================

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

São os limiares usados na evidência morfológica de
:doc:`perfis-por-subestacao`. A ponderação é **por área, não por contagem**.

Cartão · Notas de cada classe
=============================

Observações por classe: o que caracteriza o perfil, o que o distingue dos
demais e que cuidado tomar ao interpretá-lo.

Onde este painel é consumido
============================

.. code-block:: text

   Classes de consumo
        ├──► Perfis por subestação    (prior regional, peso 25%)
        └──► Parametrização CLM       (repartição por classe dos
                                       componentes do CMPLDW)

A tabela de repartição por classe usada em :doc:`parametrizacao-clm` tem suas
frações de motor somando exatamente a fração motora que
:doc:`perfis-por-subestacao` publica — e há teste que exige desvio zero.

Limitações específicas
======================

.. admonition:: O que este painel não afirma
   :class: limite

   * **Os perfis canônicos são estilizados**, não medidos. Calibração exige
     BDGD ou IBGE PPH.
   * A decomposição roda **por subsistema**, porque não existe curva de carga
     por subestação em dado aberto (R3).
   * O peso resultante é **participação na forma da curva**, não
     participação em energia faturada por classe.
   * **Industrial e comercial só se separam pela assinatura de fim de
     semana.** Onde essa assinatura é fraca, a separação é frágil, e o R²
     do cartão é o indicador disso.

Para aprofundar
===============

* Uso como prior regional: :doc:`perfis-por-subestacao`
* Repartição nos componentes do CLM: :doc:`parametrizacao-clm`
* Código: :doc:`../../referencia/profiles`
