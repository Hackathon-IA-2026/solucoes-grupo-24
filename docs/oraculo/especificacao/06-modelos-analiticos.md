# 06 · Modelos analíticos

## 6.1 Estimador de MMGD

O Portal de Dados Abertos não publica a MMGD como série horária por área. Ela
aparece apenas **implicitamente**, como redução da carga verificada. Estimá-la é
o núcleo do produto.

### 6.1.1 Geometria solar (`models/solar.py`)

Implementação determinística, sem dependência externa:

1. **Dia do ano e ângulo fracionário** — `γ = 2π (n − 1) / 365`.
2. **Equação do tempo** (Spencer, 1971) — correção entre tempo solar médio e
   verdadeiro, em minutos.
3. **Declinação solar** (Spencer, 1971) — `δ(γ)` em radianos.
4. **Tempo solar verdadeiro** — a partir do horário local, da longitude da área e
   do fuso (`UTC−3`).
5. **Ângulo horário** — `ω = (TSV − 12) · 15°`.
6. **Cosseno do zênite** — `cos θz = sin φ sin δ + cos φ cos δ cos ω`.
7. **Irradiância extraterrestre** — `I₀ = 1367 · (1 + 0,033 cos γ) · cos θz`.
8. **Céu claro (Haurwitz)** — `GHI_cs = 1098 · cos θz · exp(−0,059 / cos θz)`,
   zerado quando `cos θz ≤ 0`.

Escolhas: Haurwitz é um modelo de céu claro de um parâmetro, adequado a um
protótipo porque não exige turbidez de Linke nem perfil de aerossol — dados que o
protótipo não tem. A limitação está declarada.

### 6.1.2 Estimativa de potência (`models/mmgd.py`)

```
MMGD_est(t, a) = C(a) · PR · (GHI_cs(t, a) / 1000) · k_nuvem(t, a)
```

| Termo | Significado | Fonte no protótipo |
|---|---|---|
| `C(a)` | capacidade instalada de MMGD na área, em MWp | `config.py`, ancorado nos 43,5 GW verificados em 2025 (PAR/PEL) e rateado por participação regional |
| `PR` | *performance ratio* agregado (perdas, orientação, sombreamento, indisponibilidade) | 0,78, valor típico de referência para sistemas distribuídos |
| `GHI_cs/1000` | fração da irradiância padrão de teste | `models/solar.py` |
| `k_nuvem` | fator de nebulosidade em `[0,15 ; 1,0]` | duas vias, abaixo |

**Via A — calibração por resíduo (modo `live`).** A carga noturna não contém
efeito solar. Ajusta-se um modelo de carga *ancorado na noite* (calendário +
Fourier + temperatura, treinado só com horas de `cos θz ≤ 0`), extrapola-se para
as horas diurnas e o **déficit diurno observado** é atribuído à geração
distribuída:

```
deficit(t) = carga_ancorada(t) − carga_verificada(t)
k_nuvem(t) = clip( deficit(t) / (C · PR · GHI_cs(t)/1000), 0.15, 1.0 )
```

Essa é a mesma lógica que o Operador descreve informalmente: a MMGD é o que
"falta" na carga em relação ao comportamento esperado de consumo. O protótipo a
torna explícita e auditável.

**Via B — proxy determinístico (modo `demo`).** Sem rede, `k_nuvem` vem de um
processo pseudoaleatório suavizado com semente fixa, dependente de dia e área.
Reprodutível e rotulado como demonstrativo.

### 6.1.3 Validações automatizadas

- MMGD estimada é exatamente zero quando `cos θz ≤ 0` (noite).
- Máximo diário ocorre em janela de ±90 min do meio-dia solar local.
- `0 ≤ MMGD_est ≤ C · PR`.
- Integral diária cresce de inverno para verão no hemisfério sul.

## 6.2 Decomposição da carga (`models/decomposition.py`)

```
carga_global(t) = carga_supervisionada(t) + mmgd_estimada(t)
```

Onde `carga_supervisionada` é `val_carga` do balanço de energia — exatamente a
grandeza que o ONS opera. A identidade é imposta por construção; o teste verifica
resíduo nulo (RF-10). Derivados publicados:

- `mmgd_share_peak` — participação máxima da MMGD na carga global no dia.
- `min_supervised` e `min_supervised_hour` — a "barriga".
- `ramp_mw_h` — maior rampa horária no intervalo, o "pescoço".

## 6.3 Engenharia de variáveis (`features/builder.py`)

| Grupo | Variáveis |
|---|---|
| Calendário | hora do dia, dia da semana, dia-tipo (útil/sábado/domingo-feriado), feriado nacional, véspera de feriado |
| Fourier | 4 harmônicos diários, 2 semanais, 2 anuais — capturam sazonalidade sem explodir a dimensão |
| Solar | `cos θz`, `GHI_cs`, MMGD estimada, indicador de janela solar |
| Clima | temperatura, ponto de orvalho e índice de desconforto térmico, com defasagens de 1 h, 3 h e 24 h e média móvel de 72 h (memória de onda de calor) |
| Defasagens | carga em `t−1`, `t−2`, `t−24`, `t−168`; média móvel de 24 h |
| Regime | margem de fontes controláveis, geração eólica, intercâmbio |

Feriados nacionais brasileiros são calculados, não tabelados: datas fixas mais as
móveis derivadas da Páscoa (algoritmo de Butcher/Meeus) — Carnaval, Sexta-feira
Santa e Corpus Christi.

## 6.4 Previsão quantílica com perda assimétrica (`models/quantile.py`)

### 6.4.1 Formulação

Regressão quantílica linear sobre a matriz de projeto, resolvida por minimização
da **perda pinball ponderada**:

```
L(β) = Σₜ wₜ · ρ_τ( yₜ − xₜᵀβ ),     ρ_τ(u) = u·τ        se u ≥ 0
                                              u·(τ − 1)   se u < 0
```

com `τ ∈ {0,10; 0,50; 0,90}`, resolvida por gradiente subdiferencial com
suavização de Huber em torno de zero (`scipy.optimize.minimize`, L-BFGS-B).
Regularização L2 leve para estabilidade numérica.

### 6.4.2 A assimetria por patamar

O peso `wₜ` não é uniforme. Ele depende do **patamar horário** e do **sinal do
erro**, refletindo o custo operativo real:

| Patamar | Horas | Subestimar custa | Superestimar custa | Peso relativo |
|---|---|---|---|---|
| Mínima diurna | 09–15 | pouco | **muito** (térmica caríssima ligada à toa, menos margem de absorção) | 1,0 / **2,2** |
| Rampa vespertina | 16–19 | **muito** | médio | **2,0** / 1,2 |
| Ponta noturna | 18–22 | **muito** (acionamento emergencial, risco de não atendimento) | médio | **2,8** / 1,0 |
| Demais | resto | 1,0 | 1,0 | 1,0 / 1,0 |

Implementação: o peso é aplicado dentro da pinball, o que preserva a
interpretação de quantil e ao mesmo tempo desloca o ajuste na direção
operacionalmente segura. Os pesos ficam em `config.py`, versionados, porque são
**premissa de negócio** e devem ser discutidos com a operação — não constante de
código.

O parâmetro `asymmetric=0` da API desliga os pesos, permitindo medir na tela o
efeito da assimetria. É o que transforma o argumento do deck em evidência.

### 6.4.3 Baselines obrigatórios (`models/baselines.py`)

| Baseline | Definição |
|---|---|
| Persistência | `ŷ(t+h) = y(t)` |
| Sazonal-ingênuo diário | `ŷ(t+h) = y(t+h−24h)` |
| Sazonal-ingênuo semanal | `ŷ(t+h) = y(t+h−168h)` |

Nenhum resultado de acurácia é publicado sem o *skill score* correspondente:
`skill = 1 − MAE_modelo / MAE_baseline`.

## 6.5 Classificador de risco de restrição (`models/risk.py`)

### 6.5.1 Rótulo

Extraído dos registros reais de constrained-off. Para área `a` e hora `t`:

```
corte_mw(a,t)      = Σ_usinas max(0, val_geracaoreferencia − val_geracao)
restricao(a,t)     = corte_mw(a,t) > limiar(a)
razao_dominante    = argmax_r  Σ corte_mw por cod_razaorestricao
```

O limiar é percentual da capacidade agregada da área, para não rotular ruído de
apuração como evento.

> **Limite conceitual declarado.** O rótulo reflete a **decisão operativa
> observada**, não o potencial físico de geração. O modelo aprende a decisão, não
> um contrafactual.

### 6.5.2 Modelo

Regressão logística regularizada (L2), ajustada por **IRLS** em `numpy`, sobre as
variáveis da seção 6.3 mais:

- razão entre geração renovável disponível e carga supervisionada prevista;
- margem de fontes controláveis até o mínimo técnico estimado;
- intercâmbio projetado (proxy dos limites de exportação NE e N/NE);
- histórico recente de restrição na mesma área (memória de 7 dias).

Duas saídas:

1. **Probabilidade** de ocorrência, calibrada por *isotonic-like binning* sobre
   o conjunto de validação.
2. **Potência esperada**: `E[corte] = P(restrição) · E[corte | restrição]`, com o
   segundo termo estimado por regressão quantílica (mediana) sobre os eventos.

### 6.5.3 Decomposição do motivo

`reason_weights` combina três evidências, normalizadas para somar 1,0:

- frequência histórica de cada `cod_razaorestricao` na área e no patamar;
- sinal energético corrente (excedente projetado versus margem controlável);
- sinal elétrico corrente (intercâmbio próximo do limite histórico da área).

Assim o alerta diz **por que** e não apenas **quanto** — requisito do painel
descrito nos slides 7 e 10.

### 6.5.4 Severidade

```
severidade = 0,45 · P(restrição) + 0,35 · norm(E[corte]) + 0,20 · criticidade(área)
```

`criticidade(área)` é premissa configurável: áreas com fronteira já sinalizada em
fluxo reverso recebem peso maior. Ordenação estável por `(severidade, área)`.

## 6.6 Triangulação de evidências (`triangulation/evidence.py`)

Três camadas independentes, com cadências diferentes:

| Camada | Fonte | Pergunta | Cadência | Limitação |
|---|---|---|---|---|
| 1 · Realidade física | satélite + visão computacional | o ativo existe e onde está? | mensal/trimestral | data de captura pode ter meses |
| 2 · Topologia | BDGD (ANEEL) | a que alimentador e transformador está conectado? | anual | heterogeneidade entre distribuidoras |
| 3 · Cadastro | Empreendimentos de GD (ANEEL) | foi homologado, e quando? | diária | não localiza a unidade na malha |

### Matriz de desempate

| | **Consta na ANEEL** | **Não consta** |
|---|---|---|
| **Detectado no satélite** | `confirmada`; se ausente na BDGD → **`lag_de_sistema`** (defasagem administrativa, **entra** no fator de correção) | **`nao_homologada`** — exceção escalada, **não entra** no fator de correção |
| **Não detectado** | `cadastro_sem_evidencia` — imagem defasada ou obra não concluída; revisar captura | `sem_evidencia` — nada a corrigir |

O valor não está em nenhuma camada isolada: sem o desempate diário, defasagem
administrativa e instalação irregular seriam tratadas como a mesma coisa, e o
fator de correção de capacidade — que alimenta o estimador de MMGD — sairia
enviesado.

### Fator de correção

```
C_corrigida(a) = C_declarada(a) + Σ capacidade(lag_de_sistema)
correction_factor(a) = C_corrigida(a) / C_declarada(a)
coverage(a) = unidades com as três camadas disponíveis / unidades totais
```

`nao_homologada` é reportada em separado, nunca somada silenciosamente.
