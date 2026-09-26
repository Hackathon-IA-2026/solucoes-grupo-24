=======================
Método e sensibilidade
=======================

.. rubric:: Seção Investimento · aba ``#bessmetodo``

**Pergunta que responde:** de onde vem cada número do ranking, o que ficou de
fora e o quanto o resultado depende dos pesos escolhidos?

Rota consumida
==============

``GET /api/bess/metodo``

Cobertura
=========

Fração da energia cortada localizada pela SE do ONS, pelas usinas no SIGA e
não localizada. Sítio sem coordenada continua no ranking, com a penetração de
MMGD da UF, e aparece listado.

Estabilidade do top 10
======================

O top 10 com os pesos padrão é comparado ao top 10 em seis cenários: só
energia, curva do pato (excedente da MMGD em destaque), restrição local, pesos
iguais, sem MMGD e o próprio padrão. Excedente da MMGD e restrição local são
quase complementares: expressam duas teses diferentes. Sítio que
permanece em todos é candidato **robusto**: sua posição não depende de uma
escolha de peso.

Limites declarados
==================

#. O corte apurado é a decisão operativa observada, não o potencial físico, e
   obras de transmissão previstas podem eliminá-lo.
#. Um ciclo por dia, sem restrição de rede na descarga; sem modelo de receita
   (PLD, serviços ancilares, capacidade).
#. Corte sistêmico (SIS) é aliviado por armazenamento em qualquer ponto do
   subsistema; o local (LOC), só no ponto.
#. O corte induzido pela MMGD é um limite superior contrafactual, e a MMGD
   vem da estimativa do envelope (um piso).
#. A MMGD não é cortada e não escolhe o sítio de geração.
