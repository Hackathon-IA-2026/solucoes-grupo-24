# 16 · Operação — curva do pato prevista pelo tempo

Objetivo: prever a carga supervisionada dos próximos dias — a **barriga** do
meio-dia e a **rampa** do fim da tarde — cruzando a radiação solar prevista com
**onde a MMGD está instalada**.

## 16.1 Modelos de tempo

| Modelo | Tipo | Situação |
|---|---|---|
| ECMWF AIFS | IA | em uso (Open-Meteo): previsão e previsões arquivadas |
| ECMWF IFS | físico | em uso |
| NOAA GFS | físico | em uso |
| NVIDIA Earth-2 (FourCastNet, CorrDiff) | IA | indisponível: GPU + `earth2studio` (PyTorch) ou NIM com chave de API; proxy bloqueia o PyPI |
| GraphCast (DeepMind) | IA | no Open-Meteo, mas sem radiação solar |
| ERA5 | reanálise | calibração e "tempo perfeito" do backtest |

## 16.2 Decisões

| # | Decisão | Motivo |
|---|---|---|
| T1 | MMGD em células de ~2,5° por subsistema (≥ 100 MW) | 5.568 municípios não cabem numa requisição; 83 células preservam a distribuição espacial |
| T2 | PV: `P = C·PR·G/1000·(1 − 0,004·(T + 0,03G − 25))` | Modelo mínimo com perda térmica |
| T3 | PR calibrado pelo ERA5 contra a MMGD média oficial de 2026 (PLAN) | Nível oficial; PR resultante 0,64–0,83, faixa física real |
| T4 | Carga = dia-tipo − β·ΔMMGD + γ·ΔT | Sem a temperatura, β some por confusão (sol aquece e aumenta a refrigeração) |
| T5 | β e γ estimados antes da janela de teste | Sem vazamento |
| T6 | Hora h do ONS ← rótulo h+1 do Open-Meteo | Radiação é média da hora anterior; verificado no backtest |
| T7 | Barriga = mínimo das 10h–15h | O mínimo das 9h–16h pegava a encosta da manhã em dia útil |
| T8 | Média dos modelos como previsão principal | Nenhum modelo vence em tudo; o AIFS erra mais a rampa |
| T9 | TLS pelo repositório do Windows, sem o modo X.509 estrito | A CA do proxy não declara keyUsage; cadeia e hostname continuam verificados |
| T10 | Previsões arquivadas no backtest | Mede o que cada modelo de fato previu, não o tempo observado |

## 16.3 Resultado (63 dias, SIN)

| Método | Erro 9–16h | Erro na barriga | Erro na rampa |
|---|---|---|---|
| Persistência | 2.843 MW | 2.966 MW | 2.324 MW |
| Média dos modelos | 1.844 MW (−35%) | 1.783 MW | 1.699 MW (−27%) |

## 16.4 Limites

1. O dia-tipo não prevê mudanças de regime de carga; feriados ficam fora.
2. Um PR por subsistema: orientação, sombreamento e limitação de inversores só
   em média.
3. MMGD do cadastro atual; o crescimento dentro da semana é desprezível.
