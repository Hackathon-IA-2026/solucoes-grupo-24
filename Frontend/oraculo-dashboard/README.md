# oraculo-dashboard

Dashboard do O.R.A.C.U.L.O., em dark mode no estilo SCADA de sala de controle.

```bash
npm install
npm run dev      # servidor de desenvolvimento (http://localhost:5173), dados da API do Backend
npm run dev:mock # idem, sem Backend: lê src/data/mock/*.json
npm run build    # typecheck + build de produção em dist/ (servido pelo `python main.py` do Backend)
npm run lint     # oxlint
npm test         # vitest (contrato de dados)
npm run mocks:series  # regenera src/data/mock/previsao.json e validacao.json
npm run geo:brasil    # contorno do Brasil (Natural Earth, offline)
npm run geo:ufs       # divisas das UFs (API de malhas do IBGE; precisa de internet só aqui)
```

Design (revisão de 2026-09-26, com o protótipo Figma "SCADA Dashboard Design" como referência):
tipografia IBM Plex Sans + JetBrains Mono, escala de texto por papel (`text-label`, `text-body`,
`text-kpi`), cantos retos, topbar de largura total e sidebar de 13rem (ícones abaixo de `lg`).
Do Figma NÃO entraram: números sem fonte (frequência do SIN, ciclo DESSEM, mínimo técnico,
"extrapolação de tendências"), a semântica errada das razões (CNF é confiabilidade, não
intercâmbio) e a paleta de cinzas de baixo contraste.

## Estrutura

```
src/
  index.css                 tokens do design system (@theme do Tailwind v4) — única fonte de cores/fontes
  theme/severity.ts         níveis de risco, filtros NORMAL/LOADING/CRITICAL/NO-RISK e SEVERIDADE_STATUS (que filtro controla cada severidade)
  modules.ts                registro único dos 8 módulos (gera menu lateral E rotas)
  state/severityFilter.tsx  contexto com os filtros de severidade ativos (useSeverityFilter / useFiltradosPorSeveridade)
  content/calendario.ts     patamares e faixas de curtailment LIDOS de Backend/config/processamento.yaml no build
  content/limitacoes.ts     limitações declaradas (dados e escopo), fonte única da Validação e da Metodologia
  components/ui/            Card, KpiCard, MiniStat, SegmentedControl, Tabela, ToggleChip, SeverityBadge, RazaoBadge, StatusPill, MockTag, AvisoFiltro, ListaLimitacoes, Carregando/ErroDados
  components/charts/        gráficos (BarraComposicao, GraficoPrevisao, GraficoErro, BarrasShap)
  components/mapa/          camadas do Mapa Híbrido (CamadaCalor / leaflet.heat)
  data/geo/                 contorno do Brasil (npm run geo:brasil) e divisas das UFs (npm run geo:ufs): fundo do mapa 100% local
  utils/format.ts           formatação pt-BR de MW/GW/% e horário BRT
  components/layout/        AppLayout, Sidebar, Topbar, Clock, SeverityFilters, ModuleFrame
  pages/                    uma página por módulo (+ NotFound)
  data/types.ts             contrato de dados: schemas Zod + tipos inferidos
  data/dataSource.ts        getCarga, getPrevisao, getRiscos, getAlerta, getExcedentes, getValidacao
  data/derivados.ts         KPIs derivados (risco agregado ponderado por MW, limiares de severidade)
  data/useDados.ts          hook de leitura assíncrona (loading | ok | erro)
  data/mock/                JSONs mockados (todo registro com mock: true)
```

## Tokens

| Token | Valor | Uso |
|---|---|---|
| `fundo` / `surface` | `#0a0e17` / `#0f1524` | fundo da página / cards e barras (o token se chamava `base` e colidia com o tamanho `text-base`) |
| `accent` | `#22d3ee` | dados, linhas, item ativo |
| `risk-low` | `#22c55e` | risco baixo, NORMAL |
| `risk-medium` | `#eab308` | risco médio, LOADING |
| `risk-high` | `#f97316` | risco alto |
| `risk-critical` | `#ef4444` | risco crítico, CRITICAL |
| `risk-none` | `#64748b` | NO-RISK |
| `chart-1` / `chart-2` / `chart-3` | `#0891b2` / `#8b5cf6` / `#db2777` | séries de gráfico e razões ENE/CNF/REL, ordem fixa |
| `patamar-dia` / `patamar-noite` | `#f59e0b` / `#6366f1` | só tinta translúcida das faixas de mínima diurna / ponta noturna |
| `font-sans` | IBM Plex Sans | texto |
| `font-mono` / `kpi` | JetBrains Mono, algarismos tabulares | números e KPIs |
| `text-label` / `text-body` / `text-kpi` / `text-kpi-xl` | 11 / 13 / 30 / 40 px | rótulo de painel / corpo / KPI / equação da carga |

## Como adicionar conteúdo a um módulo

Edite o arquivo do módulo em `src/pages/` (o título e a descrição já vêm de `modules.ts`).
Para um módulo novo, crie a página e acrescente uma entrada em `MODULES`.

## Dados

As telas leem dados **só** por `src/data/dataSource.ts`. O modo vem de `VITE_DATA_SOURCE`
(ver `.env.example`): `api` (padrão) busca em `VITE_API_BASE_URL` (padrão `/api`, que o Vite
repassa ao Backend — host/porta lidos de `Backend/config/api.yaml`); `mock` (`npm run dev:mock`,
`--mode mock` no `vite.config.ts`) lê `src/data/mock/`. Os testes rodam sempre em mock (`vite.config.ts`).
A pill da topbar (`FonteDados`) mostra a origem: "DADOS MOCK", "DADOS DE dd/mm HH:MM" (instante
do replay publicado, via `/api/saude`) ou "API INDISPONÍVEL".
Nos dois modos toda resposta é validada pelo schema de `types.ts`; no modo mock, registro sem
`mock: true` é rejeitado. Mocks registrados em `docs/real_vs_mock.md` (raiz do repositório).
