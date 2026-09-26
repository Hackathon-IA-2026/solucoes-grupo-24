/**
 * Erro diário do modelo vs. baseline (uma métrica por gráfico).
 *
 * Decisões (guia de dataviz):
 * - MAE e RMSE em gráficos SEPARADOS (small multiples), cada um com seu eixo: nunca dois
 *   eixos Y no mesmo gráfico.
 * - Modelo = accent (mesma cor da série de carga no Despacho Preditivo); baseline = linha
 *   tracejada neutra, lida como referência e não como segunda série concorrente.
 * - Tooltip com crosshair mostra os dois valores e a diferença no dia.
 */
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  type TooltipContentProps,
} from 'recharts'
import { ticksRedondos } from '../../utils/escala'
import { formatMw } from '../../utils/format'

const COR = {
  modelo: 'var(--color-accent)',
  baseline: 'var(--color-ink-muted)',
  grade: 'var(--color-line)',
  eixo: 'var(--color-ink-faint)',
}
const TICK = { fill: COR.eixo, fontSize: 11, fontFamily: 'var(--font-mono)' }

export interface PontoErro {
  data: string
  modelo: number
  baseline: number
}

/** "2026-09-24" -> "24/09" sem passar por Date (evita deslocar o dia pelo fuso). */
const diaMes = (iso: string) => `${iso.slice(8, 10)}/${iso.slice(5, 7)}`

export function GraficoErro({ dados, metrica, baselineNome }: { dados: PontoErro[]; metrica: string; baselineNome: string }) {
  // erro é magnitude: eixo começa em zero
  const { dominio, ticks } = ticksRedondos(0, Math.max(...dados.map((d) => Math.max(d.modelo, d.baseline))))
  return (
    <figure>
      <div className="h-56 w-full" role="img" aria-label={`${metrica} diário do modelo e do baseline ${baselineNome}, últimos 30 dias`}>
        <ResponsiveContainer>
          <LineChart data={dados} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
            <CartesianGrid stroke={COR.grade} strokeDasharray="2 4" vertical={false} />
            <XAxis dataKey="data" tickFormatter={diaMes} interval={6} stroke={COR.eixo} tick={TICK} tickLine={false} />
            <YAxis
              domain={dominio}
              ticks={ticks}
              tickFormatter={(v: number) => formatMw(v)}
              width={52}
              stroke={COR.eixo}
              tick={TICK}
              tickLine={false}
              axisLine={false}
            />
            <Line dataKey="baseline" name={baselineNome} stroke={COR.baseline} strokeWidth={2} strokeDasharray="5 4" dot={false} isAnimationActive={false} />
            <Line
              dataKey="modelo"
              name="Modelo"
              stroke={COR.modelo}
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
              activeDot={{ r: 4, strokeWidth: 2, stroke: 'var(--color-surface)' }}
            />
            <Tooltip content={(p) => <TooltipErro {...p} metrica={metrica} baselineNome={baselineNome} />} cursor={{ stroke: COR.eixo, strokeDasharray: '3 3' }} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <figcaption className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-xs text-ink-muted">
        <span className="flex items-center gap-2">
          <span className="h-0.5 w-5 rounded bg-accent" aria-hidden /> Modelo
        </span>
        <span className="flex items-center gap-2">
          <span className="w-5 border-t-2 border-dashed border-ink-muted" aria-hidden /> {baselineNome} (baseline)
        </span>
      </figcaption>
    </figure>
  )
}

function TooltipErro({ active, payload, metrica, baselineNome }: TooltipContentProps & { metrica: string; baselineNome: string }) {
  if (!active || !payload?.length) return null
  const p = payload[0].payload as PontoErro
  const ganho = p.baseline > 0 ? (1 - p.modelo / p.baseline) * 100 : 0
  return (
    <div className="rounded border border-line bg-fundo px-3 py-2 text-xs shadow-lg">
      <p className="mb-1 text-ink-muted">
        {diaMes(p.data)} · {metrica}
      </p>
      <p className="kpi flex justify-between gap-4 text-ink">
        <span>Modelo</span>
        <span>{formatMw(p.modelo)} MW</span>
      </p>
      <p className="kpi flex justify-between gap-4 text-ink-muted">
        <span>{baselineNome}</span>
        <span>{formatMw(p.baseline)} MW</span>
      </p>
      <p className="kpi mt-1 border-t border-line pt-1 text-ink-muted">{Math.round(ganho)}% menor que o baseline</p>
    </div>
  )
}
