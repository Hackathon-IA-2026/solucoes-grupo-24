/**
 * Curva de previsão probabilística: banda P10–P90 sombreada + linha P50, com o trecho de
 * maior rampa destacado e rotulado ("15,8 GW / 3h") e os patamares de carga ao fundo.
 *
 * Decisões (guia de dataviz):
 * - Uma série (carga supervisionada) com incerteza: banda translúcida da mesma cor da
 *   linha, não três linhas concorrentes. P10/P90 aparecem como bordas finas da banda.
 * - Cores via CSS vars das tokens (--color-*), nunca hex solto: o tema continua sendo
 *   definido só em index.css.
 * - Rampa: faixa de fundo discreta + segmento do P50 reforçado em cor de texto (não é uma
 *   categoria nem um status, então não usa cor de série nem de risco) + rótulo direto.
 * - Patamares (mínima diurna e ponta noturna, de Backend/config/processamento.yaml): tinta de
 *   fundo muito leve com rótulo — são os dois horários em que o erro custa mais (perda
 *   assimétrica do planejamento v2), então o operador precisa vê-los na curva.
 * - Tooltip com crosshair mostrando os três quantis no instante sob o cursor.
 * - Eixo Y em GW começando perto do mínimo da banda (curva de carga, não magnitude a
 *   partir de zero); grade horizontal recessiva, sem grade vertical.
 */
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceArea,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  type TooltipContentProps,
} from 'recharts'
import { formatIntervalo, PATAMARES, type ChavePatamar } from '../../content/calendario'
import type { PrevisaoCurva } from '../../data/types'
import { trechoDeRampa, trechosNoIntervalo } from '../../data/derivados'
import { ticksRedondos } from '../../utils/escala'
import { formatDataHoraBrt, formatGw, formatHoraBrt, formatNum } from '../../utils/format'

const COR = {
  serie: 'var(--color-accent)',
  grade: 'var(--color-line)',
  eixo: 'var(--color-ink-faint)',
  rampa: 'var(--color-ink)',
  rotulo: 'var(--color-ink-muted)',
}
const TICK = { fill: COR.eixo, fontSize: 11, fontFamily: 'var(--font-mono)' }

/**
 * Patamares desenhados ao fundo e a tinta de cada um. A rampa vespertina fica de fora: o
 * trecho de MAIOR rampa já é destacado com o valor calculado, e duas marcas de "rampa" na
 * mesma região confundiriam.
 */
const TINTA_PATAMAR: Partial<Record<ChavePatamar, { cor: string; amostra: string }>> = {
  minima_diurna: { cor: 'var(--color-patamar-dia)', amostra: 'bg-patamar-dia/25' },
  ponta_noturna: { cor: 'var(--color-patamar-noite)', amostra: 'bg-patamar-noite/30' },
}
/** Patamares com faixa no gráfico, na ordem do dia (nome e horas vêm da config do Backend). */
const PATAMARES_DESENHADOS = PATAMARES.flatMap((p) => {
  const tinta = TINTA_PATAMAR[p.chave]
  return tinta ? [{ ...p, ...tinta }] : []
})

interface Linha {
  t: string
  p10: number
  p50: number
  p90: number
  banda: [number, number]
  /** P50 só dentro do trecho de rampa (null fora), para desenhar o segmento destacado */
  rampa: number | null
}

export function GraficoPrevisao({ curva, altura = 'h-80' }: { curva: PrevisaoCurva; altura?: string }) {
  const trecho = trechoDeRampa(curva.pontos, curva.janelaRampaHoras)
  const dados: Linha[] = curva.pontos.map((p, i) => ({
    t: p.timestamp,
    p10: p.p10,
    p50: p.p50,
    p90: p.p90,
    banda: [p.p10, p.p90],
    rampa: trecho && i >= trecho.inicio && i <= trecho.fim ? p.p50 : null,
  }))
  const min = Math.min(...curva.pontos.map((p) => p.p10))
  const max = Math.max(...curva.pontos.map((p) => p.p90))
  // Folga de 5% em cada lado; ticks redondos (regra única de eixo em utils/escala.ts).
  const { dominio, ticks: ticksY } = ticksRedondos(min * 0.95, max * 1.05)

  // Faixas de patamar: um ReferenceArea por trecho contíguo dentro das horas do patamar.
  const faixas = PATAMARES_DESENHADOS.flatMap((p) =>
    trechosNoIntervalo(curva.pontos, p.horas).map((t) => ({ ...t, cor: p.cor, nome: p.nome, chave: p.chave })),
  )

  return (
    <div className={`${altura} w-full`} role="img" aria-label={`Previsão de carga supervisionada, horizonte ${curva.horizonte}, P10 a P90`}>
      <ResponsiveContainer>
        <ComposedChart data={dados} margin={{ top: 28, right: 16, bottom: 0, left: 0 }}>
          <CartesianGrid stroke={COR.grade} strokeDasharray="2 4" vertical={false} />
          <XAxis dataKey="t" tickFormatter={formatHoraBrt} interval="preserveStartEnd" minTickGap={28} stroke={COR.eixo} tick={TICK} tickLine={false} />
          <YAxis
            domain={dominio}
            ticks={ticksY}
            tickFormatter={(v: number) => `${formatNum(v / 1000, 0)} GW`}
            width={60}
            stroke={COR.eixo}
            tick={TICK}
            tickLine={false}
            axisLine={false}
          />

          {faixas.map((f) => (
            <ReferenceArea
              key={`${f.chave}-${f.inicio}`}
              x1={dados[f.inicio].t}
              x2={dados[f.fim].t}
              fill={f.cor}
              fillOpacity={0.045}
              strokeOpacity={0}
              label={{ value: f.nome.toUpperCase(), position: 'insideTopLeft', fill: COR.rotulo, fontSize: 10, fontFamily: 'var(--font-mono)' }}
            />
          ))}

          {trecho && (
            <ReferenceArea
              x1={dados[trecho.inicio].t}
              x2={dados[trecho.fim].t}
              fill={COR.rampa}
              fillOpacity={0.05}
              stroke={COR.rampa}
              strokeOpacity={0.25}
              strokeDasharray="3 3"
              label={{
                value: `▲ ${formatGw(trecho.variacaoMw)} GW / ${curva.janelaRampaHoras}h`,
                position: 'top',
                fill: COR.rampa,
                fontSize: 12,
                fontFamily: 'var(--font-mono)',
                fontWeight: 600,
              }}
            />
          )}

          {/* banda de incerteza P10–P90 (Area de intervalo: dataKey devolve [baixo, alto]) */}
          <Area
            dataKey="banda"
            stroke={COR.serie}
            strokeOpacity={0.35}
            strokeWidth={1}
            fill={COR.serie}
            fillOpacity={0.14}
            isAnimationActive={false}
            activeDot={false}
          />
          <Line dataKey="p50" stroke={COR.serie} strokeWidth={2} dot={false} isAnimationActive={false} activeDot={{ r: 4, strokeWidth: 2, stroke: 'var(--color-surface)' }} />
          <Line dataKey="rampa" stroke={COR.rampa} strokeWidth={3} dot={false} connectNulls={false} isAnimationActive={false} activeDot={false} />

          <Tooltip content={TooltipQuantis} cursor={{ stroke: COR.eixo, strokeDasharray: '3 3' }} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
}

/** Legenda do gráfico (P50, banda, rampa e patamares), reaproveitada pelas telas que o usam. */
export function LegendaPrevisao({ janelaRampaHoras }: { janelaRampaHoras: number }) {
  return (
    <ul className="flex flex-wrap gap-x-5 gap-y-1.5 text-xs text-ink-muted">
      <li className="flex items-center gap-2">
        <span className="h-0.5 w-5 bg-accent" aria-hidden /> P50 (mediana)
      </li>
      <li className="flex items-center gap-2">
        <span className="h-3 w-5 border border-accent/40 bg-accent/15" aria-hidden /> Banda P10–P90
      </li>
      <li className="flex items-center gap-2">
        <span className="h-1 w-5 bg-ink" aria-hidden /> Maior rampa em {janelaRampaHoras}h
      </li>
      {PATAMARES_DESENHADOS.map((p) => (
        <li key={p.chave} className="flex items-center gap-2">
          <span className={`h-3 w-5 ${p.amostra}`} aria-hidden /> {p.nome}{' '}
          <span className="kpi text-ink-faint">{formatIntervalo(p.horas)}</span>
        </li>
      ))}
    </ul>
  )
}

function TooltipQuantis({ active, payload }: TooltipContentProps) {
  if (!active || !payload?.length) return null
  const l = payload[0].payload as Linha
  const linhas: [string, number][] = [
    ['P90', l.p90],
    ['P50', l.p50],
    ['P10', l.p10],
  ]
  return (
    <div className="border border-line bg-fundo px-3 py-2 text-xs shadow-lg">
      <p className="mb-1 text-ink-muted">{formatDataHoraBrt(l.t)} BRT</p>
      {linhas.map(([q, v]) => (
        <p key={q} className="kpi flex justify-between gap-4">
          <span className={q === 'P50' ? 'text-ink' : 'text-ink-muted'}>{q}</span>
          <span className="text-ink">{formatGw(v)} GW</span>
        </p>
      ))}
    </div>
  )
}
