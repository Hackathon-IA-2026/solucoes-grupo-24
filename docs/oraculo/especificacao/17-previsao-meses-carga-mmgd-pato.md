# Especificação — Previsão de carga, geração de MMGD e curva do pato prevista

**Status:** Fase 1 implementada em 2026-09-27 (`Backend/src/models/demanda_meses.py`, etapa
`demanda_meses` do `run_heavywork.py`, relatório em `docs/reports/demanda_meses.md`); Fases 2 e 3 implementadas (`src/models/pato_meses.py`, tela Operação › Previsão de meses);
fases 4 e 5 e o SEAS5 não implementados. **Escopo:** repositório `solucoes-grupo-24`
(Backend/ + Frontend/oraculo-dashboard). **Relaciona-se com:** `16-curva-do-pato-tempo.md`
(curva do pato de curto prazo, já implementada em `Backend/oraculo/tempo/`),
`15-projecao-corte-ene.md` (trajetórias PLAN/PAR-PEL), auditoria MMGD em 3 camadas
(`Backend/pipeline/auditoria_*.py`) e o modelo de carga do time (`Backend/config/modelos_carga.yaml`).

---

## 1. Objetivo

Três perguntas, uma cadeia:

1. **Carga:** quanto o SIN (e cada subsistema) vai demandar, hora a hora, nos próximos meses?
2. **MMGD:** quanto a micro e minigeração distribuída vai gerar nesse mesmo período, dado onde
   ela está (visão computacional + BDGD + cadastro ANEEL) e o tempo previsto (FourCastNet 3 e
   Open-Meteo)?
3. **Curva do pato:** qual a carga líquida que o ONS verá (carga − geração de MMGD), com a
   profundidade da "barriga" ao meio-dia e a rampa do fim de tarde, com incerteza?

Saída principal: para cada subsistema e o SIN, curvas horárias **P10/P50/P90** da demanda, da
MMGD e da carga líquida, nos horizontes de dias a meses, com a proveniência de cada número.

## 2. Definições (evitar a contagem dupla)

O ONS publica, por semi-hora, `val_cargaglobal` e `val_cargammgd`; o repositório já define
**carga supervisionada = carga global − MMGD** (`Backend/data/processed/carga_supervisionada.csv`).

| Grandeza | Definição | Papel nesta especificação |
|---|---|---|
| **Demanda bruta** `D(t)` | carga global do ONS (inclui o que a MMGD atende) | alvo do **modelo de carga** |
| **MMGD** `G(t)` | geração distribuída (estimativa ONS no histórico; modelo físico no futuro) | alvo do **modelo de geração** |
| **Carga líquida** `L(t) = D(t) − G(t)` | o que o sistema supervisionado atende | a **curva do pato prevista** |

Decisão: **não** prever a carga supervisionada diretamente para horizontes longos. Ela mistura
dois sinais com causas diferentes (consumo, que depende de temperatura e calendário; MMGD, que
depende de radiação e de capacidade instalada que cresce ~10%/ano). Separá-los permite trocar
a trajetória de MMGD (cenários) sem retreinar o modelo de carga, e manter a correlação física
entre os dois pelo mesmo membro do ensemble meteorológico (§6).

Observação: a `val_cargammgd` do ONS é **estimativa**, não medição. Ela serve para calibrar o
modelo físico de MMGD (§5.4), não como verdade de campo; o erro dela entra nas limitações.

## 3. Horizontes

| Faixa | Horizonte | Resolução | Tempo usado | Uso |
|---|---|---|---|---|
| Curto | 0–15 dias | horária | FourCastNet 3 (ensemble) + Open-Meteo (AIFS, IFS, GFS) | programação, curva do pato da semana (estende o painel atual) |
| Subsazonal | 2–6 semanas | horária agregada por dia-tipo | Open-Meteo sazonal (ECMWF SEAS5) + climatologia ERA5 | planejamento mensal da operação |
| Sazonal | 1–6 meses (até 9 se a fonte permitir) | perfil horário por mês × dia-tipo | Open-Meteo sazonal + climatologia ERA5 condicionada + cenários | "próximos meses": profundidade da barriga, rampa, risco de carga líquida mínima |

Nota honesta sobre habilidade: previsão determinística de tempo perde habilidade depois de
~10–15 dias. Para meses, a entrega é **distribuição** (quantis por mês e hora), não um valor
por hora de uma data futura; o painel precisa dizer isso.

## 4. Arquitetura

```text
                   ┌─────────────────────── INGESTÃO (run_heavywork, etapa 1) ───────────────────────┐
 ONS dados abertos │ carga verificada (apicarga, 30 min) · balanço · curva_carga · val_cargammgd      │
 ANEEL             │ cadastro MMGD (município, potência, data de conexão) · BDGD (UCBT/UCMT, SED)     │
 Visão + auditoria │ camada1 (painéis, m²) · camadas 2/3 (desempate e fator de correção por mancha)   │
 Tempo             │ FourCastNet 3 (GPU/NIM) · Open-Meteo forecast/historical/seasonal · ERA5        │
 Planejamento      │ PLAN 2026-2030 2ª RQ (carga global e MMGD anuais) · PAR/PEL 2025 (trajetória)   │
                   └─────────────────────────────────────────────────────────────────────────────────┘
                                   │
          ┌────────────────────────┼─────────────────────────────┐
          ▼                        ▼                             ▼
  A. CAPACIDADE DE MMGD     B. TEMPO NAS CÉLULAS           C. CALENDÁRIO
  cadastro × fator da       FCN3 / Open-Meteo / ERA5       feriados, dia-tipo,
  auditoria, por célula;    reamostrados para as células   horário de verão
  trajetória mensal         (GHI, T2m, nuvens); ensemble   (UTC−3 fixo)
          │                        │                             │
          └──────────┬─────────────┘                             │
                     ▼                                           │
          D. MODELO DE GERAÇÃO MMGD  (físico PV + PR calibrado)  │
             G_m(t) por membro m, célula → subsistema → SIN      │
                     │                                           │
                     │        E. MODELO DE DEMANDA  ◄────────────┤ temperatura do mesmo membro m
                     │           D_m(t) quantílico               │
                     ▼                  ▼                        │
          F. CURVA DO PATO   L_m(t) = D_m(t) − G_m(t)  → quantis, métricas (barriga, rampa)
                     │
                     ▼
          G. VALIDAÇÃO (backtest cronológico) → H. PUBLICAÇÃO (banco + contrato) → API → telas
```

Tudo o que é pesado roda no **`run_heavywork.py`** como etapas novas (idempotentes, puladas quando
as entradas não mudam, como as atuais); o serviço web (`main.py`) só lê o que foi publicado.
A única exceção é o FourCastNet 3, que roda num **executor com GPU** separado (§5.2).

## 5. Componentes

### 5.1 A — Capacidade de MMGD por célula (onde está a MMGD)

**Entrada:** cadastro ANEEL (já ingerido: `capacidade_mmgd.csv`, município × data, 53,97 GW);
BDGD (unidades com GD por alimentador/transformador); saída das camadas 2/3 da auditoria
(`output/auditoria/auditoria_camadas_2_3.json`: fator de correção por mancha).

**Processo:**
1. Capacidade cadastrada por município e mês (reuso de `oraculo/tempo/pato.clusters`, que agrupa
   municípios em células de ~2,5°, preservando a potência total).
2. **Correção pela visão computacional**: onde há auditoria, `cap_efetiva = cap_cadastrada ×
   fator_mancha`, agregando manchas no município. Onde não há, fator = 1 com flag
   `sem_auditoria`. Detecções "Não homologada" **não** entram (regra da auditoria: exceção
   escalada, nunca incorporada em silêncio); ficam num cenário à parte ("MMGD oculta").
3. **Defasagem de cadastro:** os últimos 3 meses são sub-registrados (premissa já usada em
   `config.ENE["defasagem_cadastro_meses"]`); completa-se pela taxa recente.
4. **Trajetória futura:** crescimento mensal pela **taxa** das trajetórias oficiais (PLAN 2026-2030
   2ª RQ: 55,6 GW em 2026 → 72,5 GW em 2030; PAR/PEL 2025), aplicada ao nível do cadastro (bases
   diferentes: aplica-se taxa, não nível). Cenários: baixo / referência / alto.
5. **Orientação e tipo:** sem dado por sistema, premissa de azimute norte e inclinação ≈ latitude,
   com incerteza no PR (§5.4).

**Saída:** `mmgd_capacidade_celula` (célula, subsistema, mês, cenário, MWp, fonte, fator, flags).

### 5.2 B — Tempo nas células (FourCastNet 3 + Open-Meteo)

| Fonte | O que dá | Onde roda | Papel |
|---|---|---|---|
| **FourCastNet 3** (NVIDIA Earth-2, `earth2studio`) | ensemble global 0,25°, passos de 6 h, até ~15 dias | executor com GPU (servidor próprio, nuvem ou NIM com chave NVIDIA) | ensemble de IA de curto prazo; membros para a incerteza |
| Open-Meteo `forecast` (AIFS, IFS, GFS) | horário, 7–16 dias, radiação e temperatura | API HTTP (já integrado em `oraculo/tempo/clima.py`) | base operacional e comparação entre modelos; contingência se o FCN3 faltar |
| Open-Meteo `historical-forecast` | previsões arquivadas | API | backtest honesto (o que cada modelo previu na época) |
| Open-Meteo `archive` (ERA5) | reanálise horária | API | verdade para calibrar e validar; base da climatologia |
| Open-Meteo sazonal (ECMWF SEAS5) | anomalias/membros para meses à frente | API | horizonte de meses |

Pontos de atenção (a confirmar na implementação, antes de codificar):
- **Radiação no FCN3:** o prognóstico do FCN3 traz variáveis de estado (temperatura, vento,
  umidade, pressão, geopotencial); a radiação solar à superfície (SSRD/GHI) precisa de um
  **modelo diagnóstico** acoplado (o `earth2studio` oferece diagnósticos de radiação solar do tipo
  AFNO) ou de uma relação estatística nuvens/umidade → GHI calibrada no ERA5. Sem isso, o FCN3
  fornece temperatura e o GHI vem do Open-Meteo. Esta é a decisão de desenho mais sensível.
- **Resolução temporal:** FCN3 em 6 h exige interpolação para horário; a radiação não pode ser
  interpolada linearmente (ciclo solar): interpola-se o **índice de céu claro** `k = GHI/GHI_cc`
  e reconstrói-se `GHI = k × GHI_cc(t)` com geometria solar horária (já existe o cálculo de céu
  claro em `oraculo/models/mmgd.py`).
- **Resolução espacial:** 0,25° (~28 km) é mais fino que as células de MMGD (~2,5°); média
  ponderada pela capacidade dentro da célula.
- **GPU e proxy:** este ambiente não tem GPU e o proxy dificultava o PyPI; o FCN3 fica atrás de
  uma **interface de provedor** (`ProvedorTempo.previsao(pontos, inicio, fim) -> Ensemble`), a mesma
  que o `oraculo/tempo/clima.providers_status()` já declara para o "earth2". O resto da cadeia não
  muda se o provedor for FCN3, AIFS ou IFS.
- **Viés:** correção de viés por célula, mês e hora contra o ERA5 (quantile mapping) antes de
  alimentar os modelos; aplicada igual a todos os provedores.

Para meses: **climatologia condicionada**. Para cada mês alvo, sorteiam-se anos-análogos do ERA5
(2000–2025) ponderados pela anomalia prevista pelo SEAS5 (temperatura e radiação do mês). Cada
ano-análogo vira um membro com a sequência horária real daquele ano, o que preserva dias nublados
em sequência e a correlação temperatura × radiação.

**Saída:** `tempo_celula` (membro, célula, hora, GHI, T2m, fonte, correção aplicada).

### 5.3 C — Calendário

Reuso de `Backend/data/processed/calendario.csv` (UTC−3 fixo, patamares, feriados). Acrescentar
feriados futuros (biblioteca `holidays`, já dependência) e dia-tipo (útil, sábado, domingo/feriado,
ponte).

### 5.4 D — Modelo de geração de MMGD

Modelo físico, o mesmo do painel "Curva do pato · tempo" (`oraculo/tempo/pato.pv_mw`):

```text
G_c(t) = Cap_c(t) × PR_ss × GHI_c(t)/1000 × [1 + γ_T (T_célula − 25 °C)]
T_célula = T2m + (NOCT − 20)/800 × GHI
```

- `PR_ss` (performance ratio por subsistema) calibrado para reproduzir a `val_cargammgd` do ONS
  no histórico com o ERA5 (já existe: `calibrate_pr`); recalibração trimestral.
- Soma por célula → subsistema → SIN; ensemble por membro `m`.
- Incerteza: membros do tempo × incerteza do PR (bootstrap dos resíduos da calibração) ×
  cenário de capacidade.
- Opcional (fase 2): correção residual por LightGBM (hora, mês, nuvens, idade média do parque)
  treinada no resíduo `val_cargammgd − G_físico`, sem deixar o modelo "esquecer" a física.

### 5.5 E — Modelo de demanda (carga global)

Três camadas, cada uma no seu horizonte:

1. **Curto prazo (0–15 dias):** estende o LightGBM quantílico do time (`src/models/carga.py`) com
   features de **tempo previsto** (T2m, umidade, radiação do membro `m`, média ponderada pela
   carga do subsistema) e alvo = demanda bruta. Modelos diretos por horizonte (h em dias), como
   hoje. O modelo é aplicado a cada membro: demanda condicionada ao tempo.
2. **Meses (1–6+):** decomposição
   `D(t) = Tendência_mês × Perfil(hora, dia-tipo, mês) + β_T × ΔT(t) + ε`:
   - tendência mensal ancorada no **PLAN 2026-2030** (carga global média anual 84.989 MWmed em
     2026 → 101.947 em 2030) e reconciliada com o histórico recente;
   - perfil horário normalizado por mês × dia-tipo (média dos últimos anos, sem MMGD);
   - sensibilidade à temperatura por subsistema e hora (regressão já usada no painel do pato:
     `fit_sensitivity`, γ em MW/°C).
   Cada membro climático produz uma trajetória horária; os quantis saem do conjunto.
   **Implementado na Fase 1** (`src/models/demanda_meses.py`); ver o docstring do módulo para as
   escolhas concretas.
3. **Reconciliação:** o SIN é modelado direto e os subsistemas são reconciliados (MinT ou ajuste
   proporcional), porque somar quantis de subsistemas não dá o quantil do SIN (regra do time).

### 5.6 F — Curva do pato prevista

Para cada membro `m`, cenário de capacidade `k` e hora `t`:

```text
L_{m,k}(t) = D_m(t) − G_{m,k}(t)
```

**O mesmo membro** alimenta demanda (temperatura) e MMGD (radiação): um dia de sol forte é
quente, a demanda sobe e a MMGD também; sortear os dois de forma independente superestima a
incerteza e perde o formato do pato.

Métricas por dia (já definidas em `oraculo/tempo/pato.day_metrics`) e, para meses, por mês × dia-tipo:

| Métrica | Definição |
|---|---|
| Barriga | mínimo de `L` entre 10h e 15h e a hora em que ocorre |
| Rampa | `max L(17–21h) − min L(10–15h)` e a maior rampa horária (MW/h) |
| Profundidade relativa | `1 − barriga / L(ponta noturna)` |
| Risco de carga líquida mínima | P(L < limiar de inflexibilidade do subsistema), limiar configurável |
| Participação da MMGD | `G / D` no horário da barriga |

Ligações com o que existe: o risco de carga líquida baixa alimenta a **projeção do corte ENE**
(`oraculo/ene`) e a **alocação de BESS** (`oraculo/bess`) como cenário prospectivo.

## 6. Incerteza (como os quantis são formados)

```text
membros de tempo (FCN3 ~ N; Open-Meteo 3 modelos; análogos ERA5 para meses)
 × cenários de capacidade de MMGD (baixo/ref/alto)       → não se mistura: cenário é eixo, não ruído
 × incerteza do PR (bootstrap)                           → amostras por membro
 × resíduo do modelo de demanda (quantis LightGBM ou bootstrap dos resíduos mensais)
= conjunto de trajetórias L(t) por cenário  → P10/P50/P90 por hora
```

Calibração: conformal (CQR, como o time já faz na banda de carga) sobre a janela de teste, para
que a banda de 80% cubra de fato ~80%.

## 7. Validação

- **Split cronológico** (nunca aleatório); teste cobre pelo menos 12 meses (todas as estações).
- **Previsões de tempo arquivadas** (Open-Meteo historical-forecast; FCN3 reexecutado sobre as
  condições iniciais da época): nunca validar com o tempo observado no lugar do previsto.
- **Baselines obrigatórios:** persistência semanal; sazonal ingênuo (mesmo dia-tipo do ano anterior,
  escalado pelo crescimento); climatologia ERA5; para meses, "perfil do mesmo mês do ano anterior +
  crescimento PLAN".
- **Métricas:** MAE/RMSE por patamar (mínima diurna, rampa, ponta); **erro na barriga** e **erro na
  rampa** (as que importam para a operação); pinball loss e **CRPS** para os quantis; cobertura da
  banda P10–P90; skill sobre cada baseline; comparação FCN3 × AIFS × IFS × GFS no mesmo backtest.
- **MMGD:** erro da geração prevista contra `val_cargammgd` por hora do dia; separado o erro de
  tempo (rodando com ERA5 = "tempo perfeito") do erro do modelo.
- Critério de aceite sugerido: skill > 0 sobre o sazonal ingênuo no erro da barriga em pelo menos
  3 dos 4 subsistemas; cobertura da banda entre 75% e 85%.

## 8. Dados, contrato e API

**Tabelas novas (`data/processed/`, Parquet):** `mmgd_capacidade_celula`, `tempo_celula`
(particionado por fonte/emissão), `previsao_demanda`, `previsao_mmgd`, `previsao_carga_liquida`,
`metricas_pato`.

**Etapas novas no `run_heavywork.py`** (depois das atuais, com impressão digital das entradas):
`ingestao_tempo` → `capacidade_mmgd_celulas` → `treino_demanda_longo` → `previsao_mmgd` →
`previsao_demanda` → `curva_pato_prevista` → publicação no banco (mesma transação única de hoje).
O FCN3 é um passo externo (`python -m pipeline.fcn3_rodar --emissao AAAA-MM-DDTHH`) no executor
com GPU, que grava `tempo_celula` com `fonte=fcn3`; a etapa `ingestao_tempo` só lê o que já existir.

**Contrato (espelhado em `src/contrato/modelos.py` e `types.ts`):**

```text
CurvaPatoPrevista {
  mock: bool, subsistema, cenarioCapacidade, horizonte: "semana" | "mes",
  referencia: data | mês, emitidoEm, fontesTempo: string[],
  horas: [0..23], demanda: {p10,p50,p90}[], mmgd: {p10,p50,p90}[], cargaLiquida: {p10,p50,p90}[],
  barriga: {mw, hora, p10, p90}, rampa: {mw, maxMwH}, riscoCargaMinima: number,
  proveniencia: Proveniencia[]
}
```

**Rotas (só leitura):** `GET /api/previsao/demanda?ss=&horizonte=`, `GET /api/previsao/mmgd?...`,
`GET /api/previsao/pato?ss=&horizonte=&cenario=`, `GET /api/previsao/validacao`.

**Telas (dashboard, grupo Operação/Investimento):**
- *Curva do pato prevista (meses):* seletor de subsistema, mês e cenário de MMGD; leque P10–P90 de
  demanda, MMGD e carga líquida por hora; evolução mensal da barriga e da rampa; comparação entre
  provedores de tempo.
- *Validação do preditivo:* métricas do §7, com FCN3 × Open-Meteo lado a lado.
- A tela atual "Curva do pato · tempo" passa a consumir o mesmo pipeline no horizonte semanal.

## 9. Reuso do que já existe

| Existe | Onde | Uso aqui |
|---|---|---|
| Carga global, MMGD ONS e supervisionada (30 min, desde 2019) | `Backend/data/processed/carga_supervisionada.csv` | alvo e calibração |
| LightGBM quantílico + CQR + backtest | `Backend/src/models/carga.py`, `config/modelos_carga.yaml` | demanda de curto prazo |
| Cliente Open-Meteo com cache, lotes e TLS corporativo | `Backend/oraculo/tempo/clima.py` | provedores Open-Meteo |
| Células de MMGD, PV físico, calibração de PR, sensibilidade à temperatura, métricas do pato | `Backend/oraculo/tempo/pato.py` | modelo de geração e métricas |
| Trajetórias PLAN/PAR-PEL | `Backend/oraculo/config.py` (`ENE["plan"]`, `ENE["parpel"]`) | tendência de demanda e capacidade |
| Auditoria em 3 camadas (fator por mancha) | `Backend/pipeline/auditoria_camadas_2_3.py` | correção da capacidade |
| Detector de painéis + cena georreferenciada | `Backend/oraculo/vision/` | fonte alternativa de área de painel |

## 10. Riscos e limitações

1. **Radiação no FCN3** depende de diagnóstico acoplado ou de relação estatística (§5.2); se não
   houver, o FCN3 contribui só com temperatura.
2. **GPU:** sem executor com GPU (ou chave NIM), o FCN3 fica declarado indisponível e a cadeia roda
   com Open-Meteo. A interface de provedor garante que nada mais quebre.
3. **Visão computacional ainda sem imagem real da área piloto:** a auditoria roda em modo mock; até
   haver imagem submétrica e pesos do YOLO, o fator de correção é 1 (com flag) e a capacidade vem
   só do cadastro.
4. **MMGD do ONS é estimativa:** calibrar o PR nela herda o viés dela; declarar e medir.
5. **Meses à frente:** o tempo tem pouca habilidade; a entrega é distribuição climática
   condicionada, e o painel deve dizê-lo. O maior motor de mudança em meses é a **capacidade**
   instalada, que tem cenários, não previsão.
6. **Mudança estrutural:** tarifa, tarifa branca, veículos elétricos, BESS atrás do medidor mudam o
   perfil; monitorar deriva do resíduo e recalibrar.
7. **Dados pessoais:** BDGD e cadastro ANEEL têm identificadores; só agregados por
   município/mancha saem de `data/raw` (regra atual do repositório).
8. **Horário de verão** (se voltar) e UTC−3 fixo: o calendário precisa marcar.

## 11. Fases de implementação sugeridas

| Fase | Entrega | Critério de pronto | Estado |
|---|---|---|---|
| 1 | Demanda bruta separada da MMGD; modelo de meses (tendência PLAN + perfil + temperatura) com ERA5 como "tempo perfeito" | backtest de 12 meses com skill sobre o sazonal ingênuo | ✅ 2026-09-27: skill da variante sem tempo +0,11 (N) a +0,29 (SE), +0,26 no SIN (`docs/reports/demanda_meses.md`) |
| 2 | MMGD futura por célula com capacidade do cadastro + trajetória; tempo Open-Meteo (curto) e análogos ERA5 condicionados ao SEAS5 (meses) | erro da MMGD por hora do dia medido | ✅ 2026-09-27 (anos-análogos; SEAS5 pendente) |
| 3 | Curva do pato prevista com ensemble conjunto, quantis calibrados, contrato, API e tela | cobertura P10–P90 entre 75% e 85% | ✅ 2026-09-27: cobertura 75–82%, skill na barriga em 3 de 4 subsistemas; rota fora do contrato |
| 4 | FourCastNet 3 no executor com GPU (+ diagnóstico de radiação), comparado com AIFS/IFS/GFS no mesmo backtest | FCN3 publicado como provedor, com métricas lado a lado | ⬜ (sem GPU nem `earth2studio` neste ambiente) |
| 5 | Correção da capacidade pela auditoria de visão computacional com imagem real; cenário "MMGD oculta" | fator por mancha publicado para a área piloto | ⬜ |
