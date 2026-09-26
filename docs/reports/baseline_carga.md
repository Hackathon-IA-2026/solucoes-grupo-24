# Backtest da previsão de carga supervisionada (Fase 3)

Gerado por `python run_heavywork.py` (etapa 4; código em `Backend/src/models/`). Não editar à mão.

- Treino: alvos de 2019-03-01 a 2025-06-30. Teste (fora da amostra): emissões a partir de 2025-07-01; alvos avaliados de 2025-07-01 a 2026-09-25 23:30 (horário UTC−3).
- Split cronológico; cada previsão usa só dados até a emissão (alvo − horizonte). Testes: `Backend/tests/test_features_carga.py` e `test_modelos_carga.py`.
- Features: calendário (feriado = domingo) + defasagens da carga supervisionada e da MMGD. Sem meteorologia (decisão de 2026-09-25).
- P10/P90 dos baselines: P50 + quantis do resíduo no treino. LightGBM: um modelo por quantil.
- skill = 1 − MAE / MAE da climatologia (média do treino por mês × dia da semana × horário).
- Cobertura: % dos reais dentro de P10–P90 (ideal: 80%).

## SIN: todos os modelos

| horizonte | modelo | mae | rmse | mape | pinball | cobertura | skill | erro_pico | erro_vale | erro_rampa |
|---|---|---|---|---|---|---|---|---|---|---|
| 30min | persistencia | 1631 | 2033 | 2.25 | 532 | 56.8 | 0.810 | 108 | 108 | 459 |
| 30min | sazonal_dia | 4441 | 6775 | 6.68 | 1614 | 78.3 | 0.482 | 3226 | 6529 | 4038 |
| 30min | sazonal_semana | 3169 | 4528 | 4.61 | 1086 | 74.0 | 0.630 | 2061 | 4642 | 3909 |
| 30min | climatologia | 8573 | 9501 | 11.73 | 2774 | 31.3 | 0.000 | 12415 | 9079 | 21513 |
| 30min | lightgbm | 555 | 700 | 0.76 | 167 | 74.8 | 0.935 | 486 | 283 | 592 |
| 3h | persistencia | 8983 | 10788 | 12.28 | 2906 | 55.9 | -0.048 | 581 | 289 | 1471 |
| 3h | sazonal_dia | 4441 | 6776 | 6.68 | 1615 | 78.3 | 0.482 | 3226 | 6529 | 4038 |
| 3h | sazonal_semana | 3169 | 4529 | 4.61 | 1086 | 74.0 | 0.630 | 2061 | 4642 | 3909 |
| 3h | climatologia | 8573 | 9502 | 11.73 | 2774 | 31.3 | 0.000 | 12415 | 9079 | 21513 |
| 3h | lightgbm | 1557 | 2238 | 2.31 | 512 | 73.8 | 0.818 | 1142 | 2383 | 2433 |
| D+1 | persistencia | 4447 | 6782 | 6.69 | 1616 | 78.2 | 0.482 | 3226 | 6529 | 4038 |
| D+1 | sazonal_dia | 4447 | 6782 | 6.69 | 1616 | 78.2 | 0.482 | 3226 | 6529 | 4038 |
| D+1 | sazonal_semana | 3173 | 4533 | 4.62 | 1087 | 74.0 | 0.630 | 2061 | 4642 | 3909 |
| D+1 | climatologia | 8577 | 9505 | 11.74 | 2775 | 31.3 | 0.000 | 12415 | 9079 | 21513 |
| D+1 | lightgbm | 1683 | 2416 | 2.50 | 551 | 74.5 | 0.804 | 1182 | 2705 | 2844 |

MW, exceto MAPE e cobertura (%) e skill (fração). Pico, vale e rampa: erro médio diário.

## SIN: MAE por patamar (MW)

| horizonte | modelo | minima_diurna | outro | ponta_noturna | rampa_vespertina |
|---|---|---|---|---|---|
| 30min | persistencia | 1761 | 1316 | 854 | 3261 |
| 30min | sazonal_dia | 7052 | 3046 | 3166 | 4734 |
| 30min | sazonal_semana | 4698 | 2494 | 2255 | 2990 |
| 30min | climatologia | 6886 | 8545 | 12145 | 9038 |
| 30min | lightgbm | 436 | 640 | 506 | 572 |
| 3h | persistencia | 7887 | 7345 | 7601 | 18929 |
| 3h | sazonal_dia | 7052 | 3046 | 3166 | 4734 |
| 3h | sazonal_semana | 4698 | 2495 | 2255 | 2990 |
| 3h | climatologia | 6886 | 8545 | 12145 | 9038 |
| 3h | lightgbm | 2469 | 1115 | 1188 | 1419 |
| D+1 | persistencia | 7064 | 3048 | 3172 | 4743 |
| D+1 | sazonal_dia | 7064 | 3048 | 3172 | 4743 |
| D+1 | sazonal_semana | 4704 | 2497 | 2258 | 2994 |
| D+1 | climatologia | 6895 | 8547 | 12147 | 9039 |
| D+1 | lightgbm | 2637 | 1225 | 1222 | 1601 |

## LightGBM × melhor baseline, por série e horizonte (MAE, MW)

| serie | horizonte | melhor_baseline | mae_baseline | mae_lightgbm | ganho_pct | ganha |
|---|---|---|---|---|---|---|
| N | 30min | persistencia | 128 | 47 | 63.1 | sim |
| N | 3h | sazonal_semana | 259 | 156 | 40.0 | sim |
| N | D+1 | sazonal_semana | 259 | 173 | 33.3 | sim |
| NE | 30min | persistencia | 318 | 100 | 68.7 | sim |
| NE | 3h | sazonal_semana | 482 | 331 | 31.3 | sim |
| NE | D+1 | sazonal_semana | 482 | 370 | 23.3 | sim |
| S | 30min | persistencia | 415 | 150 | 63.9 | sim |
| S | 3h | sazonal_semana | 1107 | 516 | 53.4 | sim |
| S | D+1 | sazonal_semana | 1106 | 634 | 42.7 | sim |
| SE | 30min | persistencia | 931 | 252 | 73.0 | sim |
| SE | 3h | sazonal_semana | 2261 | 1044 | 53.8 | sim |
| SE | D+1 | sazonal_semana | 2263 | 1196 | 47.2 | sim |
| SIN | 30min | persistencia | 1631 | 555 | 66.0 | sim |
| SIN | 3h | sazonal_semana | 3169 | 1557 | 50.9 | sim |
| SIN | D+1 | sazonal_semana | 3173 | 1683 | 47.0 | sim |
