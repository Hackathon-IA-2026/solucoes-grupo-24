# 03 · Arquitetura

## 3.1 Visão em camadas

```
┌──────────────────────────────────────────────────────────────────────────┐
│  APRESENTAÇÃO — web/ (HTML + CSS + JS sem dependência externa)           │
│  7 painéis: Operação · Excedentes · Curtailment · Perfis/CLM ·           │
│             Triangulação · Validação · Dados Abertos                     │
└───────────────────────────────▲──────────────────────────────────────────┘
                                │ JSON com envelope de proveniência
┌───────────────────────────────┴──────────────────────────────────────────┐
│  SERVIÇO — oraculo/api (ASGI/Starlette)                                  │
│  /api/health /catalog /series /decomposition /forecast /risk             │
│  /profiles /triangulation /validation /provenance                        │
└───────────────────────────────▲──────────────────────────────────────────┘
                                │
┌───────────────────────────────┴──────────────────────────────────────────┐
│  DOMÍNIO                                                                 │
│                                                                          │
│  pipeline/      orquestra ingest → features → train → forecast           │
│  models/        mmgd · decomposition · baselines · quantile · risk       │
│  features/      calendário, Fourier, clima, patamares, defasagens        │
│  validation/    backtest cronológico · métricas · calibração             │
│  triangulation/ três camadas de evidência · matriz de desempate          │
└───────────────────────────────▲──────────────────────────────────────────┘
                                │
┌───────────────────────────────┴──────────────────────────────────────────┐
│  DADOS                                                                   │
│  ons/ckan.py     cliente da API CKAN do Portal de Dados Abertos          │
│  ons/catalog.py  registro curado dos conjuntos usados                    │
│  ons/csvio.py    leitor CSV em fluxo, com tipagem e tolerância a nulos    │
│  ons/cache.py    cache em disco com TTL, hash e manifesto de proveniência │
│  demo/synthetic  gerador determinístico para modo offline                 │
│  core/frame.py   tabela colunar mínima sobre numpy (substitui pandas)     │
└──────────────────────────────────────────────────────────────────────────┘
```

## 3.2 Fluxo de dados

```
Portal de Dados Abertos do ONS (CKAN + S3)
   │  BALANCO_ENERGIA_SUBSISTEMA_<ano>.csv      (horário, por subsistema)
   │  CURVA_CARGA_<ano>.csv                     (horário, por subsistema)
   │  RESTRICAO_COFF_FOTOVOLTAICA_<ano>_<mês>.csv   (semi-horário, por usina)
   │  RESTRICAO_COFF_EOLICA_<ano>_<mês>.csv         (semi-horário, por usina)
   ▼
[ingest] cache em disco + manifesto de proveniência
   ▼
[core.Frame] tabela colunar tipada
   ▼
[models.mmgd] geometria solar → céu claro → capacidade × PR × nebulosidade
   ▼
[models.decomposition] carga_global = carga_supervisionada + mmgd_estimada
   ▼
[features.builder] calendário · Fourier (dia/semana/ano) · clima · defasagens
   │
   ├─► [models.quantile] previsão P10/P50/P90 ─────────► PRODUTO 1
   │        ▲ perda assimétrica por patamar
   │        └── [models.baselines] persistência, sazonal-ingênuo
   │
   └─► [models.risk] classificador de restrição ───────► PRODUTO 2
            ▲ rótulo extraído dos registros de constrained-off
            └── razão ENE separada das demais

[validation.backtest] corte cronológico → métricas → skill vs. baselines
[triangulation.evidence] física + topologia + cadastro → fator de correção
```

## 3.3 Decisões de engenharia e seus porquês

| # | Decisão | Por que | Custo aceito |
|---|---|---|---|
| D1 | **Sem `pandas`**: tabela colunar própria (`core/frame.py`) sobre `numpy`. | O ambiente-alvo tem proxy corporativo com certificado próprio, o que bloqueia `pip install`. A solução precisa rodar onde o problema existe. | Reimplementar filtro, ordenação, agrupamento e junção. Escopo contido: ~300 linhas testadas. |
| D2 | **Sem `scikit-learn`**: modelos em `numpy`/`scipy`. | Mesma razão de D1. Além disso, a **perda assimétrica por patamar** é o diferencial declarado no deck e não existe pronta em biblioteca. | Implementar regressão quantílica e regressão logística. Ganho: controle total da função de perda. |
| D3 | **Sem CDN no front-end**: gráficos em SVG gerados em JavaScript puro. | Garante que a interface funcione em rede restrita e em apresentação offline. | Escrever os primitivos de gráfico (eixos, áreas, bandas, mapa de calor, mapa esquemático). |
| D4 | **Starlette em vez de FastAPI.** | Starlette está disponível no ambiente; FastAPI não. O contrato é validado por `pydantic`, que está disponível. | Rotas declaradas manualmente, sem geração automática de OpenAPI. O contrato está em `05-api.md`. |
| D5 | **Estimar MMGD em vez de consumir série publicada.** | A MMGD estimada pelo ONS não está publicada como série horária por área no Portal. Estimá-la **é** o produto. | O estimador precisa ser fisicamente defensável e calibrável — ver `06-modelos-analiticos.md`. |
| D6 | **Cache em disco com manifesto.** | Ingestão idempotente, reexecução rápida e proveniência auditável. Atende RNF-04. | Um diretório `.cache/` versionado por hash de URL. |
| D7 | **Modo `live` / `demo` explícito.** | O deck rotula as telas como demonstrativas. Confundir dado real com sintético seria o pior defeito possível numa banca do setor. | Toda resposta declara `mode`; a interface exibe selo correspondente. |
| D8 | **Requisições HTTP com `Range`.** | Os recursos mensais de constrained-off chegam a 15 MB. Ler apenas o necessário mantém a ingestão em segundos. | Leitor precisa lidar com linha parcial no limite do intervalo. |

## 3.4 Estrutura de diretórios do protótipo

```
02-PROTOTIPO/
├── README.md                    como executar, o que esperar, limitações
├── requirements.txt             dependências (todas já presentes no ambiente)
├── pytest.ini
├── run_api.py                   sobe o serviço
├── run_pipeline.py              executa ingestão + treino + backtest em lote
├── oraculo/
│   ├── config.py                caminhos, áreas, capacidades, pesos de patamar
│   ├── core/
│   │   ├── frame.py             Frame colunar (D1)
│   │   ├── timeutils.py         parsing e grade temporal
│   │   └── calendar_br.py       feriados nacionais e dia-tipo
│   ├── ons/
│   │   ├── ckan.py              cliente CKAN
│   │   ├── catalog.py           conjuntos curados + metadados
│   │   ├── csvio.py             leitor CSV em fluxo
│   │   └── cache.py             cache + manifesto de proveniência
│   ├── demo/synthetic.py        gerador determinístico (RF-03)
│   ├── models/
│   │   ├── solar.py             geometria solar e céu claro
│   │   ├── mmgd.py              estimador de MMGD
│   │   ├── decomposition.py     identidade de carga
│   │   ├── baselines.py         persistência e sazonal-ingênuo
│   │   ├── quantile.py          regressão quantílica + perda assimétrica
│   │   └── risk.py              classificador de restrição
│   ├── features/builder.py      matriz de projeto
│   ├── validation/
│   │   ├── backtest.py          corte cronológico
│   │   └── metrics.py           MAE/RMSE/MAPE/pinball/rampa/calibração
│   ├── triangulation/evidence.py    três camadas + desempate
│   └── api/
│       ├── app.py               aplicação ASGI e rotas
│       ├── envelope.py          envelope de proveniência (RNF-04)
│       └── service.py           fachada de domínio usada pelas rotas
├── web/
│   ├── index.html               casca da aplicação
│   ├── css/oraculo.css          tema claro e escuro
│   └── js/                      router, camada de dados, gráficos, 7 painéis
└── tests/                       suíte pytest
```

## 3.5 Contratos entre camadas

- **Dados → Domínio**: `Frame` com colunas tipadas e um objeto `Provenance`
  imutável. Nenhum módulo de domínio conhece HTTP, CSV ou cache.
- **Domínio → Serviço**: funções puras que recebem `Frame` e devolvem estruturas
  serializáveis. Nenhum módulo de domínio importa `starlette`.
- **Serviço → Apresentação**: JSON envelopado (ver `05-api.md`). A interface não
  faz cálculo analítico; apenas apresenta e navega.

Essa separação é o que permite testar modelos sem subir servidor e testar rotas
sem rede.
