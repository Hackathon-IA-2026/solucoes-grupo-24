# Teste ponta a ponta (bases ONS → modelos → contrato → dashboard → alerta)

Gerado em 2026-09-26 14:31 UTC por `python -m pipeline.teste_e2e`. O status de cada etapa é LIDO dos dados (existência e flag `mock`), não declarado em config.

| etapa | status | origem |
|---|---|---|
| bases ONS | **ausente** | Tabelas processadas do ONS (etapa 2 do run_heavywork.py) |
| modelos | **ausente** | Modelos treinados e previsões fora da amostra (etapas 3 e 4) |
| contrato JSON | **mock** | mocks do dashboard (Frontend/oraculo-dashboard/src/data/mock) |
| dashboard (contrato) | **ok** | src/contrato/modelos.py (espelho do types.ts) |
| alerta | **mock** | pipeline/explicabilidade.py::gerar_texto_alerta |
| auditoria MMGD | **mock** | fluxo mock (camada 1 sintética + BDGD/ANEEL mock) -> Backend/output/auditoria/mock/auditoria_camadas_2_3_mock.json |

## bases ONS — ausente

```
falta data/processed/carga_supervisionada.csv
falta data/processed/rotulos_curtailment.parquet
falta data/processed/calendario.csv
-> rode `python run_heavywork.py` nesta máquina (dados do ONS)
```

## modelos — ausente

```
falta data/modelos/carga
falta data/modelos/curtailment
-> rode `python run_heavywork.py` nesta máquina (dados do ONS)
```

## contrato JSON — mock

```
carga           mock    (1 registro(s), 1 com mock:true)
previsao        mock    (3 registro(s), 3 com mock:true)
riscos          mock    (7 registro(s), 7 com mock:true)
alertas         mock    (7 registro(s), 7 com mock:true)
excedentes      mock    (5 registro(s), 5 com mock:true)
validacao       mock    (1 registro(s), 1 com mock:true)
mmgd_densidade  mock    (1 registro(s), 1 com mock:true)
```

## dashboard (contrato) — ok

```
7 recursos validam no contrato; todo alerta aponta para um risco
```

## alerta — mock

```
7 alertas coerentes com os riscos; exemplo:
  ⚠ ALERTA — Risco de Curtailment
  Probabilidade de 87% de curtailment de 312 MW em Complexo do Litoral Eólico, hoje às 17:30.
  Motivo: 70% REL · 20% CNF · 10% ENE
  Fonte: ONS — Restrição de operação por constrained-off de usinas eólicas (tm) · janela de previsão 3h · atualizado há 4 min
```

## auditoria MMGD — mock

```
classificação: {'Cadastrada': 5, 'Lag de Sistema': 3, 'Divergência cadastral': 1, 'Não homologada': 3}
AL-JAN-01: fator 1.3477 (26.28 / 19.5 kW)
AL-JAN-02: fator 1.032 (15.48 / 15.0 kW)
não homologadas (exceção, fora do fator): ['D10', 'D11', 'D12']
```

## Cenário dia_dos_pais_2024 (2024-08-11) — indisponível (só referência documental)

- Referência documental (ONS, PAR/PEL 2025 — Sumário Executivo (curvas de carga supervisionada mínima)): carga supervisionada mínima 39.024 MW; MMGD instalada 32.809 MW.
- Atenção: 2024-08-11 está DENTRO do treino do classificador (2023-04-01 → 2025-12-31): o que o modelo disser deste dia é in-sample — serve como caso documentado, não como backtest.
- Carga real indisponível nesta máquina (falta data/processed/carga_supervisionada.csv).
- Rótulos de curtailment indisponíveis nesta máquina (falta data/processed/rotulos_curtailment.parquet).
