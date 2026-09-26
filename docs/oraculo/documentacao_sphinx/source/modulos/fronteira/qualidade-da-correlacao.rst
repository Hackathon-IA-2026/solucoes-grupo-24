===========================
Qualidade da correlação
===========================

.. rubric:: Seção Fronteira T–D · aba ``#correlacao``

**Pergunta que responde:** o quanto se pode confiar na associação SED → SE de
fronteira, se não existe verdade de campo para comparar?

Rota consumida
==============

``GET /api/fronteira/qualidade``

Três frentes de validação
=========================

1. Validação externa contra o ONS
---------------------------------

A energia alocada às SEs de fronteira de cada subsistema é comparada com a
**carga verificada do ONS** no mesmo ano (balanço de energia horário). As duas
grandezas são calculadas de forma independente: nenhuma base da ANEEL entra
na carga do ONS, e vice-versa.

A razão fica **abaixo de 100% por construção**. Perdas técnicas e não
técnicas, autoconsumo da MMGD e carga ligada direto na rede básica não
aparecem no faturamento da distribuidora. O que se verifica é a **ordem de
grandeza** e a estabilidade entre subsistemas. No Norte a razão é menor
porque parte relevante da carga é eletrointensiva e conectada à rede básica.

2. Coerência física
-------------------

O **carregamento implícito** de cada SE é a carga média alocada sobre o MVA
de fronteira (FP 0,92). Uma associação boa distribui a carga de forma que
esse carregamento seja homogêneo e plausível. SE acima de 100% indica SE
vizinha ausente do cadastro de fronteira ou atração excessiva; SE abaixo de
5% costuma ser de interligação, com pouca carga local.

3. Sensibilidade às premissas
-----------------------------

As duas premissas que mais mexem no resultado são o expoente da capacidade
(α) e a escala de distância (λ). A tela varre α ∈ {1; 0,5; 0} e
λ ∈ {30; 20; 12} km e mostra, para cada combinação, a fração de vínculos
ambíguos, a fração em que a SE mais próxima foi escolhida, as SEs sem carga,
o coeficiente de variação e o máximo do carregamento.

.. admonition:: Como ler a varredura
   :class: medido

   Não existe linha "certa" na tabela: existe a linha fisicamente mais
   coerente. λ menor reduz a ambiguidade, mas com α = 0,5 e λ = 12 km surgem
   SEs acima de 100%. A configuração em uso (destacada) é a de menor dispersão
   de carregamento sem nenhuma SE sobrecarregada.

Histogramas
===========

* **Distância SED → SE** — a mediana em torno de 20 km é compatível com o
  alcance da subtransmissão de 69–138 kV.
* **Probabilidade do vínculo** — concentração abaixo de 0,5 nas metrópoles,
  onde há várias SEs de fronteira a poucos quilômetros.
* **Carregamento implícito** — energia média, não ponta: valores entre 10% e
  40% são esperados.

Limites declarados
==================

#. A topologia de subtransmissão não é dado público: a associação deve ser
   confirmada com o cadastro da distribuidora ou com o SIGA/ONS antes de uso
   operativo.
#. A posição da SED é a mediana das UCs de média e alta tensão, não a
   coordenada do barramento.
#. A baixa tensão residencial é rateada por população, não medida por SED.
#. Carregamento é energia média sobre MVA nominal — indicador de consistência,
   não de carregamento de ponta.
