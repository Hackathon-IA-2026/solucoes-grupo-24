# Desempate da MMGD: BDGD × cadastro da ANEEL (área piloto RJ)

Gerado por `python -m src.spatial.construir` (etapa `espacializacao` do run_heavywork).
Método em `docs/metodo_espacial.md`. Potências em MW.

| distribuidora | BDGD (data) | categoria | empreendimentos | potência ANEEL | potência BDGD |
|---|---|---|---:|---:|---:|
| ENEL RJ | 2025-12-31 | bdgd_e_aneel | 111,538 | 912.4 | 234.4 |
| ENEL RJ | 2025-12-31 | bdgd_sem_homologacao | 3 | 0.0 | 0.0 |
| ENEL RJ | 2025-12-31 | lag_sistema | 17,410 | 149.7 | 0.0 |
| LIGHT | 2025-12-31 | bdgd_e_aneel | 56,957 | 702.8 | 718.3 |
| LIGHT | 2025-12-31 | bdgd_sem_homologacao | 27 | 0.0 | 1.4 |
| LIGHT | 2025-12-31 | lag_sistema | 7,294 | 143.8 | 0.0 |

## Leitura

- **ENEL RJ**: potência BDGD ÷ ANEEL (mediana, mesmo CEG) = 0.20. Lag de sistema: 17,410 empreendimentos (149.7 MW), dos quais 3,658 cadastrados na ANEEL até a data da BDGD (ausentes da BDGD, não só atrasados). Lag sem rede da distribuidora no município (sem mancha): 1 (0.01 MW).
- **LIGHT**: potência BDGD ÷ ANEEL (mediana, mesmo CEG) = 1.00. Lag de sistema: 7,294 empreendimentos (143.8 MW), dos quais 2,579 cadastrados na ANEEL até a data da BDGD (ausentes da BDGD, não só atrasados). Lag sem rede da distribuidora no município (sem mancha): 0 (0.00 MW).

## Manchas

- 448 manchas (uma por subestação), 162 sem transformadores suficientes para o fecho (semente + Voronoi).
- Geometria vazia depois dos recortes: 1 (ENEL_RJ:VWG); a MMGD delas continua contada.
- Recorte pelo limite do IBGE ignorado (apagaria a mancha): 5.
- Classificação: Distribuição plena: 179; Transporte/manobra: 141; Distribuição satélite: 110; Transformadora pura: 18.

## Fluxo reverso medido (BDGD)

12 alimentadores têm energia líquida negativa em pelo menos um mês (exportam para a subestação; lista em `docs/reports/alimentadores_fluxo_reverso.csv`), com origem em 9 manchas: SETD ROCHA FREIRE, SETD SANTA CECILIA, SETD BRISAMAR, SETD INFLUENCIA, SETD CENTENARIO, SETD CARMARI, SETD FONTINELE, SETD TRES RIOS, SETD VOLTA REDONDA. É a evidência medida pela distribuidora com que os excedentes previstos devem bater.
