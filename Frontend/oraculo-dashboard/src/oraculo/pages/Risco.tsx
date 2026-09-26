/**
 * Risco de curtailment e excedentes (protótipo, painel "risco"). Porte de V.risco em
 * 02-PROTOTIPO/web/js/views/operacao.js: mapa esquemático por UF, eventos priorizados por
 * severidade, alerta explicado com evidências e probabilidade horária da área selecionada.
 */
import { Api, type Envelope } from '../api'
import { lineChart } from '../charts'
import { usePersistido } from '../estado'
import { num, pct } from '../format'
import { Conteudo, Grafico, Kpi, OCard, Pagina, Proveniencia, ReasonTag, Vazio, useApi } from '../ui'

/* eslint-disable @typescript-eslint/no-explicit-any */
type Dado = any

// Arranjo geografico aproximado das UF (linhas x colunas).
const UF_GRID = [
  ['', '', '', '', '', 'AP', ''],
  ['AC', 'AM', '', 'PA', 'MA', '', 'RR'],
  ['', 'RO', 'MT', 'TO', 'PI', 'CE', 'RN'],
  ['', '', 'MS', 'GO', 'BA', 'PE', 'PB'],
  ['', '', '', 'MG', 'ES', 'AL', 'SE'],
  ['', '', 'PR', 'SP', 'RJ', '', ''],
  ['', '', 'RS', 'SC', '', '', ''],
]

function sevColor(s: number): string {
  return s >= 0.72 ? 'crimson' : s >= 0.55 ? 'amber' : 'green'
}

export default function Risco() {
  const [horizon] = usePersistido('oraculo.horizon', '3h')
  const estado = useApi(() => Api.risk(horizon === '30min' ? '30min' : horizon, 'estado', 0), [horizon])
  return (
    <Pagina>
      <Conteudo estado={estado} texto="Treinando o classificador de restrição por área…">
        {(body) => <Corpo body={body} horizon={horizon} />}
      </Conteudo>
    </Pagina>
  )
}

function Corpo({ body, horizon }: { body: Envelope; horizon: string }) {
  const r = body.data as Dado
  const areas: Dado[] = r.areas || []
  const events: Dado[] = r.events || []
  const [selAreaRaw, setSelArea] = usePersistido<string | null>('oraculo.selArea', null)

  if (!areas.length) {
    return (
      <>
        <Vazio>Sem áreas com histórico suficiente de constrained-off na janela carregada.</Vazio>
        <Proveniencia body={body} />
      </>
    )
  }
  const selArea: string = selAreaRaw && areas.some((a) => a.area === selAreaRaw) ? selAreaRaw : areas[0].area
  const totalMw = areas.reduce((s, a) => s + (a.expected_mw || 0), 0)
  const high = areas.filter((a) => a.probability >= 0.5).length
  const ene = areas.filter((a) => a.reason === 'ENE').length

  return (
    <>
      <div className="grid g4" style={{ marginBottom: 14 }}>
        <Kpi
          label="Áreas com risco ≥ 50%"
          value={num(high)}
          unit={'de ' + areas.length}
          foot={'janela de ' + (horizon === 'd1' ? 'D+1' : horizon)}
          accent="amber"
        />
        <Kpi label="Potência esperada de corte" value={num(totalMw)} unit="MW" foot="soma de E[corte] nas áreas modeladas" accent="crimson" />
        <Kpi label="Predominância de razão energética" value={num(ene)} unit="áreas" foot="ENE é a razão que mais cresce desde abr/2025" accent="green" />
        <Kpi
          label="AUC fora da amostra (mediana)"
          value={num((r.model || {}).auc_oos_median, 3)}
          foot="avaliado só na janela solar, onde a pergunta é não trivial"
          accent="teal"
        />
      </div>

      <div className="grid g-1-2" style={{ marginBottom: 14 }}>
        <OCard
          title="Mapa esquemático · severidade por área"
          note="Arranjo geográfico aproximado por unidade federativa. A granularidade-alvo em produção é área de concessão e transformação de fronteira, que exige a BDGD."
        >
          <Mapa areas={areas} selArea={selArea} onSel={setSelArea} />
          <div className="legend">
            <span className="legend-item">
              <span className="legend-swatch" style={{ background: 'var(--o-crimson)' }} />
              severidade alta
            </span>
            <span className="legend-item">
              <span className="legend-swatch" style={{ background: 'var(--o-amber)' }} />
              média
            </span>
            <span className="legend-item">
              <span className="legend-swatch" style={{ background: 'var(--o-green)' }} />
              baixa
            </span>
          </div>
        </OCard>
        <OCard title="Eventos priorizados por severidade" hint="severidade = 0,45·P + 0,35·E[corte] + 0,20·criticidade">
          <div className="table-wrap scroll-y">
            <Eventos events={events} selArea={selArea} onSel={setSelArea} />
          </div>
        </OCard>
      </div>

      <div className="grid g-2-1">
        <div>
          <Alerta events={events} areas={areas} selArea={selArea} />
        </div>
        <OCard title="Probabilidade horária · área selecionada" note="Probabilidade calibrada por binning monotônico no conjunto de validação.">
          <Prob areas={areas} selArea={selArea} />
        </OCard>
      </div>
      <Proveniencia body={body} />
    </>
  )
}

function Mapa({ areas, selArea, onSel }: { areas: Dado[]; selArea: string; onSel: (uf: string) => void }) {
  const byUf: Record<string, Dado> = {}
  areas.forEach((a) => {
    byUf[a.area] = a
  })
  return (
    <div className="map-grid">
      {UF_GRID.flatMap((row, i) =>
        row.map((uf, j) => {
          const key = i + '-' + j
          if (!uf) return <div key={key} className="map-cell empty" />
          const a = byUf[uf]
          if (!a) {
            return (
              <div key={key} className="map-cell empty">
                <span className="uf">{uf}</span>
              </div>
            )
          }
          const c = sevColor(a.severity)
          return (
            <div
              key={key}
              className={'map-cell' + (selArea === uf ? ' sel' : '')}
              data-uf={uf}
              onClick={() => onSel(uf)}
              style={{ background: `color-mix(in srgb, var(--o-${c}) ${Math.round(12 + a.severity * 45)}%, var(--o-panel-2))` }}
            >
              <span className="uf">{uf}</span>
              <span className="mw">{num(a.expected_mw)} MW</span>
            </div>
          )
        }),
      )}
    </div>
  )
}

function Eventos({ events, selArea, onSel }: { events: Dado[]; selArea: string; onSel: (uf: string) => void }) {
  return (
    <table>
      <thead>
        <tr>
          <th>Área</th>
          <th>Razão</th>
          <th className="num">P</th>
          <th className="num">E[corte] MW</th>
          <th className="num">Sev.</th>
          <th>Patamar</th>
        </tr>
      </thead>
      <tbody>
        {events.map((e, i) => (
          <tr key={e.area + '-' + i} className={e.area === selArea ? 'sel' : ''} style={{ cursor: 'pointer' }} onClick={() => onSel(e.area)}>
            <td>
              <strong>{e.area}</strong>
              <br />
              <span className="small faint">{e.subsystem}</span>
            </td>
            <td>
              <ReasonTag code={e.reason} />
            </td>
            <td className="num">{pct(e.probability, 0)}</td>
            <td className="num">{num(e.expected_mw)}</td>
            <td className="num">{num(e.severity, 3)}</td>
            <td className="small">
              {String(e.patamar || '').replace(/_/g, ' ')}
              <br />
              {String(e.peak_hour).padStart(2, '0')}h
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function Alerta({ events, areas, selArea }: { events: Dado[]; areas: Dado[]; selArea: string }) {
  const e = events.find((x) => x.area === selArea) || events[0]
  if (!e) return <Vazio>Selecione uma área.</Vazio>
  const a = areas.find((x) => x.area === e.area) || {}
  const h = a.history || {}
  const rw: Record<string, number> = e.reason_weights || {}
  const motive = Object.keys(rw)
    .sort((x, y) => rw[y] - rw[x])
    .filter((k) => rw[k] > 0.01)
    .map((k) => pct(rw[k], 0) + ' ' + k)
    .join(' · ')
  const win = e.window || []
  return (
    <div className="alert">
      <div className="alert-title">⚠ Alerta — risco de curtailment · {e.area}</div>
      <div className="alert-main">
        Probabilidade de <strong>{pct(e.probability, 0)}</strong> de restrição com montante esperado de <strong>{num(e.expected_mw)} MW</strong>, na janela{' '}
        {String(win[0] || '').replace('T', ' ')} → {String(win[1] || '').replace('T', ' ')}.
      </div>
      <div className="alert-reason">
        Motivo predominante: <ReasonTag code={e.reason} /> {e.reason_label || ''} · decomposição {motive}
      </div>
      <div className="evidence">
        {(e.evidence || []).map((ev: Dado, i: number) => (
          <div className="evidence-row" key={i}>
            <span className="lbl">{ev.label}</span>
            <span className="val">{ev.value}</span>
            <span className="src">fonte: {ev.source}</span>
          </div>
        ))}
      </div>
      <ul className="actions">
        {(e.recommended_actions || []).map((x: string, i: number) => (
          <li key={i}>{x}</li>
        ))}
      </ul>
      <div className="alert-src">
        ponto de conexão: {e.point_of_connection || '—'} · histórico da área: corte total {num(h.total_cut_gwh, 2)} GWh · taxa de ocorrência{' '}
        {pct(h.occurrence_rate, 1)} · limiar de rótulo {num(h.threshold_mw, 1)} MW · AUC {num(a.auc_oos, 3)}
      </div>
      <div className="alert-src">As ações são apoio à decisão humana. O produto não automatiza despacho nem substitui procedimentos operativos.</div>
    </div>
  )
}

function Prob({ areas, selArea }: { areas: Dado[]; selArea: string }) {
  const a = areas.find((x) => x.area === selArea) || areas[0]
  if (!a) return null
  return (
    <Grafico
      deps={[a]}
      desenhar={(el) =>
        lineChart(el, {
          index: a.hourly_index || [],
          height: 300,
          digits: 2,
          yMin: 0,
          series: [{ label: 'P(restrição) — ' + a.area, values: a.hourly_probability || [], color: sevColor(a.severity), area: true, digits: 3 }],
        })
      }
    />
  )
}
