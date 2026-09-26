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
| 30min | sazonal_dia | 4442 | 6776 | 6.69 | 1615 | 78.3 | 0.482 | 3228 | 6530 | 4038 |
| 30min | sazonal_semana | 3172 | 4530 | 4.62 | 1086 | 74.0 | 0.630 | 2062 | 4645 | 3909 |
| 30min | climatologia | 8570 | 9498 | 11.73 | 2773 | 31.3 | 0.000 | 12408 | 9085 | 21513 |
| 30min | lightgbm | 555 | 699 | 0.76 | 167 | 74.8 | 0.935 | 486 | 283 | 592 |
| 3h | persistencia | 8983 | 10788 | 12.28 | 2906 | 55.9 | -0.048 | 581 | 289 | 1471 |
| 3h | sazonal_dia | 4442 | 6777 | 6.69 | 1615 | 78.2 | 0.482 | 3228 | 6530 | 4038 |
| 3h | sazonal_semana | 3172 | 4530 | 4.62 | 1087 | 74.0 | 0.630 | 2062 | 4645 | 3909 |
| 3h | climatologia | 8571 | 9499 | 11.73 | 2773 | 31.3 | 0.000 | 12408 | 9085 | 21513 |
| 3h | lightgbm | 1559 | 2239 | 2.32 | 512 | 73.8 | 0.818 | 1144 | 2384 | 2432 |
| D+1 | persistencia | 4448 | 6783 | 6.70 | 1617 | 78.2 | 0.481 | 3228 | 6530 | 4038 |
| D+1 | sazonal_dia | 4448 | 6783 | 6.70 | 1617 | 78.2 | 0.481 | 3228 | 6530 | 4038 |
| D+1 | sazonal_semana | 3176 | 4534 | 4.62 | 1088 | 74.0 | 0.630 | 2062 | 4645 | 3909 |
| D+1 | climatologia | 8574 | 9502 | 11.74 | 2774 | 31.3 | 0.000 | 12408 | 9085 | 21513 |
| D+1 | lightgbm | 1685 | 2418 | 2.51 | 551 | 74.4 | 0.803 | 1183 | 2708 | 2845 |

MW, exceto MAPE e cobertura (%) e skill (fração). Pico, vale e rampa: erro médio diário.

## SIN: MAE por patamar (MW)

| horizonte | modelo | minima_diurna | outro | ponta_noturna | rampa_vespertina |
|---|---|---|---|---|---|
| 30min | persistencia | 1761 | 1316 | 854 | 3261 |
| 30min | sazonal_dia | 7053 | 3047 | 3168 | 4735 |
| 30min | sazonal_semana | 4701 | 2497 | 2256 | 2992 |
| 30min | climatologia | 6892 | 8539 | 12139 | 9032 |
| 30min | lightgbm | 436 | 640 | 505 | 572 |
| 3h | persistencia | 7887 | 7345 | 7601 | 18929 |
| 3h | sazonal_dia | 7053 | 3047 | 3168 | 4735 |
| 3h | sazonal_semana | 4701 | 2497 | 2256 | 2992 |
| 3h | climatologia | 6892 | 8540 | 12139 | 9032 |
| 3h | lightgbm | 2470 | 1118 | 1190 | 1418 |
| D+1 | persistencia | 7065 | 3048 | 3174 | 4744 |
| D+1 | sazonal_dia | 7065 | 3048 | 3174 | 4744 |
| D+1 | sazonal_semana | 4707 | 2500 | 2259 | 2996 |
| D+1 | climatologia | 6901 | 8541 | 12140 | 9032 |
| D+1 | lightgbm | 2640 | 1227 | 1222 | 1603 |

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
| S | 3h | sazonal_semana | 1108 | 516 | 53.4 | sim |
| S | D+1 | sazonal_semana | 1106 | 634 | 42.7 | sim |
| SE | 30min | persistencia | 931 | 252 | 73.0 | sim |
| SE | 3h | sazonal_semana | 2264 | 1045 | 53.8 | sim |
| SE | D+1 | sazonal_semana | 2265 | 1198 | 47.1 | sim |
| SIN | 30min | persistencia | 1631 | 555 | 66.0 | sim |
| SIN | 3h | sazonal_semana | 3172 | 1559 | 50.8 | sim |
| SIN | D+1 | sazonal_semana | 3176 | 1685 | 46.9 | sim |
