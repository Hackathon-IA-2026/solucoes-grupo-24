# O.R.A.C.U.L.O. — Especificação da Solução

**Observabilidade de Redes e Análise de Curtailment em Usinas e Limites Operacionais**

Equipe 24 — LINKFY · Hackathon IA COPPE/UFRJ 2026 · Trilha Transição Energética

---

## O que este diretório contém

Especificação técnica derivada do deck consolidado
`ORACULO_pitch_12_slides_revisado.pptx`. Cada documento é rastreável aos slides
que o originaram (ver `09-rastreabilidade-deck.md`).

| Documento | Conteúdo |
|---|---|
| [`01-visao-e-escopo.md`](01-visao-e-escopo.md) | Problema, proposta de valor, os dois eixos, o que está dentro e fora do escopo |
| [`02-requisitos.md`](02-requisitos.md) | Requisitos funcionais (RF) e não funcionais (RNF), com critérios de aceite |
| [`03-arquitetura.md`](03-arquitetura.md) | Camadas, componentes, fluxo de dados, decisões de engenharia e seus porquês |
| [`04-modelo-de-dados.md`](04-modelo-de-dados.md) | Fontes reais do Portal de Dados Abertos do ONS, esquemas verificados, contratos internos |
| [`05-api.md`](05-api.md) | Contrato HTTP do serviço, incluindo o envelope de proveniência obrigatório |
| [`06-modelos-analiticos.md`](06-modelos-analiticos.md) | Estimador de MMGD, decomposição de carga, regressão quantílica com perda assimétrica, classificador de risco |
| [`07-validacao.md`](07-validacao.md) | Backtest cronológico, baselines obrigatórios, métricas por patamar e calibração probabilística |
| [`08-limitacoes.md`](08-limitacoes.md) | Limitações declaradas, riscos e mitigações |
| [`09-rastreabilidade-deck.md`](09-rastreabilidade-deck.md) | Matriz slide → requisito → módulo → teste |
| [`10-roadmap.md`](10-roadmap.md) | Fatiamento do MVP e evolução pós-Ideathon |
| [`11-desafio-radix-mapa-inteligente.md`](11-desafio-radix-mapa-inteligente.md) | **Desafio Radix + AXIA + Cepel**: Mapa Inteligente de Perfis de Carga e Geração Distribuída — entrada, as duas perguntas, visão computacional, desempenho medido e limites |
| [`12-modelo-clm-parametrizacao.md`](12-modelo-clm-parametrizacao.md) | **Modelo de Carga Composta (CMPLDW)**: teoria, equações, registro de parâmetros com procedência campo a campo e parametrização sugerida para o CLM no ORGANON |

O protótipo executável está em [`../02-PROTOTIPO`](../02-PROTOTIPO), e a
documentação da aplicação em [`../03-DOCUMENTACAO`](../03-DOCUMENTACAO)
(Sphinx: uma página por painel).

---

## Resumo em um parágrafo

O ONS dispõe de elevada observabilidade sobre o sistema sob sua supervisão. Na
fronteira com a distribuição, essa visão depende de informação agregada e
estimativas: a MMGD e as usinas Tipo III somam cerca de **63,5 GW** — em torno de
**25% da capacidade instalada** — sem a telemetria, a previsibilidade e a
controlabilidade dos recursos centralizados. O O.R.A.C.U.L.O. é uma **camada de
observabilidade e inteligência preditiva da fronteira transmissão–distribuição**:
integra séries operativas do Portal de Dados Abertos do ONS, cadastro e topologia
de distribuição, meteorologia e evidência física por satélite, e entrega dois
produtos — **(i)** previsão da carga supervisionada com estimativa de MMGD por
área e **(ii)** indicadores preditivos de **risco de curtailment por razão
energética**, localizados e rastreáveis até o dado de origem.

## Princípio de projeto

> Nenhuma promessa de desempenho sem teste; nenhum alerta sem evidência
> rastreável.

Operacionalmente, isso significa três regras que atravessam toda a especificação:

1. **Todo número exibido carrega proveniência.** Dataset de origem, recurso,
   instante de extração e defasagem conhecida acompanham o valor até a tela
   (`05-api.md`, envelope `provenance`).
2. **Todo modelo é comparado a baselines.** Persistência e sazonal-ingênuo são
   obrigatórios; um modelo que não os supera por horizonte não é promovido
   (`07-validacao.md`).
3. **Todo limite é declarado antes de ser perguntado.** A solução não executa
   fluxo de potência, não substitui o PREVCARGA e não automatiza despacho
   (`08-limitacoes.md`).

## Fontes técnicas

- ONS — PAR/PEL 2025, Sumário Executivo:
  <https://www.ons.org.br/Paginas/energia-no-futuro/suprimento-eletrico/parpel2025/sumario-executivo/index.aspx>
- ONS — Portal de Dados Abertos: <https://dados.ons.org.br/>
- ONS — FAQ Curtailment: <https://www.ons.org.br/Paginas/faq_curtailment.aspx>
- WECC — Composite Load Model Specification:
  <https://www.wecc.org/sites/default/files/documents/meeting/2024/WECC%20Comp%20Load%20Model%20Specification_final.pdf>
- Huang, Jin, Diao, Palmer et al. — *A Reference Implementation of WECC
  Composite Load Model in Matlab and GridPACK* (conjunto de parâmetros de
  referência, apêndice): <https://arxiv.org/pdf/1708.00939>
- NERC — Reliability Guideline: Developing Load Model Composition Data (fonte
  indicada para calibrar a composição por classe; não consultada nesta
  versão — o servidor nega acesso automatizado):
  <https://www.nerc.com/comm/RSTC_Reliability_Guidelines/Reliability_Guideline_-_Load_Model_Composition_-_2017-02-28.pdf>
