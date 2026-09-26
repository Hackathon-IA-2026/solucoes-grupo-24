# 11 · Desafio Radix — Mapa Inteligente de Perfis de Carga e Geração Distribuída

Fonte: `Hackathon - Tema do Desafio_Radix.pptx` (Radix + AXIA + Cepel).

## 11.1 O que o desafio pede

Uma camada de inteligência de dados, construída sobre bases abertas, que
responda **duas perguntas para cada subestação da rede de distribuição**:

1. **Qual é o perfil predominante de consumo da área atendida?**
   Residencial, comercial, industrial ou misto, com indicador de percentual.
2. **Existe presença relevante de geração distribuída no entorno?**
   Baixa / média / alta penetração de MMGD em telhados.

Requisitos adicionais do enunciado:

- **Pipeline replicável**: sempre que as bases forem atualizadas, a metodologia
  reproduz o mapa.
- **Entrada**: uma lista de subestações georreferenciadas.
- **Saída, por subestação**: classificação predominante da carga e indicador de
  presença de MMGD.
- **Valor de negócio**: redução de incertezas em análises técnicas; redução do
  conservadorismo no planejamento da operação; apoio a decisões de investimento
  em rede, MMGD e armazenamento.
- **Destino técnico**: subsidiar a parametrização e a evolução do modelo de
  carga **CLM no ORGANON**.

Contexto que motiva o desafio (slide 2): a perturbação de **15/08/2023**, com o
desligamento automático da LT 500 kV Quixadá–Fortaleza II e interrupção de
**23.368 MW**, em que *"o desempenho dos parques eólicos e fotovoltaicos
observado em campo foi inesperado, muito aquém daquele obtido pelo ONS nos seus
estudos, os quais são realizados utilizando-se os modelos matemáticos
encaminhados pelos agentes"*. A lacuna é de **representação**, não de dado
inexistente.

## 11.2 Entrada: subestações georreferenciadas, reais

O ONS publica exatamente o insumo pedido no conjunto **`subestacao`**:

```
id_subsistema;nom_subsistema;id_estado;nom_estado;nom_agente_principal;
id_subestacao;nom_subestacao;val_niveltensao;id_estacao;num_barra;
val_latitude;val_longitude
```

Resultado da ingestão real (setembro de 2026):

| Grandeza | Valor |
|---|---|
| Registros lidos | 1.689 |
| Descartados por coordenada ausente ou fora do território | 9 |
| Subestações únicas | 909, em 27 UF |
| Com capacidade de transformação associada | 600 |
| **Com transformação de fronteira com a distribuição** | **522** |

### Por que "fronteira" e não "subestação de distribuição"

O conjunto `subestacao` cobre a **rede de operação** — transmissão. A subestação
de distribuição propriamente dita está na BDGD, que não é dado aberto de acesso
direto. A **fronteira T–D**, porém, está no dado público: identificamos as
transformações cujo **lado secundário é de tensão de distribuição**
(≤ 138 kV, campo `val_tensaosecundario_kv` de `capacidade-transformacao`). É
exatamente onde o problema de observabilidade se manifesta, e é o recorte
honesto possível com base aberta.

### Área de influência

Dimensionada pela **capacidade que efetivamente desce para a distribuição**, não
pela capacidade total: um transformador 765/500 kV não atende carga, apenas
interliga transmissão.

```
área_km² = MVA_fronteira / 9      (densidade de carga urbana típica, MVA/km²)
raio_km  = √(área/π),  limitado a [0,8 ; 6,0]
```

Raio resultante nas 522 subestações de fronteira: mínimo 0,80 km, mediana
3,34 km, máximo 6,00 km.

## 11.3 Pergunta 1 — perfil predominante de consumo

Duas evidências, com pesos declarados.

### Evidência local: morfologia construída (75%)

Distribuição de área dos telhados na amostra de ortoimagem, **ponderada por
área e não por contagem** — um galpão de 5.000 m² pesa muito mais na carga do
que uma casa de 120 m², ainda que conte como uma edificação:

| Classe | Área de telhado |
|---|---|
| Residencial | até 220 m² |
| Comercial | 220 a 1.200 m² |
| Industrial | acima de 1.200 m² |

### Prior regional: forma da curva de carga (25%)

Decomposição da curva de carga **verificada do ONS**, por subsistema, nos perfis
canônicos de cada classe, por **mínimos quadrados não negativos**:

```
carga_norm(t) ≈ Σ_c  w_c · perfil_c(t) ,    w_c ≥ 0 ,   Σ w_c = 1
```

A restrição de soma unitária entra como equação extra com peso alto. Uma segunda
equação usa a **razão fim de semana / dia útil**, assinatura independente da
forma horária — é o que separa comercial (0,62) de industrial (0,90) quando as
duas têm platô diurno.

Perfis canônicos (estilizados a partir das características documentadas de cada
classe — premissa versionada, não medição de campo):

| Classe | Assinatura |
|---|---|
| Residencial | ponta noturna acentuada, vale de madrugada |
| Comercial | platô de expediente, queda no fim de semana |
| Industrial | quase plano nas 24 h, fator de carga alto |
| Rural / irrigação | bombeamento noturno e de madrugada |

### Nota metodológica importante

**O prior regional não é uma segunda medida da mesma grandeza.** Comparar a
curva agregada do subsistema de igual para igual com a morfologia local
produziria divergência por construção, porque o subsistema agrega todas as
classes. O que se reporta é o **desvio da área em relação à média regional** —
que é a informação útil: *onde esta área difere do seu subsistema* e, portanto,
onde vale aprofundar o estudo.

### Limite declarado

Discriminar **industrial** com segurança exige base de classe de consumo — BDGD
ou a Pesquisa de Posse e Hábitos de Consumo do IBGE, citada no próprio
enunciado. O indicador cadastral **não** afirma industrial; esse rótulo só
aparece pela morfologia da amostra.

## 11.4 Pergunta 2 — presença de geração distribuída

### Visão computacional sobre ortoimagem

Detecção de painéis fotovoltaicos, com dois backends de mesma interface:

| Backend | Estado | Implementação |
|---|---|---|
| **Detector clássico** | **ativo** | índice espectral de excesso de azul + luminância (suavizados), densidade de borda por Sobel, morfologia binária, componentes conexas, filtro de forma, refinamento em duas etapas |
| **YOLOv8-seg** | pronto, sem runtime | letterbox e inversa, decodificação das saídas, NMS, recorte de máscara por protótipos, transformação de coordenadas — tudo implementado e testado |

> **Sobre o YOLO, sem rodeio.** `torch`, `onnxruntime` e `ultralytics` **não
> podem ser instalados** neste ambiente: o proxy corporativo bloqueia o PyPI com
> certificado próprio (`CERTIFICATE_VERIFY_FAILED`, verificado). O adaptador
> detecta a ausência do runtime, **declara isso na API e na tela**, e cede o
> lugar ao detector clássico. Quando houver pesos e runtime, trocar o backend é
> uma linha: ladrilhamento, NMS, deduplicação na costura e georreferência são
> compartilhados e testados.

### Da detecção ao indicador

```
pixel → lat/lon (geo-transformação local plana)
área conexa × área do pixel → m² de painel
× calibração de área (1,19, medida)  → m² corrigido
× 200 W/m² de módulo                 → kWp
÷ área amostrada                     → kWp/km²  →  nível de penetração
```

**Amostragem, não cobertura total.** Ortoimagem de 30 cm sobre 113 km² por
subestação é inviável. A detecção roda em **2 janelas de 230 m de lado a
0,30 m/pixel** (0,106 km² no total) e a densidade medida é extrapolada para a
área de influência, aplicando a **fração construída** típica da morfologia
identificada (comercial 0,80 · residencial 0,60 · industrial 0,40 · misto 0,55).
O **nível** usa a densidade medida, sem extrapolação; só o total absoluto é
extrapolado.

### Faixas do indicador

Ancoragem: uma unidade com MMGD tem tipicamente 5 kWp; a densidade construída
urbana fica entre 800 e 2.000 telhados por km²; a penetração média brasileira é
da ordem de 3% das unidades consumidoras, chegando a 8–10% nos municípios mais
avançados.

| Nível | kWp/km² |
|---|---|
| Baixa | < 200 |
| Média | 200 a 800 |
| Alta | > 800 |

### Conferência cruzada com dado real

O conjunto `modalidade-usina` do ONS traz as usinas **Tipo III** — geração
conectada à rede de distribuição — com ponto de conexão e potência autorizada
por UF. São dado real, usados para ancorar a ordem de grandeza relativa entre
estados e como conferência do indicador.

## 11.5 Desempenho medido

O detector é avaliado contra **verdade fundamental conhecida** da ortoimagem
sintética: 4 classes urbanas × 3 sementes = 12 cenas.

| Métrica | Valor |
|---|---|
| Precisão | 0,982 |
| Revocação | 0,997 |
| F1 | 0,988 |
| IoU de máscara | 0,876 |
| *Average precision* | 0,730 |
| Erro de área, calibrado | +0,7% |
| Erro de área, bruto | −15,4% |

A calibração de área (1,19×) é **medida**, não arbitrada: mesmo após o
refinamento em duas etapas, o detector subestima a área em torno de 16%, porque
a borda do painel é um gradiente e qualquer limiar corta parte dela. O viés é
sistemático e consistente entre classes urbanas (−12% a −21%), portanto
corrigível. O valor bruto permanece na API para auditoria, e o teste de
regressão exige erro calibrado abaixo de 8%.

## 11.6 Saída para o Modelo de Carga Composta

Por subestação, o payload `clm` propõe:

| Campo | Significado |
|---|---|
| `composicao_classe` | fração por classe de consumo |
| `fracao_motor_estimada` | fração de carga motora, combinando as classes com premissas declaradas (residencial 0,22 · comercial 0,38 · industrial 0,62 · rural 0,55) |
| `mmgd_kwp_na_area` | potência distribuída estimada |
| `distributed_generation_flag` | se o modelo deve representar GD explicitamente |
| `confianca` | confiança da classificação |

> **Não são parâmetros prontos para simulação no ORGANON.** São as grandezas
> observadas que o especialista usa para escolher a composição do Composite Load
> Model. A distinção está no próprio payload, no campo `aviso`.

## 11.7 Limitações específicas deste desafio

| # | Limitação | Consequência |
|---|---|---|
| R1 | **A ortoimagem é sintética.** O detector é o mesmo que roda em imagem real, e as métricas são medições reais dele; a imagem é de demonstração. Em imagem real, esperar degradação. | A acurácia reportada é um teto, não uma promessa de campo. |
| R2 | **Subestação de distribuição exige BDGD.** O dado aberto do ONS cobre a rede de operação; usamos a fronteira T–D como recorte possível. | A granularidade-alvo do enunciado ainda não é alcançada. |
| R3 | **Não existe curva de carga por subestação em dado aberto.** A decomposição roda por subsistema e entra como prior regional. | A classificação local repousa sobre a morfologia. |
| R4 | **Industrial não é afirmado pelo cadastro.** Exige base de classe de consumo (BDGD ou IBGE PPH). | Rótulo industrial vem só da morfologia da amostra. |
| R5 | **Variância de amostragem alta onde as edificações são poucas e grandes.** | O payload reporta `sample_adequacy` (boa / limitada / insuficiente). |
| R6 | **A calibração de área foi medida em imagem sintética.** | Precisa ser remedida contra conjunto rotulado real. |
| R7 | **YOLO sem runtime** (§11.4). | O backend ativo é o clássico; declarado na API e na tela. |

## 11.8 Próximos passos para este desafio

1. **BDGD de uma distribuidora piloto** — move a granularidade para a
   subestação de distribuição real e ativa a classe de consumo por unidade
   consumidora.
2. **IBGE — Pesquisa de Posse e Hábitos de Consumo** — citada no enunciado;
   permite discriminar industrial e calibrar os perfis canônicos com medição.
3. **Ortoimagem real e pesos YOLO** — troca de backend e remedição da
   calibração de área contra conjunto rotulado.
4. **Cadastro de GD da ANEEL por município** — conferência do indicador de
   penetração contra registro administrativo.
5. **Amostragem adaptativa** — aumentar o número de janelas onde
   `sample_adequacy` for limitada ou insuficiente.
