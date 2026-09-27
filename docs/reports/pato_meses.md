# MMGD e curva do pato prevista para meses — backtest (Fases 2 e 3)

Gerado por `src/models/pato_meses.py`. Parâmetros: `Backend/config/pato_meses.yaml`. Tela: **Operação ›
Previsão de meses** (`/previsao-meses`). Especificação: `docs/oraculo/especificacao/17-previsao-meses-carga-mmgd-pato.md`.

Backtest com origem móvel mensal desde 2025-07-01, horizontes 1–6 meses, membros =
anos-análogos do ERA5, cenário de capacidade histórico. Baseline: sazonal ingênuo (364 dias antes).

**Aceite:** {'fase2_mmgd_medida': True, 'fase3_skill_barriga_subsistemas_positivos': 3, 'fase3_skill_barriga_ok': True, 'fase3_cobertura_l_ok': True}

| serie | mmgd_mae_mw | mmgd_mae_tempo_perfeito_mw | skill_mmgd | l_mae_mw | skill_l | barriga_mae_mw | skill_barriga | skill_rampa | l_cobertura | barriga_cobertura |
|---|---|---|---|---|---|---|---|---|---|---|
| N | 116 | 145 | -0.272 | 286 | -0.032 | 427 | -0.361 | -0.246 | 0.816 | 0.698 |
| NE | 187 | 159 | 0.143 | 554 | 0.125 | 537 | 0.228 | -0.091 | 0.753 | 0.917 |
| S | 365 | 162 | 0.109 | 934 | 0.203 | 1,458 | 0.231 | 0.192 | 0.819 | 0.812 |
| SE | 681 | 387 | 0.132 | 2,043 | 0.233 | 2,371 | 0.230 | 0.159 | 0.808 | 0.827 |
| SIN | 899 | 642 | 0.053 | 2,978 | 0.205 | 3,529 | 0.237 | 0.126 | 0.805 | 0.851 |

## Previsão para a frente — SIN, cenário de referência (média do mês, MW)

| mês | carga líquida P50 | barriga P10–P50–P90 | rampa P50 | risco carga mínima |
|---|---|---|---|---|
| 2026-09 | 75,332 | 52,079 – 57,535 – 63,354 | 38,230 | 9% |
| 2026-10 | 76,328 | 54,205 – 59,546 – 65,703 | 35,678 | 3% |
| 2026-11 | 76,093 | 52,532 – 58,639 – 65,365 | 36,167 | 2% |
| 2026-12 | 76,477 | 53,326 – 58,706 – 64,775 | 36,099 | 5% |
| 2027-01 | 78,257 | 54,251 – 60,076 – 66,011 | 37,011 | 6% |
| 2027-02 | 82,253 | 57,563 – 63,573 – 70,925 | 37,244 | 0% |
| 2027-03 | 81,339 | 57,194 – 62,517 – 69,472 | 37,170 | 1% |

## Premissas

- Membros = anos-análogos do ERA5 (sequência horária real de k anos antes); o mesmo membro dá a temperatura da demanda e a radiação da MMGD.
- Meses à frente não têm previsão de tempo: a banda é a variabilidade climática dos análogos, calibrada por conformal no backtest.
- MMGD física (PR recalibrado por subsistema contra a MMGD do ONS nos 12 meses anteriores); a MMGD do ONS é estimativa.
- Distribuição espacial da MMGD = cadastro atual; o nível no tempo segue o cadastro do subsistema.
- Cenários de capacidade: baixo = PAR/PEL 2025, referência = PLAN 2026-2030, alto = taxa do cadastro dos últimos 12 meses.
- Crescimento da demanda para a frente: taxa da carga global do SIN no PLAN 2026-2030, aplicada aos subsistemas.
- Não implementado: condicionamento pelo SEAS5, FourCastNet 3 (sem GPU), fator de correção da visão computacional.
