========
Operação
========

O módulo de uso corrente: **o que vai acontecer nas próximas horas**, e o que
fazer a respeito. Dois painéis, um por eixo da solução.

.. toctree::
   :maxdepth: 2

   despacho-preditivo
   risco-e-excedentes
   curva-do-pato-tempo

O que une os dois painéis
=========================

Ambos partem da mesma decomposição:

.. math::

   \text{carga global} = \text{carga supervisionada} + \text{MMGD estimada}

A carga supervisionada é o que o ONS mede. A MMGD **não é publicada** como
série horária por área: aparece apenas como redução da carga verificada. O
primeiro painel estima essa parcela e prevê a supervisionada; o segundo usa a
geração renovável resultante para antecipar onde a restrição vai aparecer.

.. admonition:: Viés declarado
   :class: premissa

   A estimativa de MMGD é **conservadora — um piso, não um valor central**.
   O método do envelope usa o percentil 90 da carga em horas comparáveis como
   aproximação da carga global, e mesmo os dias de maior carga contêm alguma
   geração distribuída.
