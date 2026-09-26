/**
 * Visão Geral: 3 KPIs de destaque (carga supervisionada, MMGD, risco de curtailment) e a
 * composição da carga global do CargaSnapshot.
 */
import { BarraComposicao } from '../components/charts/BarraComposicao'
import { Card } from '../components/ui/Card'
import { Carregando, ErroDados } from '../components/ui/Estado'
import { KpiCard } from '../components/ui/KpiCard'
import { MockTag } from '../components/ui/MockTag'
import { SeverityBadge } from '../components/ui/SeverityBadge'
import { getCarga, getRiscos } from '../data/dataSource'
import { composicaoCarga, montanteEmRiscoMw, riscoAgregadoPct, severidadePorProbabilidade } from '../data/derivados'
import type { CargaSnapshot, RiscoUsina } from '../data/types'
import { useDados } from '../data/useDados'
import { formatGw, formatHoraBrt, formatMw, formatPct } from '../utils/format'

// Rótulo e cor de cada parcela (ordem fixa: supervisionada = chart-1, MMGD = chart-2).
const SERIES = {
  supervisionada: { rotulo: 'Carga supervisionada (atendida pelo SIN)', cor: 'bg-chart-1' },
  mmgd: { rotulo: 'MMGD estimada (geração distribuída)', cor: 'bg-chart-2' },
} as const

export default function VisaoGeral() {
  // getCarga/getRiscos são referências estáveis de módulo: o efeito do hook roda uma vez.
  const carga = useDados(getCarga)
  const riscos = useDados(getRiscos)

  return (
    <div className="space-y-6">
      <div className="grid gap-4 lg:grid-cols-3">
        {carga.status === 'ok' ? (
          <KpisCarga c={carga.data} />
        ) : carga.status === 'erro' ? (
          <div className="lg:col-span-2"><ErroDados erro={carga.erro} /></div>
        ) : (
          <>
            <Carregando />
            <Carregando />
          </>
        )}
        {riscos.status === 'ok' ? (
          <KpiRisco riscos={riscos.data} />
        ) : riscos.status === 'erro' ? (
          <ErroDados erro={riscos.erro} />
        ) : (
          <Carregando />
        )}
      </div>

      {carga.status === 'ok' && <ComposicaoCarga c={carga.data} />}
      {carga.status === 'loading' && <Carregando altura="h-48" />}
    </div>
  )
}

function KpisCarga({ c }: { c: CargaSnapshot }) {
  return (
    <>
      <KpiCard
        label="Carga supervisionada"
        value={formatGw(c.cargaSupervisionadaMw)}
        unit="GW"
        actions={<MockTag mock={c.mock} />}
        hint={<>{formatMw(c.cargaSupervisionadaMw)} MW · {formatHoraBrt(c.timestampUtc)} BRT</>}
      />
      <KpiCard
        label="MMGD estimada"
        value={formatGw(c.mmgdEstimadaMw)}
        unit="GW"
        actions={<MockTag mock={c.mock} />}
        hint={<>{formatMw(c.mmgdEstimadaMw)} MW · {formatPct(c.percentualMmgdNaGeracao)}% da geração</>}
      />
    </>
  )
}

function KpiRisco({ riscos }: { riscos: RiscoUsina[] }) {
  const pct = riscoAgregadoPct(riscos)
  const algumMock = riscos.some((r) => r.mock)
  return (
    <KpiCard
      label="Risco de curtailment"
      value={pct === null ? '—' : formatPct(pct)}
      unit="%"
      actions={
        <>
          <MockTag mock={algumMock} />
          {pct !== null && <SeverityBadge level={severidadePorProbabilidade(pct)} />}
        </>
      }
      hint={
        <>
          média ponderada por MW · {riscos.length} usinas · {formatMw(montanteEmRiscoMw(riscos))} MW em risco
        </>
      }
    />
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
      <dl className="mt-6 grid gap-4 border-t border-line pt-4 sm:grid-cols-2">
        <div>
          <dt className="text-xs uppercase tracking-widest text-ink-muted">MMGD na geração</dt>
          <dd className="kpi mt-1 text-2xl text-ink">{formatPct(c.percentualMmgdNaGeracao)}%</dd>
        </div>
        <div>
          <dt className="text-xs uppercase tracking-widest text-ink-muted">MMGD ÷ capacidade instalada</dt>
          <dd className="kpi mt-1 text-2xl text-ink">{formatPct(c.mmgdSobreCapacidadeInstalada * 100)}%</dd>
        </div>
      </dl>
    </Card>
  )
}
