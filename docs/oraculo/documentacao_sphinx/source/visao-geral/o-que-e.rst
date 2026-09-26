========================
O que é o O.R.A.C.U.L.O.
========================

O problema
==========

O ONS supervisiona o Sistema Interligado Nacional com alta observabilidade
sobre os recursos centralizados: telemetria, previsão e controlabilidade. Na
**fronteira com a distribuição**, essa visão muda de natureza — passa a
depender de informação agregada e de estimativa.

A micro e minigeração distribuída (MMGD) e as usinas Tipo III somam cerca de
**63,5 GW**, em torno de **25% da capacidade instalada**. Essa parcela:

* não tem telemetria em tempo real por área;
* não aparece no Portal de Dados Abertos como série horária por área —
  manifesta-se apenas como **redução da carga verificada**;
* responde a distúrbios de forma que os modelos usados em estudo não
  reproduzem, como a perturbação de 15/08/2023 evidenciou.

O que a solução faz
===================

Integra séries operativas do Portal de Dados Abertos do ONS, cadastro e
topologia de distribuição, geometria solar e evidência física por imagem, e
entrega:

.. list-table::
   :header-rows: 1
   :widths: 8 42 50

   * - Eixo
     - Produto
     - Onde está no painel
   * - **i**
     - Previsão da carga supervisionada com estimativa de MMGD por área
     - :doc:`../modulos/operacao/despacho-preditivo`
   * - **ii**
     - Indicadores preditivos de risco de curtailment por razão energética
     - :doc:`../modulos/operacao/risco-e-excedentes`

Mais o módulo :doc:`../modulos/mapa/index`, que responde ao desafio
Radix + AXIA + Cepel: perfil de carga e presença de geração distribuída
**por subestação**, terminando em parâmetros para o Modelo de Carga Composta.

Por que o nome
==============

**O**\ bservabilidade de **R**\ edes e **A**\ nálise de **C**\ urtailment em
**U**\ sinas e **L**\ imites **O**\ peracionais.

Não é um oráculo que adivinha: é uma camada que **torna observável** o que
hoje é estimado, e que declara a incerteza de cada estimativa.

O que a solução não faz
=======================

.. admonition:: Fronteiras de escopo, declaradas
   :class: limite

   * **Não executa fluxo de potência.** Não calcula tensão, carregamento nem
     estabilidade. O destino natural dos seus produtos são as ferramentas que
     fazem isso — e é por isso que existe o painel de parametrização do CLM.
   * **Não substitui o PREVCARGA.** É camada complementar, focada na parcela
     não supervisionada.
   * **Não automatiza despacho.** Produz indicador e evidência rastreável; a
     decisão é do operador.
   * **Não mede a MMGD.** Estima, com viés declarado e conservador.

Referências do projeto
======================

* Especificação técnica: ``01-ESPECIFICACAO/`` (12 documentos)
* Protótipo executável: ``Backend/oraculo/`` (API) e ``Frontend/oraculo-dashboard/src/oraculo/`` (telas React)
* ONS — Portal de Dados Abertos: https://dados.ons.org.br/
* ONS — PAR/PEL 2025, Sumário Executivo
* ONS — FAQ Curtailment: https://www.ons.org.br/Paginas/faq_curtailment.aspx
* WECC — Composite Load Model Specification
