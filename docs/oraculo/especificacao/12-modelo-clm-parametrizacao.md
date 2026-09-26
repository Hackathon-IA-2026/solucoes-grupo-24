# 12 · Modelo de Carga Composta — teoria e parametrização sugerida

Destino: **parametrização do CLM no ORGANON**. Os campos do CMPLDW são os
mesmos em PSS/E (`CMLDxxU2`), PSLF (`cmpldw`), PowerWorld, DSATools e ORGANON,
e por isso o cartão que esta ferramenta emite é **neutro** — não a sintaxe de
uma ferramenta específica.

## 12.1 Fontes, e só estas

| Rótulo | Fonte | O que vem dela |
|---|---|---|
| **WECC** | *WECC Composite Load Model Specification*, Modeling and Validation Subcommittee, abril de 2021 (aprovada em 27/01/2015) | Estrutura, nomes dos campos, equações, o exemplo numérico resolvido e os poucos números que o texto fixa |
| **REF** | Q. Huang, S. Jin, R. Diao, B. Palmer et al., *A Reference Implementation of WECC Composite Load Model in Matlab and GridPACK*, arXiv:1708.00939, apêndice — conjunto completo em formato PSLF DYD, barra 90 do IEEE 300 barras | **Todo** valor numérico de referência do registro |

Links:

- <https://www.wecc.org/sites/default/files/documents/meeting/2024/WECC%20Comp%20Load%20Model%20Specification_final.pdf>
- <https://arxiv.org/pdf/1708.00939>

O que **não** vem dessas duas fontes recebe rótulo próprio, e é essa a regra
que organiza o módulo: **nenhum número sem procedência**.

| Rótulo | Significado |
|---|---|
| **DERIVADO** | Calculado com dado que esta ferramenta observa |
| **PREMISSA** | Hipótese versionada aqui, com o motivo escrito |
| **A_CALIBRAR** | Não afirmado. Exibido com o valor de referência e o rótulo; exige ensaio, medição de campo ou base cadastral |

### Uma fonte que ficou de fora, e por quê

O *Reliability Guideline — Developing Load Model Composition Data* (NERC Load
Modeling Task Force, março de 2017) é a fonte certa para substituir a premissa
de composição por classe por dado. **Não foi consultada nesta versão**: o
servidor da NERC nega acesso automatizado (HTTP 403, verificado). Consta como
próximo passo e como referência declarada na API — não como base de número
algum.

## 12.2 Estrutura: o CLM não é uma mistura de motores

```
Barramento          Barramento            Barramento
do sistema            de baixa             de carga
(230/115/69 kV)                     (extremidade do alim.)
    │                    │                     │
    ├──── jXxf, 1:T ─────┤─── Rfdr + jXfdr ────┤── M  Motor A   3φ
    │       (LTC)        │                     │── M  Motor B   3φ
    │                    ⊥ Bss                 │── M  Motor C   3φ
    │                    ⊥ Fb·Bfdr   (1−Fb)·Bfdr ⊥  │── M  Motor D   1φ
    │                                          │── ▭  Eletrônica
  UVLS                                         │── ▭  Estática
  UFLS                                         └── Pdg + jQdg (MMGD)
```

Os barramentos **de baixa** e **de carga** não existem no fluxo de potência:
são criados na inicialização do modelo.

**O ponto que costuma passar em branco:** metade do efeito dinâmico vem da
**rede entre** o barramento de transmissão e o uso final. É a impedância do
transformador e do alimentador que faz a tensão no uso final cair mais do que
a tensão medida na subestação — e é isso que leva o compressor a travar. A
especificação observa que as ferramentas **reajustam** Rfdr e Xfdr na
inicialização para manter o barramento de carga acima de **0,95 pu**.

### Aplicabilidade

O CLM não deve ser aplicado a qualquer barra. Critérios citados na
especificação para o caso WECC:

| Critério | Limite |
|---|---|
| Carga | > 5 MW |
| Tensão | > 0,98 pu |
| Relação P/Q | > 1,61 |

Abaixo disso a inicialização falha. A API reporta **qual** critério reprovou,
porque é essa a informação útil.

## 12.3 Os seis componentes

As frações `Fma`, `Fmb`, `Fmc`, `Fmd` e `Fel` reparte a carga; **o resto é
estática**. Se somarem mais de 1, a estática vai a zero e as demais são
normalizadas — regra explícita da especificação, implementada em
`theory.static_remainder`.

Cada slot de motor pode ser trifásico (`Mtyp = 3`) ou compressor monofásico
(`Mtyp = 1`).

### O que de fato distingue os motores A, B e C

**Não existe campo “tipo de equipamento” no CMPLDW.** A diferença está
inteiramente em duas grandezas, que o conjunto de referência fixa:

| Motor | H | Etrq | Desligamento por subtensão | Leitura convencional |
|---|---|---|---|---|
| A | 0,3 s | 0 — conjugado constante | não | compressores, carga de conjugado constante |
| B | 0,5 s | 2 — ∝ velocidade² | 0,80 pu / 2 s · 0,60 pu / 0,16 s | ventiladores |
| C | 1,0 s | 2 — ∝ velocidade² | idem B | bombas, alta inércia |

`H` e `Etrq` são **REF**. A leitura de equipamento é a convencional da
literatura de modelagem de carga, e está **rotulada como tal** na tela — não é
dado.

Conjugado mecânico: `Tm = Tmo · ω^Etrq`.

### Motor D — compressor monofásico, modelo por desempenho

Desenvolvido pelo WECC Load Modeling Task Force a partir de **ensaio de
laboratório** em unidades reais de ar condicionado. É o componente que governa
a recuperação lenta de tensão.

```
V > 0,86            P = Po (1 + Δf)
                    Q = [Q'o + 6 (V − 0,86)²] (1 − 3,3 Δf)

V'stall < V < 0,86  P = [Po + 12 (0,86 − V)^3,2] (1 + Δf)
                    Q = [Q'o + 11 (0,86 − V)^2,5] (1 − 3,3 Δf)

V < V'stall         P =  Gstall · V²
                    Q = −Bstall · V²
```

com `Q'o = Po·tan(acos(CompPF)) − 6(1 − 0,86)²` e
`Gstall + jBstall = 1/(Rstall + jXstall)` invertido.

`Δf` é `f − 1`, negativo em subfrequência.

**`Vstallbrk`** é onde a curva de rotor bloqueado cruza a de regime II. A
especificação publica o laço que o encontra a 0,01 pu:

```
for (V = 0,4; V < Vstall; V += 0,01)
    pst    = Gstall · V²
    p_comp = Po + 12 (0,86 − V)^3,2
    if (p_comp <= pst) { V'stall = V; break }
```

Implementamos o laço publicado **e** uma bissecção independente, e exigimos
que concordem dentro de um passo. Com o conjunto de referência: laço 0,5500 pu,
bissecção 0,544942 pu.

**A posição relativa de `Vstall` e `Vstallbrk` muda o resultado**, não apenas o
valor de `Vstall` — é o que as figuras 6 a 8 da especificação mostram, e o que
o painel reproduz.

### Carga eletrônica — tem memória

Cai em rampa entre `Vd1` e `Vd2`, e a variável interna `Vmin` guarda a menor
tensão já vista. Consequência: **a curva de descida não é a de subida**, e com
`Frcel = 0` a carga desligada **não volta sozinha**. É esse laço, e não o valor
de `Vd1`, o que costuma surpreender em estudo.

### Carga estática

```
P = Po (P1c V^P1e + P2c V^P2e + P3)(1 + Pfrq Δf),   P3 = 1 − P1c − P2c
Q = Qo (Q1c V^Q1e + Q2c V^Q2e + Q3)(1 + Qfrq Δf),   Q3 = 1 − Q1c − Q2c
```

Em `V = 1` e `Δf = 0` o fator é **exatamente 1**, qualquer que seja a
repartição ZIP. Se não fosse, o CLM deslocaria o ponto de operação na
inicialização — o modelo passaria a mentir sobre a própria carga inicial. Há
teste para isso.

### Proteções agregadas

| Proteção | Caracterização |
|---|---|
| Relé de subtensão, 3φ | dois estágios `Vtr1/Ttr1/Ftr1` e `Vtr2/Ttr2/Ftr2`, **cumulativos** |
| Relé de subtensão, motor D | fração `Fuvr`, que **não religa** no resto da simulação |
| Contatores | histerese `Vc1off`/`Vc2off` na descida, `Vc2on`/`Vc1on` na subida |
| Térmica | unitária até `Th1t`, decrescente até zero em `Th2t`; temperatura de `I²Rstall` filtrada por `1/(Tth s + 1)` |

## 12.4 O que esta ferramenta preenche

De **124** campos do registro:

| Procedência | Campos | O que são |
|---|---|---|
| DERIVADO | 5 a 6 | as cinco frações e, havendo subestação real, a base MVA |
| PREMISSA | 2 | `Rfdr` e `Xfdr`, escalados pelo comprimento equivalente |
| WECC | 3 a 4 | fixados na especificação (`Ll = 0,80 Lpp`, base MVA padrão) |
| REF | 84 a 91 | conjunto de referência publicado |
| A_CALIBRAR | 29 | **não afirmados** |

Dado aberto brasileiro não determina nem um quinto do CMPLDW. O módulo existe
para deixar essa fronteira explícita, não para escondê-la.

### As frações, a partir da composição de classe

Combinação linear da composição medida no Mapa Inteligente (doc. 11) pela
repartição por classe abaixo — **premissa versionada**, com o raciocínio:

| Classe | Fma | Fmb | Fmc | Fmd | Fel | estática | motora |
|---|---|---|---|---|---|---|---|
| Residencial | 0,05 | 0,03 | 0,02 | **0,12** | 0,20 | 0,58 | 0,22 |
| Comercial | 0,12 | 0,10 | 0,06 | 0,10 | 0,22 | 0,40 | 0,38 |
| Industrial | 0,20 | 0,12 | **0,28** | 0,02 | 0,10 | 0,28 | 0,62 |
| Rural | 0,06 | 0,04 | **0,43** | 0,02 | 0,08 | 0,37 | 0,55 |

- **Residencial** — carga motora pequena e quase toda monofásica: compressor
  de refrigerador e de ar condicionado, o motor D. Carga eletrônica alta e
  crescente. O resto é resistivo — chuveiro, no Brasil, é parcela relevante e
  puramente estática.
- **Comercial** — climatização central reparte entre compressores de conjugado
  constante (A) e ventilação forçada (B).
- **Industrial** — predomínio de bombas e alta inércia (C), pouca carga
  monofásica.
- **Rural** — irrigação e bombeamento, praticamente tudo C.

**A coluna “motora” reproduz exatamente a fração motora que o Mapa Inteligente
já publica**, e há teste que exige desvio zero. Duas telas que discordassem
sobre a mesma grandeza destruiriam a credibilidade das duas.

### O parâmetro que expusemos em vez de fixar

A **penetração de ar condicionado no Brasil não é a do sudoeste
norte-americano** de onde vem o modelo do motor D — e o motor D é justamente o
componente que governa a recuperação lenta de tensão. Não temos esse dado. A
tela oferece um multiplicador de `Fmd` (o delta volta para a estática, de modo
que a soma continua fechando em 1), porque **expor a sensibilidade é mais
honesto do que fixar um número que não temos**.

### Impedância do alimentador

A impedância série é proporcional ao comprimento. O raio de influência do Mapa
Inteligente é o único proxy de comprimento em dado aberto:

```
escala = raio_km / 3,34          (raio mediano das 522 de fronteira)
        limitada a [0,35 ; 2,20]
Rfdr = Xfdr = 0,04 · escala
```

Premissa de primeira ordem, e ponto de partida apenas: a especificação diz que
as ferramentas reajustam esses valores na inicialização.

## 12.5 Onde entra a MMGD, e onde não entra

A figura de inicialização da especificação (figura 11) mostra `Pdg + jQdg`
injetado **no barramento de carga**: o CLM **acomoda** geração distribuída como
injeção, e o balanço de reativos da inicialização já conta com ela.

O que o CMPLDW **não** tem é **dinâmica de inversor** — nem resposta a
subtensão, nem a frequência, nem anti-ilhamento. Isso é outro modelo (família
DER_A), em paralelo ao CLM. Dizê-lo é mais útil do que sugerir que o CLM
resolve.

## 12.6 O que prova que a implementação está correta

A especificação resolve um exemplo numérico de 100 MW e **publica a tabela de
resultado** (seção *Handling of extra vars due to end-use load tripping*,
páginas 19 e 20). Reproduzi-la é a única forma de mostrar que a implementação
está **correta**, e não apenas plausível.

| Componente | MW | Mvar | peso | B calc. | B publ. | em serviço | rem. calc. | rem. publ. |
|---|---|---|---|---|---|---|---|---|
| Motor A | 40 | 9 | 0,40 | 0,1440 | 0,144 | 0,20 | 0,0288 | 0,0288 |
| Motor B | 20 | 6 | 0,20 | 0,0720 | 0,072 | 0,70 | 0,0504 | 0,0504 |
| Motor C | 5 | 4 | 0,05 | 0,0180 | 0,018 | 0,40 | 0,0072 | 0,0072 |
| Motor D | 15 | 1 | 0,15 | 0,0540 | 0,054 | 1,00 | 0,0540 | 0,0540 |
| Eletrônica | 10 | −2 | 0,10 | 0,0360 | 0,036 | 0,80 | 0,0288 | 0,0288 |
| Estática | 10 | −2 | 0,10 | 0,0360 | 0,036 | 1,00 | 0,0360 | 0,0360 |
| **total** | 100 | 16 | | **0,3600** | 0,360 | | **0,2052** | 0,2052 |

**Desvio máximo nas 12 comparações: 0,0.**

### Um detalhe que quase virou erro

Os reativos extras do exemplo são **−36 Mvar**, enquanto a soma dos reativos
dos componentes é **+16**. Os dois números não são o mesmo: o montante vem do
**balanço de rede da inicialização** — transformador, alimentador, shunts e a
própria geração distribuída. Derivar um do outro seria errado, e a primeira
versão deste código fazia exatamente isso. Há teste nomeado para impedir que a
simplificação volte.

### Conferências independentes

| Conferência | Por que importa |
|---|---|
| Carga estática devolve fator 1,000000 em 1 pu | se não, o CLM desloca o ponto de operação |
| `Vstallbrk` por laço publicado e por bissecção concordam em 0,01 pu | um valida o outro |
| Continuidade das equações do motor D em 0,86 pu | descontinuidade ali seria degrau de potência na faixa normal |
| Fator de potência inicial do motor D é o `CompPF` pedido | verifica o termo de correção de `Q'o` |
| Frações que somam mais de 1 normalizam e zeram a estática | regra explícita da especificação |
| Fração motora igual à do Mapa Inteligente, desvio 0 | coerência entre telas |

**61 testes** em `tests/test_clm.py`.

## 12.7 Limitações

| # | Limitação | Consequência |
|---|---|---|
| C1 | **Nada aqui simula o CLM no tempo.** São as relações algébricas e a lógica de proteção. | A parametrização é exposta e verificável; a resposta transitória é do ORGANON. |
| C2 | **A composição por classe é premissa versionada**, não medição de uso final. | Calibração pede o guia da NERC e a Pesquisa de Posse e Hábitos de Consumo. |
| C3 | **29 campos não são afirmados** (A_CALIBRAR): parâmetros elétricos de máquina e os de ensaio do compressor. | Aparecem com o valor de referência e o rótulo. A escolha é do especialista. |
| C4 | **A penetração de ar condicionado brasileira é desconhecida aqui.** | A tela expõe a sensibilidade de `Fmd` em vez de fixar um número. |
| C5 | **`Rfdr`/`Xfdr` saem de um proxy de comprimento**, não de cadastro de alimentador. | Ponto de partida; as ferramentas reajustam na inicialização. |
| C6 | **Não há curva de carga por subestação em dado aberto** (herdada de R3, doc. 11). | A composição local repousa sobre a morfologia da amostra. |
| C7 | **O CMPLDW não representa dinâmica de inversor.** | MMGD entra como injeção; o comportamento dinâmico exige DER_A. |
| C8 | **O cartão não é caso pronto para simulação.** | Está escrito no próprio cartão, na tela e no payload. |

## 12.8 Próximos passos

1. **Guia de composição de carga da NERC** — substitui a premissa de
   `CLASS_COMPONENTS` por base reconhecida.
2. **Pesquisa de Posse e Hábitos de Consumo** — penetração de ar condicionado
   e de uso final por classe no Brasil; resolve C2 e C4.
3. **BDGD de uma distribuidora piloto** — cadastro de alimentador para
   `Rfdr`/`Xfdr` reais, resolvendo C5, e classe de consumo por unidade.
4. **Oscilografia de perturbação real** — ajuste dos parâmetros elétricos
   hoje em A_CALIBRAR. A perturbação de 15/08/2023, citada no enunciado da
   Radix, é o caso natural.
5. **DER_A em paralelo** — fecha C7.
