============================
Dados abertos e proveniência
============================

.. rubric:: Módulo Confiança · aba ``#dados``

**Pergunta que responde:** de onde veio cada número, quando foi extraído, e o
que mais existe no Portal que ainda não usamos?

Subtítulo na tela: *navegação pelo catálogo do Portal de Dados Abertos do ONS,
estado do cache e auditoria*.

Rotas consumidas
================

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Rota
     - O que traz
   * - ``GET /api/catalog``
     - catálogo do Portal, conjuntos curados, fontes externas
   * - ``GET /api/catalog/{pkg}``
     - detalhe de um conjunto, com dicionário e recursos
   * - ``GET /api/provenance``
     - auditoria completa: relatórios de ingestão e manifesto de cache
   * - ``POST /api/ingest``
     - dispara ingestão (é a única rota de escrita da aplicação)

Os quatro KPIs
==============

.. list-table::
   :header-rows: 1
   :widths: 32 14 54

   * - KPI
     - Unidade
     - Como ler
   * - **Conjuntos no Portal**
     - contagem
     - Tamanho do catálogo CKAN do ONS — 85 conjuntos.
   * - **Recursos em cache**
     - contagem
     - Quantos recursos estão em ``.cache/`` com hash registrado.
   * - **Modo corrente**
     - ``live`` / ``cache`` / ``demo``
     - Origem predominante dos dados nesta sessão.
   * - **Fontes externas mapeadas**
     - contagem
     - Fontes de fora do ONS identificadas, com o estado de cada uma.

Cartão · Conjuntos usados na solução
====================================

Os sete conjuntos que a solução consome, com granularidade e uso.

.. list-table::
   :header-rows: 1
   :widths: 34 22 44

   * - Conjunto
     - Granularidade
     - Uso
   * - ``balanco-energia-subsistema``
     - horária, por subsistema
     - carga verificada e geração por fonte — espinha dorsal
   * - ``curva-carga``
     - horária, por subsistema
     - conferência cruzada da carga
   * - ``restricao_coff_fotovoltaica``
     - semi-horária, por usina
     - rótulo do risco de curtailment
   * - ``restricao_coff_eolica_usi``
     - semi-horária, por usina
     - rótulo, fonte eólica
   * - ``subestacao``
     - cadastral, por subestação
     - subestações georreferenciadas — entrada do Mapa Inteligente
   * - ``capacidade-transformacao``
     - cadastral, por transformador
     - área de influência e identificação da fronteira T–D
   * - ``modalidade-usina``
     - cadastral, por usina
     - usinas Tipo III conectadas à distribuição

Cartão · Catálogo completo do Portal
====================================

Lista navegável dos 85 conjuntos. Clicar carrega o detalhe.

.. admonition:: Por que o catálogo inteiro está na tela
   :class: important

   Duas razões. Primeira: mostra que a solução conhece o terreno — os
   conjuntos usados foram **escolhidos**, não os primeiros encontrados.
   Segunda: torna verificável o que ainda não foi usado, que é matéria dos
   próximos passos.

Cartão · Detalhe do conjunto
============================

Ao selecionar um conjunto: descrição, dicionário de campos, e a lista de
recursos por ano/mês com tamanho e data de atualização.

Cartão · Relatório de ingestão
==============================

Por operação de ingestão: conjunto, recurso, linhas lidas, bytes lidos,
instante, modo resultante e eventuais avisos.

.. admonition:: Requisições Range
   :class: important

   Os CSV do Portal são grandes. O protótipo usa cabeçalho HTTP ``Range``
   para ler apenas o trecho necessário, em vez de baixar o arquivo inteiro.
   O campo ``bytes_read`` do relatório mostra o efeito disso.

Cartão · Previsto para a fase presencial
========================================

Conjuntos e fontes que a solução pretende incorporar, com a justificativa de
cada um. É a lista honesta do que **falta**, no lugar em que o avaliador vai
procurá-la.

Cartão · Fontes externas e seu estado
=====================================

Fontes de fora do Portal do ONS — BDGD e cadastro de GD da ANEEL, IBGE,
meteorologia — com o estado corrente de acessibilidade.

.. admonition:: Uma fonte inacessível é informação
   :class: limite

   O guia de composição de carga da NERC, citado em
   :doc:`../mapa/parametrizacao-clm`, retorna **HTTP 403** a acesso
   automatizado. A BDGD **não é dado aberto de acesso direto**. Nos dois
   casos o estado está registrado, e nenhum número da aplicação se apoia
   nelas.

Cartão · Manifesto de cache · auditoria
=======================================

A tabela que fecha a auditoria. Por recurso em cache:

* nome do recurso e conjunto de origem;
* **hash SHA-256** do conteúdo;
* tamanho em bytes;
* instante de extração;
* URL de origem.

.. admonition:: A pergunta que o hash responde
   :class: medido

   *Este número mudou porque o modelo mudou, ou porque o dado mudou?*

   Se o hash do recurso é o mesmo, o dado é o mesmo — e a diferença está no
   código. Sem o hash, essa distinção depende de memória, e memória não é
   auditoria.

Controles de ingestão e cache
=============================

O painel oferece:

* **Disparar ingestão** — ``POST /api/ingest``, com opção de forçar
  reextração.
* **Limpar cache** do cliente.
* **Atualizar catálogo**.

Os três modos
=============

.. list-table::
   :header-rows: 1
   :widths: 14 36 50

   * - Modo
     - Origem
     - Quando ocorre
   * - ``live``
     - Portal de Dados Abertos do ONS, agora
     - rede disponível
   * - ``cache``
     - ``.cache/`` local, com hash registrado
     - sem rede, com extração anterior
   * - ``demo``
     - gerador determinístico
     - sem rede e sem cache, ou ``ORACULO_OFFLINE=1``

O modo é declarado **por recurso**: uma resposta pode legitimamente misturar
carga do cache com restrição ao vivo, e o envelope mostra isso linha por
linha.

Limitações específicas
======================

.. admonition:: O que este painel não afirma
   :class: limite

   * O catálogo é o que o CKAN do ONS publica. Conjunto novo aparece aqui
     quando aparece lá.
   * A **defasagem de publicação** é informada quando conhecida
     (``lag_note``); onde não é conhecida, o campo vem vazio em vez de
     estimado.
   * O cache é **local à execução**. Não é repositório compartilhado nem
     substitui ingestão programada.

Para aprofundar
===============

* O envelope de proveniência: :doc:`../../visao-geral/proveniencia`
* Modelo de dados e esquemas verificados:
  ``01-ESPECIFICACAO/04-modelo-de-dados.md``
* Código: :doc:`../../referencia/ons`
* ONS — Portal de Dados Abertos: https://dados.ons.org.br/
