====================
Visão computacional
====================

.. rubric:: Módulo Mapa Inteligente · aba ``#visao``

**Pergunta que responde:** o detector de painéis fotovoltaicos funciona? Com
que precisão, medida contra o quê?

Este painel existe porque a resposta da pergunta 2 do desafio vale exatamente
o que vale o detector. Publicar o indicador de MMGD sem publicar o desempenho
do detector seria pedir confiança sem oferecer evidência.

Rotas consumidas
================

.. list-table::
   :header-rows: 1
   :widths: 46 54

   * - Rota
     - O que traz
   * - ``GET /api/mapa/vision``
     - backends, banco de ensaio, curva P×R, calibração
   * - ``GET /api/mapa/bench.png``
     - cena de referência renderizada, com sobreposições

Os quatro KPIs
==============

Agregados sobre **4 classes urbanas × 3 sementes = 12 cenas** com verdade
fundamental conhecida.

.. list-table::
   :header-rows: 1
   :widths: 30 20 50

   * - KPI
     - Valor medido
     - Como ler
   * - **Precisão**
     - **0,982**
     - Das detecções, quantas eram painel de verdade. Precisão baixa aqui
       significaria contar telhado ou asfalto como painel.
   * - **Revocação**
     - **0,997**
     - Dos painéis existentes, quantos foram encontrados.
   * - **IoU de máscara**
     - 0,876
     - Sobreposição da máscara detectada com a verdadeira. Mede a
       **geometria**, não só a existência.
   * - **Erro de área**
     - **+0,7%**
     - Erro relativo da área total, **após calibração**. É o número que
       importa para o kWp, porque a potência é proporcional à área.

Também no painel: F1 **0,988** e *average precision* **0,730**.

.. admonition:: Por que a AP é bem menor que o F1
   :class: important

   O F1 é medido no ponto de operação escolhido; a *average precision*
   integra toda a curva precisão × revocação. A diferença indica que o
   detector é bom **no limiar calibrado** e degrada fora dele — informação
   honesta sobre a margem de robustez, e a razão de a curva estar na tela.

Cartão · Backends de detecção
=============================

.. list-table::
   :header-rows: 1
   :widths: 26 16 58

   * - Backend
     - Estado
     - Implementação
   * - **Detector clássico**
     - **ativo**
     - índice espectral de excesso de azul + luminância (suavizados),
       densidade de borda por Sobel, morfologia binária, componentes
       conexas, filtro de forma, refinamento em duas etapas
   * - **YOLOv8-seg**
     - pronto, **sem runtime**
     - letterbox e inversa, decodificação das saídas, NMS, recorte de
       máscara por protótipos, transformação de coordenadas — tudo
       implementado e testado

.. admonition:: Sobre o YOLO, sem rodeio
   :class: limite

   ``torch``, ``onnxruntime`` e ``ultralytics`` **não podem ser instalados**
   neste ambiente: o proxy corporativo bloqueia o PyPI com certificado
   próprio (``CERTIFICATE_VERIFY_FAILED``, verificado).

   O adaptador **detecta a ausência do runtime, declara isso na API e na
   tela**, e cede o lugar ao detector clássico. O campo ``available`` vem
   ``false`` com o motivo escrito.

   Quando houver pesos e runtime, trocar o backend é **uma linha**:
   ladrilhamento, NMS, deduplicação na costura entre ladrilhos e
   georreferência são compartilhados e já testados.

Cartão · Etapas do detector ativo
=================================

A sequência, na ordem em que executa:

#. **Índices espectrais** — excesso de azul e luminância, suavizados em 5 px.
#. **Densidade de borda** — Sobel, normalizada pelo tamanho físico do módulo.
#. **Limiarização** conjunta dos três canais.
#. **Morfologia binária** — fechamento **antes** da abertura.
#. **Componentes conexas** e filtro de forma (retangularidade, razão de
   aspecto, área mínima e máxima).
#. **Refinamento em duas etapas** sobre o índice bruto, com relaxamento do
   limiar na vizinhança da detecção.
#. **NMS e deduplicação** na costura entre ladrilhos, por IoU e contenção.
#. **Geo-transformação** de pixel para lat/lon.

.. admonition:: Duas correções que definiram estes parâmetros
   :class: medido

   **O detector detectava a malha viária inteira** (precisão 0,33). O
   excesso de azul do asfalto é 0,021, acima do limiar de 0,012 que eu havia
   arbitrado. Recalibrado para **0,090** de excesso de azul e luminância
   máxima **74**.

   **A revocação despencou para 0,17.** As linhas de junta entre módulos, de
   tamanho fixo, fragmentavam a máscara. Corrigido suavizando os índices
   espectrais em 5 px e **reordenando a morfologia** — fechamento antes da
   abertura.

Cartão · Cena de referência
===========================

A ortoimagem renderizada, com sobreposições alternáveis:

* **detecções** — o que o detector encontrou;
* **verdade fundamental** — o que existe de fato;
* **grade de ladrilhos** — mostra onde estão as costuras que a deduplicação
  precisa tratar;
* **não detectados** — os falsos negativos, em destaque;
* **canais de característica** — excesso de azul, densidade de borda ou
  luminância, para inspecionar *por que* o detector decidiu.

Cartão · Curva precisão × revocação
===================================

A curva completa, com o ponto de operação marcado. É o que sustenta a
*average precision* e o que mostra a margem disponível ao mover o limiar.

Cartão · Desempenho por classe urbana e semente
===============================================

Tabela com as 12 cenas individualmente: classe urbana, semente, precisão,
revocação, F1, IoU e erro de área.

.. admonition:: Por que expor as 12 linhas
   :class: important

   A média esconde o pior caso. Publicar cada cena permite ver em qual classe
   urbana o detector sofre — e, no nosso caso, mostra que o viés de área é
   **sistemático entre classes** (−12% a −21%), o que é o que autoriza
   corrigi-lo por uma constante.

Cartão · Calibração de área
===========================

.. list-table::
   :header-rows: 1
   :widths: 46 54

   * - Grandeza
     - Valor
   * - Erro de área, bruto
     - **−15,4%**
   * - Fator de calibração
     - **1,19**
   * - Erro de área, calibrado
     - **+0,7%**

.. admonition:: A calibração é medida, não arbitrada
   :class: medido

   Mesmo após o refinamento em duas etapas, o detector subestima a área em
   torno de 16%: a borda do painel é um **gradiente**, e qualquer limiar
   corta parte dela. O viés é sistemático e consistente entre classes
   urbanas, portanto corrigível por constante.

   O **valor bruto permanece na API** para auditoria, e o teste de regressão
   exige erro calibrado abaixo de 8%.

Cartão · Parâmetros do YOLOv8-seg
=================================

Tabela dos parâmetros do adaptador: dimensão de entrada, número de classes
(``nc``), número de protótipos de máscara (``nm``), limiares de confiança e
de NMS.

.. admonition:: Um erro de decodificação que o teste pegou
   :class: medido

   A decodificação retornava zero caixas. A causa: uma heurística
   ``arr.shape[0] < arr.shape[1]`` para descobrir a orientação do tensor de
   saída, que falha quando há poucas âncoras. Substituída pela verificação
   determinística ``expected_c = 4 + nc + nm``.

   Vale registrar que esse caminho de código **não roda** aqui por falta de
   runtime — foi o teste unitário que o encontrou, não a execução.

Limitações específicas
======================

.. admonition:: O que este painel não afirma
   :class: limite

   * **R1 — a ortoimagem é sintética.** As métricas acima são medições reais
     de um detector real sobre imagem sintética com verdade conhecida. Não
     são promessa de desempenho em campo: são um **teto**.
   * **R6 — a calibração de área foi medida em imagem sintética.** Precisa
     ser remedida contra conjunto rotulado real.
   * **R7 — YOLO sem runtime.** O backend ativo é o clássico, e isso está
     declarado na API e na tela.
   * O detector encontra **painel fotovoltaico em telhado**. Não classifica
     tecnologia, não estima orientação nem inclinação, não estima
     sombreamento.

Para aprofundar
===============

* Como o indicador é construído: :doc:`perfis-por-subestacao`
* Uso na triangulação: :doc:`../analise/triangulacao`
* Especificação: ``01-ESPECIFICACAO/11-desafio-radix-mapa-inteligente.md``
* Código: :doc:`../../referencia/vision`
