==========================
Triangulação de evidências
==========================

.. rubric:: Módulo Análise · aba ``#triangulacao``

**Pergunta que responde:** o ativo de geração distribuída existe fisicamente,
está na topologia da distribuidora e está homologado na ANEEL?

Subtítulo na tela: *três camadas independentes e a lógica de desempate*.

Rota consumida
==============

``GET /api/triangulation``

O problema
==========

Nenhuma das três bases disponíveis é suficiente sozinha, e todas discordam
entre si — por razões legítimas, de **cadência**:

.. list-table::
   :header-rows: 1
   :widths: 8 24 34 34

   * - #
     - Camada
     - Pergunta que responde
     - Cadência
   * - 1
     - Realidade física — imagem de satélite e visão computacional
     - O ativo existe, e onde está?
     - mensal / trimestral
   * - 2
     - Topologia — BDGD (ANEEL)
     - A que alimentador está conectado?
     - anual
   * - 3
     - Cadastro — Empreendimentos de GD (ANEEL)
     - Foi homologado, e quando?
     - diária

.. admonition:: Por que a discordância é informação, não ruído
   :class: important

   Um ativo homologado ontem **não pode** estar na BDGD, que é anual. Tratar
   essa ausência como erro de cadastro seria errado. Tratá-la como
   irrelevante também. O que a matriz de desempate faz é **nomear** cada
   combinação e dar a ela um encaminhamento distinto.

Os quatro KPIs
==============

.. list-table::
   :header-rows: 1
   :widths: 30 14 56

   * - KPI
     - Unidade
     - Como ler
   * - **Unidades avaliadas**
     - contagem
     - Tamanho da amostra classificada.
   * - **Defasagem de sistema**
     - %
     - Homologadas e ausentes da BDGD. **Não é irregularidade** — é a
       cadência anual da base. Entra no fator de correção.
   * - **Não homologadas**
     - %
     - Presentes fisicamente e sem registro. Escaladas como exceção.
   * - **Confirmadas**
     - %
     - As três camadas concordam. É o caso em que a estimativa pode ser
       usada sem ressalva.

Cartão · Lógica de desempate
============================

A matriz completa. Cinco classificações possíveis:

.. list-table::
   :header-rows: 1
   :widths: 26 12 10 12 40

   * - Classificação
     - satélite
     - BDGD
     - ANEEL
     - Encaminhamento
   * - **CONFIRMADA**
     - sim
     - sim
     - sim
     - Usar sem ressalva.
   * - **LAG_DE_SISTEMA**
     - sim
     - não
     - sim
     - Homologada, ausente da base anual. **Entra no fator de correção** — é
       o caso que torna a estimativa melhor do que o cadastro.
   * - **NAO_HOMOLOGADA**
     - sim
     - —
     - não
     - Existe e gera sem registro. **Escalada como exceção, nunca somada
       silenciosamente.**
   * - **CADASTRO_SEM_EVIDENCIA**
     - não
     - —
     - sim
     - Registro sem evidência física. Pode ser instalação pendente, erro de
       coordenada ou limite do detector.
   * - **SEM_EVIDENCIA**
     - não
     - não
     - não
     - Nada a afirmar.

Implementação em ``oraculo/triangulation/evidence.py``, função
``classify(detected, in_bdgd, in_aneel)``.

.. admonition:: A decisão de projeto mais importante deste painel
   :class: important

   Separar **defasagem de sistema** de **não homologada**. Um sistema que
   somasse as duas produziria um número maior e sem sentido: misturaria
   atraso administrativo com irregularidade. Separadas, cada uma tem um
   destino distinto — a primeira corrige a estimativa, a segunda vira
   exceção a tratar.

Cartão · Três camadas de evidência
==================================

Tabela com, por camada: a fonte, a pergunta que responde, a cadência de
atualização e o estado corrente de disponibilidade.

Cartão · Fator de correção por área
===================================

Por área: quantas unidades em defasagem de sistema, e o fator de correção
resultante a ser aplicado sobre a capacidade cadastrada.

É o produto operacional do painel: a capacidade instalada declarada
**subestima** a realidade na proporção das unidades homologadas que a base
topológica ainda não incorporou.

Cartão · Amostra de unidades classificadas
==========================================

Tabela com exemplos individuais e sua classificação, para inspeção. Permite
verificar se a lógica está se comportando em casos concretos em vez de
confiar apenas no agregado.

Limitações específicas
======================

.. admonition:: O que este painel não afirma
   :class: limite

   * A camada de **realidade física** usa, nesta versão, a detecção sobre
     **ortoimagem sintética** — ver
     :doc:`../mapa/visao-computacional`. O detector é real; a imagem é de
     demonstração.
   * A **BDGD não é dado aberto de acesso direto**. A camada 2 opera com o
     que é publicamente acessível, e a granularidade-alvo exige convênio ou
     base de distribuidora piloto.
   * A classificação **não é fiscalização**. "Não homologada" é uma
     hipótese a verificar, não uma imputação — pode haver erro de
     coordenada, de detecção ou de recorte temporal.
   * A amostra exibida é **amostra**, não censo.

Para aprofundar
===============

* Desempenho do detector: :doc:`../mapa/visao-computacional`
* Limitações declaradas: ``01-ESPECIFICACAO/08-limitacoes.md``
* Código: :doc:`../../referencia/triangulation`
