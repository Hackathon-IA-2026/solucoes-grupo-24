/**
 * Visão Geral: faixa de KPIs (carga supervisionada, MMGD, risco de curtailment, montante em
 * risco), curva D+1 com patamares, composição da carga global e a coluna "Alertas ativos".
 *
 * Arranjo inspirado no protótipo Figma (KPIs com borda superior de identidade + coluna de
 * alertas à direita), mas só com dados do contrato: o Figma também mostrava frequência do SIN,
 * "margem até o mínimo técnico" e ciclo DESSEM, que não existem em nenhuma fonte do projeto
 * e por isso NÃO aparecem aqui (regra "nunca inventar dados").
 */
import { ArrowRight } from 'lucide-react'
import { Link } from 'react-router-dom'
import { BarraComposicao } from '../components/charts/BarraComposicao'
import { GraficoPrevisao, LegendaPrevisao } from '../components/charts/GraficoPrevisao'
import { AvisoFiltro } from '../components/ui/AvisoFiltro'
import { Card } from '../components/ui/Card'
import { Carregando, ErroDados } from '../components/ui/Estado'
import { KpiCard } from '../components/ui/KpiCard'
import { MockTag } from '../components/ui/MockTag'
import { RazaoBadge } from '../components/ui/RazaoBadge'
import { SeverityBadge } from '../components/ui/SeverityBadge'
import { getCarga, getPrevisao, getRiscos } from '../data/dataSource'
import {
  composicaoCarga,
  montanteEmRiscoMw,
  contarPor,
  montantePorRazao,
  ordenarPorSeveridade,
  resumoCurva,
  riscoAgregadoPct,
  severidadePorProbabilidade,
} from '../data/derivados'
import { HorizonteSchema, RazaoSchema, type CargaSnapshot, type PrevisaoCurva, type RiscoUsina } from '../data/types'
import { useDados } from '../data/useDados'
import { MODULES, rotaDetalheAlerta } from '../modules'
import { useFiltradosPorSeveridade } from '../state/useSeverityFilter'
import { RAZAO_INFO } from '../theme/razao'
import { RISK_STYLES } from '../theme/severity'
import { formatGw, formatHoraBrt, formatMw, formatPct } from '../utils/format'

// Rótulo e cor de cada parcela (ordem fixa: supervisionada = chart-1, MMGD = chart-2).
const SERIES = {
  supervisionada: { rotulo: 'Carga supervisionada (atendida pelo SIN)', cor: 'bg-chart-1' },
  mmgd: { rotulo: 'MMGD estimada (geração distribuída)', cor: 'bg-chart-2' },
} as const

// Links pelo registro de módulos (nenhum caminho escrito à mão).
const DESPACHO = MODULES.find((m) => m.label === 'Despacho Preditivo')!
const LISTA = MODULES.find((m) => m.label === 'Lista de Riscos')!
const MAPA = MODULES.find((m) => m.label === 'Mapa Híbrido')!

export default function VisaoGeral() {
  // getCarga/getRiscos/getPrevisao são referências estáveis de módulo: cada efeito roda uma vez.
  const carga = useDados(getCarga)
  const riscos = useDados(getRiscos)
  const previsao = useDados(getPrevisao)

  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_19rem]">
      <div className="min-w-0 space-y-4">
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {carga.status === 'ok' ? (
            <KpisCarga c={carga.data} />
          ) : carga.status === 'erro' ? (
            <div className="sm:col-span-2"><ErroDados erro={carga.erro} /></div>
          ) : (
            <>
              <Carregando />
              <Carregando />
            </>
          )}
          {riscos.status === 'ok' ? (
            <KpisRisco riscos={riscos.data} />
          ) : riscos.status === 'erro' ? (
            <div className="sm:col-span-2"><ErroDados erro={riscos.erro} /></div>
          ) : (
            <>
              <Carregando />
              <Carregando />
            </>
          )}
        </div>

        {previsao.status === 'ok' && <CurvaD1 curvas={previsao.data} />}
        {previsao.status === 'erro' && <ErroDados erro={previsao.erro} />}
        {previsao.status === 'loading' && <Carregando altura="h-72" />}

        {carga.status === 'ok' && <ComposicaoCarga c={carga.data} />}
        {carga.status === 'loading' && <Carregando altura="h-40" />}
      </div>

      {riscos.status === 'ok' && <AlertasAtivos riscos={riscos.data} />}
      {riscos.status === 'loading' && <Carregando altura="h-96" />}
    </div>
  )
}

function KpisCarga({ c }: { c: CargaSnapshot }) {
  return (
    <>
      <KpiCard
        label="Carga supervisionada"
        to={DESPACHO.path}
        accent="border-t-chart-1"
        value={formatGw(c.cargaSupervisionadaMw)}
        unit="GW"
        actions={<MockTag mock={c.mock} />}
        hint={<>{formatMw(c.cargaSupervisionadaMw)} MW · {formatHoraBrt(c.timestampUtc)} BRT</>}
      />
      <KpiCard
        label="MMGD estimada"
        to={MAPA.path}
        accent="border-t-chart-2"
        value={formatGw(c.mmgdEstimadaMw)}
        unit="GW"
        actions={<MockTag mock={c.mock} />}
        hint={<>{formatMw(c.mmgdEstimadaMw)} MW · {formatPct(c.percentualMmgdNaGeracao)}% da geração</>}
      />
    </>
  )
}

function KpisRisco({ riscos }: { riscos: RiscoUsina[] }) {
  // KPIs de SISTEMA: calculados sobre todos os riscos, sem os filtros da topbar (o filtro muda
  // o que se lista, não a medida do SIN).
  const pct = riscoAgregadoPct(riscos)
  const nivel = pct === null ? 'none' : severidadePorProbabilidade(pct)
  const algumMock = riscos.some((r) => r.mock)
  return (
    <>
      <KpiCard
        label="Risco de curtailment"
        to={LISTA.path}
        accent={RISK_STYLES[nivel].topo}
        value={pct === null ? '—' : formatPct(pct)}
        unit="%"
        actions={<MockTag mock={algumMock} />}
        hint={
          <span className="flex flex-wrap items-center gap-2">
            {pct !== null && <SeverityBadge level={nivel} />}
            média ponderada por MW
          </span>
        }
      />
      <KpiCard
        label="Montante em risco"
        to={LISTA.path}
        value={formatMw(montanteEmRiscoMw(riscos))}
        unit="MW"
        actions={<MockTag mock={algumMock} />}
        hint={<>{riscos.length} usinas/conjuntos com previsão de corte</>}
      />
    </>
  )
}

/** Curva D+1 da carga supervisionada (atalho para o Despacho Preditivo). */
function CurvaD1({ curvas }: { curvas: PrevisaoCurva[] }) {
  const curva = curvas.find((c) => c.horizonte === 'D+1')
  if (!curva) return null
  const r = resumoCurva(curva.pontos)
  return (
    <Card
      title="Carga supervisionada prevista · D+1 · P10/P50/P90"
      actions={
        <>
          <MockTag mock={curva.mock} />
          <Link to={DESPACHO.path} className="inline-flex items-center gap-1 text-xs text-accent hover:underline">
            {DESPACHO.label} <ArrowRight className="size-3.5" aria-hidden />
          </Link>
        </>
      }
    >
      {r && (
        <p className="kpi mb-2 flex flex-wrap gap-x-5 gap-y-1 text-xs text-ink-muted">
          <span>mín <span className="text-ink">{formatGw(r.minimo.mw)} GW</span> às {formatHoraBrt(r.minimo.timestamp)}</span>
          <span>máx <span className="text-ink">{formatGw(r.maximo.mw)} GW</span> às {formatHoraBrt(r.maximo.timestamp)}</span>
          <span>amplitude <span className="text-ink">{formatGw(r.amplitudeMw)} GW</span></span>
          <span>incerteza média <span className="text-ink">{formatGw(r.bandaMediaMw)} GW</span></span>
        </p>
      )}
      <GraficoPrevisao curva={curva} altura="h-64" />
      <div className="mt-3">
        <LegendaPrevisao janelaRampaHoras={curva.janelaRampaHoras} />
      </div>
    </Card>
  )
}

function ComposicaoCarga({ c }: { c: CargaSnapshot }) {
  const parcelas = composicaoCarga(c).map((p) => ({ ...p, ...SERIES[p.chave] }))
  return (
    <Card
      title="Composição da carga global"
      actions={
        <>
          <MockTag mock={c.mock} />
          <span className="kpi text-xs text-ink-muted">
            total {formatMw(c.cargaGlobalMw)} MW · {formatHoraBrt(c.timestampUtc)} BRT
          </span>
        </>
      }
    >
      <BarraComposicao titulo="Carga global dividida entre carga supervisionada e MMGD" parcelas={parcelas} />

      {/* Indicadores complementares do snapshot (não cabem na barra: não são parcelas do total) */}
      <dl className="mt-4 grid gap-4 border-t border-line pt-3 sm:grid-cols-2">
        <div>
          <dt className="rotulo">MMGD na geração</dt>
          <dd className="kpi mt-1 text-xl text-ink">{formatPct(c.percentualMmgdNaGeracao)}%</dd>
        </div>
        <div>
          <dt className="rotulo">MMGD ÷ capacidade instalada</dt>
          <dd className="kpi mt-1 text-xl text-ink">{formatPct(c.mmgdSobreCapacidadeInstalada * 100)}%</dd>
        </div>
      </dl>
    </Card>
  )
}

/**
 * Coluna "Alertas ativos" (padrão do Figma): riscos por severidade, cada um levando ao seu
 * Detalhe do Alerta, e o montante previsto por razão no rodapé. Respeita os filtros da topbar.
 */
function AlertasAtivos({ riscos }: { riscos: RiscoUsina[] }) {
  const { visiveis, ocultos } = useFiltradosPorSeveridade(ordenarPorSeveridade(riscos), (r) => r.severidade)
  const porRazao = montantePorRazao(visiveis)
  const porHorizonte = contarPor(visiveis, (r) => r.horizonte, HorizonteSchema.options)

  return (
    <Card
      flush
      title="Alertas ativos"
      className="xl:sticky xl:top-0 xl:max-h-[calc(100dvh-7.5rem)]"
      actions={
        <>
          <MockTag mock={riscos.some((r) => r.mock)} />
          <span className="kpi border border-risk-critical/40 bg-risk-critical/10 px-1.5 text-[11px] text-risk-critical">
            {visiveis.length}
          </span>
        </>
      }
    >
      <div className="flex h-full flex-col">
        <ul className="flex-1 divide-y divide-line/60 overflow-y-auto">
          {visiveis.map((r) => (
            <li key={r.id}>
              <Link
                to={rotaDetalheAlerta(r.id)}
                className={`block border-l-2 px-3.5 py-2.5 hover:bg-surface-raised ${RISK_STYLES[r.severidade].barra}`}
              >
                <span className="flex items-center justify-between gap-2">
                  <span className="flex items-center gap-1.5">
                    <RazaoBadge razao={r.razao} />
                    <span className="font-mono text-[10px] text-ink-faint">{r.uf}</span>
                  </span>
                  <span className="kpi text-[11px] text-ink-faint">{r.horizonte}</span>
                </span>
                <span className="mt-1 block truncate text-body text-ink">{r.nome}</span>
                <span className="mt-1 flex items-baseline justify-between">
                  <span className="kpi text-sm font-semibold text-ink">
                    {formatMw(r.montanteMw)} <span className="text-[10px] font-normal text-ink-muted">MW</span>
                  </span>
                  <span className="kpi text-xs text-ink-muted">{formatPct(r.probabilidadePct, 0)}%</span>
                </span>
                {/* probabilidade como barra fina de magnitude (cor única; a severidade é a borda) */}
                <span className="mt-1.5 block h-0.5 bg-line" aria-hidden>
                  <span className="block h-full bg-accent" style={{ width: `${r.probabilidadePct}%` }} />
                </span>
              </Link>
            </li>
          ))}
          {visiveis.length === 0 && <li className="px-4 py-6 text-center text-xs text-ink-muted">Nenhum alerta visível.</li>}
        </ul>

        <AvisoFiltro ocultos={ocultos} className="border-t border-line px-3.5 py-2" />

        <div className="border-t border-line">
          <p className="rotulo px-3.5 pt-2.5 text-[10px]">Montante previsto por razão</p>
          <dl className="grid grid-cols-3 divide-x divide-line/60">
            {RazaoSchema.options.map((razao) => (
              <div key={razao} className="px-2 py-2.5 text-center" title={RAZAO_INFO[razao].nome}>
                <dt className="flex items-center justify-center gap-1.5 font-mono text-[10px] font-semibold text-ink-muted">
                  <span className={`size-1.5 rounded-full ${RAZAO_INFO[razao].dot}`} aria-hidden />
                  {razao}
                </dt>
                <dd className="kpi mt-1 text-sm text-ink">{formatMw(porRazao[razao])}</dd>
              </div>
            ))}
          </dl>
          <p className="rotulo border-t border-line/60 px-3.5 pt-2.5 text-[10px]">Alertas por horizonte</p>
          <dl className="grid grid-cols-3 divide-x divide-line/60">
            {HorizonteSchema.options.map((h) => (
              <div key={h} className="px-2 py-2.5 text-center">
                <dt className="font-mono text-[10px] font-semibold text-ink-muted">{h}</dt>
                <dd className="kpi mt-1 text-sm text-ink">{porHorizonte[h]}</dd>
              </div>
            ))}
          </dl>
          <Link to={LISTA.path} className="flex items-center justify-center gap-1 border-t border-line py-2 text-xs text-accent hover:bg-surface-raised">
            {LISTA.label} <ArrowRight className="size-3.5" aria-hidden />
          </Link>
        </div>
      </div>
    </Card>
  )
}
