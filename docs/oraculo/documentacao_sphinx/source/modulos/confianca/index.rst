=========
Confiança
=========

O módulo que existe para ser auditado. Dois painéis: um mostra se o método
funciona, o outro mostra de onde veio cada número.

.. toctree::
   :maxdepth: 2

   validacao
   dados-abertos

Por que este módulo não é um apêndice
=====================================

Em um hackathon é fácil mostrar um gráfico bonito. O que distingue uma
solução operável é conseguir responder, sem preparo, a três perguntas:

#. **Qual o desempenho fora da amostra, contra um baseline honesto?**
   Painel :doc:`validacao`.
#. **De onde veio este número, e quando?** Painel :doc:`dados-abertos`, mais o
   envelope de proveniência que acompanha **toda** resposta da API.
#. **O que a solução não faz?** :doc:`../../limitacoes`.

Um *skill score* negativo aparece em vermelho no painel de validação. Isso é
deliberado: esconder o caso em que o modelo perde do baseline tornaria o resto
da tela inútil.
