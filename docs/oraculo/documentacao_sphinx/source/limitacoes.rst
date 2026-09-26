=====================
Limitações declaradas
=====================

.. admonition:: Por que esta página existe
   :class: important

   Terceira consequência do princípio de projeto: **todo limite é declarado
   antes de ser perguntado**. Uma limitação descoberta pelo avaliador custa
   credibilidade; a mesma limitação declarada pelo autor demonstra domínio do
   problema.

Fronteiras de escopo
====================

.. list-table::
   :header-rows: 1
   :widths: 34 66

   * - A solução não
     - Consequência
   * - **executa fluxo de potência**
     - Não calcula tensão, carregamento nem estabilidade. O destino natural
       dos seus produtos são as ferramentas que fazem isso — e é por isso que
       existe o painel de parametrização do CLM.
   * - **substitui o PREVCARGA**
     - É camada complementar, focada na parcela não supervisionada.
   * - **automatiza despacho**
     - Produz indicador e evidência rastreável; a decisão é do operador.
   * - **mede a MMGD**
     - Estima, com viés conservador declarado.

Limitações do núcleo analítico
==============================

.. list-table::
   :header-rows: 1
   :widths: 8 40 52

   * - #
     - Limitação
     - Consequência
   * - L1
     - **A MMGD é estimada, não medida.** O método do envelope usa o
       percentil 90 da carga em horas comparáveis como aproximação da carga
       global.
     - A estimativa é **um piso, não um valor central**: mesmo os dias de
       maior carga contêm alguma geração distribuída.
   * - L2
     - **Não existe série horária de MMGD por área** no Portal.
     - Não há como validar a estimativa contra medição. A validação é
       indireta, por coerência com a capacidade instalada declarada.
   * - L3
     - **Os perfis por dia-tipo são por subsistema.**
     - Granularidade abaixo disso exige BDGD.
   * - L4
     - **O rótulo de curtailment é a decisão operativa observada**, não o
       potencial físico de geração.
     - A ferramenta aprende quando houve restrição registrada, não quanta
       energia teria sido gerada.
   * - L5
     - **O classificador opera só na janela solar**, com limiar de rótulo de
       10% da capacidade.
     - Fora dela a resposta é trivial, e incluí-la inflaria a AUC sem
       informar.
   * - L6
     - **O desempenho publicado é do conjunto de teste corrente.**
     - Janela de dados diferente, número diferente.
   * - L7
     - **A severidade embute ponderação de criticidade de área**, que é
       premissa.
     - Não é medição; está declarada em ``config.py``.

Limitações do Mapa Inteligente
==============================

.. list-table::
   :header-rows: 1
   :widths: 8 40 52

   * - #
     - Limitação
     - Consequência
   * - R1
     - **A ortoimagem é sintética.** O detector é o mesmo que roda em imagem
       real e as métricas são medições reais dele; a imagem é de
       demonstração.
     - A acurácia reportada é um **teto**, não promessa de campo.
   * - R2
     - **Subestação de distribuição exige BDGD.** O dado aberto do ONS cobre
       a rede de operação.
     - Usamos a fronteira T–D como recorte possível; a granularidade-alvo do
       enunciado ainda não é alcançada.
   * - R3
     - **Não existe curva de carga por subestação em dado aberto.**
     - A decomposição roda por subsistema e entra como prior regional; a
       classificação local repousa sobre a morfologia.
   * - R4
     - **Industrial não é afirmado pelo cadastro.**
     - O rótulo industrial vem só da morfologia da amostra. Exige BDGD ou a
       Pesquisa de Posse e Hábitos de Consumo do IBGE.
   * - R5
     - **Variância de amostragem alta** onde as edificações são poucas e
       grandes.
     - O payload reporta ``sample_adequacy`` (boa / limitada / insuficiente).
   * - R6
     - **A calibração de área foi medida em imagem sintética.**
     - Precisa ser remedida contra conjunto rotulado real.
   * - R7
     - **YOLO sem runtime.** ``torch``, ``onnxruntime`` e ``ultralytics`` não
       podem ser instalados: o proxy corporativo bloqueia o PyPI.
     - O backend ativo é o clássico. O adaptador declara a ausência na API e
       na tela; trocar o backend é uma linha.

Limitações do Modelo de Carga Composta
======================================

.. list-table::
   :header-rows: 1
   :widths: 8 40 52

   * - #
     - Limitação
     - Consequência
   * - C1
     - **Nada simula o CLM no tempo.** São as relações algébricas e a lógica
       de proteção.
     - A resposta transitória é do ORGANON.
   * - C2
     - **A composição por classe é premissa versionada**, não medição de uso
       final.
     - Calibração pede o guia da NERC e a Pesquisa de Posse e Hábitos.
   * - C3
     - **29 dos 124 campos não são afirmados.**
     - Aparecem com o valor de referência publicado e o rótulo *a calibrar*.
       A escolha final é do especialista.
   * - C4
     - **A penetração de ar condicionado brasileira é desconhecida aqui.**
     - A tela expõe a sensibilidade de ``Fmd`` em vez de fixar um número.
   * - C5
     - **``Rfdr``/``Xfdr`` saem de um proxy de comprimento.**
     - Ponto de partida; as ferramentas reajustam na inicialização.
   * - C7
     - **O CMPLDW não representa dinâmica de inversor.**
     - MMGD entra como injeção; o comportamento dinâmico exige DER_A.
   * - C8
     - **O cartão não é caso pronto para simulação.**
     - Está escrito no próprio cartão, na tela e no payload.

Limitações de ambiente
======================

.. list-table::
   :header-rows: 1
   :widths: 34 66

   * - Restrição
     - Consequência
   * - **PyPI bloqueado** por proxy com certificado próprio
       (``CERTIFICATE_VERIFY_FAILED``)
     - Sem ``pandas``, ``scikit-learn``, ``fastapi``, ``torch``,
       ``onnxruntime``, ``ultralytics``, ``cv2``, ``skimage``. Cada
       substituição está declarada em
       :doc:`visao-geral/como-executar`.
   * - **Fontes externas que negam acesso automatizado**
     - O guia de composição de carga da NERC retorna HTTP 403. Está
       registrado como próximo passo, e nenhum número se apoia nele.
   * - **BDGD não é dado aberto de acesso direto**
     - Origem de R2, R3 e R4.

Fontes que resolveriam o que falta
==================================

.. list-table::
   :header-rows: 1
   :widths: 40 26 34

   * - Fonte
     - Resolve
     - Como obter
   * - **BDGD de distribuidora piloto**
     - R2, R3, R4, C5
     - convênio ou parceria
   * - **IBGE — Pesquisa de Posse e Hábitos de Consumo**
     - R4, C2, C4
     - citada no próprio enunciado do desafio
   * - **NERC — guia de composição de carga**
     - C2
     - acesso manual ao PDF
   * - **Ortoimagem real e pesos YOLO**
     - R1, R6, R7
     - contrato de imagem e ambiente sem bloqueio de PyPI
   * - **Cadastro de GD da ANEEL por município**
     - conferência do indicador de penetração
     - dado aberto, ingestão prevista
   * - **Oscilografia de perturbação real**
     - C3
     - a perturbação de 15/08/2023 é o caso natural

Onde cada limitação aparece na aplicação
========================================

Nenhuma destas limitações vive só nesta página. Cada uma está:

* **no código**, como comentário ou docstring com a justificativa;
* **no payload da API**, em campo próprio (``aviso``, ``nota``,
  ``sample_adequacy``, ``available``);
* **na tela**, em nota de cartão ou faixa de aviso;
* **na especificação**, em ``01-ESPECIFICACAO/08-limitacoes.md`` e nos
  documentos 11 e 12.
