/**
 * Perfis representativos e insumos ao CLM (protótipo, painel "perfis"). Porte de V.perfis em
 * 02-PROTOTIPO/web/js/views/analise.js: perfis por dia-tipo e presença da MMGD.
 */
import { Api, type Envelope } from '../api'
import { lineChart } from '../charts'
import { useOraculo } from '../estado'
import { num, pct } from '../format'
import { Conteudo, Grafico, Kpi, OCard, Pagina, Proveniencia, StatLines, useApi } from '../ui'

/* eslint-disable @typescript-eslint/no-explicit-any */
type Dado = any

const CORES = ['amber', 'green', 'purple']
const hora = (x: unknown) => String(x).padStart(2, '0') + 'h'

export default function Perfis() {
  const { area } = useOraculo()
  const estado = useApi(() => Api.profiles(area), [area])
  return (
    <Pagina>
      <Conteudo estado={estado} texto="Construindo perfis por dia-tipo…">
        {(body) => <Corpo body={body} />}
      </Conteudo>
    </Pagina>
  )
}

function Corpo({ body }: { body: Envelope }) {
  const p = body.data as Dado
  const c = p.clm_inputs || {}
  const typedays: Dado[] = p.typedays || []

  return (
    <>
      <div className="note-strip">
        A solução <strong>não executa</strong> fluxo de potência nem estudos de estabilidade. Entrega insumos consistentes para os modelos oficiais e para os especialistas do ONS.
        Referência técnica: WECC — Composite Load Model Specification.
      </div>

      <div className="grid g4" style={{ marginBottom: 14 }}>
        <Kpi label="Fator de carga" value={num(c.load_factor, 3)} foot="média / máxima no período" accent="teal" />
        <Kpi label="Penetração solar no pico" value={pct(c.solar_penetration_peak, 1)} foot="participação máxima da MMGD na carga global" accent="amber" />
        <Kpi label="Âncora noturna" value={num(c.night_anchor_mw)} unit="MWmed" foot="carga média nas horas sem geração solar" accent="green" />
        <Kpi label="Rampa máxima" value={num(c.ramp_max_mw_h)} unit="MW/h" foot={'amplitude ' + num(c.amplitude_mw) + ' MW · ' + num(c.samples) + ' amostras'} accent="crimson" />
      </div>

      <div className="grid g3" style={{ marginBottom: 14 }}>
        {typedays.map((td, i) => (
          <OCard key={td.kind || i} title={td.label} hint={num(Math.max(...(td.samples || [0]))) + ' amostras/hora'}>
            <Grafico
              deps={[td]}
              desenhar={(el) =>
                lineChart(el, {
                  index: td.hours.map(hora),
                  height: 210,
                  compact: true,
                  xTicks: 6,
                  formatTime: (v) => String(v),
                  bands: [{ lower: td.carga_p10, upper: td.carga_p90, color: 'teal', opacity: 0.18, label: 'P10–P90' }],
                  series: [{ label: 'Carga P50', values: td.carga_p50, color: 'teal', width: 2 }],
                })
              }
            />
          </OCard>
        ))}
      </div>

      <div className="grid g-2-1">
        <OCard
          title="Perfil de MMGD estimada por dia-tipo"
          note="A MMGD é estimada, não medida. O perfil é o insumo que qualifica a representação equivalente da geração distribuída nos estudos."
        >
          <Grafico
            deps={[p]}
            desenhar={(el) =>
              lineChart(el, {
                index: (typedays[0] || { hours: [] }).hours.map(hora),
                height: 280,
                compact: true,
                xTicks: 8,
                formatTime: (v) => String(v),
                zeroBase: true,
                series: typedays.map((td, i) => ({
                  label: td.label,
                  values: td.mmgd_p50,
                  color: CORES[i % 3],
                  area: i === 0,
                  areaOpacity: 0.12,
                })),
              })
            }
          />
        </OCard>
        <OCard title="Insumos agregados propostos" note={p.note || ''}>
          <StatLines
            pares={[
              ['Fator de carga', num(c.load_factor, 4)],
              ['Penetração solar (pico)', pct(c.solar_penetration_peak, 2)],
              ['Âncora noturna', num(c.night_anchor_mw, 1) + ' MW'],
              ['Mínima supervisionada', num(c.min_supervised_mw, 1) + ' MW'],
              ['Máxima supervisionada', num(c.max_supervised_mw, 1) + ' MW'],
              ['Amplitude diária', num(c.amplitude_mw, 1) + ' MW'],
              ['Rampa máxima', num(c.ramp_max_mw_h, 1) + ' MW/h'],
              ['Amostras', num(c.samples)],
            ]}
          />
        </OCard>
      </div>
      <Proveniencia body={body} />
    </>
  )
}
