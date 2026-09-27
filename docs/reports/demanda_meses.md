# Demanda bruta para meses à frente — backtest (Fase 1)

Gerado por `src/models/demanda_meses.py` (etapa `demanda_meses` do `run_heavywork.py`).
Parâmetros: `Backend/config/demanda_meses.yaml`. Especificação: `docs/oraculo/especificacao/17-previsao-meses-carga-mmgd-pato.md`.

**Alvo:** demanda bruta = carga global consistida do ONS (não a supervisionada: a MMGD é
prevista à parte nas fases seguintes e a curva do pato é D − G). Resolução horária.

**Modelo:** nível dos últimos 12 meses × crescimento × índice sazonal mensal × perfil
(mês × dia-tipo × hora, últimos 3 anos) + sensibilidade à temperatura (β por mês × hora).
- `era5`: temperatura ERA5 observada nos alvos (**tempo perfeito**: teto do que o tempo previsto pode dar).
- `clim`: sem tempo (anomalia 0). É a variante publicada para a frente até o SEAS5 entrar (Fase 2).

**Backtest:** origem móvel, uma emissão no 1º dia de cada mês desde 2025-07-01
(15 emissões de teste), horizontes de 1 a 6 meses,
270,120 previsões horárias com real conhecido. Crescimento no backtest: só a taxa histórica (o PLAN
2026-2030 2ª RQ saiu em 07/08/2026, depois do início do teste). Banda P10–P90: quantis do erro relativo
das 12 emissões anteriores, só com alvos já ocorridos na emissão.

**Baselines:** sazonal ingênuo (mesmo horário 364 dias antes × crescimento) e persistência semanal.

## Critério de aceite da Fase 1

Skill da variante `clim` (sem tempo) sobre o sazonal ingênuo, média dos horizontes: SE +0.290, S +0.204, NE +0.168, N +0.109, SIN +0.255.

## Resumo por série (média dos horizontes)

| serie | modelo | mae_mw | mape_pct | skill_vs_sazonal_ingenuo | cobertura_p10_p90 |
|---|---|---|---|---|---|
| SE | era5 | 1,677 | 3.68 | +0.388 | 66% |
| SE | clim | 1,945 | 4.25 | +0.290 | 66% |
| SE | sazonal_ingenuo | 2,739 | 5.97 | +0.000 | — |
| SE | persistencia_semanal | 3,604 | 7.99 | -0.311 | — |
| S | era5 | 728 | 5.10 | +0.266 | 76% |
| S | clim | 790 | 5.51 | +0.204 | 78% |
| S | sazonal_ingenuo | 992 | 6.86 | +0.000 | — |
| S | persistencia_semanal | 1,920 | 13.43 | -0.934 | — |
| NE | era5 | 540 | 3.84 | +0.201 | 71% |
| NE | clim | 562 | 4.00 | +0.168 | 70% |
| NE | sazonal_ingenuo | 676 | 4.82 | +0.000 | — |
| NE | persistencia_semanal | 901 | 6.42 | -0.326 | — |
| N | era5 | 258 | 2.95 | +0.146 | 79% |
| N | clim | 269 | 3.08 | +0.109 | 79% |
| N | sazonal_ingenuo | 302 | 3.46 | +0.000 | — |
| N | persistencia_semanal | 593 | 6.71 | -0.964 | — |
| SIN | era5 | 2,588 | 3.13 | +0.312 | 66% |
| SIN | clim | 2,800 | 3.38 | +0.255 | 66% |
| SIN | sazonal_ingenuo | 3,760 | 4.52 | +0.000 | — |
| SIN | persistencia_semanal | 5,829 | 7.09 | -0.544 | — |

## Por horizonte

| serie | horizonte_mes | modelo | mae_mw | mape_pct | vies_mw | mae_minima_diurna_mw | mae_ponta_noturna_mw | cobertura_p10_p90 | skill_vs_sazonal_ingenuo |
|---|---|---|---|---|---|---|---|---|---|
| SE | 1 | clim | 1,862 | 4.12 | -365 | 2,163 | 1,721 | 76% | +0.284 |
| SE | 1 | era5 | 1,587 | 3.53 | -383 | 1,864 | 1,311 | 77% | +0.389 |
| SE | 1 | sazonal_ingenuo | 2,598 | 5.71 | -334 | 3,244 | 2,192 | — | +0.000 |
| SE | 2 | clim | 1,942 | 4.27 | -500 | 2,210 | 1,824 | 75% | +0.295 |
| SE | 2 | era5 | 1,663 | 3.67 | -513 | 1,910 | 1,416 | 75% | +0.396 |
| SE | 2 | sazonal_ingenuo | 2,755 | 6.03 | -419 | 3,403 | 2,339 | — | +0.000 |
| SE | 3 | clim | 1,957 | 4.28 | -625 | 2,196 | 1,860 | 70% | +0.304 |
| SE | 3 | era5 | 1,674 | 3.67 | -637 | 1,893 | 1,452 | 71% | +0.405 |
| SE | 3 | sazonal_ingenuo | 2,814 | 6.14 | -495 | 3,450 | 2,388 | — | +0.000 |
| SE | 4 | clim | 1,956 | 4.26 | -748 | 2,161 | 1,905 | 63% | +0.277 |
| SE | 4 | era5 | 1,678 | 3.67 | -745 | 1,869 | 1,500 | 64% | +0.380 |
| SE | 4 | sazonal_ingenuo | 2,706 | 5.88 | -765 | 3,303 | 2,329 | — | +0.000 |
| SE | 5 | clim | 1,971 | 4.28 | -832 | 2,155 | 1,959 | 57% | +0.283 |
| SE | 5 | era5 | 1,714 | 3.74 | -807 | 1,886 | 1,588 | 57% | +0.376 |
| SE | 5 | sazonal_ingenuo | 2,749 | 5.96 | -840 | 3,333 | 2,393 | — | +0.000 |
| SE | 6 | clim | 1,980 | 4.29 | -864 | 2,155 | 1,995 | 53% | +0.296 |
| SE | 6 | era5 | 1,743 | 3.79 | -820 | 1,922 | 1,629 | 52% | +0.380 |
| SE | 6 | sazonal_ingenuo | 2,813 | 6.09 | -764 | 3,395 | 2,464 | — | +0.000 |
| S | 1 | clim | 756 | 5.35 | -25 | 987 | 679 | 82% | +0.218 |
| S | 1 | era5 | 695 | 4.93 | -53 | 902 | 647 | 81% | +0.281 |
| S | 1 | sazonal_ingenuo | 966 | 6.78 | +37 | 1,311 | 837 | — | +0.000 |
| S | 2 | clim | 782 | 5.53 | -20 | 1,005 | 706 | 82% | +0.215 |
| S | 2 | era5 | 719 | 5.09 | -54 | 917 | 676 | 80% | +0.277 |
| S | 2 | sazonal_ingenuo | 995 | 6.97 | +35 | 1,334 | 862 | — | +0.000 |
| S | 3 | clim | 785 | 5.50 | -55 | 1,003 | 718 | 81% | +0.221 |
| S | 3 | era5 | 722 | 5.06 | -91 | 912 | 687 | 78% | +0.284 |
| S | 3 | sazonal_ingenuo | 1,008 | 7.01 | +18 | 1,344 | 879 | — | +0.000 |
| S | 4 | clim | 804 | 5.59 | -74 | 1,012 | 754 | 77% | +0.198 |
| S | 4 | era5 | 743 | 5.18 | -108 | 923 | 727 | 74% | +0.258 |
| S | 4 | sazonal_ingenuo | 1,002 | 6.91 | -26 | 1,316 | 893 | — | +0.000 |
| S | 5 | clim | 827 | 5.73 | -88 | 1,019 | 793 | 74% | +0.180 |
| S | 5 | era5 | 762 | 5.30 | -123 | 926 | 756 | 71% | +0.244 |
| S | 5 | sazonal_ingenuo | 1,008 | 6.90 | -82 | 1,308 | 922 | — | +0.000 |
| S | 6 | clim | 784 | 5.38 | -109 | 963 | 785 | 73% | +0.194 |
| S | 6 | era5 | 728 | 5.02 | -139 | 886 | 739 | 69% | +0.252 |
| S | 6 | sazonal_ingenuo | 973 | 6.60 | -142 | 1,265 | 915 | — | +0.000 |
| NE | 1 | clim | 533 | 3.84 | -115 | 622 | 529 | 79% | +0.162 |
| NE | 1 | era5 | 513 | 3.71 | -101 | 612 | 491 | 79% | +0.194 |
| NE | 1 | sazonal_ingenuo | 636 | 4.59 | -106 | 817 | 548 | — | +0.000 |
| NE | 2 | clim | 557 | 3.98 | -150 | 629 | 566 | 75% | +0.154 |
| NE | 2 | era5 | 536 | 3.84 | -134 | 619 | 529 | 75% | +0.186 |
| NE | 2 | sazonal_ingenuo | 659 | 4.72 | -142 | 833 | 573 | — | +0.000 |
| NE | 3 | clim | 568 | 4.02 | -193 | 612 | 595 | 74% | +0.168 |
| NE | 3 | era5 | 545 | 3.87 | -176 | 601 | 554 | 74% | +0.202 |
| NE | 3 | sazonal_ingenuo | 683 | 4.86 | -180 | 842 | 604 | — | +0.000 |
| NE | 4 | clim | 575 | 4.06 | -211 | 614 | 609 | 70% | +0.166 |
| NE | 4 | era5 | 552 | 3.90 | -192 | 602 | 568 | 71% | +0.199 |
| NE | 4 | sazonal_ingenuo | 689 | 4.89 | -215 | 851 | 609 | — | +0.000 |
| NE | 5 | clim | 569 | 4.01 | -245 | 577 | 626 | 66% | +0.173 |
| NE | 5 | era5 | 546 | 3.86 | -223 | 565 | 582 | 67% | +0.208 |
| NE | 5 | sazonal_ingenuo | 688 | 4.88 | -257 | 835 | 620 | — | +0.000 |
| NE | 6 | clim | 572 | 4.04 | -261 | 565 | 639 | 57% | +0.182 |
| NE | 6 | era5 | 546 | 3.87 | -236 | 553 | 588 | 58% | +0.219 |
| NE | 6 | sazonal_ingenuo | 700 | 4.97 | -268 | 845 | 633 | — | +0.000 |
| N | 1 | clim | 275 | 3.16 | -5 | 330 | 256 | 82% | +0.078 |
| N | 1 | era5 | 266 | 3.05 | -7 | 321 | 230 | 82% | +0.109 |
| N | 1 | sazonal_ingenuo | 299 | 3.43 | -14 | 362 | 283 | — | +0.000 |
| N | 2 | clim | 283 | 3.22 | -21 | 345 | 261 | 81% | +0.070 |
| N | 2 | era5 | 273 | 3.10 | -24 | 335 | 233 | 80% | +0.102 |
| N | 2 | sazonal_ingenuo | 304 | 3.47 | -35 | 374 | 288 | — | +0.000 |
| N | 3 | clim | 278 | 3.16 | -40 | 347 | 254 | 80% | +0.099 |
| N | 3 | era5 | 268 | 3.04 | -41 | 339 | 230 | 79% | +0.131 |
| N | 3 | sazonal_ingenuo | 309 | 3.52 | -51 | 385 | 292 | — | +0.000 |
| N | 4 | clim | 272 | 3.10 | -37 | 345 | 246 | 77% | +0.104 |
| N | 4 | era5 | 262 | 2.97 | -38 | 335 | 220 | 77% | +0.139 |
| N | 4 | sazonal_ingenuo | 304 | 3.47 | -68 | 388 | 284 | — | +0.000 |
| N | 5 | clim | 260 | 2.97 | -19 | 329 | 233 | 76% | +0.132 |
| N | 5 | era5 | 247 | 2.83 | -15 | 317 | 198 | 77% | +0.174 |
| N | 5 | sazonal_ingenuo | 299 | 3.44 | -55 | 386 | 277 | — | +0.000 |
| N | 6 | clim | 246 | 2.85 | +15 | 308 | 223 | 80% | +0.170 |
| N | 6 | era5 | 231 | 2.68 | +22 | 294 | 180 | 81% | +0.221 |
| N | 6 | sazonal_ingenuo | 297 | 3.44 | -38 | 383 | 276 | — | +0.000 |
| SIN | 1 | clim | 2,672 | 3.26 | -530 | 3,147 | 2,526 | 77% | +0.255 |
| SIN | 1 | era5 | 2,453 | 3.00 | -572 | 2,842 | 2,334 | 77% | +0.316 |
| SIN | 1 | sazonal_ingenuo | 3,588 | 4.36 | -436 | 4,680 | 2,986 | — | +0.000 |
| SIN | 2 | clim | 2,788 | 3.38 | -715 | 3,182 | 2,720 | 76% | +0.262 |
| SIN | 2 | era5 | 2,569 | 3.12 | -752 | 2,883 | 2,514 | 76% | +0.320 |
| SIN | 2 | sazonal_ingenuo | 3,779 | 4.57 | -583 | 4,841 | 3,206 | — | +0.000 |
| SIN | 3 | clim | 2,786 | 3.36 | -937 | 3,105 | 2,778 | 72% | +0.276 |
| SIN | 3 | era5 | 2,559 | 3.09 | -974 | 2,809 | 2,549 | 72% | +0.335 |
| SIN | 3 | sazonal_ingenuo | 3,847 | 4.63 | -730 | 4,861 | 3,297 | — | +0.000 |
| SIN | 4 | clim | 2,813 | 3.38 | -1,094 | 3,084 | 2,862 | 64% | +0.240 |
| SIN | 4 | era5 | 2,589 | 3.11 | -1,115 | 2,807 | 2,633 | 64% | +0.300 |
| SIN | 4 | sazonal_ingenuo | 3,702 | 4.44 | -1,098 | 4,664 | 3,207 | — | +0.000 |
| SIN | 5 | clim | 2,876 | 3.45 | -1,211 | 3,092 | 2,997 | 57% | +0.236 |
| SIN | 5 | era5 | 2,667 | 3.21 | -1,204 | 2,831 | 2,783 | 57% | +0.292 |
| SIN | 5 | sazonal_ingenuo | 3,765 | 4.51 | -1,261 | 4,705 | 3,322 | — | +0.000 |
| SIN | 6 | clim | 2,866 | 3.43 | -1,248 | 3,032 | 3,060 | 51% | +0.261 |
| SIN | 6 | era5 | 2,688 | 3.23 | -1,217 | 2,818 | 2,849 | 49% | +0.307 |
| SIN | 6 | sazonal_ingenuo | 3,878 | 4.64 | -1,238 | 4,814 | 3,468 | — | +0.000 |

## Previsão para a frente — SIN (média mensal)

Emitida em 2026-09-26 00:00, variante `clim`, crescimento
`plan` (taxa da carga global do SIN no PLAN 2026-2030 2ª RQ, aplicada a todos os subsistemas).
Previsão horária completa em `Backend/data/processed/previsao_demanda_meses.parquet`.

| mês | P10 (MWmed) | P50 (MWmed) | P90 (MWmed) |
|---|---|---|---|
| 2026-09 | 82,032 | 85,298 | 90,906 |
| 2026-10 | 83,151 | 86,493 | 92,808 |
| 2026-11 | 84,020 | 87,608 | 94,437 |
| 2026-12 | 83,663 | 87,807 | 95,081 |
| 2027-01 | 84,531 | 89,387 | 97,731 |
| 2027-02 | 87,978 | 93,344 | 102,983 |
| 2027-03 | 86,659 | 91,995 | 101,543 |

## Limitações

- Meses à frente sem previsão de tempo: a banda da variante `clim` inclui a variabilidade do tempo
  (é medida no erro real). A variante `era5` mostra quanto o tempo previsto poderia ganhar no máximo.
- **Banda ainda estreita nos horizontes longos:** a cobertura P10–P90 fica perto de 75–78% no mês 1
  e cai nos seguintes (meta da spec: 75–85%). A calibração vê só as 12 emissões anteriores, e o erro de
  nível de um ano inteiro (crescimento) mal aparece nelas. Próximo passo: CQR/janela maior (Fase 3).
- O último mês da previsão para a frente é parcial (emissão no meio do mês) e usa a banda do horizonte 6.
- A taxa do PLAN é do SIN; nos subsistemas é premissa.
- O sazonal ingênuo compara o mesmo dia da semana 364 dias antes: um feriado móvel pode cair em dia
  diferente (o modelo trata feriado como domingo; o baseline não).
- Mudanças estruturais (tarifa branca, veículo elétrico, BESS atrás do medidor) não estão modeladas.
