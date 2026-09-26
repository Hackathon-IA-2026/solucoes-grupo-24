# 07 · Validação

> Princípio: nenhuma promessa de desempenho sem teste.

## 7.1 Separação de amostras

**Corte estritamente cronológico.** Treino até uma data de corte, teste no
período posterior. Divisão aleatória é proibida: as variáveis de defasagem
(`y(t−1)`, `y(t−24)`) vazariam informação do futuro para o treino, inflando
artificialmente a acurácia.

```
|<--------------- treino (70%) --------------->|<---- teste (30%) ---->|
                                              corte
```

Verificação automatizada (`tests/test_backtest.py`): `max(idx_treino) <
min(idx_teste)`. Falha o teste se qualquer índice violar a ordem.

Para os horizontes de 30 min e 3 h, o alvo é deslocado antes do corte, garantindo
que nenhum ponto de teste tenha sido visto como alvo no treino.

## 7.2 Três regimes de avaliação, não confundidos

O deck distingue explicitamente, e a implementação respeita:

| Regime | O que é | Como é avaliado |
|---|---|---|
| **Projeção de tendência** | trajetória estrutural plurianual (MMGD instalada, participação da GD) | cenários declarados, com premissa explícita; não recebe métrica de acurácia |
| **Previsão operacional** | carga supervisionada e risco em 30 min / 3 h / D+1 | backtest fora da amostra contra baselines |
| **Avaliação fora da amostra** | desempenho medido no período de teste | métricas da seção 7.4 |

Misturar os três é o erro clássico que transforma um cenário em falsa promessa de
acurácia.

## 7.3 Baselines obrigatórios

| Baseline | Papel |
|---|---|
| Persistência | piso de referência para horizontes curtos |
| Sazonal-ingênuo diário (`t−24 h`) | piso de referência para o perfil diário |
| Sazonal-ingênuo semanal (`t−168 h`) | piso de referência para o efeito de dia da semana |

O modelo só é considerado útil onde `skill = 1 − MAE_modelo/MAE_baseline > 0`.
O painel de validação mostra o skill por horizonte; um skill negativo aparece em
vermelho e não é escondido.

## 7.4 Métricas

### Ponto (mediana P50)

| Métrica | Por que |
|---|---|
| MAE (MW) | erro médio em unidade operacional |
| RMSE (MW) | penaliza erro grande, que é o que dói |
| MAPE (%) | comparabilidade entre áreas de porte diferente |
| Erro de rampa (MW/h) | a rampa vespertina é o que exige recurso; erra-la é diferente de errar o nível |
| Erro no vale e no pico | o instante e o valor dos extremos são o que a operação usa |

### Probabilística

| Métrica | Por que |
|---|---|
| *Pinball loss* por quantil | função de perda coerente com a saída quantílica |
| Cobertura empírica | um P90 que cobre 60% dos casos não é um P90 |
| Largura média da banda | uma banda larguíssima "acerta" sempre e não informa nada |

### Por patamar (RF-51)

Todas as métricas de ponto são reportadas também para **mínima diurna (09–15h)**,
**rampa (16–19h)** e **ponta noturna (18–22h)**, porque é ali que a assimetria de
custo se manifesta. Uma melhoria de MAE global que piora a ponta noturna é uma
piora operacional, e o painel deixa isso visível.

### Risco de curtailment

| Métrica | Por que |
|---|---|
| ROC-AUC | discriminação entre horas com e sem restrição |
| Precisão / revocação por razão | um alerta de ENE e um de CNF pedem ações diferentes |
| Erro no montante cortado (MWmed) | quanto, não só se |
| *Lead time* útil | com quanta antecedência o alerta seria acionável |

## 7.5 Calibração probabilística

Diagrama de confiabilidade: para cada quantil nominal `τ`, a fração observada de
`y ≤ ŷ_τ` no conjunto de teste. Reportado na rota `/api/validation` e plotado no
painel. Desvio sistemático indica que a banda comunica uma confiança que o modelo
não tem — defeito mais grave que um MAE alto, porque engana a decisão.

## 7.6 Determinismo e reprodutibilidade

- Semente fixa em todo componente estocástico.
- `tests/test_determinism.py` executa o pipeline duas vezes e compara os arrays.
- O manifesto de proveniência registra o hash do recurso usado, permitindo
  reproduzir a execução exata.

## 7.7 O que o protótipo ainda não valida

Declarado sem rodeio:

1. **Desempenho com previsão meteorológica real.** O protótipo usa proxy
   determinístico de nebulosidade. O viés de *perfect-prog* — treinar com
   condição reconstruída e operar com previsão — não está medido.
2. **Estimativa de MMGD contra medição.** Não existe série pública de MMGD
   horária por área para servir de verdade fundamental. A validação hoje é de
   consistência física e de plausibilidade do resíduo, não de erro absoluto.
3. **Granularidade de área de concessão.** Requer BDGD. O protótipo valida no
   recorte de subsistema e de estado.
4. **Camada de satélite.** A lógica de triangulação é testada; a acurácia da
   detecção por visão computacional não, porque depende de aquisição de imagem.
