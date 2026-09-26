================
Mapa Inteligente
================

O módulo que responde ao **desafio Radix + AXIA + Cepel**: para cada
subestação georreferenciada, qual o perfil predominante de consumo da área
atendida e se existe presença relevante de geração distribuída no entorno.

.. toctree::
   :maxdepth: 2

   perfis-por-subestacao
   visao-computacional
   classes-de-consumo
   parametrizacao-clm

O encadeamento dos quatro painéis
=================================

Não são quatro assuntos: são quatro etapas de um mesmo percurso.

.. code-block:: text

   subestações do ONS  →  amostra de ortoimagem  →  detecção de painéis
   (Perfis por subestação)                          (Visão computacional)
            │                                              │
            └──────────────┬───────────────────────────────┘
                           ▼
              composição de classe da área
              (Classes de consumo: prior regional
               por decomposição da curva real)
                           │
                           ▼
              parâmetros do Modelo de Carga Composta
                    (Parametrização CLM)

A leitura natural é nessa ordem. Quem quer o resultado final sem o caminho
pode ir direto a :doc:`parametrizacao-clm`.

O contexto que motiva o desafio
===============================

A perturbação de **15/08/2023**, com desligamento automático da LT 500 kV
Quixadá–Fortaleza II e interrupção de **23.368 MW**, em que — nas palavras do
enunciado — *"o desempenho dos parques eólicos e fotovoltaicos observado em
campo foi inesperado, muito aquém daquele obtido pelo ONS nos seus estudos, os
quais são realizados utilizando-se os modelos matemáticos encaminhados pelos
agentes"*.

A lacuna é de **representação**, não de dado inexistente. É por isso que o
módulo termina em parametrização de modelo, e não em um mapa bonito.

.. admonition:: O limite mais importante deste módulo
   :class: limite

   **A ortoimagem é sintética, com verdade fundamental conhecida.** O detector
   e as métricas são reais — é o mesmo código que roda em imagem real, e os
   números medidos são dele. A imagem é de demonstração. Em imagem real,
   esperar degradação. Está rotulado na tela, na API e aqui.
