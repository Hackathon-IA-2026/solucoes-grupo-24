# 01 · Visão e escopo

## 1.1 O problema

A expansão dos recursos energéticos distribuídos deslocou parcela crescente da
oferta para as redes de distribuição, fora do despacho centralizado. O
diagnóstico do PAR/PEL 2025 registra:

| Grandeza | Valor | Consequência operativa |
|---|---|---|
| MMGD + usinas Tipo III na distribuição | ≈ 63,5 GW | ≈ 25% da capacidade instalada de geração do SIN |
| Participação máxima da GD no atendimento à demanda global | 46% (2025) → 64% (2029, projetado) | a carga que o Operador enxerga é cada vez mais líquida |
| Excedente projetado em domingos de 2029 | até 4,9 GW entre 10h e 12h | todas as fontes centralizadas no mínimo técnico |

O efeito não é marginal: **altera o balanço carga–geração e as margens de
segurança operativas**. Em janelas de alta produção fotovoltaica e baixa demanda,
a carga líquida supervisionada cai, a margem de absorção diminui e a necessidade
de restrição de geração por razão energética se agrava.

A lacuna não é de dado inexistente, e sim de dado **fragmentado**: séries
operativas, cadastro de geração distribuída, topologia de distribuição,
meteorologia e imagens de satélite existem e são públicos — mas são analisados
separadamente, em granularidades e cadências incompatíveis.

## 1.2 A proposta

Uma camada de observabilidade e inteligência preditiva da fronteira
transmissão–distribuição, estruturada em dois eixos.

### Eixo 1 · Carga e MMGD nos estudos elétricos

- **Objetivo** — caracterizar perfis de consumo e a presença de geração
  distribuída nas redes de distribuição.
- **Entrega** — perfis e parâmetros consistentes para validar e calibrar modelos
  dinâmicos equivalentes de carga e MMGD.
- **Destino** — parametrização do Composite Load Model (CLM) e estudos de
  estabilidade eletromecânica do SIN.
- **Aderência institucional** — frente do ONS de parametrização, validação e
  calibração de modelos de carga e MMGD.

### Eixo 2 · Fortalecimento da interface ONS–DSO

- **Objetivo** — ampliar a observabilidade e a previsibilidade da carga e da
  MMGD na fronteira transmissão–distribuição.
- **Entrega** — previsões e indicadores de risco por área, horizonte e causa,
  com rastreabilidade até as fontes.
- **Destino** — coordenação, flexibilidade e gestão de excedentes.
- **Aderência institucional** — Projeto Interface ONS/DSO e Plano de Gestão de
  Excedentes de Energia na Rede de Distribuição.

### O payload da interface

O deck define o contrato informacional que a interface ONS–DSO hoje não tem. Ele
é normativo para esta especificação:

| Dimensão | Definição |
|---|---|
| **Grandeza** | carga supervisionada + MMGD estimada |
| **Granularidade** | área de concessão + transformação de fronteira |
| **Antecedência** | 30 min · 3 h · D+1 |
| **Formato** | probabilístico + rastreável |

## 1.3 Os dois produtos

| # | Produto | Consumidor | Forma |
|---|---|---|---|
| 1 | Carga supervisionada prevista e MMGD estimada | operação (tempo real, programação) e estudos elétricos | série probabilística P10/P50/P90 por área e horizonte |
| 2 | Risco de curtailment por razão energética | operação e coordenação com distribuidoras | probabilidade + potência esperada + motivo provável, por área e janela |

## 1.4 Escopo do protótipo

### Dentro do escopo

1. Ingestão real do **Portal de Dados Abertos do ONS** via API CKAN e recursos
   CSV, com cache em disco e proveniência registrada.
2. **Decomposição da carga**: carga verificada, MMGD estimada e carga
   supervisionada, hora a hora, por subsistema.
3. **Estimador de MMGD** fisicamente fundamentado (geometria solar + céu claro +
   fator de nebulosidade calibrado por resíduo), sem depender de série de MMGD
   publicada.
4. **Previsão probabilística** da carga supervisionada por regressão quantílica
   com **perda assimétrica por patamar horário**, contra baselines obrigatórios.
5. **Classificador de risco de curtailment por razão energética**, treinado nos
   registros reais de constrained-off fotovoltaico e eólico.
6. **Triangulação de evidências** (realidade física, topologia, cadastro) com a
   lógica de desempate que separa defasagem administrativa de instalação não
   homologada.
7. **Backtest cronológico** com baselines, métricas por patamar e avaliação de
   calibração probabilística.
8. **API HTTP** com envelope de proveniência obrigatório em toda resposta.
9. **Interface web** com sete painéis navegáveis, incluindo explorador do
   catálogo de dados abertos.

### Fora do escopo (declarado)

1. Fluxo de potência, análise de estabilidade e controle de tensão. A solução
   entrega **insumos** para esses estudos.
2. Substituição do PREVCARGA ou do PREVCARGA PMO. A solução é camada
   complementar de granularidade espacial na fronteira T–D.
3. Automação de despacho ou de comando de restrição. O produto apoia a decisão
   humana e não executa ação operativa.
4. Ingestão da BDGD completa e de imagens de satélite em produção. O protótipo
   implementa o **contrato e a lógica** de triangulação sobre um conjunto
   demonstrativo, com os campos e cadências reais.

## 1.5 Personas

| Persona | Necessidade | Onde é atendida |
|---|---|---|
| Operador de centro (tempo real) | saber, com 30 min a 3 h de antecedência, onde a carga líquida cai e onde surge excedente | painel de despacho preditivo e mapa de risco |
| Engenheiro de estudos elétricos | perfis representativos de carga e MMGD por área para parametrizar modelos equivalentes | painel de perfis e exportação de parâmetros |
| Analista de dados / P&D | reproduzir a cadeia da fonte pública ao número exibido | explorador de catálogo, envelope de proveniência, backtest |
| Interlocutor da distribuidora | previsão de excedente e de fluxo reverso na sua área de concessão | painel de excedentes TSO–DSO |
