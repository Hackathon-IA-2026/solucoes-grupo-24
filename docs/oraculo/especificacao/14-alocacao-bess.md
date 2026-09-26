# 14 · Investimento — alocação de BESS pelo corte observado

Objetivo: apoiar a decisão de **onde investir em armazenamento (BESS)**,
priorizando as subestações das usinas **eólicas e fotovoltaicas centralizadas**
onde o corte (constrained-off) é maior e mais recorrente, e medindo quanto
desse corte é **excedente criado pela MMGD**.

## 14.1 Onde está o corte, e onde está a MMGD

O corte acontece nas usinas centralizadas; a MMGD não é cortada. Ela reduz a
carga líquida do sistema ao meio-dia e aprofunda a barriga da **curva do
pato**: o excedente vira corte por razão energética de origem sistêmica
(ENE + SIS) em qualquer usina do SIN. MMGD alta ao lado de uma usina **não** a
torna mais cortada. Daí duas teses de investimento, mostradas separadas:

| Tese | Onde | O que resolve |
|---|---|---|
| BESS junto à geração | SE de conexão das usinas cortadas (ranking) | recupera o corte e devolve na rampa |
| BESS junto à carga | SE de fronteira de alta MMGD (seção Fronteira T–D) | achata a curva do pato na origem |

A seção se encaixa no **Eixo 2** (excedentes, flexibilidade) e usa a MMGD
estimada pelo protótipo (Eixo 1).

## 14.2 Dados

| Conjunto | Uso |
|---|---|
| ONS · `restricao_coff_fotovoltaica` e `restricao_coff_eolica_usi` | 12 meses completos, semi-horário, por usina e ponto de conexão |
| ONS · `subestacao` | coordenada da SE do ponto de conexão |
| ONS · `modalidade-usina` + ANEEL · SIGA | coordenada quando a SE é coletora privada |
| Seção Fronteira T–D | MW de MMGD e MW médio de carga por SE de fronteira |

O corte é o campo oficial `val_geracaonaorealizadaapurada` (MW médio em 30
min). Em agosto de 2026: 1,6 TWh FV e 4,0 TWh eólica, ENE dominante.

## 14.3 Decisões

| # | Decisão | Motivo |
|---|---|---|
| B1 | Unidade = SE de conexão (pontos de tensões diferentes somados) | É onde o armazenamento absorve o corte sem rede adicional |
| B2 | Código da SE = 6 primeiros caracteres do `id_pontoconexao` | Separar pelo hífen erra `MGJBA3500-A` (Janaúba 3, 500 kV); a regra leva o casamento de 62% a 88% da energia FV |
| B3 | Recuo de localização: nome do ponto → `modalidade-usina` → CEG → SIGA | SEs coletoras privadas não estão no cadastro do ONS; cobertura 97% da energia |
| B4 | BESS com 1 ciclo/dia, carga limitada por P e E, η = 0,88 | Modelo mínimo e auditável; a descarga cai na rampa do fim da tarde |
| B5 | Energia e ciclos anualizados (× 365 / dias da janela) | Sem isso, janela curta nunca atinge o limiar e tudo parece subutilizado |
| B6 | Dimensionamento pelo **ciclo marginal** ≥ 200/ano | "Maior BESS que ainda cicla bem" escolhe sempre o topo da grade |
| B7 | Componente de energia = entrega do BESS dimensionado, não de um BESS fixo | O BESS de referência (100 MW/4 h) satura em quase todo sítio grande e empata |
| B8 | Pontuação por postos percentuais, empate pelo posto médio | Um sítio gigante não esmaga os outros; empatados recebem a mesma nota |
| B9 | Pesos padrão 45/20/20/15, ajustáveis, com teste de estabilidade | A escolha de peso é política; a robustez do ranking é mostrada |
| B11 | MMGD entra como corte induzido: mín(corte ENE+SIS do SIN, MMGD do SIN) por meia hora, rateado pelos sítios | A MMGD não é cortada; ela cria excedente sistêmico. A primeira versão pontuava MMGD num raio de 100 km do sítio — errado: proximidade não causa corte |
| B12 | Atribuição no SIN, não no subsistema | A razão energética é um balanço do SIN; a energia circula pelos intercâmbios |
| B10 | Mês agregado e guardado; bruto descartado | 24 arquivos (~800 MB); a reconstrução só baixa o mês novo |

## 14.4 Limites

1. O corte observado não é o corte futuro: obras de transmissão previstas
   podem eliminar restrições locais.
2. Sem modelo de receita (PLD, serviços ancilares, capacidade) e sem restrição
   de rede na descarga.
3. Corte SIS é aliviado por armazenamento em qualquer ponto do subsistema; LOC,
   só no ponto.
4. O corte induzido pela MMGD é um limite superior contrafactual: supõe que
   a carga atendida pela MMGD seria suprida pela geração cortada. A MMGD é a
   estimativa do envelope (um piso).
