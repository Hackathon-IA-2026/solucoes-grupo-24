============
Investimento
============

Apoio à decisão de investimento em **armazenamento (BESS)**: onde um sistema de
baterias recupera mais energia cortada das usinas **eólicas e fotovoltaicas
centralizadas**, e quanto desse corte é excedente criado pela MMGD.

.. toctree::
   :maxdepth: 2

   alocacao-de-bess
   metodo-e-sensibilidade
   projecao-do-corte-ene

Onde está o corte, e onde está a MMGD
=====================================

**O corte acontece nas usinas centralizadas.** A MMGD não é cortada. O que ela
faz é reduzir a carga líquida do sistema ao meio-dia e aprofundar a barriga da
**curva do pato**: o excedente resultante vira restrição por **razão
energética de origem sistêmica** (ENE + SIS) em qualquer usina do SIN, não
necessariamente perto de onde a MMGD está instalada.

Por isso a seção separa duas teses de investimento:

* **BESS junto à geração cortada** — o ranking. Absorve o corte da usina e
  devolve na rampa do fim da tarde. A MMGD entra como a *fração do corte do
  sítio que o excedente criado por ela explica*.
* **BESS junto à carga** — onde a MMGD mais pesa sobre a carga (seção
  Fronteira T–D). Achata a curva do pato na origem, mas não recupera o corte de
  uma usina específica.

.. code-block:: text

   constrained-off apurado (ONS, 12 meses, FV + eólica)
            │  por ponto de conexão → SE (código ONS · SIGA/ANEEL)
            ▼
   série semi-horária do corte por sítio
            │  BESS simulado: carga no corte, 1 ciclo/dia
            ▼
   energia recuperável e dimensionamento pelo ciclo marginal
            │  + corte ENE+SIS atribuível à MMGD do SIN (curva do pato)
            ▼
   ranking de sítios, com pesos ajustáveis e teste de estabilidade

.. admonition:: O limite mais importante desta seção
   :class: limite

   **O corte observado não é o corte futuro.** Obras de transmissão previstas
   podem eliminar restrições locais. O ranking indica onde o armazenamento
   teria recuperado mais energia na janela observada; a decisão de investimento
   ainda depende de receita, regulação e do plano de expansão.
