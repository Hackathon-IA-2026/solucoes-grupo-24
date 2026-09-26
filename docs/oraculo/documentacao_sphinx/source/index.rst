==========================================
O.R.A.C.U.L.O. — documentação da aplicação
==========================================

**Observabilidade de Redes e Análise de Curtailment em Usinas e Limites
Operacionais**

Equipe 24 — LINKFY · Hackathon IA COPPE/UFRJ 2026 · Trilha Transição Energética

----

O que é
=======

Uma **camada de observabilidade e inteligência preditiva da fronteira
transmissão–distribuição**. O ONS dispõe de elevada observabilidade sobre o
sistema que supervisiona; na fronteira com a distribuição, essa visão depende
de informação agregada e de estimativas. A micro e minigeração distribuída e
as usinas Tipo III somam cerca de **63,5 GW** — em torno de **25% da
capacidade instalada** — sem a telemetria, a previsibilidade e a
controlabilidade dos recursos centralizados.

A aplicação entrega dois produtos:

1. **previsão da carga supervisionada** com estimativa de MMGD por área;
2. **indicadores preditivos de risco de curtailment por razão energética**,
   localizados e rastreáveis até o dado de origem.

Princípio de projeto
====================

.. admonition:: A regra que atravessa toda a aplicação
   :class: important

   Nenhuma promessa de desempenho sem teste; nenhum alerta sem evidência
   rastreável.

Operacionalmente, três consequências:

* **Todo número exibido carrega proveniência** — conjunto de origem, recurso,
  instante de extração e defasagem conhecida acompanham o valor até a tela.
* **Todo modelo é comparado a baselines** — persistência e sazonal-ingênuo são
  obrigatórios; modelo que não os supera por horizonte não é promovido.
* **Todo limite é declarado antes de ser perguntado** — a solução não executa
  fluxo de potência, não substitui o PREVCARGA e não automatiza despacho.

Como esta documentação está organizada
======================================

A navegação **espelha a da aplicação**: os quatro módulos abaixo são os quatro
grupos da barra lateral do painel, e cada subseção é uma aba. Quem está com o
painel aberto encontra a página correspondente no mesmo lugar.

.. toctree::
   :maxdepth: 2
   :caption: Visão geral

   visao-geral/index

.. toctree::
   :maxdepth: 3
   :caption: Módulos da aplicação

   modulos/index

.. toctree::
   :maxdepth: 2
   :caption: Referência técnica

   api/index
   referencia/index

.. toctree::
   :maxdepth: 2
   :caption: Transparência

   limitacoes
   glossario

Mapa rápido dos onze painéis
============================

.. list-table::
   :header-rows: 1
   :widths: 16 26 58

   * - Módulo
     - Painel
     - Pergunta que responde
   * - :doc:`Operação <modulos/operacao/index>`
     - :doc:`Despacho preditivo <modulos/operacao/despacho-preditivo>`
     - Quanto de carga o ONS vai enxergar, e quanto a MMGD está escondendo?
   * -
     - :doc:`Risco e excedentes <modulos/operacao/risco-e-excedentes>`
     - Onde há risco de curtailment nas próximas horas, e por quê?
   * - :doc:`Análise <modulos/analise/index>`
     - :doc:`Curtailment <modulos/analise/curtailment>`
     - Quanto foi efetivamente restringido, em que área e por qual razão?
   * -
     - :doc:`Perfis e CLM <modulos/analise/perfis-e-clm>`
     - Qual é a forma típica da carga e da MMGD por dia-tipo?
   * -
     - :doc:`Triangulação <modulos/analise/triangulacao>`
     - O ativo de GD existe, está na topologia e está homologado?
   * - :doc:`Mapa Inteligente <modulos/mapa/index>`
     - :doc:`Perfis por subestação <modulos/mapa/perfis-por-subestacao>`
     - Qual o perfil de consumo e a penetração de MMGD de cada subestação?
   * -
     - :doc:`Visão computacional <modulos/mapa/visao-computacional>`
     - O detector de painéis funciona? Com que precisão, medida como?
   * -
     - :doc:`Classes de consumo <modulos/mapa/classes-de-consumo>`
     - Como a curva de carga real se decompõe em classes?
   * -
     - :doc:`Parametrização CLM <modulos/mapa/parametrizacao-clm>`
     - Que parâmetros usar no Modelo de Carga Composta, e em quais confiar?
   * - :doc:`Confiança <modulos/confianca/index>`
     - :doc:`Validação <modulos/confianca/validacao>`
     - O método supera os baselines? Onde ele erra?
   * -
     - :doc:`Dados abertos <modulos/confianca/dados-abertos>`
     - De onde veio cada número, e quando foi extraído?

Como construir esta documentação
================================

Sphinx, do diretório ``docs/oraculo/documentacao_sphinx``:

.. code-block:: bash

   python build_docs.py --open      # constrói e abre no navegador
   python build_docs.py --strict     # trata aviso como erro
   python build_docs.py --clean      # reconstrói do zero

   make html                         # equivalente, se `make` existir
   .\make.bat html                   # equivalente no Windows

A saída fica em ``build/html/index.html``. A construção é **offline**: não
depende de rede, e o ``autodoc`` importa o pacote ``oraculo`` com
``ORACULO_OFFLINE=1`` para garanti-lo.
