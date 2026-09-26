=================
Alocação de BESS
=================

.. rubric:: Seção Investimento · aba ``#bess``

**Pergunta que responde:** em quais subestações de conexão das usinas
centralizadas um BESS recuperaria mais energia cortada, e quanto desse corte é
excedente que a MMGD cria ao reduzir a carga líquida?

Rotas consumidas
================

``GET /api/bess/status`` · ``GET /api/bess/ranking`` ·
``GET /api/bess/sitio/{code}``. Os pesos seguem na query
(``w_energia``, ``w_mmgd``, ``w_recorrencia``, ``w_local``).

A base
======

Doze meses completos dos conjuntos ``restricao_coff_fotovoltaica`` e
``restricao_coff_eolica_usi`` do ONS. O corte é o campo oficial
``val_geracaonaorealizadaapurada`` (MW médio no intervalo de 30 min). Cada mês
é agregado por ponto de conexão e guardado; o bruto (~70 MB por mês) não.

**Do ponto à SE.** O ``id_pontoconexao`` tem o código da SE em largura fixa de
6 caracteres (``RNACT-500-A`` → RNACT; ``MGJBA3500-A`` → MGJBA3). Separar pelo
primeiro hífen erra os códigos de 6 letras. Quando a SE é coletora privada e
não está no cadastro do ONS, a posição vem das usinas: nome do ponto em
``modalidade-usina`` → CEG → coordenada no SIGA/ANEEL.

Simulação do BESS
=================

Por dia, com potência *P* e energia *E*:

.. math::

   \text{absorvido} = \min\Big(E,\ \sum_t \min(\text{corte}_t, P)\cdot 0{,}5\,\text{h}\Big),
   \qquad \text{entregue} = \eta \cdot \text{absorvido}

com um ciclo por dia e :math:`\eta = 0{,}88`. Energia e ciclos são anualizados.

**Dimensionamento pelo ciclo marginal.** Sobe-se na fronteira eficiente da
grade (25 a 500 MW × 2, 4 e 6 h) e para-se quando o MWh **adicional** cicla
menos de 200 vezes por ano. A regra "maior BESS que ainda cicla bem" escolhe
sempre o topo da grade num sítio de corte grande: o ativo inteiro cicla bem
mesmo quando os últimos MWh quase não são usados.

Corte induzido pela MMGD
========================

A MMGD não é cortada. Ela reduz a carga líquida e cria o excedente que vira
corte por razão energética de origem sistêmica. Como a razão energética é um
balanço do SIN, a atribuição usa a MMGD do SIN, em cada meia hora *t*:

.. math::

   \text{induzido}(t) = \min\big(\text{corte}_{\text{ENE+SIS, SIN}}(t),\;
   \text{MMGD}_{\text{SIN}}(t)\big)

— sem a MMGD, a carga líquida seria maior nessa quantidade. O volume é rateado
entre os sítios pelo corte ENE+SIS de cada um. É um **limite superior**
contrafactual; corte por confiabilidade (CNF), indisponibilidade (REL) ou de
origem local não é atribuído à MMGD.

.. admonition:: A MMGD vizinha não escolhe o sítio de geração
   :class: important

   MMGD alta ao lado de uma usina não faz aquela usina ser mais cortada. A
   penetração local de MMGD aparece na outra tese, **BESS junto à carga**, e
   não na pontuação do sítio de geração.

Curva do pato
=============

Perfil médio horário, nos dias da janela, por subsistema: carga com MMGD,
carga supervisionada, carga líquida (menos eólica e solar centralizadas) e o
corte apurado.

Pontuação
=========

Soma ponderada de postos percentuais (0 a 1) de quatro componentes:

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Componente
     - Peso padrão
     - Medida
   * - Energia recuperável
     - 45%
     - GWh/ano entregues pelo BESS dimensionado para o sítio
   * - Excedente da MMGD
     - 20%
     - fração do corte do sítio atribuível à MMGD (ENE+SIS na curva do pato)
   * - Recorrência
     - 20%
     - fração dos dias da janela com corte ≥ 1 MWh
   * - Restrição local
     - 15%
     - fração do corte com origem LOC

Postos em vez de valores brutos impedem que um sítio gigante esmague os
outros; o empate recebe o posto médio.

O que a tela mostra
===================

* **Mapa e ranking** — sítios dimensionados pela energia cortada; top 10
  numerado.
* **Pesos** — ajustáveis; o servidor refaz a pontuação.
* **Detalhe** — BESS sugerido, energia recuperada, as frases de *por que este
  sítio*, curva de dimensionamento, mapa de calor mês × hora, perfil diário,
  razão, origem e usinas.
