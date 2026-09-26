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
```

## Estrutura

```
src/
  index.css                 tokens do design system (@theme do Tailwind v4) — única fonte de cores/fontes
  theme/severity.ts         níveis de risco e filtros NORMAL/LOADING/CRITICAL/NO-RISK → classes
  modules.ts                registro único dos 8 módulos (gera menu lateral E rotas)
  state/severityFilter.tsx  contexto com os filtros de severidade ativos (useSeverityFilter)
  components/ui/            Card, KpiCard, MiniStat, SegmentedControl, Tabela, ToggleChip, SeverityBadge, RazaoBadge, StatusPill, MockTag, Carregando/ErroDados
  components/charts/        gráficos (BarraComposicao, GraficoPrevisao, GraficoErro, BarrasShap)
  components/mapa/          camadas do Mapa Híbrido (CamadaCalor / leaflet.heat)
  data/geo/                 contorno do Brasil offline (npm run geo:brasil)
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
| `base` / `surface` | `#0a0e17` / `#0f1524` | fundo da página / cards e barras |
| `accent` | `#22d3ee` | dados, linhas, item ativo |
| `risk-low` | `#22c55e` | risco baixo, NORMAL |
| `risk-medium` | `#eab308` | risco médio, LOADING |
| `risk-high` | `#f97316` | risco alto |
| `risk-critical` | `#ef4444` | risco crítico, CRITICAL |
| `risk-none` | `#64748b` | NO-RISK |
| `chart-1` / `chart-2` / `chart-3` | `#0891b2` / `#8b5cf6` / `#db2777` | séries de gráfico e razões ENE/CNF/REL, ordem fixa |
| `font-mono` / `kpi` | JetBrains Mono, algarismos tabulares | números e KPIs |

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
