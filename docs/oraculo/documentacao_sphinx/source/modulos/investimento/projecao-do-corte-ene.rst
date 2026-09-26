======================================
Projeção do corte por razão energética
======================================

.. rubric:: Seção Investimento · aba ``#projecao``

**Pergunta que responde:** quanto corte por razão energética (ENE) vem pela
frente, quanto dele a MMGD explica, e quanto armazenamento ele justifica no
SIN?

Rotas consumidas
================

``GET /api/ene/status`` · ``GET /api/ene/projecao``. O cenário personalizado
segue na query: ``g_vre``, ``g_mmgd``, ``g_load`` e ``flex_gw``.

As séries
=========

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - Série
     - Origem
   * - Corte ENE+SIS horário do SIN
     - constrained-off do ONS, eólica desde 10/2021 e fotovoltaica desde 04/2024
   * - Carga, eólica e solar verificadas
     - balanço de energia horário do ONS, SIN
   * - MMGD conectada por mês
     - cadastro técnico fotovoltaico da ANEEL, pela data de conexão

A série fotovoltaica de corte só é publicada a partir de 04/2024. Antes disso o
total do SIN está incompleto, e o modelo só é calibrado dali em diante.

Por que um modelo físico
========================

O corte ENE cresceu em saltos; uma tendência ajustada a isso projeta o próprio
salto para sempre. O que o gera, porém, é mensurável hora a hora:

.. math::

   NL(t) = \text{carga supervisionada}(t) - \big[\text{eólica} + \text{solar}\big]_{\text{potencial}}(t)

   \text{corte}_{\text{ENE+SIS}}(t) = \alpha \cdot \max\big(0,\ \theta_{\text{mês}} - NL(t)\big)

A geração **potencial** é a verificada mais a cortada. Sem somar o corte de
volta, o modelo seria circular: o corte reduz a geração verificada e "eleva" a
carga líquida. θ tem um valor por mês do ano (a inflexibilidade hidráulica é
sazonal) e α mede quanto do excedente vira corte apurado. Os parâmetros são
ajustados por mínimos quadrados em grade.

Validação
=========

Ajuste até 08/2025, teste nos 12 meses seguintes, comparado com o ingênuo
*mesmo mês do ano anterior*. A tela mostra o erro percentual mensal, o viés
do total e a correlação horária no período de teste.

Projeção
========

Sobre o ano de referência observado (os últimos 12 meses: mesmo clima, mesmo
perfil), no ano *k*:

.. math::

   NL_k = \big[(\text{sup} + \text{MMGD})(1+g_c)^k - \text{MMGD}(1+g_m)^k\big]
          - \text{VRE}(1+g_v)^k, \qquad \theta_k = \theta - \text{flex}\cdot k

Crescer a MMGD reduz a carga supervisionada e aprofunda a curva do pato. A
tela mostra também o corte **sem** crescimento da MMGD, o que isola o efeito
dela.

Os cenários:

* **PLAN 2026-2030 (2ª RQ)** — a referência. Carga global e MMGD do SIN **ano a
  ano** da 2ª Revisão Quadrimestral do PLAN 2026-2030 (ONS/EPE/CCEE,
  07/08/2026): carga global de 84.989 MWmed (2026) a 101.947 MWmed (2030);
  MMGD de 8.536 a 11.240 MWmed (55,6 a 72,5 GW instalados). O documento não
  traz a geração centralizada: eólica + solar seguem o PAR/PEL 2025 (55,1 GW
  em dez/2025 a 60,3 GW no fim de 2029, +2,3% a.a.).
* **PAR/PEL 2025** — MMGD de 46,2 GW (dez/2025) a 65,3 GW (fim de 2029);
  carga máxima de 2030 17% acima da de 2025.
* **tendência observada** — extrapolação das séries; só contraste.

A MMGD horária tem o perfil da estimativa do envelope e o **nível oficial**:
a estimativa (3,1 GWmed no ano de referência) é escalada para os 8.536 MWmed
do PLAN em 2026. A estimativa, sozinha, subestimava a MMGD em 2,7 vezes.

A coluna "da MMGD" é a diferença para a mesma projeção com a MMGD no nível de
referência: **atribuição, não cenário** — a MMGD continua crescendo.

.. admonition:: A leitura que decide o investimento
   :class: medido

   Na trajetória oficial, a carga global (+4,5% a.a., com datacenters) cresce
   mais que a expansão centralizada considerada (+2,3% a.a.): o corte ENE+SIS
   cai, mas cerca de metade dele em 2030 passa a ser devida ao crescimento da
   MMGD. No ritmo observado de expansão centralizada, o corte explode. O caso
   de BESS depende sobretudo do ritmo da expansão centralizada frente à carga.

BESS justificável
=================

O corte ENE+SIS é **sistêmico**: um armazenamento em qualquer ponto do SIN o
absorve. O BESS é dimensionado no nível do SIN com o mesmo critério da
alocação: sobe-se na grade (1 a 30 GW × 2, 4 e 6 h) enquanto o GWh
**adicional** ainda cicla ao menos 200 vezes por ano. O resultado do último
ano é rateado entre os sítios de maior corte ENE+SIS, como leitura de onde ele
recupera mais sem depender de rede.

.. admonition:: Limites
   :class: limite

   Um único ano de referência (clima e hidrologia daquele ano). θ constante no
   cenário base: sem nova transmissão nem flexibilidade, o corte projetado é o
   que rede, armazenamento e flexibilidade precisariam resolver. A expansão
   centralizada do PAR/PEL cobre o que já é considerado nos estudos; expansão
   adicional aumenta o corte.
