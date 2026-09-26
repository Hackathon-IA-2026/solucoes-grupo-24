/**
 * Classes de consumo e assinatura da curva (protótipo, painel "classes"). Porte de
 * 02-PROTOTIPO/web/js/views/mapa.js (V.classes): perfis canônicos por classe e decomposição
 * da curva verificada de cada subsistema por mínimos quadrados não negativos.
 */
import { Api, type Envelope } from '../api'
import { lineChart } from '../charts'
import { num, pct } from '../format'
import { BarRow, Conteudo, Grafico, OCard, Pagina, Proveniencia, StatLines, useApi } from '../ui'

/* eslint-disable @typescript-eslint/no-explicit-any */
type Dado = any

const CLASS_COLORS: Record<string, string> = { residencial: 'teal', comercial: 'navy', industrial: 'amber', rural: 'green' }

function WeightBars({ weights }: { weights: Dado }) {
  const w = weights || {}
  return (
    <>
      {['residencial', 'comercial', 'industrial', 'rural'].map((k) => (
        <BarRow key={k} label={k} frac={w[k] || 0} value={pct(w[k] || 0, 1)} color={CLASS_COLORS[k]} />
      ))}
    </>
  )
}

const ident = (v: unknown) => String(v)

export default function Classes() {
  const estado = useApi(() => Api.get('mapa/classes'), [])
  return (
    <Pagina>
      <Conteudo estado={estado} texto="Decompondo a curva de carga por subsistema…">
        {(body) => <Corpo body={body} />}
      </Conteudo>
    </Pagina>
  )
}

function Corpo({ body }: { body: Envelope }) {
  const d = body.data as Dado
  const canon = d.canonical || {}
  const subs: Dado[] = d.subsystems || []
  const classes: Dado[] = canon.classes || []
  const hours: string[] = (canon.hours || []).map((h: number) => String(h).padStart(2, '0') + 'h')
  const t = canon.footprint_thresholds_m2 || {}

  return (
    <>
      <div className="note-strip">{d.note}</div>

      <div className="grid g-2-1" style={{ marginBottom: 14 }}>
        <OCard title="Perfis canônicos por classe" note={canon.note || undefined}>
          <Grafico
            deps={[d]}
            desenhar={(el) =>
              lineChart(el, {
                index: hours,
                height: 280,
                digits: 4,
                xTicks: 8,
                formatTime: ident,
                zeroBase: true,
                series: classes.map((c) => ({ label: c.label, values: c.profile, color: CLASS_COLORS[c.key] || 'teal', digits: 4 })),
              })
            }
          />
        </OCard>
        <OCard
          title="Assinatura de fim de semana"
          note="Segunda assinatura, independente da forma horária: é o que separa comercial de industrial quando as duas têm platô diurno."
        >
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Classe</th>
                  <th className="num">fim de semana / dia útil</th>
                </tr>
              </thead>
              <tbody>
                {classes.map((c, i) => (
                  <tr key={c.key || i}>
                    <td>{c.label}</td>
                    <td className="num">{num(c.weekend_ratio, 2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </OCard>
      </div>

      <div className="grid g2" style={{ marginBottom: 14 }}>
        {subs.map((s, i) => (
          <OCard
            key={s.subsystem || i}
            title={s.subsystem + ' · ' + s.name}
            hint={s.label + ' · R² ' + num(s.r2, 3) + ' (' + (s.fit_quality || '—') + ')'}
            note={s.fit_warning || undefined}
          >
            <Grafico
              deps={[s]}
              desenhar={(el) =>
                lineChart(el, {
                  index: hours,
                  height: 200,
                  digits: 4,
                  xTicks: 6,
                  formatTime: ident,
                  series: [
                    { label: 'observado', values: s.observed, color: 'ink', width: 2.2, digits: 4 },
                    { label: 'ajustado', values: s.fitted, color: 'teal', style: 'dash', digits: 4 },
                  ],
                })
              }
            />
            <div style={{ marginTop: 10 }}>
              <WeightBars weights={s.weights} />
            </div>
          </OCard>
        ))}
      </div>

      <OCard title="Composição por subsistema" hint={'método: ' + ((subs[0] || {}).method || '—')}>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Subsistema</th>
                <th>Classe dominante</th>
                <th className="num">resid.</th>
                <th className="num">comerc.</th>
                <th className="num">indust.</th>
                <th className="num">rural</th>
                <th className="num">R²</th>
                <th className="num">fim de sem.</th>
                <th className="num">amostras</th>
              </tr>
            </thead>
            <tbody>
              {subs.map((s, i) => {
                const w = s.weights || {}
                return (
                  <tr key={s.subsystem || i}>
                    <td>
                      <strong>{s.subsystem}</strong> <span className="small faint">{s.name}</span>
                    </td>
                    <td>{s.label}</td>
                    <td className="num">{pct(w.residencial, 1)}</td>
                    <td className="num">{pct(w.comercial, 1)}</td>
                    <td className="num">{pct(w.industrial, 1)}</td>
                    <td className="num">{pct(w.rural, 1)}</td>
                    <td className="num">{num(s.r2, 3)}</td>
                    <td className="num">{num(s.weekend_ratio, 3)}</td>
                    <td className="num">{num(s.samples)}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </OCard>

      <div className="grid g2" style={{ marginTop: 14 }}>
        <OCard
          title="Limiares de área de telhado"
          note="Usados na evidência morfológica do Mapa Inteligente. A ponderação é por ÁREA, não por contagem: um galpão de 5.000 m² pesa muito mais na carga do que uma casa de 120 m²."
        >
          <StatLines
            pares={[
              ['Residencial', 'até ' + num(t.residencial_max) + ' m²'],
              ['Comercial', num(t.residencial_max) + ' a ' + num(t.comercial_max) + ' m²'],
              ['Industrial', 'acima de ' + num(t.comercial_max) + ' m²'],
            ]}
          />
        </OCard>
        <OCard title="Notas de cada classe">
          {classes.map((c, i) => (
            <div className="stat-line" style={{ display: 'block' }} key={c.key || i}>
              <div style={{ color: 'var(--o-' + (CLASS_COLORS[c.key] || 'teal') + ')', fontWeight: 600 }}>{c.label}</div>
              <div className="small muted">{c.note}</div>
            </div>
          ))}
        </OCard>
      </div>
      <Proveniencia body={body} />
    </>
  )
}
