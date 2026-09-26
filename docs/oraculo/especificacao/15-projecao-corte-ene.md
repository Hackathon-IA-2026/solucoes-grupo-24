# 15 · Investimento — projeção do corte por razão energética e BESS futuro

Objetivo: estimar **quanto corte por razão energética (ENE) vem pela frente**
e **quanto armazenamento ele justifica**, a partir das séries temporais
observadas, e isolar o efeito do crescimento da MMGD.

## 15.1 Séries

| Série | Origem | Início |
|---|---|---|
| Corte ENE+SIS e total, horário, SIN | ONS · constrained-off eólico e FV | eólica 10/2021 · FV 04/2024 |
| Carga, eólica e solar verificadas, horárias, SIN | ONS · balanço de energia | 2019 |
| MMGD conectada por mês | ANEEL · cadastro técnico FV (`DatConexao`) | 2012 |

A série fotovoltaica de corte só é publicada desde 04/2024: antes disso o total
do SIN está incompleto, e a calibração começa ali.

Taxas observadas (medidas em 26/09/2026): carga +3,5% a.a. (2019–2025); eólica
+7% (2025); solar centralizada +25% (2025, desacelerando de +70% em 2024);
MMGD 2,4 GW (2019) → 53,7 GW (08/2026), com crescimento em 12 meses caindo de
97% (2021) para 24% (2025).

## 15.2 Decisões

| # | Decisão | Motivo |
|---|---|---|
| P1 | Modelo físico `corte = α·máx(0, θ_mês − NL)`, não extrapolação de tendência | O corte cresceu em saltos; tendência projeta o salto para sempre |
| P2 | NL com geração POTENCIAL (verificada + cortada) | Com a verificada, o modelo é circular |
| P3 | θ por mês do ano | A inflexibilidade hidráulica e os limites de intercâmbio são sazonais |
| P4 | Backtest: ajuste até 08/2025, teste nos 12 meses seguintes, contra o ingênuo "mesmo mês do ano anterior" | Nenhuma projeção sem desempenho medido fora da amostra |
| P5 | Projeção sobre o ano de referência observado | Mantém clima, hidrologia e perfis reais; cresce só o que o cenário diz |
| P6 | Referência = trajetória oficial: carga global e MMGD ano a ano da 2ª RQ do PLAN 2026-2030 (ONS/EPE/CCEE, 07/08/2026); eólica + solar do PAR/PEL 2025 | A MMGD não para de crescer; o planejamento oficial projeta sua trajetória. A primeira versão usava taxas extrapoladas e uma coluna "se a MMGD parasse de crescer" — trocada por atribuição |
| P6b | Nível da MMGD horária calibrado ao oficial (8.536 MWmed em 2026) | A estimativa do envelope dava 3,1 GWmed: 2,7 vezes abaixo |
| P7 | Efeito da MMGD isolado (mesmo cenário com MMGD congelada) | Quantifica o aprofundamento da curva do pato |
| P8 | BESS dimensionado no SIN pelo ciclo marginal ≥ 200/ano | O corte ENE+SIS é sistêmico; mesmo critério da seção de alocação |
| P9 | θ constante no cenário base (flex = 0), com controle de flexibilidade | O corte projetado é o que rede, armazenamento e flexibilidade precisariam resolver |

## 15.3 Limites

1. Um único ano de referência: clima e hidrologia daquele ano.
2. Sem nova transmissão nem flexibilidade no cenário base.
3. O corte é a decisão operativa observada, não o potencial físico.
4. Perfil horário da MMGD pela estimativa do envelope, com o nível oficial.
5. A série de balanço registra geração verificada: as taxas de VRE subestimam
   o crescimento da capacidade.
6. A expansão centralizada do PAR/PEL (+5,2 GW até 2029) é a considerada nos
   estudos; o resultado é muito sensível a ela (ver o cenário "tendência
   observada").
