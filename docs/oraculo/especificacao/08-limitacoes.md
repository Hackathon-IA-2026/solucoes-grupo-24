# 08 · Limitações e riscos

> Declarar limitação é critério de avaliação, não fraqueza da proposta.

## 8.1 Limites de escopo, assumidos desde o início

| # | Limite | Consequência prática |
|---|---|---|
| L1 | **Não há modelo elétrico da rede.** | A solução não executa fluxo de potência, análise de estabilidade ou controle de tensão. Entrega insumos para quem realiza esses estudos. |
| L2 | **Não substitui o PREVCARGA nem o PREVCARGA PMO.** | Posiciona-se como camada complementar de granularidade espacial na fronteira T–D. |
| L3 | **Não automatiza despacho nem comando de restrição.** | Apoia a decisão humana; `recommended_actions` é sugestão, não instrução. |
| L4 | **A previsão não elimina o corte.** | O valor está na antecipação e na alocação de flexibilidade. O próprio ONS conclui que a solução exige medidas integradas. |
| L5 | **O rótulo de curtailment é a decisão observada.** | Modela-se a decisão operativa registrada, não um contrafactual físico de geração possível. |

## 8.2 Limitações de dados

| # | Limitação | Mitigação implementada |
|---|---|---|
| D1 | **MMGD não é publicada como série horária por área.** | Estimador físico com calibração por resíduo noturno (`06-modelos-analiticos.md`, §6.1). A grandeza é rotulada `mmgd_estimada`, nunca `mmgd_medida`. |
| D2 | **BDGD é anual e heterogênea entre distribuidoras.** | Triangulação com cadastro diário da ANEEL; cobertura reportada por área; contrato pronto para a base real. |
| D3 | **Satélite é periódico, não tempo real.** | A camada física entra como evidência datada; a atualização contínua vem das camadas cadastrais. |
| D4 | **ERA5 é reanálise, não previsão.** | Uso restrito a treino e backtest. Em produção, covariáveis futuras vêm de ECMWF, GFS, WRF e INMET. O viés de *perfect-prog* está declarado e não medido. |
| D5 | **`id_ons` não é identificador único global entre fontes.** | Chave composta `(fonte, id_ons)` na ingestão. |
| D6 | **Subsistemas não coincidem com áreas operativas.** | Os dois recortes nunca são cruzados diretamente; a chave de área é campo livre. |
| D7 | **Nulos frequentes nos campos de caracterização da restrição.** | Campo vazio vira `NaN`, nunca zero; contagem de descarte visível no painel de dados. |
| D8 | **Volume dos recursos mensais de constrained-off (≈15 MB).** | Requisições HTTP com `Range` e cache em disco por hash. |

## 8.3 Riscos do projeto

| # | Risco | Probabilidade | Impacto | Mitigação |
|---|---|---|---|---|
| R1 | Estimativa de MMGD sem verdade fundamental disponível | alta | alto | validação por consistência física e por resíduo; declarar a incerteza na banda, não esconder |
| R2 | Rede corporativa bloqueia dependências e fontes externas | **materializou-se** | médio | zero dependência fora do ambiente; modo `demo` determinístico; a API do ONS foi verificada como acessível |
| R3 | Sobreposição com modelos já maduros do ONS | média | médio | posicionamento explícito como camada complementar (L2) |
| R4 | Banca com especialistas do setor identificar imprecisão terminológica | média | alto | glossário do deck aplicado no código e na interface: carga global, carga supervisionada, MMGD, Tipo III, REL/CNF/ENE, LOC/SIS |
| R5 | Janela curta de desenvolvimento | alta | médio | fatiamento em MVP, cada fatia demonstrável isoladamente (`10-roadmap.md`) |
| R6 | Confundir dado real com demonstrativo na apresentação | média | **alto** | campo `mode` em toda resposta e selo permanente na interface |

## 8.4 O que responder se perguntarem

**"Cadê o fluxo de potência?"** — Não há, por decisão. A solução é camada de
observabilidade e inteligência preditiva da fronteira T–D; o fluxo de potência é
feito pelos modelos oficiais, que passam a receber insumos melhores.

**"Isso não é o que o PREVCARGA já faz?"** — O PREVCARGA prevê carga global e
abate a MMGD estimada. Atacamos as três lacunas que o próprio Operador declara:
defasagem do cadastro de GD, granularidade espacial da estimativa e função de
erro inadequada ao custo operativo.

**"Como vocês sabem que a MMGD estimada está certa?"** — Não sabemos o erro
absoluto, e dizemos isso. Sabemos que a estimativa é fisicamente consistente
(zero à noite, máximo no meio-dia solar, limitada pela capacidade instalada) e
que o resíduo diurno da carga ancorada na noite é a assinatura que o próprio ONS
descreve. A banda probabilística comunica a incerteza.

**"E se a previsão errar?"** — A perda assimétrica por patamar existe justamente
porque errar não é simétrico. Penalizamos mais a subestimação na ponta noturna e
a superestimação na mínima diurna, e mostramos na tela o efeito de ligar e
desligar essa assimetria.
