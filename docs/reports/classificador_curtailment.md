# Backtest do classificador de risco de curtailment (Fase 4)

Gerado por `python run_heavywork.py` (etapa 4; código em `Backend/src/models/curtailment.py`). Não editar à mão.

- 271 usinas/conjuntos (chave = fonte + id). Treino: alvos de 2023-04-01 a 2025-12-31; teste: emissões a partir de 2026-01-01 (fora da amostra).
- Cada previsão usa só dados até a emissão (alvo − horizonte): histórico de cortes da usina, estado do sistema, carga supervisionada e MMGD, calendário do alvo. Sem meteorologia.
- Baselines: **persistência** (havia corte na emissão?) e **frequência_1d** (fração do último dia com corte, até a emissão).
- CNF sem os limites de exportação NE e N/NE (não existem no portal nem no MCP): só as mesmas features gerais.
- Precisão e recall no limiar 50% de probabilidade; montante = P(corte) × E[MW | corte] (persistência: MW cortados na emissão).

## ENE: todas as usinas

| horizonte | modelo | n | prevalencia | roc_auc | pr_auc | brier | precisao | recall | mae_montante_mw |
|---|---|---|---|---|---|---|---|---|---|
| 30min | lightgbm | 2,968,990 | 26.3 | 0.994 | 0.984 | 0.0253 | 96.3 | 91.7 | 3.66 |
| 30min | persistencia | 2,968,990 | 26.3 | 0.957 | 0.893 | 0.0337 | 93.6 | 93.6 | 3.74 |
| 30min | frequencia_1d | 2,968,990 | 26.3 | 0.679 | 0.371 | 0.1790 | 39.6 | 4.0 | — |
| 3h | lightgbm | 2,967,780 | 26.3 | 0.965 | 0.907 | 0.0752 | 88.1 | 70.7 | 8.65 |
| 3h | persistencia | 2,967,780 | 26.3 | 0.747 | 0.491 | 0.1961 | 62.7 | 62.7 | 14.26 |
| 3h | frequencia_1d | 2,967,780 | 26.3 | 0.651 | 0.352 | 0.1857 | 37.2 | 3.7 | — |
| D+1 | lightgbm | 2,957,616 | 26.2 | 0.950 | 0.872 | 0.0946 | 85.7 | 62.7 | 10.18 |
| D+1 | persistencia | 2,957,616 | 26.2 | 0.843 | 0.650 | 0.1218 | 76.8 | 76.8 | 12.21 |
| D+1 | frequencia_1d | 2,957,616 | 26.2 | 0.596 | 0.312 | 0.1966 | 31.5 | 3.2 | — |

## ENE: por fonte (LightGBM)

| horizonte | fonte | n | prevalencia | roc_auc | pr_auc | brier | mae_montante_mw |
|---|---|---|---|---|---|---|---|
| 30min | eolica | 1,968,900 | 26.8 | 0.994 | 0.985 | 0.0253 | 3.19 |
| 30min | solar | 1,000,090 | 25.3 | 0.994 | 0.985 | 0.0251 | 4.59 |
| 3h | eolica | 1,968,120 | 26.8 | 0.962 | 0.905 | 0.0766 | 7.89 |
| 3h | solar | 999,660 | 25.3 | 0.969 | 0.913 | 0.0724 | 10.16 |
| D+1 | eolica | 1,961,568 | 26.7 | 0.945 | 0.865 | 0.0973 | 9.48 |
| D+1 | solar | 996,048 | 25.3 | 0.960 | 0.888 | 0.0893 | 11.55 |

## CNF: todas as usinas

| horizonte | modelo | n | prevalencia | roc_auc | pr_auc | brier | precisao | recall | mae_montante_mw |
|---|---|---|---|---|---|---|---|---|---|
| 30min | lightgbm | 2,968,990 | 7.9 | 0.994 | 0.969 | 0.0079 | 95.8 | 92.8 | 1.19 |
| 30min | persistencia | 2,968,990 | 7.9 | 0.964 | 0.876 | 0.0106 | 93.3 | 93.3 | 1.05 |
| 30min | frequencia_1d | 2,968,990 | 7.9 | 0.947 | 0.600 | 0.0446 | 61.1 | 49.1 | — |
| 3h | lightgbm | 2,967,780 | 7.9 | 0.966 | 0.769 | 0.0335 | 73.7 | 66.9 | 3.86 |
| 3h | persistencia | 2,967,780 | 7.9 | 0.823 | 0.481 | 0.0514 | 67.5 | 67.4 | 3.49 |
| 3h | frequencia_1d | 2,967,780 | 7.9 | 0.912 | 0.540 | 0.0485 | 58.1 | 46.7 | — |
| D+1 | lightgbm | 2,957,616 | 7.9 | 0.922 | 0.615 | 0.0458 | 67.3 | 46.7 | 4.95 |
| D+1 | persistencia | 2,957,616 | 7.9 | 0.796 | 0.421 | 0.0593 | 62.7 | 62.3 | 3.96 |
| D+1 | frequencia_1d | 2,957,616 | 7.9 | 0.864 | 0.437 | 0.0558 | 52.9 | 42.2 | — |

## CNF: por fonte (LightGBM)

| horizonte | fonte | n | prevalencia | roc_auc | pr_auc | brier | mae_montante_mw |
|---|---|---|---|---|---|---|---|
| 30min | eolica | 1,968,900 | 10.5 | 0.994 | 0.974 | 0.0093 | 1.46 |
| 30min | solar | 1,000,090 | 2.8 | 0.991 | 0.921 | 0.0053 | 0.65 |
| 3h | eolica | 1,968,120 | 10.5 | 0.963 | 0.802 | 0.0402 | 4.71 |
| 3h | solar | 999,660 | 2.8 | 0.958 | 0.412 | 0.0204 | 2.19 |
| D+1 | eolica | 1,961,568 | 10.5 | 0.912 | 0.651 | 0.0571 | 6.11 |
| D+1 | solar | 996,048 | 2.8 | 0.925 | 0.278 | 0.0235 | 2.65 |

Prevalência, precisão e recall em %; montante em MW por usina e semi-hora.
