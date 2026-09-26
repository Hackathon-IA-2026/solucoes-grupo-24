============================================
SE de fronteira × subestação de distribuição
============================================

.. rubric:: Seção Fronteira T–D · aba ``#fronteira``

**Pergunta que responde:** que subestações de distribuição cada SE de
fronteira da rede básica alimenta, e que carga e que MMGD chegam a ela por
esse caminho?

Rotas consumidas
================

``GET /api/fronteira/status`` · ``GET /api/fronteira/resumo`` ·
``GET /api/fronteira/se/{sub_id}`` · ``GET /api/clm/cartao?fonte=bdgd``

Na primeira execução a base agregada é construída em segundo plano (cerca de
1 minuto, ~270 MB baixados da ANEEL e do IBGE). A tela mostra o progresso por
etapa e se redesenha sozinha. Depois disso a base fica no cache por 7 dias.

Como a SED é reconstruída
=========================

A BDGD aberta traz, por unidade consumidora de média (``UCMT``) e alta
(``UCAT``) tensão, o código ``SUB`` da subestação de distribuição que a
atende. Agrupando por ``DIST|SUB`` (o código é único dentro da
distribuidora, não no país):

* **posição** — mediana das coordenadas das UCs. É a posição da **carga**, não
  a do barramento, e é o que importa para a associação;
* **energia por classe** — soma dos 12 meses, por classe da ANEEL mapeada nas
  quatro classes do CLM;
* **demanda** — máximo mensal de cada UC, somado (não coincidente);
* **municípios atendidos** — contagem de UCs por município, usada no rateio.

Só entram UCs ativas (``SIT_ATIV = AT``).

A associação
============

Para cada SED *s* e cada SE de fronteira *f* a até 150 km:

.. math::

   a(s,f) = \mathrm{MVA}_f^{\,\alpha}\; e^{-d(s,f)/\lambda}
            \cdot b_{UF} \cdot b_{grupo},
   \qquad p(s,f) = \frac{a(s,f)}{\sum_{f'} a(s,f')}

com :math:`\alpha = 0{,}5`, :math:`\lambda = 20` km, bônus de 1,5 para a
mesma UF e de 1,5 quando a distribuidora e o agente da SE no ONS são do
mesmo grupo econômico. O vínculo primário é o de maior *p*; abaixo de 0,5 ele
é marcado **ambíguo**.

.. admonition:: Por que α = 0,5 e λ = 20 km
   :class: medido

   Escolhidos pela varredura do painel :doc:`qualidade-da-correlacao`. Com
   α = 1, a SE de grande capacidade atrai demais e deixa 103 SEs sem carga;
   com α = 0 (só distância), SEs ficam sobrecarregadas em até 330%. A
   combinação escolhida dá o carregamento mais homogêneo, nenhuma SE acima de
   100% e escolhe a SE mais próxima em 87% dos casos.

Baixa tensão e MMGD
===================

A BDGD aberta publica só pessoa jurídica. A baixa tensão (residencial, na
maior parte) vem do **SAMP**: energia TUSD por distribuidora e classe, apenas
mercados *Regular*. As linhas de *Sistema de Compensação* registram energia
compensada, e somá-las contaria o mesmo consumo duas vezes. O SAMP desce aos
municípios pela população do IBGE e sobe às SEDs na proporção das UCs de
média tensão que cada uma atende no município.

A MMGD vem do cadastro da ANEEL (4,66 milhões de empreendimentos, 54 GW). Os
que estão numa UC de média tensão casam **exatamente** com a SED pelo
``CEG_GD`` (cerca de 7,7 GW). O restante é rateado pelo município.

O que a tela mostra
===================

* **Mapa** — SEs de fronteira (tamanho proporcional à √MVA) e SEDs coloridas
  pela probabilidade do vínculo. A SE selecionada desenha as linhas até suas
  SEDs.
* **Detalhe** — energia medida e rateada por classe, sazonalidade mensal,
  carregamento implícito, MMGD e penetração (MW de GD sobre MW médio de
  carga).
* **Duas representações da mesma SE** — composição e MMGD pelo Mapa
  Inteligente e pela BDGD, lado a lado, com a diferença em pontos
  percentuais.
* **Insumo ao CLM** — o botão envia a SE ao painel de Parametrização CLM com a
  composição pela BDGD (``fonte=bdgd``).
* **SEDs associadas** — distribuidora, UCs, energia, classe dominante, MMGD
  direta, distância, *p* e as SEs alternativas.

.. admonition:: Privacidade
   :class: important

   CPF/CNPJ e nome do titular da GD, endereço e CEP das UCs não são lidos. O
   arquivo bruto vai para um diretório temporário e é apagado após a
   agregação; o cache guarda só agregados por SED, município e distribuidora.
