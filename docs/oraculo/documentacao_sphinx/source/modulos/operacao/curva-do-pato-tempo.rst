==================================
Curva do pato prevista pelo tempo
==================================

.. rubric:: Módulo Operação · aba ``#pato``

**Pergunta que responde:** como será a carga supervisionada dos próximos dias
— a barriga do meio-dia e a rampa do fim da tarde — dado o tempo previsto e
onde está instalada a MMGD?

Rotas consumidas
================

``GET /api/tempo/status`` · ``GET /api/tempo/pato``

Modelos de tempo
================

.. list-table::
   :header-rows: 1
   :widths: 30 15 55

   * - Modelo
     - Tipo
     - Situação
   * - ECMWF AIFS
     - IA
     - em uso (Open-Meteo), previsão e previsões arquivadas
   * - ECMWF IFS
     - físico
     - em uso
   * - NOAA GFS
     - físico
     - em uso
   * - NVIDIA Earth-2 (FourCastNet, CorrDiff)
     - IA
     - **indisponível aqui**: exige GPU e ``earth2studio`` (PyTorch) ou NIM
       com chave de API da NVIDIA; o proxy bloqueia o PyPI
   * - GraphCast (DeepMind)
     - IA
     - disponível no Open-Meteo, mas não produz radiação solar

O NVIDIA Earth-2 fica como provedor plugável: o contrato é o mesmo dos
demais, e trocar o provedor é uma função.

.. admonition:: Rede corporativa
   :class: important

   O cliente valida o TLS contra o repositório de certificados do Windows,
   onde está a CA do proxy corporativo. Essa CA não declara a extensão
   *keyUsage*, que o modo estrito do OpenSSL (padrão desde o Python 3.13)
   exige; só esse modo é desligado. Cadeia e nome do servidor continuam
   verificados.

Método
======

#. **Onde está a MMGD** — capacidade por município (cadastro ANEEL) agrupada
   em células de ~2,5° por subsistema.
#. **Geração prevista** — em cada célula,

   .. math::

      P = C \cdot PR \cdot \frac{G}{1000} \cdot \big(1 - 0{,}004\,(T + 0{,}03\,G - 25)\big)

   com *G* a radiação global horizontal e *T* a temperatura previstas. O PR
   é calibrado por subsistema com o ERA5 para reproduzir a MMGD média oficial
   de 2026 (2ª RQ do PLAN 2026-2030); os valores (0,64 a 0,83) são os de
   sistemas fotovoltaicos reais.
#. **Carga supervisionada prevista** —

   .. math::

      \text{sup}(d) = \text{sup}_{\text{tipo}}(d) - \beta\,\Delta\text{MMGD}
                      + \gamma\,\Delta T

   O dia-tipo é a média do mesmo dia da semana nas duas últimas semanas, sem
   feriados. β e γ são estimados por subsistema numa janela de treino
   anterior ao teste.

.. admonition:: O tempo mexe nos dois lados da curva
   :class: medido

   Sem controlar a temperatura, a sensibilidade estimada da carga à MMGD sai
   perto de zero (R² 0,02 no Sudeste): dia de sol aumenta a MMGD, mas também
   aquece e aumenta a refrigeração. Com a temperatura, β volta a ~0,8 no
   Sudeste, γ fica em ~830 MW/°C e o R² sobe para 0,30.

Validação
=========

Backtest com as **previsões arquivadas** de cada modelo (o que ele de fato
previu), contra a carga supervisionada do ONS. As comparações:

* **persistência** — o mesmo dia da semana das duas últimas semanas, sem
  tempo;
* cada modelo e a **média dos modelos**;
* **ERA5 (tempo perfeito)** — o teto; o erro que sobra ali não é do tempo.

A barriga é o mínimo das 10h às 15h; a rampa vai da barriga ao pico das 17h
às 21h. Nenhum modelo é o melhor em tudo: a média dos modelos é a escolha
equilibrada.

Limites
=======

#. O dia-tipo não prevê mudanças de regime de carga (feriados longos,
   eventos); dias de feriado ficam fora do backtest.
#. O PR é um só por subsistema: orientação, sombreamento e limitação de
   inversores entram só em média.
#. A MMGD é a do cadastro atual; o crescimento dentro da semana é
   desprezível.
