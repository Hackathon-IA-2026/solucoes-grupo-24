/**
 * Despacho preditivo (protótipo, painel "operacao"). Porte de 02-PROTOTIPO/web/js/views/operacao.js.
 * Carga medida − MMGD estimada = carga supervisionada, com banda P10–P90 e horizontes 30 min/3 h/D+1.
 */
import { Api, type Envelope } from '../api'
import { lineChart } from '../charts'
import { usePersistido, useOraculo } from '../estado'
import { lastFinite, num, pct, signed } from '../format'
import { BarRow, Chip, Conteudo, Grafico, Kpi, OCard, Pagina, Proveniencia, StatLines, Vazio, useApi } from '../ui'

/* eslint-disable @typescript-eslint/no-explicit-any */
type Dado = any

const HZ: Record<string, string> = { '30min': '30 min', '3h': '3 h', d1: 'D+1' }

export default function Operacao() {
  const { area } = useOraculo()
  const [horizon, setHorizon] = usePersistido('oraculo.horizon', '3h')
  const [asym, setAsym] = usePersistido('oraculo.asymmetric', true)
  const estado = useApi(() => Promise.all([Api.decomposition(area, 72), Api.forecast(area, horizon, asym)]), [area, horizon, asym])

  return (
    <Pagina>
      <Conteudo estado={estado} texto="Decompondo a carga e treinando o preditor…">
        {([decB, fcB]) => <Corpo decB={decB} fcB={fcB} horizon={horizon} asym={asym} setHorizon={setHorizon} setAsym={setAsym} />}
      </Conteudo>
    </Pagina>
  )
}

function Corpo({
  decB,
  fcB,
  horizon,
  asym,
  setHorizon,
  setAsym,
}: {
  decB: Envelope
  fcB: Envelope
  horizon: string
  asym: boolean
  setHorizon: (h: string) => void
  setAsym: (a: boolean) => void
}) {
  const d = decB.data as Dado
  const f = fcB.data as Dado
  const lastLoad = lastFinite(d.carga_supervisionada)
  const mmgdPeak = Math.max(...(d.mmgd_estimada || [0]).map((v: number | null) => (v === null || !Number.isFinite(v) ? 0 : v)))
  const m = f.metrics || {}
  const tr = f.train || {}

  return (
    <>
      <div className="grid g4" style={{ marginBottom: 14 }}>
        <Kpi label="Carga supervisionada (último ponto)" value={num(lastLoad)} unit="MWmed" foot={'Área ' + d.area + ' · grade horária'} accent="teal" />
        <Kpi label="MMGD estimada — pico na janela" value={num(mmgdPeak)} unit="MWmed" foot={'Participação máxima ' + pct(d.mmgd_share_peak, 1) + ' da carga global'} accent="amber" />
        <Kpi label="Mínima supervisionada" value={num(d.min_supervised_mw)} unit="MWmed" foot={'em ' + String(d.min_supervised_at || '').replace('T', ' ')} accent="green" />
        <Kpi label="Maior rampa horária" value={num(d.max_ramp_mw_h)} unit="MW/h" foot={'amplitude diária ' + num(d.daily_amplitude_mw) + ' MW'} accent="crimson" />
      </div>

      <div className="grid g-2-1" style={{ marginBottom: 14 }}>
        <OCard
          title="Decomposição da carga · últimas 72 h"
          hint={'identidade verificada · resíduo ' + num(d.identity_residual_max, 6)}
          note={'A MMGD não é medida: é estimada pelo método do envelope (' + ((d.mmgd || {}).method || '—') + '). ' + ((d.mmgd || {}).bias_note || '')}
        >
          <Grafico
            deps={[d]}
            desenhar={(el) =>
              lineChart(el, {
                index: d.index,
                height: 268,
                compact: true,
                yLabel: 'MWmed',
                series: [
                  { label: 'Carga global (estimada)', values: d.carga_global, color: 'muted', style: 'dash' },
                  { label: 'MMGD estimada', values: d.mmgd_estimada, color: 'amber', area: true },
                  { label: 'Carga supervisionada', values: d.carga_supervisionada, color: 'teal', width: 2.2 },
                ],
              })
            }
          />
        </OCard>
        <OCard title="Fator de nebulosidade e irradiância" note="O fator de nebulosidade é o que separa a geração potencial de céu claro da geração provável.">
          <Grafico
            deps={[d]}
            desenhar={(el) =>
              lineChart(el, {
                index: d.index,
                height: 268,
                digits: 2,
                series: [
                  { label: 'Irradiância céu claro (norm.)', values: d.ghi_norm, color: 'navy', area: true, digits: 2 },
                  { label: 'Fator de nebulosidade', values: d.cloud_factor, color: 'amber', digits: 2 },
                ],
              })
            }
          />
        </OCard>
      </div>

      <OCard
        title="Previsão da carga supervisionada"
        hint={'treino ' + num(tr.train_rows) + ' h · teste ' + num(tr.test_rows) + ' h · corte ' + String(tr.cut_at || '').replace('T', ' ')}
        note={'Métricas calculadas sobre todo o conjunto de teste; o gráfico mostra a janela recente. ' + lossNote(f)}
      >
        <div className="chips" style={{ marginBottom: 10 }}>
          {Object.keys(HZ).map((hz) => (
            <Chip key={hz} on={horizon === hz} onClick={() => setHorizon(hz)}>
              {HZ[hz]}
            </Chip>
          ))}
          <Chip on={asym} onClick={() => setAsym(!asym)} title="Liga e desliga a perda assimétrica por patamar">
            perda assimétrica {asym ? 'ativa' : 'desligada'}
          </Chip>
        </div>
        <Grafico
          deps={[f]}
          desenhar={(el) =>
            lineChart(el, {
              index: f.index,
              height: 300,
              compact: true,
              yLabel: 'MWmed',
              bands: [{ lower: f.p10, upper: f.p90, color: 'teal', opacity: 0.2, label: 'Banda P10–P90' }],
              series: [
                { label: 'Observado', values: f.observed, color: 'ink', width: 2.2 },
                { label: 'P50 previsto', values: f.p50, color: 'teal', width: 2 },
                { label: 'Persistência', values: f.baseline_persistence, color: 'muted', style: 'dash' },
                { label: 'Sazonal-ingênuo', values: f.baseline_seasonal, color: 'purple', style: 'dash' },
              ],
            })
          }
        />
      </OCard>

      <div className="grid g3" style={{ marginTop: 14 }}>
        <OCard title="Desempenho no teste">
          <StatLines
            pares={[
              ['MAE', num(m.mae, 1) + ' MW'],
              ['RMSE', num(m.rmse, 1) + ' MW'],
              ['MAPE', num(m.mape, 2) + '%'],
              ['Viés', signed(m.bias, 1) + ' MW'],
              ['Erro de rampa', num(m.ramp_mae_mw_h, 1) + ' MW/h'],
              ['Skill vs. persistência', <Skill key="p" v={(f.skill || {}).vs_persistence} />],
              ['Skill vs. sazonal-ingênuo', <Skill key="s" v={(f.skill || {}).vs_seasonal} />],
            ]}
          />
        </OCard>
        <OCard title="Erro por patamar operativo">
          <TabelaPatamar byP={f.by_patamar} />
        </OCard>
        <OCard title="Peso por grupo de variável" note="Contribuição relativa dos coeficientes da mediana, escalada pelo desvio de cada variável.">
          {(f.drivers || []).length ? (f.drivers as Dado[]).map((g) => <BarRow key={g.group} label={g.group} frac={g.weight} value={pct(g.weight, 1)} />) : <Vazio>—</Vazio>}
        </OCard>
      </div>
      <Proveniencia body={decB} />
    </>
  )
}

function lossNote(f: Dado): string {
  const l = f.loss || {}
  if (!f.asymmetric) return 'Perda simétrica: todos os patamares pesam igual.'
  const w = l.weights_by_patamar || {}
  const parts = Object.keys(w)
    .filter((k) => k !== 'base')
    .map((k) => k.replace(/_/g, ' ') + ' ' + w[k].subestimacao + '/' + w[k].superestimacao)
  return 'Perda assimétrica (subestimação/superestimação): ' + parts.join(' · ') + '.'
}

function TabelaPatamar({ byP }: { byP: Dado }) {
  const chaves = Object.keys(byP || {})
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Patamar</th>
            <th className="num">MAE</th>
            <th className="num">Viés</th>
            <th className="num">n</th>
          </tr>
        </thead>
        <tbody>
          {chaves.length ? (
            chaves.map((k) => {
              const v = byP[k] || {}
              return (
                <tr key={k}>
                  <td>{k.replace(/_/g, ' ')}</td>
                  <td className="num">{num(v.mae, 1)}</td>
                  <td className="num">{signed(v.bias, 1)}</td>
                  <td className="num">{num(v.n)}</td>
                </tr>
              )
            })
          ) : (
            <tr>
              <td colSpan={4}>—</td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  )
}

function Skill({ v }: { v: number | null | undefined }) {
  if (v === null || v === undefined || !Number.isFinite(v)) return <>—</>
  return <span className={v > 0 ? 'pos' : 'neg'}>{signed(v, 3)}</span>
}
