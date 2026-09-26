/**
 * Curtailment observado (protótipo, painel "curtailment"). Porte de V.curtailment em
 * 02-PROTOTIPO/web/js/views/analise.js: montante, razão e origem da restrição a partir dos
 * registros de constrained-off do ONS.
 */
import { Api, type Envelope } from '../api'
import { heatStrip, stackedBars } from '../charts'
import { num, pct } from '../format'
import { Conteudo, Grafico, Kpi, OCard, Pagina, Proveniencia, ReasonTag, Vazio, useApi } from '../ui'

/* eslint-disable @typescript-eslint/no-explicit-any */
type Dado = any

const RAZOES = ['ENE', 'CNF', 'REL', 'PAR']
const CORES: Record<string, string> = { ENE: 'green', CNF: 'purple', REL: 'crimson', PAR: 'muted' }

export default function Curtailment() {
  const estado = useApi(() => Api.risk('d1', 'estado', 0), [])
  return (
    <Pagina>
      <Conteudo estado={estado} texto="Agregando os registros de constrained-off…">
        {(body) => <Corpo body={body} />}
      </Conteudo>
    </Pagina>
  )
}

function Corpo({ body }: { body: Envelope }) {
  const r = body.data as Dado
  const areas: Dado[] = (r.areas || []).slice()
  if (!areas.length) {
    return (
      <>
        <Vazio>Sem registros de constrained-off na janela carregada.</Vazio>
        <Proveniencia body={body} />
      </>
    )
  }
  areas.sort((a, b) => (b.history.total_cut_gwh || 0) - (a.history.total_cut_gwh || 0))

  const totalGwh = areas.reduce((s, a) => s + (a.history.total_cut_gwh || 0), 0)
  const peak = Math.max(...areas.map((a) => a.history.peak_cut_mw || 0))
  const meanOcc = areas.reduce((s, a) => s + (a.history.occurrence_rate || 0), 0) / areas.length
  const shares = aggregateReasons(areas)

  return (
    <>
      <div className="note-strip">
        A razão energética (ENE) é a única não ressarcida e é a que mais cresce desde abril de 2025. O O.R.A.C.U.L.O. foca o risco por razão energética; o corte é medida técnica para
        preservar segurança, confiabilidade e limites elétricos do SIN.
      </div>

      <div className="grid g4" style={{ marginBottom: 14 }}>
        <Kpi label="Energia restringida na janela" value={num(totalGwh, 1)} unit="GWh" foot={num(areas.length) + ' áreas com registro'} accent="crimson" />
        <Kpi label="Maior corte horário" value={num(peak)} unit="MWmed" foot="pico entre todas as áreas" accent="amber" />
        <Kpi label="Taxa média de ocorrência" value={pct(meanOcc, 1)} foot="horas com corte acima do limiar, na janela solar" accent="teal" />
        <Kpi label="Participação da razão ENE" value={pct(shares.ENE || 0, 1)} foot="do montante restringido nas áreas modeladas" accent="green" />
      </div>

      <div className="grid g2" style={{ marginBottom: 14 }}>
        <OCard title="Montante restringido por área e razão" note="Códigos do ONS: REL indisponibilidade externa · CNF confiabilidade · ENE razão energética · PAR parecer de acesso.">
          <Grafico
            deps={[r]}
            desenhar={(el) =>
              stackedBars(el, {
                labels: areas.map((a) => a.area),
                unit: 'GWh',
                height: 260,
                stacks: RAZOES.map((rz) => ({
                  label: rz,
                  color: CORES[rz],
                  values: areas.map((a) => ((a.history.reason_shares || {})[rz] || 0) * (a.history.total_cut_gwh || 0)),
                })),
              })
            }
          />
        </OCard>
        <OCard title="Probabilidade horária por área" note="Cada linha é uma área; cada coluna, uma hora da janela prospectiva. Intensidade proporcional à probabilidade.">
          <Grafico
            deps={[r]}
            desenhar={(el) =>
              heatStrip(el, {
                rows: areas.map((a) => ({
                  label: a.area,
                  values: (a.hourly_probability || []).map((v: number | null) => (v === null ? null : v)),
                })),
                raw: areas.map((a) => a.hourly_probability || []),
                colLabel: (c) => {
                  const idx = (areas[0].hourly_index || [])[c]
                  return idx ? String(idx).slice(11, 13) + 'h' : c + 'h'
                },
                color: 'crimson',
                seriesLabel: 'P(restrição)',
                digits: 3,
              })
            }
          />
        </OCard>
      </div>

      <OCard title="Histórico por área" hint="limiar de rótulo = 10% da disponibilidade agregada (p95)">
        <TabelaAreas areas={areas} />
      </OCard>

      <div className="grid g2" style={{ marginTop: 14 }}>
        <OCard title="Códigos de razão">
          <TabelaDict dict={r.reasons} />
        </OCard>
        <OCard title="Códigos de origem">
          <TabelaDict dict={r.origins} />
        </OCard>
      </div>
      <Proveniencia body={body} />
    </>
  )
}

function aggregateReasons(areas: Dado[]): Record<string, number> {
  const tot: Record<string, number> = {}
  let all = 0
  areas.forEach((a) => {
    const g = a.history.total_cut_gwh || 0
    all += g
    const sh = a.history.reason_shares || {}
    Object.keys(sh).forEach((k) => {
      tot[k] = (tot[k] || 0) + sh[k] * g
    })
  })
  const out: Record<string, number> = {}
  Object.keys(tot).forEach((k) => {
    out[k] = all ? tot[k] / all : 0
  })
  return out
}

function TabelaAreas({ areas }: { areas: Dado[] }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Área</th>
            <th className="num">Horas</th>
            <th className="num">Corte (GWh)</th>
            <th className="num">Pico (MW)</th>
            <th className="num">Ocorrência</th>
            <th>Composição por razão</th>
            <th className="num">Criticidade</th>
          </tr>
        </thead>
        <tbody>
          {areas.map((a) => {
            const h = a.history || {}
            const sh = h.reason_shares || {}
            return (
              <tr key={a.area}>
                <td>
                  <strong>{a.area}</strong> <span className="small faint">{a.subsystem}</span>
                </td>
                <td className="num">{num(h.hours)}</td>
                <td className="num">{num(h.total_cut_gwh, 2)}</td>
                <td className="num">{num(h.peak_cut_mw)}</td>
                <td className="num">{pct(h.occurrence_rate, 1)}</td>
                <td>
                  {['ENE', 'CNF', 'REL'].map((k, i) => (
                    <span key={k}>
                      {i ? ' ' : null}
                      <span className={'chip ' + (k === 'ENE' ? 'green' : k === 'CNF' ? '' : 'crimson')}>
                        {k} {pct(sh[k] || 0, 0)}
                      </span>
                    </span>
                  ))}
                </td>
                <td className="num">{num(a.criticality, 2)}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function TabelaDict({ dict }: { dict: Record<string, string> | null | undefined }) {
  const d = dict || {}
  return (
    <div className="table-wrap">
      <table>
        <tbody>
          {Object.keys(d).map((k) => (
            <tr key={k}>
              <td>
                <ReasonTag code={k} />
              </td>
              <td>{d[k]}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
