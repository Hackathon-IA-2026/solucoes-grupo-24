Crie uma apresentação de 10 slides, em português do Brasil, 16:9, sobre a nova seção **"Alocação de BESS"** do protótipo O.R.A.C.U.L.O. (Equipe 24 — Linkfy, Hackathon IA COPPE/UFRJ 2026). O público são especialistas do ONS e avaliadores técnicos do hackathon. O tom deve ser técnico, direto e sem exagero: cada número vem de dado aberto e cada premissa é declarada.

## Mensagem central (não pode ser distorcida)

- O corte (*constrained-off*) acontece nas usinas **eólicas e fotovoltaicas centralizadas**, no ponto de conexão delas. **A MMGD não é cortada.**
- A MMGD reduz a carga líquida do sistema ao meio-dia e aprofunda a barriga da **curva do pato**. Isso cria o excedente que vira corte por **razão energética de origem sistêmica (ENE + SIS)** em qualquer usina do SIN.
- **MMGD alta perto de uma usina não faz essa usina ser mais cortada.** Nunca apresente "penetração de MMGD na vizinhança" como critério para escolher o local do BESS junto à geração.
- Há duas teses de investimento, que devem aparecer separadas:
  1. **BESS junto à geração cortada:** recupera o corte e devolve a energia na rampa do fim da tarde. É o ranking.
  2. **BESS junto à carga:** onde a MMGD mais pesa sobre a carga. Achata a curva do pato na origem, mas não recupera o corte de uma usina específica.
- A seção se encaixa no **Eixo 2** (Fortalecimento da interface ONS–DSO: coordenação, flexibilidade, excedentes) e usa a MMGD estimada pelo **Eixo 1** (Carga e MMGD nos estudos elétricos).

## Identidade visual

- **Fundo claro** `#F7FAFD` nos slides de conteúdo; **fundo escuro** `#11172A` no fechamento. A capa fica escura à esquerda e com imagem à direita (mapa do Brasil com rede elétrica, usinas e painéis).
- **Cores:**
  - títulos `#061B33`
  - texto secundário `#52667C`
  - linhas e bordas `#C9D7E5`
  - rótulo pequeno acima do título (*kicker*) em ciano `#22C7F2`
  - Eixo 1 em laranja `#D8690E`
  - Eixo 2 em azul-marinho `#123C67`
  - apoio: teal `#0E8B7E`, verde `#2E9E5B`, vermelho `#E85C5C`, roxo `#7B2C8A`
- **Fonte:** DejaVu Sans (ou Verdana como substituta). Título do slide com 28 pt em negrito; *kicker* com 9,75 pt em negrito e caixa alta; subtítulo com 13,5 pt; rodapé de fonte com 8 pt.
- **Estrutura de cada slide de conteúdo:**
  - *kicker* ciano no topo, à esquerda, e número do slide ("02", "03"…) no canto superior direito;
  - título grande;
  - linha fina divisória abaixo do título;
  - subtítulo de uma ou duas linhas;
  - rodapé com a fonte dos dados.
- **Elementos:** cartões brancos com cantos arredondados e borda fina; faixas coloridas arredondadas (*pills*) para tags; círculos numerados para as etapas; setas entre as etapas de um fluxo.
- **Gráficos:** nativos e editáveis, sem título automático, com legenda discreta e grade clara.

## Slides

**1 · Capa**
- Tag: "NOVA SEÇÃO DO PROTÓTIPO".
- Título: "Alocação de BESS".
- Subtítulo: "Onde o armazenamento recupera mais energia cortada das usinas centralizadas".
- Linha de apoio: "E quanto desse corte é excedente que a MMGD cria na curva do pato".
- Rodapé: "O.R.A.C.U.L.O. · Eixo 2 · Excedentes e flexibilidade · apoiado no Eixo 1".

**2 · Onde se encaixa — "Eixo 2, com a MMGD do Eixo 1"**
- Cartão grande do **Eixo 2**, marcado como EIXO PRINCIPAL.
  - Objetivo: indicar onde o armazenamento recupera mais energia cortada das eólicas e fotovoltaicas centralizadas.
  - Entrega: ranking de subestações de conexão, com BESS dimensionado e energia recuperável por ano.
  - Tag: COORDENAÇÃO · FLEXIBILIDADE · EXCEDENTES.
- Cartão do **Eixo 1**, marcado como APOIO.
  - Objetivo: medir quanto do corte é excedente criado pela MMGD.
  - Tag: MMGD → CURVA DO PATO.
- Embaixo, um fluxo de 4 caixas do painel de excedentes do pitch: 1 Antecipar → 2 Priorizar → 3 Coordenar → **4 Investir (novo, em destaque)**.

**3 · O problema em escala — "41,3 TWh cortados em 12 meses"**
- Período: 09/2025 a 08/2026. Fonte: constrained-off apurado pelo ONS, FV + eólica.
- Quatro números em destaque:
  - 41,3 TWh/ano cortados em 101 subestações;
  - 64% por razão energética;
  - 43% em 10 subestações;
  - 83% de origem sistêmica (17% local).
- Gráfico de colunas empilhadas: corte mensal em TWh, eólica + fotovoltaica.

  | Mês | Eólica | FV |
  |---|---|---|
  | set/25 | 3,72 | 1,36 |
  | out/25 | 4,84 | 1,35 |
  | nov/25 | 2,54 | 0,99 |
  | dez/25 | 1,61 | 0,66 |
  | jan/26 | 2,46 | 0,75 |
  | fev/26 | 0,50 | 0,35 |
  | mar/26 | 0,85 | 0,87 |
  | abr/26 | 1,42 | 1,04 |
  | mai/26 | 2,09 | 1,15 |
  | jun/26 | 1,77 | 1,00 |
  | jul/26 | 3,09 | 1,27 |
  | ago/26 | 4,02 | 1,60 |

**4 · "A MMGD não é cortada: ela cria o excedente"**
- Kicker: "ONDE ESTÁ O CORTE, E ONDE ESTÁ A MMGD".
- Gráfico de linhas: **curva do pato do Nordeste**, perfil médio por hora (00h a 23h) em GW. Rótulos do eixo das horas na base do gráfico, porque há valores negativos.
  - Carga com MMGD (tracejada, cinza): 14,0 13,6 13,3 13,1 12,9 12,6 12,5 13,4 13,5 13,7 13,9 13,9 13,6 13,7 13,9 14,1 14,6 14,6 14,9 14,8 14,6 14,9 14,9 14,5
  - Carga supervisionada (azul-marinho): 14,0 13,6 13,3 13,1 12,9 12,6 12,3 12,3 12,5 12,5 12,6 12,6 12,3 12,5 12,8 13,2 13,7 14,2 14,9 14,8 14,6 14,9 14,9 14,5
  - Carga líquida, descontadas eólica e solar centralizadas (teal): −1,5 −1,8 −1,9 −2,0 −2,0 −2,3 −3,9 −5,4 −5,3 −4,6 −3,7 −3,3 −2,8 −2,8 −2,7 −2,1 0,0 2,3 2,2 1,0 0,3 0,0 −0,4 −1,0
  - Corte apurado (vermelho, mais grosso): 1,3 1,2 1,1 1,1 1,0 1,1 2,6 6,0 8,7 10,3 10,5 9,8 9,3 7,8 6,1 4,5 2,8 1,3 0,9 1,3 1,6 1,7 1,6 1,5
- Quatro cartões numerados à direita:
  1. O corte é na geração centralizada: o corte médio no Nordeste chega a 10,5 GW às 10h.
  2. Carga líquida negativa: eólica e solar centralizadas superam a carga do Nordeste, com mínimo de −5,4 GW.
  3. A MMGD aprofunda o vale: atende carga ao meio-dia e tira espaço da geração centralizada no SIN.
  4. A MMGD vizinha não escolhe o sítio: proximidade de MMGD não faz uma usina ser mais cortada.
- Rodapé: "MMGD: estimativa do O.R.A.C.U.L.O. pelo método do envelope (um piso)".

**5 · Duas teses de investimento — "Geração cortada ou carga com MMGD"**
- Cartão azul-marinho, **Tese 1 · BESS junto à geração cortada**:
  - Onde: SE de conexão das eólicas e fotovoltaicas cortadas.
  - Resolve: recupera o corte e devolve na rampa do fim da tarde.
  - Como a MMGD entra: fração do corte explicada pelo excedente que ela cria (ENE+SIS).
  - Na ferramenta: o ranking.
- Cartão laranja, **Tese 2 · BESS junto à carga**: achata a curva do pato na origem e não recupera o corte de uma usina. Tabela das 5 SEs de fronteira com maior MMGD sobre a carga:

  | SE | MMGD MW | Carga MW | MMGD ÷ carga |
  |---|---|---|---|
  | Foz do Iguaçu Norte (PR) | 444 | 68 | 6,49 |
  | Realeza Sul (PR) | 227 | 43 | 5,27 |
  | Umuarama Sul (PR) | 375 | 80 | 4,68 |
  | Paranavaí Norte (PR) | 254 | 55 | 4,58 |
  | Guaíra (PR) | 598 | 131 | 4,57 |

- Nota: "Oeste do Paraná: longe de onde o corte acontece — a MMGD não está onde o corte está."

**6 · Como funciona — "Do registro do corte à decisão de investimento"**
- Fluxo de 5 etapas:
  1. Corte por ponto (ONS, 12 meses, 30 min)
  2. Ponto → SE (código ONS, SIGA/ANEEL)
  3. BESS simulado (carga no corte, 1 ciclo/dia)
  4. Excedente da MMGD (ENE+SIS × MMGD do SIN)
  5. Pontuação (pesos ajustáveis)
- Cartão com as duas fórmulas:
  - `absorvido = mín(E ; Σ mín(corte, P) × 0,5 h)`
  - `induzido(t) = mín(corte ENE+SIS do SIN ; MMGD do SIN)`
- Texto do cartão:
  - Eficiência de 88%.
  - O tamanho do BESS sobe enquanto o MWh **adicional** ainda for usado ≥ 200 vezes por ano.
  - A parcela da MMGD é um **limite superior** e não inclui corte local nem de confiabilidade.
- Barras horizontais com os pesos padrão:
  - energia recuperável 45%
  - excedente da MMGD 20%
  - recorrência 20%
  - restrição local 15%

**7 · "O corte tem endereço"**
- Subtítulo: 97,4% da energia cortada localizada; o top 10 está no Nordeste e no norte de Minas.
- À esquerda: espaço para a captura de tela do mapa do protótipo.
- À direita, tabela do top 10:

  | # | Subestação | UF | Corte GWh/ano | BESS sugerido | Entrega GWh/ano | Excedente da MMGD |
  |---|---|---|---|---|---|---|
  | 1 | João Câmara III | RN | 3.277 | 500 MW · 6 h | 792 | 23% |
  | 2 | Monte Verde | RN | 1.835 | 500 MW · 6 h | 710 | 21% |
  | 3 | Janaúba 3 | MG | 1.405 | 500 MW · 4 h | 501 | 39% |
  | 4 | Açu III | RN | 2.830 | 500 MW · 6 h | 798 | 23% |
  | 5 | João Câmara 2 | RN | 1.346 | 500 MW · 6 h | 666 | 24% |
  | 6 | Jaíba | MG | 805 | 300 MW · 4 h | 296 | 36% |
  | 7 | Bom Nome | PE | 716 | 300 MW · 4 h | 315 | 36% |
  | 8 | Ourolândia II | BA | 1.734 | 500 MW · 4 h | 489 | 37% |
  | 9 | Açu II | RN | 755 | 300 MW · 6 h | 408 | 28% |
  | 10 | Santa Luzia II | PB | 1.042 | 500 MW · 4 h | 490 | 43% |

- Rodapé: "Recuperável com o BESS dimensionado nos 10 sítios: 5,5 TWh/ano".

**8 · Exemplo — "Janaúba 3 (MG): 500 MW / 4 h"**
- Kicker: "EXEMPLO · 3º DO RANKING". Fotovoltaica, corte ao meio-dia: 1.405 GWh/ano cortados, 27% da geração, corte em 91% dos dias.
- Gráfico de dispersão com linhas: GWh/ano entregues × MWh instalados, uma série por duração.
  - 2 h: (50; 15) (100; 29) (200; 58) (400; 114) (600; 169) (1.000; 272)
  - 4 h: (100; 29) (200; 57) (400; 112) (800; 219) (1.200; 318) (2.000; 501)
  - 6 h: (150; 41) (300; 82) (600; 160) (1.200; 309) (1.800; 444) (3.000; 675)
- Três cartões:
  - BESS sugerido: 500 MW · 4 h, 285 ciclos/ano, MWh marginal usado 326 vezes/ano.
  - Energia recuperada: 501 GWh/ano, 41% do corte do sítio.
  - Excedente da MMGD: até 39% (552 GWh/ano); ENE+SIS é 74% do corte do sítio.
- Leitura: "74% do corte é excedente sistêmico e só 11% é restrição local. Até 39% é atribuível à MMGD: o BESS aqui absorve o que a curva do pato empurra para fora do sistema."

**9 · Confiança — "O que é robusto, e o que depende da tese"**
- Barras "quantos dos 10 primeiros permanecem sob outros pesos":

  | Cenário de pesos | Permanecem |
  |---|---|
  | só energia | 7 de 10 |
  | curva do pato | 2 de 10 (destacar em vermelho) |
  | restrição local | 7 de 10 |
  | pesos iguais | 9 de 10 |
  | sem MMGD | 9 de 10 |

- Cartão "Como ler":
  - Os sítios de corte grande e recorrente são robustos.
  - Priorizar o excedente da MMGD é outra decisão, que favorece fotovoltaicas com corte ao meio-dia (Pecém II, Paracatu 4, Acaraú II).
- Faixa vermelha clara, "Limites declarados":
  - O corte observado não é o corte futuro.
  - O excedente da MMGD é um limite superior sobre uma MMGD estimada como piso.
  - Não há modelo de receita (PLD, serviços ancilares, capacidade).

**10 · Fechamento (fundo escuro)**
- Kicker verde-menta: "ALOCAÇÃO DE BESS · MENSAGEM FINAL".
- Frase grande em branco: "O corte está nas usinas centralizadas; até 33% dele é excedente criado pela MMGD. Armazenamento em 10 subestações recuperaria 5,5 TWh por ano."
- Faixa ciano: "LOCALIZAR · DIMENSIONAR · ATRIBUIR".
- Três cartões escuros:
  - Para o investidor: sítio, tamanho e energia recuperável por ano, com a premissa de cada número.
  - Para o ONS: quanto do excedente é da curva do pato e quanto é restrição de rede.
  - Próximo passo: somar receita (PLD e serviços) e o plano de expansão da transmissão.
- Fontes:
  - ONS: restricao_coff_fotovoltaica, restricao_coff_eolica_usi, balanço de energia, subestacao, modalidade-usina (dados.ons.org.br).
  - ANEEL: SIGA (dadosabertos.aneel.gov.br).
  - MMGD estimada pelo O.R.A.C.U.L.O.

## Regras de qualidade

- Use grafia correta dos nomes, com acentos e numerais romanos em maiúsculas: Açu III, João Câmara, Janaúba, Ourolândia, Santa Luzia II.
- Use números no padrão brasileiro: vírgula decimal e ponto no milhar.
- Não invente números além dos fornecidos; o que não estiver aqui não entra.
- Nenhum texto pode transbordar dos cartões. Mantenha margens de pelo menos 0,5" e espaço de 0,3" entre blocos.
- Inclua notas do apresentador em cada slide, resumindo a fala em 1 ou 2 frases.
