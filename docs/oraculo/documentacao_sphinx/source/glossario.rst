=========
Glossário
=========

.. glossary::
   :sorted:

   average precision
      Área sob a curva precisão × revocação. Integra todo o intervalo de
      limiares, e por isso é mais severa que o F1 medido em um único ponto de
      operação.

   backtest
      Avaliação do modelo em dados posteriores ao treino, com corte
      estritamente cronológico. Ver :doc:`modulos/confianca/validacao`.

   BDGD
      Base de Dados Geográfica da Distribuidora, da ANEEL. Traz topologia e
      classe de consumo por unidade. **Não é dado aberto de acesso direto**, e
      essa ausência é a origem das limitações R2, R3 e R4.

   CKAN
      Plataforma de catálogo de dados abertos usada pelo Portal do ONS. A
      ingestão consulta sua API para descobrir conjuntos e recursos.

   CLM
      *Composite Load Model* — Modelo de Carga Composta. Representa o sistema
      de distribuição entre o barramento de transmissão e o uso final,
      repartindo a carga em motores, carga eletrônica e carga estática. Ver
      :doc:`modulos/mapa/parametrizacao-clm`.

   CMPLDW
      Designação do CLM no GE PSLF. Os mesmos campos aparecem como
      ``CMLDxxU2`` no PSS/E, e são lidos por PowerWorld, DSATools e ORGANON.

   constrained-off
      Restrição de geração determinada pelo Operador. Os registros publicados
      pelo ONS são o rótulo usado pelo classificador de risco.

   curtailment
      Restrição de geração renovável. Quando a razão é **energética** (ENE),
      significa excedente frente à carga e ao intercâmbio — o alvo declarado
      do eixo (ii) da solução.

   DER_A
      Família de modelos dinâmicos de recurso energético distribuído.
      Representa resposta de inversor a subtensão e a frequência, e
      anti-ilhamento — **o que o CMPLDW não faz**.

   dia-tipo
      Classificação do dia em útil, sábado, domingo ou feriado nacional. Os
      feriados móveis são calculados por Meeus/Butcher.

   embargo
      Intervalo descartado entre treino e teste no backtest, para impedir que
      variáveis defasadas cruzem a fronteira e produzam vazamento.

   ENE, CNF, REL, PAR
      Códigos de razão de restrição do ONS: energética, confiabilidade,
      atendimento a requisito de reserva e atendimento a pedido de parte.

   envelope (método do)
      Estimador do fator de nebulosidade: o percentil 90 da carga em horas
      comparáveis do mês aproxima a carga global, porque o dia de maior carga
      observada é o dia de menor geração distribuída. Produz estimativa
      **conservadora**.

   Etrq
      Expoente de velocidade do conjugado mecânico no CLM.
      :math:`T_m = T_{mo}\\,\\omega^{Etrq}`. Zero é conjugado constante; 2 é
      proporcional ao quadrado da velocidade. Com ``H``, é o **único** campo
      que distingue os motores trifásicos A, B e C.

   fator de carga
      Razão entre carga média e carga de pico. Quanto mais próximo de 1, mais
      plana a curva — assinatura de predominância industrial.

   Frame
      Tabela colunar própria sobre ``numpy``, em ``oraculo/core/frame.py``.
      Substitui o ``pandas``, indisponível no ambiente, e carrega
      ``Provenance`` imutável junto com os dados.

   fronteira T–D
      Transformação cujo lado secundário é de tensão de distribuição
      (≤ 138 kV). Recorte usado pelo Mapa Inteligente por ser o que o dado
      aberto permite identificar. São **522** das 909 subestações.

   IoU
      *Intersection over Union*. Mede a sobreposição entre a máscara detectada
      e a verdadeira — avalia geometria, não apenas existência.

   IRLS
      *Iteratively Reweighted Least Squares*. Método de ajuste da regressão
      logística usada no classificador de risco.

   MMGD
      Micro e minigeração distribuída. Não é publicada como série horária por
      área: manifesta-se apenas como **redução da carga verificada**.

   MWmed
      Megawatt médio, no intervalo de integração considerado — em geral a hora.

   NNLS
      *Non-Negative Least Squares*. Usado na decomposição da curva de carga
      nas classes de consumo, porque peso negativo não tem interpretação.

   NMS
      *Non-Maximum Suppression*. Elimina detecções redundantes. Na aplicação,
      complementada por deduplicação por contenção, para tratar a costura
      entre ladrilhos.

   ORGANON
      Ferramenta de avaliação de segurança dinâmica usada pelo ONS. É o
      **destino declarado** da parametrização do CLM produzida pela aplicação,
      e a razão de o cartão de parâmetros ser neutro: os campos do CMPLDW são
      os mesmos em PSS/E, PSLF, PowerWorld, DSATools e ORGANON.

   patamar operativo
      Faixa horária com custo de erro distinto: mínima diurna (09–15 h), rampa
      (16–19 h), ponta noturna (18–22 h) e base. As faixas se sobrepõem de
      propósito, e o peso aplicado é o do patamar mais crítico.

   perda assimétrica
      Função de perda *pinball* com pesos diferentes para subestimação e
      superestimação, por patamar. É o diferencial declarado da solução, e não
      existe pronta em biblioteca alguma.

   pinball loss
      Função de perda da regressão quantílica. Penaliza erro acima e abaixo do
      quantil com pesos distintos.

   P10, P50, P90
      Quantis da previsão. P50 é a mediana; a banda exibida é P10–P90.

   Provenance
      Estrutura imutável que acompanha cada conjunto de dados: origem,
      recurso, instante de extração, linhas e bytes lidos, defasagem
      conhecida. Ver :doc:`visao-geral/proveniencia`.

   skill score
      Ganho relativo de erro em relação ao melhor baseline. Positivo é erro
      menor que o baseline; **negativo aparece em vermelho no painel** em vez
      de ser omitido.

   Tipo III
      Usina conectada à rede de distribuição, no conjunto
      ``modalidade-usina`` do ONS. Usada como conferência cruzada da ordem de
      grandeza do indicador de MMGD.

   UVLS, UFLS
      *Under-Voltage* e *Under-Frequency Load Shedding* — esquemas de corte de
      carga por subtensão e subfrequência, representados no CLM.

   Vstall
      Tensão abaixo da qual o compressor monofásico trava, decorrido
      ``Tstall``. Parâmetro de ensaio de laboratório; marcado *a calibrar* no
      cartão.

   Vstallbrk
      Tensão em que a característica de rotor bloqueado cruza a de regime do
      motor D. A **posição relativa** de ``Vstall`` e ``Vstallbrk`` muda o
      resultado, não apenas o valor de ``Vstall``.

   YOLOv8-seg
      Modelo de detecção e segmentação. O adaptador está completo e testado na
      aplicação, mas **sem runtime**: o PyPI está bloqueado no ambiente. Ver
      :doc:`modulos/mapa/visao-computacional`.

   ZIP
      Representação da carga estática como combinação de impedância,
      corrente e potência constantes. No CLM aparece na forma exponencial com
      dependência de frequência.
