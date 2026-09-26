# O.R.A.C.U.L.O. — protótipo funcional

Camada de observabilidade e inteligência preditiva da fronteira
transmissão–distribuição.

**Equipe 24 — LINKFY** · Hackathon IA COPPE/UFRJ 2026

Especificação em [`../01-ESPECIFICACAO`](../01-ESPECIFICACAO).
Documentação da aplicação, com uma página por painel, em
[`../03-DOCUMENTACAO`](../03-DOCUMENTACAO) — construa com
`python build_docs.py --open`.

---

## Como executar

```bash
cd 02-PROTOTIPO

python run_api.py --open          # sobe o serviço e abre o navegador
python run_api.py --port 9000     # porta alternativa
```

A interface fica em <http://127.0.0.1:8000/>.

### Ajuda contextual

Em qualquer painel, **`F1`** abre a página da documentação correspondente
àquele painel, dentro da própria aplicação. `Esc` fecha, e o botão `?` na
barra superior faz o mesmo.

A documentação é gerada sob demanda:

```bash
cd ../03-DOCUMENTACAO && python build_docs.py
```

Sem ela, `F1` não abre um quadro em branco: mostra o comando que a produz. O
mapeamento painel → página vive em `oraculo/api/service_docs.py`, e há teste
que exige que **todo** painel tenha página — painel novo sem ajuda reprova a
suíte.

### Execução em lote, sem interface

```bash
python run_pipeline.py --area SE      # relatório completo no terminal
python run_pipeline.py --demo         # força o modo demonstrativo
python run_pipeline.py --json         # imprime os payloads brutos
```

### Testes

```bash
python -m pytest                  # 522 testes
python -m pytest -m network       # inclui o teste que fala com o Portal do ONS
```

### Modo demonstrativo

```bash
ORACULO_OFFLINE=1 python run_api.py
```

Todos os painéis carregam com dados sintéticos determinísticos, rotulados com o
selo `DADOS DEMONSTRATIVOS`. Útil para apresentar sem rede.

---

## Dependências

Nenhuma instalação é necessária no ambiente-alvo: o protótipo usa apenas
`numpy`, `scipy`, `starlette`, `uvicorn`, `httpx`, `pydantic` e `pytest`, todos
já presentes.

**Por que não `pandas`, `scikit-learn` ou nenhuma biblioteca de gráficos.** A
rede corporativa tem proxy com certificado próprio, o que bloqueia o PyPI
(`CERTIFICATE_VERIFY_FAILED`). A solução precisa rodar onde o problema existe.
Consequências deliberadas:

| Em vez de | Usamos | Onde |
|---|---|---|
| `pandas` | tabela colunar própria sobre `numpy` | `oraculo/core/frame.py` |
| `scikit-learn` | regressão quantílica e logística em `numpy`/`scipy` | `oraculo/models/` |
| biblioteca de gráficos | primitivos SVG em JavaScript puro | `web/js/charts.js` |
| `fastapi` | `starlette` (mesma base ASGI) | `oraculo/api/app.py` |

Ganho colateral: a **perda assimétrica por patamar** — o diferencial declarado
no deck — não existe pronta em biblioteca alguma. Escrevê-la foi necessário de
todo modo.

---

## Dados: reais, do Portal do ONS

O protótipo consome o **Portal de Dados Abertos do ONS** pela API CKAN e pelos
recursos CSV em S3. Esquemas verificados por inspeção direta.

| Conjunto | Granularidade | Uso |
|---|---|---|
| `balanco-energia-subsistema` | horária, por subsistema | carga verificada e geração por fonte — espinha dorsal |
| `curva-carga` | horária, por subsistema | conferência cruzada da carga |
| `restricao_coff_fotovoltaica` | semi-horária, por usina | rótulo do risco de curtailment |
| `restricao_coff_eolica_usi` | semi-horária, por usina | rótulo, fonte eólica |
| `subestacao` | cadastral, por subestação | **subestações georreferenciadas** — entrada do Mapa Inteligente |
| `capacidade-transformacao` | cadastral, por transformador | dimensiona a área de influência e identifica a fronteira T–D |
| `modalidade-usina` | cadastral, por usina | usinas Tipo III conectadas à distribuição |

Os 85 conjuntos do Portal são navegáveis no painel **Dados abertos**, com
dicionários, recursos por ano/mês e estado do cache.

**Cache e proveniência.** Todo recurso baixado entra em `.cache/` com hash
SHA-256, tamanho e instante de extração, registrados em `manifest.json`. Toda
resposta da API carrega o envelope `provenance` — a rota `/api/provenance` é a
auditoria completa.

**Degradação graciosa.** Sem rede, a ingestão cai para o cache; sem cache, para
o gerador determinístico. A aplicação nunca fica fora do ar, e o campo `mode`
(`live` / `cache` / `demo`) declara em toda resposta de onde veio o número.

---

## O que o protótipo faz

### Estima a MMGD, que não é publicada

A micro e minigeração distribuída não existe como série horária por área no
Portal: aparece apenas como redução da carga verificada. O estimador combina
geometria solar (declinação e equação do tempo de Spencer, céu claro de
Haurwitz), a capacidade instalada declarada e um fator de nebulosidade obtido
pelo **método do envelope** — o percentil 90 da carga em horas comparáveis do
mês aproxima a carga global, porque o dia de maior carga observada é o dia de
menor geração distribuída.

> **Viés declarado:** mesmo os dias de maior carga contêm alguma geração
> distribuída. A estimativa é **conservadora — um piso, não um valor central**.

### Decompõe a carga

`carga_global = carga_supervisionada + mmgd_estimada`, com a identidade
verificada por teste (resíduo nulo). Derivados publicados: participação máxima
da MMGD, mínima supervisionada e sua hora, amplitude diária, maior rampa.

### Prevê com perda assimétrica por patamar

Regressão quantílica (P10/P50/P90) nos horizontes de **30 min, 3 h e D+1**, com
pesos diferentes para subestimação e superestimação em cada patamar operativo:

| Patamar | Subestimar | Superestimar |
|---|---|---|
| Mínima diurna (09–15h) | 1,0 | **2,2** |
| Rampa (16–19h) | **2,0** | 1,2 |
| Ponta noturna (18–22h) | **2,8** | 1,0 |

O parâmetro `asymmetric=0` da API desliga os pesos, e o painel de validação
mostra o efeito no mesmo conjunto de teste. É o que transforma o argumento em
evidência.

### Classifica o risco de curtailment por razão

Regressão logística regularizada sobre os registros reais de constrained-off,
com probabilidade calibrada, montante esperado `E[corte] = P × mediana
condicional`, decomposição do motivo (ENE / CNF / REL / PAR) e severidade que
pondera probabilidade, potência e criticidade da área.

Duas decisões que mudam o resultado, ambas documentadas no código:

1. **Sem vazamento.** Não se usa defasagem de 1 h do próprio rótulo como
   variável. A memória operativa legítima é o histórico de restrição defasado em
   24 h ou mais — o que o operador de fato conhece ao prever D+1.
2. **Só na janela solar.** Fora dela, a resposta é trivialmente "não", e incluir
   essas horas infla o AUC sem informar nada.

### Triangula três evidências

| Camada | Fonte | Pergunta | Cadência |
|---|---|---|---|
| 1 · Realidade física | satélite + visão computacional | o ativo existe e onde está? | mensal / trimestral |
| 2 · Topologia | BDGD (ANEEL) | a que alimentador está conectado? | anual |
| 3 · Cadastro | Empreendimentos de GD (ANEEL) | foi homologado, e quando? | diária |

A matriz de desempate separa **defasagem de sistema** (homologada, ausente na
BDGD — entra no fator de correção) de **instalação não homologada** (presente e
gerando sem registro — escalada como exceção, nunca somada silenciosamente).

### Valida sem esconder nada

Backtest com **corte estritamente cronológico**, verificado por teste; baselines
obrigatórios (persistência, sazonal-ingênuo diário e semanal); métricas por
patamar; calibração probabilística. Um *skill* negativo aparece em vermelho no
painel.

---

## Interface

Dezessete painéis, sem dependência de CDN, em tema claro e escuro:

| Painel | Conteúdo |
|---|---|
| **Despacho preditivo** | decomposição da carga, previsão com banda P10/P90, erro por patamar, peso por grupo de variável |
| **Curva do pato · tempo** | radiação e temperatura previstas por modelos de IA (ECMWF AIFS) e físicos (IFS, GFS) × MMGD por célula → carga supervisionada dos próximos 7 dias, com faixa entre modelos e backtest com previsões arquivadas |
| **Risco e excedentes** | mapa esquemático por UF, eventos priorizados por severidade, alerta rastreável com evidências e ações recomendadas |
| **Curtailment** | montante por área e razão, probabilidade horária, histórico e códigos do ONS |
| **Perfis e CLM** | perfis por dia-tipo com quantis, perfil de MMGD, insumos agregados propostos |
| **Triangulação** | matriz de desempate, três camadas, fator de correção por área, amostra classificada |
| **Validação** | corte cronológico, desempenho por horizonte, calibração, efeito da assimetria, baselines |
| **Dados abertos** | catálogo do ONS, conjuntos curados, relatório de ingestão, manifesto de cache |
| **Perfis por subestação** | Mapa Inteligente: lista de subestações de fronteira, classe de consumo com percentual, indicador de MMGD, ortoimagem com as detecções, insumo ao CLM |
| **Visão computacional** | backends de detecção, banco de ensaio por classe urbana, curva precisão × revocação, canais de característica, calibração de área |
| **Classes de consumo** | perfis canônicos, decomposição da curva real por subsistema (NNLS), qualidade do ajuste |
| **SE × distribuição** | Fronteira T–D: cada subestação de distribuição da BDGD associada à SE de fronteira do ONS, mapa, carga por classe medida e rateada, MMGD, comparação com o Mapa Inteligente, envio ao cartão CLM |
| **Qualidade da correlação** | validação externa contra a carga do ONS, carregamento implícito, varredura de sensibilidade α × λ, privacidade e limites |
| **Alocação de BESS** | ranking de SEs de conexão das usinas centralizadas para armazenamento: 12 meses de corte FV + eólico, BESS simulado e dimensionado pelo ciclo marginal, corte induzido pela MMGD, curva do pato por subsistema, pesos ajustáveis |
| **Projeção do corte ENE** | histórico do corte por razão energética desde 10/2021, modelo físico da carga líquida com backtest fora da amostra, cenários 2027–2030 com efeito da MMGD isolado, potencial técnico de BESS no SIN |
| **Método e sensibilidade** | cobertura da localização, razão e origem do corte, estabilidade do top 10 sob outros pesos, limites |
| **Parametrização CLM** | Modelo de Carga Composta: topologia, registro de 124 parâmetros com procedência campo a campo, curvas do modelo, exemplo publicado do WECC reproduzido |

Todos com **ajuda contextual em `F1`**.

---

## Estrutura

```
02-PROTOTIPO/
├── run_api.py                serviço HTTP + interface
├── run_pipeline.py           execução em lote com relatório
├── oraculo/
│   ├── config.py             premissas de negócio, versionadas
│   ├── core/                 Frame colunar, tempo, calendário brasileiro
│   ├── ons/                  CKAN, catálogo, leitor CSV, cache
│   ├── demo/                 gerador determinístico (modo offline)
│   ├── models/               solar, MMGD, decomposição, baselines, quantil, risco
│   ├── features/             matriz de projeto
│   ├── validation/           backtest cronológico e métricas
│   ├── triangulation/        três camadas e desempate
│   ├── vision/               ladrilhos, NMS, detectores, avaliação, render PNG
│   ├── profiles/             classes de consumo: perfis canônicos e NNLS
│   ├── substations/          registro georreferenciado e Mapa Inteligente
│   ├── clm/                  Modelo de Carga Composta: equações e parametrização
│   ├── fronteira/            SED (ANEEL) × SE de fronteira (ONS): fontes, correlação
│   ├── bess/                 constrained-off por SE, simulação e alocação de BESS
│   ├── pipeline/             ingestão
│   └── api/                  aplicação ASGI, envelope, fachada de domínio
├── web/                      interface (HTML, CSS, JS sem dependência)
└── tests/                    522 testes
```

Separação mantida por disciplina: nenhum módulo de domínio importa `starlette`,
e nenhuma rota faz cálculo analítico. É o que permite testar modelos sem subir
servidor e testar rotas sem rede.

---

## Mapa Inteligente de Perfis de Carga e Geração Distribuída

Desafio **Radix + AXIA + Cepel**. Especificação completa em
[`../01-ESPECIFICACAO/11-desafio-radix-mapa-inteligente.md`](../01-ESPECIFICACAO/11-desafio-radix-mapa-inteligente.md).

**Entrada real.** O ONS publica subestações georreferenciadas no conjunto
`subestacao`: 1.689 registros, **909 subestações únicas em 27 UF**, das quais
**522 têm transformação de fronteira com a distribuição** (secundário ≤ 138 kV,
identificado em `capacidade-transformacao`).

**Saída, por subestação.** As duas perguntas do enunciado:

1. **Perfil predominante de consumo**, com percentual por classe — morfologia
   construída da amostra (75%) combinada com a decomposição da curva de carga
   verificada do subsistema por mínimos quadrados não negativos (25%, como
   *prior* regional).
2. **Indicador de penetração de MMGD** em três níveis — kWp/km² medido por
   visão computacional sobre ortoimagem.

Mais o insumo proposto ao **Modelo de Carga Composta**, para parametrização
no **ORGANON**: composição por
classe, fração de motor estimada, sinalização de GD e confiança.

### Visão computacional: o que roda e o que não roda

| Backend | Estado |
|---|---|
| **Detector clássico** — índice espectral + textura + forma, em `scipy.ndimage` | **ativo** |
| **YOLOv8-seg** — pipeline completo: letterbox e inversa, decodificação, NMS, máscara por protótipos, transformação de coordenadas | implementado e testado, **sem runtime** |

> **Sobre o YOLO, sem rodeio:** `torch`, `onnxruntime` e `ultralytics` **não
> podem ser instalados aqui** — o proxy corporativo bloqueia o PyPI com
> certificado próprio. O adaptador detecta a ausência do runtime, **declara isso
> na API e na tela**, e cede o lugar ao detector clássico. Trocar o backend é uma
> linha: ladrilhamento, NMS, deduplicação na costura entre ladrilhos e
> georreferência são compartilhados e testados.

### Desempenho do detector, medido contra verdade fundamental

4 classes urbanas × 3 sementes = 12 cenas com verdade conhecida:

| Métrica | Valor |
|---|---|
| Precisão | **0,982** |
| Revocação | **0,997** |
| F1 | **0,988** |
| IoU de máscara | 0,876 |
| *Average precision* | 0,730 |
| Erro de área, calibrado | **+0,7%** |
| Erro de área, bruto | −15,4% |

A calibração de área (1,19×) é **medida**, não arbitrada: a borda do painel é um
gradiente e qualquer limiar corta parte dela, gerando viés sistemático de ~16%
consistente entre classes urbanas. O valor bruto fica na API para auditoria.

### Três decisões que mudaram o resultado

1. **A ortoimagem é sintética, com verdade fundamental conhecida.** O detector é
   o mesmo que roda em imagem real; as métricas são medições reais dele. Em
   imagem real, esperar degradação. Está rotulado na tela.
2. **Amostragem, não cobertura total.** Ortoimagem de 30 cm sobre 113 km² por
   subestação é inviável. A detecção roda em 2 janelas de 230 m a 0,30 m/pixel e
   a densidade é extrapolada aplicando a fração construída da morfologia. O
   **nível** usa a densidade medida, sem extrapolação.
3. **O prior regional não é uma segunda medida.** Comparar a curva agregada do
   subsistema de igual para igual com a morfologia local produziria divergência
   por construção. O que se reporta é o **desvio em relação à média regional** —
   onde esta área difere do seu subsistema e, portanto, onde vale aprofundar.

---

## Parametrização do Modelo de Carga Composta

Destino: **parametrização do CLM no ORGANON**. Especificação completa em
[`../01-ESPECIFICACAO/12-modelo-clm-parametrizacao.md`](../01-ESPECIFICACAO/12-modelo-clm-parametrizacao.md).

O cartão é **neutro**: os campos do CMPLDW são os mesmos em PSS/E
(`CMLDxxU2`), PSLF (`cmpldw`), PowerWorld, DSATools e ORGANON.

### Duas fontes, e só duas

| Rótulo | Fonte |
|---|---|
| **WECC** | *WECC Composite Load Model Specification*, abril de 2021 — estrutura, nomes, equações e o exemplo numérico resolvido |
| **REF** | arXiv:1708.00939, apêndice — conjunto completo em formato PSLF DYD, de onde vem **todo** valor numérico de referência |

O que não vem delas recebe rótulo próprio — **derivado** (dado que esta
ferramenta observa), **premissa** (hipótese versionada, com o motivo escrito)
e **a calibrar** (não afirmado). A regra que organiza o módulo: *nenhum número
sem procedência*.

### O que a ferramenta preenche, de 124 campos

| Procedência | Campos |
|---|---|
| derivado | 5 a 6 — as cinco frações e a base MVA da capacidade de fronteira |
| premissa | 2 — `Rfdr` e `Xfdr`, escalados pelo comprimento equivalente |
| WECC | 3 a 4 — fixados na especificação |
| referência | 84 a 91 |
| **a calibrar** | **29 — não afirmados** |

Dado aberto brasileiro não determina nem um quinto do CMPLDW. O módulo existe
para deixar essa fronteira explícita, não para escondê-la.

### O que prova que a implementação está correta

A especificação resolve um exemplo de 100 MW e **publica a tabela de
resultado**. Reproduzi-la é a única forma de mostrar que a implementação está
correta, e não apenas plausível:

| | B calculado | B publicado |
|---|---|---|
| Motor A | 0,1440 | 0,144 |
| Motor B | 0,0720 | 0,072 |
| Motor C | 0,0180 | 0,018 |
| Motor D | 0,0540 | 0,054 |
| Eletrônica | 0,0360 | 0,036 |
| Estática | 0,0360 | 0,036 |
| **total** | **0,3600** | 0,360 |

Com os desligamentos parciais, a admitância remanescente também confere:
0,2052 contra 0,2052 publicado. **Desvio máximo nas 12 comparações: 0,0.**

### Três decisões de fundo

1. **A fração motora bate exatamente com a do Mapa Inteligente.** Há teste que
   exige desvio zero. Duas telas que discordassem sobre a mesma grandeza
   destruiriam a credibilidade das duas.
2. **A penetração de ar condicionado brasileira não é a do modelo.** O motor D
   vem de ensaio no sudoeste norte-americano e é justamente o componente que
   governa a recuperação lenta de tensão. Não temos esse dado para o Brasil, e
   a tela **expõe a sensibilidade** em vez de fixar um número.
3. **Os reativos extras não são a soma dos reativos dos componentes.** No
   exemplo publicado são −36 Mvar contra +16 de soma: o montante vem do
   balanço de rede da inicialização. A primeira versão deste código derivava
   um do outro — errado. Há teste nomeado para impedir a volta da
   simplificação.

> **O que o CMPLDW não faz:** dinâmica de inversor. A MMGD entra como injeção
> `Pdg + jQdg` no barramento de carga, como na figura de inicialização da
> especificação, mas resposta a subtensão, a frequência e anti-ilhamento
> exigem modelo próprio de recurso distribuído (família DER_A), em paralelo ao
> CLM. Dizê-lo é mais útil do que sugerir que o CLM resolve.

---

## Fronteira T–D: subestação de distribuição × SE da rede básica

Especificação em
[`../01-ESPECIFICACAO/13-fronteira-td-correlacao.md`](../01-ESPECIFICACAO/13-fronteira-td-correlacao.md).

O ONS publica a rede básica; a **subestação de distribuição (SED)** está na
BDGD da ANEEL. A camada geográfica da BDGD (ArcGIS) é bloqueada pelo proxy,
mas o pacote BDGD no CKAN da ANEEL publica as **unidades consumidoras de média
e alta tensão** com o código da SED (`SUB`), classe, 12 meses de energia e
demanda, vínculo com a GD (`CEG_GD`) e coordenada. A SED é reconstruída a
partir das cargas que atende e associada à SE de fronteira que a alimenta.

| Fonte | Uso |
|---|---|
| ONS · `subestacao` + `capacidade-transformacao` | SE de fronteira (secundário ≤ 138 kV) |
| ANEEL · BDGD `UCMT_PJ` / `UCAT_PJ` | SED: posição, energia e demanda por classe |
| ANEEL · cadastro de MMGD (4,66 mi empreendimentos) | GD por SED (vínculo exato, 7,7 GW) e por município |
| ANEEL · SAMP 2025 | baixa tensão por distribuidora e classe |
| IBGE · SIDRA 6579 e malha municipal | rateio por população; centroide |

**Associação**: `a(s,f) = MVA^α · e^(−d/λ)` × bônus de UF e de grupo
econômico, α = 0,5, λ = 20 km — escolhidos por varredura exposta na tela
(α = 1 deixava 103 SEs vazias; α = 0 sobrecarregava SEs em até 330%). Cada
vínculo sai com probabilidade e alternativas; p < 0,5 é declarado ambíguo.

**Resultado medido** (26/09/2026): 5.119 SEDs associadas a 462 das 523 SEs de
fronteira; 443 TWh/ano alocados, 48% medidos por UC; 53,7 GW de MMGD alocada,
14% por vínculo direto. Energia alocada ÷ carga verificada do ONS em 2025:
SE 0,65 · S 0,75 · NE 0,62 · N 0,39 — abaixo de 1 por construção (perdas,
autoconsumo da MMGD, carga na rede básica).

**Para o modelo de carga**: `GET /api/clm/cartao?sub_id=…&fonte=bdgd` usa a
composição por energia faturada real e a MMGD do cadastro da ANEEL no lugar
da estimativa morfológica do Mapa Inteligente. O painel mostra as duas
representações lado a lado.

**Privacidade**: CPF/CNPJ e nome do titular da GD, endereço e CEP das UCs não
são lidos. O bruto (~270 MB) é baixado para um diretório temporário e apagado
após a agregação; o cache guarda só agregados (`.cache/fronteira_base.json`).

A primeira construção leva ~2 min, em segundo plano, com progresso na tela;
depois a base fica em cache por 7 dias. Com o download bloqueado, arquivos
baixados à mão podem ser postos em `ORACULO_FRONTEIRA_RAW`.

---

## Investimento: alocação de BESS pelo corte observado

Especificação em [`../01-ESPECIFICACAO/14-alocacao-bess.md`](../01-ESPECIFICACAO/14-alocacao-bess.md).

Doze meses completos de *constrained-off* apurado do ONS
(`restricao_coff_fotovoltaica` e `restricao_coff_eolica_usi`), agregados por
**SE de conexão**. O ponto de conexão vira SE pelo código de 6 caracteres do
`id_pontoconexao` (`MGJBA3500-A` → Janaúba 3), com recuo pelas usinas → CEG →
coordenada no SIGA/ANEEL: 97% da energia cortada localizada.

Em cada sítio um BESS é simulado: carrega durante o corte (limites de P e E) e
descarrega uma vez por dia, no fim da tarde, quando a MMGD some. O
dimensionamento sobe na grade (25–500 MW × 2/4/6 h) enquanto o **MWh
adicional** ainda cicla ≥ 200 vezes/ano.

**O corte é nas usinas centralizadas; a MMGD não é cortada.** Ela reduz a
carga líquida ao meio-dia e aprofunda a curva do pato, criando o excedente que
vira corte ENE+SIS em qualquer usina do SIN. Por isso a MMGD entra como **corte
induzido**: em cada meia hora, mín(corte ENE+SIS do SIN, MMGD estimada do SIN),
rateado pelos sítios — um limite superior contrafactual. A MMGD vizinha **não**
entra na escolha do sítio de geração; ela aparece na outra tese, **BESS junto à
carga**, listada à parte. A pontuação soma postos percentuais de energia
recuperável (45%), excedente da MMGD (20%), recorrência (20%) e restrição local
(15%), com pesos ajustáveis e teste de estabilidade do top 10.

**Resultado medido** (09/2025 a 08/2026): 41,3 TWh/ano cortados, 64% por razão
energética, 83% de origem sistêmica; 43% do corte em 10 sítios; o BESS
dimensionado nesses 10 recuperaria 5,3 TWh/ano. Topo do ranking: Jaíba e
Janaúba 3 (MG), Ourolândia II, Gentio do Ouro II e Morro do Chapéu II (BA),
Açu III e João Câmara (RN).

A primeira carga baixa ~800 MB (24 arquivos, ~7 min, em segundo plano); cada
mês agregado fica em `.cache/bess/` e a reconstrução só baixa o mês novo.

---

## Projeção do corte por razão energética e BESS futuro

Especificação em [`../01-ESPECIFICACAO/15-projecao-corte-ene.md`](../01-ESPECIFICACAO/15-projecao-corte-ene.md).

Séries: corte ENE+SIS horário do SIN (constrained-off do ONS, eólica desde
10/2021, FV desde 04/2024), balanço horário do ONS e MMGD conectada por mês
(cadastro técnico da ANEEL: 2,4 GW em 2019 → 53,7 GW em 08/2026, crescimento
desacelerando). Em vez de extrapolar a tendência — o corte era quase nulo até
2024 e disparou em 2025 —, um modelo físico:

```
carga líquida NL = supervisionada − (eólica + solar) POTENCIAIS
corte ENE+SIS    = α · máx(0, θ_mês − NL)
```

**Backtest** (ajuste até 08/2025, teste nos 12 meses seguintes): erro mensal
de 18% contra 54% do ingênuo "mesmo mês do ano anterior"; correlação horária
0,91; viés −12%.

**Projeção** sobre o ano de referência. Referência oficial: carga global e
MMGD ano a ano da **2ª Revisão Quadrimestral do PLAN 2026-2030**
(ONS/EPE/CCEE, 07/08/2026) — MMGD de 8.536 a 11.240 MWmed, 55,6 a 72,5 GW —
e eólica + solar centralizadas do **PAR/PEL 2025** (+2,3% a.a.). A MMGD horária
é calibrada ao nível oficial (a estimativa do envelope estava 2,7× abaixo).

Resultado: com a carga (+4,5% a.a., datacenters) crescendo mais que a expansão
centralizada considerada, o corte ENE+SIS cai de 26,5 TWh para 11,9 TWh em
2030 — mas 5,5 TWh (47%) dele passam a ser devidos ao crescimento da MMGD. No
ritmo observado de expansão centralizada, o corte vai a 120 TWh. **O caso de
BESS depende sobretudo do ritmo da expansão centralizada frente à carga.** O
potencial técnico de BESS (ciclo marginal ≥ 200/ano) é teto de uso, sem
receita, não recomendação; cenários acima de 25% da geração potencial cortada
são sinalizados como inconsistentes.

---

## Curva do pato prevista pelo tempo

Especificação em [`../01-ESPECIFICACAO/16-curva-do-pato-tempo.md`](../01-ESPECIFICACAO/16-curva-do-pato-tempo.md).

A MMGD por município (cadastro ANEEL) vira 83 células de ~2,5°. Em cada uma, a
radiação e a temperatura previstas — **ECMWF AIFS** (modelo de IA, mesma
família do FourCastNet do NVIDIA Earth-2), **ECMWF IFS** e **NOAA GFS**, via
Open-Meteo — viram geração fotovoltaica, com PR calibrado pelo ERA5 para
reproduzir a MMGD média oficial de 2026 (PLAN 2026-2030; PR 0,64 a 0,83). A
carga supervisionada prevista é o dia-tipo corrigido pela MMGD **e pela
temperatura**:

```
sup(d) = sup_tipo − β·ΔMMGD + γ·ΔT
```

Sem a temperatura, a sensibilidade à MMGD some (R² 0,02 no Sudeste): dia de sol
também aquece e aumenta a refrigeração. Com ela, β ≈ 0,8 e γ ≈ 830 MW/°C no
Sudeste (R² 0,30), estimados antes da janela de teste.

**Backtest** com as previsões arquivadas de cada modelo (63 dias, SIN): erro
9–16h de 2.843 MW na persistência contra 1.844 MW na média dos modelos
(**−35%**); rampa da tarde −27%. O AIFS acerta a barriga, mas erra mais a
rampa; nenhum modelo vence em tudo.

**NVIDIA Earth-2** não roda aqui (exige GPU e `earth2studio`, ou NIM com chave
de API); fica como provedor plugável e declarado. O cliente valida o TLS contra
o repositório de certificados do Windows (CA do proxy corporativo), desligando
só o modo X.509 estrito do OpenSSL.

---

## Resultado medido

Área SE, dados reais do balanço de energia (2025 + 2026), backtest cronológico
com 10.280 h de treino e 4.406 h de teste:

| Horizonte | MAE | MAPE | *skill* vs. persistência | *skill* vs. sazonal |
|---|---|---|---|---|
| 30 min | 1.116 MW | 2,59% | +0,575 | +0,632 |
| 3 h | 1.703 MW | 3,98% | +0,722 | +0,641 |
| D+1 | 1.699 MW | 4,04% | +0,543 | +0,543 |

Efeito da perda assimétrica na **ponta noturna** (horizonte de 3 h, mesmo
conjunto de teste):

| Perda | MAE no patamar | Viés no patamar |
|---|---|---|
| Assimétrica | 1.136 MW | **+340 MW** (lado seguro) |
| Simétrica | 1.144 MW | **−436 MW** (lado inseguro) |

Com MAE praticamente igual, a assimetria desloca o erro para o lado que a
operação suporta. Era exatamente o argumento do deck; agora é número.

Risco de curtailment: 10 áreas modeladas a partir dos registros reais de
constrained-off, AUC mediano fora da amostra de **0,902**, avaliado apenas na
janela solar.

> Números reproduzíveis com `python run_pipeline.py --area SE`. Variam com o
> período disponível no Portal na data da execução.

---

## Limites, declarados

1. **Não há modelo elétrico da rede.** Nada de fluxo de potência, estabilidade
   ou controle de tensão. A saída é insumo para quem faz esses estudos.
2. **Não substitui o PREVCARGA** nem o PREVCARGA PMO: é camada complementar de
   granularidade espacial na fronteira T–D.
3. **Não automatiza despacho.** `recommended_actions` é apoio à decisão humana.
4. **A MMGD estimada não tem verdade fundamental disponível.** Validamos
   consistência física, não erro absoluto.
5. **A meteorologia é proxy determinístico.** ERA5 é reanálise; em produção as
   covariáveis futuras vêm de ECMWF, GFS, WRF e INMET. O viés de *perfect-prog*
   não está medido.
6. **BDGD e satélite são demonstrativos.** O contrato e a lógica de triangulação
   são os de produção; as bases reais estão pendentes de aquisição.
7. **O rótulo de curtailment é a decisão operativa observada**, não o potencial
   físico de geração.
8. **A ortoimagem do Mapa Inteligente é sintética.** O detector e as métricas são
   reais; a imagem é de demonstração.
9. **Subestação de distribuição exige BDGD.** O dado aberto cobre a rede de
   operação; usamos a fronteira T–D como recorte possível.
10. **Industrial não é afirmado pelo cadastro.** Exige base de classe de consumo
    (BDGD ou a Pesquisa de Posse e Hábitos do IBGE, citada no enunciado). Vem só
    da morfologia da amostra.
11. **YOLO sem runtime** — ver a seção do Mapa Inteligente.
12. **Nada simula o CLM no tempo.** São as relações algébricas e a lógica de
    proteção — o que a parametrização precisa expor. A resposta transitória é
    do ORGANON.
13. **29 dos 124 campos do CMPLDW não são afirmados.** Parâmetros elétricos de
    máquina e os de ensaio do compressor aparecem com o valor de referência e
    o rótulo *a calibrar*.
14. **A composição por classe é premissa versionada**, não medição de uso
    final. A calibração pede o guia de composição de carga da NERC e a
    Pesquisa de Posse e Hábitos de Consumo.
15. **A associação SED → SE de fronteira é inferida.** A topologia de
    subtransmissão não é dado público; 52% dos vínculos são ambíguos
    (p < 0,5), concentrados nas metrópoles. Confirmar com a distribuidora ou
    o SIGA/ONS antes de uso operativo.
16. **O corte observado não é o corte futuro.** O ranking de BESS não modela
    receita nem as obras de transmissão previstas, que podem eliminar
    restrições locais.

Detalhamento em [`../01-ESPECIFICACAO/08-limitacoes.md`](../01-ESPECIFICACAO/08-limitacoes.md).

---

## Fontes técnicas

- ONS — PAR/PEL 2025, Sumário Executivo:
  <https://www.ons.org.br/Paginas/energia-no-futuro/suprimento-eletrico/parpel2025/sumario-executivo/index.aspx>
- ONS — Portal de Dados Abertos: <https://dados.ons.org.br/>
- ONS — FAQ Curtailment: <https://www.ons.org.br/Paginas/faq_curtailment.aspx>
- WECC — Composite Load Model Specification:
  <https://www.wecc.org/sites/default/files/documents/meeting/2024/WECC%20Comp%20Load%20Model%20Specification_final.pdf>
- Spencer, J. W. (1971). *Fourier series representation of the position of the sun.*
- Haurwitz, B. (1945). *Insolation in relation to cloudiness and cloud density.*
