# 02 · Requisitos

Identificadores são estáveis e citados pelos testes automatizados
(`../02-PROTOTIPO/tests`) e pela matriz de rastreabilidade
(`09-rastreabilidade-deck.md`).

## 2.1 Requisitos funcionais

### Ingestão e catálogo

| ID | Requisito | Critério de aceite |
|---|---|---|
| **RF-01** | Consultar o catálogo do Portal de Dados Abertos do ONS via API CKAN, listando conjuntos e recursos com formato, nome e URL. | `GET /api/catalog` devolve ≥ 80 conjuntos quando há rede; devolve o catálogo curado em cache quando não há. |
| **RF-02** | Baixar recursos CSV de séries operativas com cache local, verificação de tamanho e registro de instante de extração. | Segunda chamada ao mesmo recurso não gera tráfego de rede e reporta `cache_hit=true`. |
| **RF-03** | Operar em **modo offline determinístico** quando a rede estiver indisponível, com dados demonstrativos claramente rotulados. | Com rede bloqueada, todos os painéis carregam e exibem o selo `DADOS DEMONSTRATIVOS`. |
| **RF-04** | Registrar proveniência de toda série: conjunto, recurso, URL, instante de extração, número de registros e defasagem declarada. | Toda resposta da API contém o objeto `provenance` não vazio. |

### Decomposição e estimativa

| ID | Requisito | Critério de aceite |
|---|---|---|
| **RF-10** | Calcular a decomposição `carga_global ≈ carga_supervisionada + mmgd_estimada` por subsistema e hora. | A identidade fecha com resíduo relativo < 1e-9 sobre a série reconstruída. |
| **RF-11** | Estimar a geração de MMGD a partir de geometria solar, modelo de céu claro, capacidade instalada por área e fator de nebulosidade. | MMGD estimada é zero à noite (zênite > 90°) e tem máximo na vizinhança do meio-dia solar local. |
| **RF-12** | Derivar perfis representativos de carga e MMGD por dia-tipo (útil, sábado, domingo/feriado) e por área. | Painel de perfis exibe 3 dias-tipo × 24 horas com contagem de amostras por célula. |

### Previsão

| ID | Requisito | Critério de aceite |
|---|---|---|
| **RF-20** | Prever carga supervisionada nos horizontes **30 min, 3 h e D+1**, com quantis P10/P50/P90. | `GET /api/forecast?horizon=...` devolve as três bandas e satisfaz P10 ≤ P50 ≤ P90 em todos os pontos. |
| **RF-21** | Aplicar **perda assimétrica por patamar horário**, penalizando mais a subestimação na ponta noturna e a superestimação na mínima diurna. | Os pesos por patamar são configuráveis e o teste de regressão verifica que o gradiente é assimétrico. |
| **RF-22** | Comparar o modelo contra baselines de **persistência** e **sazonal-ingênuo** por horizonte. | Painel de validação exibe *skill score* por horizonte; promoção do modelo exige skill > 0. |
| **RF-23** | Expor as variáveis mais influentes de cada previsão. | Resposta inclui `drivers` com peso relativo por grupo de variável. |

### Risco de curtailment

| ID | Requisito | Critério de aceite |
|---|---|---|
| **RF-30** | Treinar classificador de ocorrência de restrição a partir dos registros reais de constrained-off. | Modelo treina sobre ≥ 1 mês de dados reais e reporta ROC-AUC fora da amostra. |
| **RF-31** | Estimar, por área e janela, a **probabilidade** de restrição e a **potência esperada** de corte. | `GET /api/risk` devolve `probability ∈ [0,1]` e `expected_mw ≥ 0` por área e horizonte. |
| **RF-32** | Separar razão energética (ENE) das demais razões e declarar o motivo provável. | Resposta contém `reason` e `reason_weights` somando 1,0. |
| **RF-33** | Priorizar eventos por severidade, combinando probabilidade, potência e criticidade da área. | Lista de eventos ordenada de forma estável e reprodutível. |

### Triangulação de evidências

| ID | Requisito | Critério de aceite |
|---|---|---|
| **RF-40** | Cruzar três camadas — realidade física, topologia e cadastro — e classificar cada unidade. | As quatro células da matriz de desempate são cobertas por teste. |
| **RF-41** | Separar **defasagem de sistema** (homologada, ausente na topologia) de **instalação não homologada**. | Unidade detectada sem homologação não entra no fator de correção de capacidade. |
| **RF-42** | Produzir fator de correção de capacidade instalada por área, com cobertura reportada. | Fator devolvido com intervalo e com `coverage` por área. |

### Validação e interface

| ID | Requisito | Critério de aceite |
|---|---|---|
| **RF-50** | Executar backtest com **corte cronológico**, nunca aleatório. | Teste verifica que nenhum índice de treino é posterior a qualquer índice de teste. |
| **RF-51** | Calcular MAE, RMSE, MAPE, *pinball loss*, erro de rampa e erro por patamar. | Painel de validação exibe as métricas por horizonte e por patamar. |
| **RF-52** | Avaliar calibração probabilística (cobertura empírica dos quantis). | Diagrama de confiabilidade com cobertura observada versus nominal. |
| **RF-53** | Oferecer interface web com navegação entre sete painéis, sem dependência de CDN. | Aplicação carrega e opera com a rede externa bloqueada. |
| **RF-54** | Permitir explorar o catálogo de dados abertos e inspecionar recursos e dicionários. | Painel de dados lista conjuntos, recursos e estado do cache. |

## 2.2 Requisitos não funcionais

| ID | Requisito | Critério de aceite |
|---|---|---|
| **RNF-01** | **Cadência operativa** compatível com o processo do ONS: atualização a cada 30 min. | Pipeline de previsão completo executa em < 10 s sobre um ano de dados horários. |
| **RNF-02** | **Reprodutibilidade**: mesma entrada produz a mesma saída. | Semente fixa; teste de determinismo compara duas execuções. |
| **RNF-03** | **Zero dependência de instalação externa** além da biblioteca padrão, `numpy`, `scipy` e servidor ASGI. | `pip install` não é necessário no ambiente-alvo; ver `../02-PROTOTIPO/README.md`. |
| **RNF-04** | **Rastreabilidade obrigatória**: nenhuma resposta sem proveniência. | Teste de contrato falha se `provenance` estiver ausente em qualquer rota. |
| **RNF-05** | **Degradação graciosa**: falha de rede não derruba a aplicação. | Simulação de falha de rede mantém a API em 200 com `mode="demo"`. |
| **RNF-06** | **Cobertura de testes** das regras de negócio críticas. | Suíte `pytest` verde, cobrindo ingestão, modelos, métricas, triangulação e API. |
| **RNF-07** | **Acessibilidade e legibilidade** da interface em tema claro e escuro, responsiva a partir de 1024 px. | Inspeção visual dos sete painéis nos dois temas. |
| **RNF-08** | **Honestidade de rótulo**: valores demonstrativos sempre identificados. | Selo visível em todo painel alimentado por dados sintéticos. |

## 2.3 Fora de requisito, por decisão

- Autenticação e perfis de usuário: o protótipo é monousuário e local.
- Persistência transacional: o estado é cache de arquivos versionado por hash.
- Alta disponibilidade e escala horizontal: fora do horizonte do Ideathon.
