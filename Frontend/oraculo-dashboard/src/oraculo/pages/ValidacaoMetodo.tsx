/**
 * Validação do método (protótipo, painel "validacao"). Porte de V.validacao em
 * 02-PROTOTIPO/web/js/views/confianca.js: backtest cronológico, baselines, métricas por
 * patamar e calibração probabilística.
 */
import { Api, type Envelope } from '../api'
import { lineChart, scatter } from '../charts'
import { usePersistido, useOraculo } from '../estado'
import { num, signed } from '../format'
import { Chip, Conteudo, Grafico, Kpi, OCard, Pagina, Proveniencia, useApi } from '../ui'

/* eslint-disable @typescript-eslint/no-explicit-any */
type Dado = any

const PATS = ['minima_diurna', 'rampa', 'ponta_noturna']
const label = (h: string) => ({ '30min': '30 min', '3h': '3 h', d1: 'D+1' })[h] || h

export default function ValidacaoMetodo() {
  const { area } = useOraculo()
  const [asym] = usePersistido('oraculo.asymmetric', true)
  const estado = useApi(() => Api.validation(area, asym), [area, asym])
  return (
    <Pagina>
      <Conteudo estado={estado} texto="Executando backtest cronológico em todos os horizontes…">
        {(body) => <Corpo body={body} />}
      </Conteudo>
    </Pagina>
  )
}

function Corpo({ body }: { body: Envelope }) {
  const v = body.data as Dado
  const split = v.split || {}
  const hz: Dado[] = v.horizons || []
  const eff = v.asymmetry_effect || {}
  const best = hz.reduce((b, x) => (x.mae && (!b.mae || x.mae < b.mae) ? x : b), {} as Dado)
  const h3 = hz.find((x) => x.horizon === '3h') || hz[0] || {}
  const cal: Dado[] = h3.calibration || []
  const series = (v.series || {})['3h'] || {}

  return (
    <>
      <div className="note-strip">
        Princípio: <strong>nenhuma promessa de desempenho sem teste; nenhum alerta sem evidência rastreável</strong>. A divisão é estritamente cronológica — divisão aleatória vazaria
        informação do futuro pelas variáveis de defasagem.
      </div>

      <div className="grid g4" style={{ marginBottom: 14 }}>
        <Kpi
          label="Corte cronológico"
          value={split.leakage_free ? <span className="pos">sem vazamento</span> : <span className="neg">verificar</span>}
          foot={num(split.train_rows) + ' h de treino · ' + num(split.test_rows) + ' h de teste'}
          accent="green"
        />
        <Kpi
          label="Instante do corte"
          value={<span style={{ fontSize: 16 }}>{String(split.cut_at || '—').replace('T', ' ')}</span>}
          foot="nenhum ponto de teste antecede o treino"
          accent="teal"
        />
        <Kpi label="Melhor MAE" value={num(best.mae, 1)} unit="MW" foot={'horizonte ' + (best.horizon || '—')} accent="amber" />
        <Kpi
          label="Função de perda"
          value={v.asymmetric ? 'assimétrica' : 'simétrica'}
          foot={v.asymmetric ? 'pesos por patamar ativos' : 'todos os patamares pesam igual'}
          accent="crimson"
        />
      </div>

      <OCard
        title="Desempenho por horizonte"
        hint="skill = 1 − MAE_modelo / MAE_baseline · positivo significa ganho"
        note="Um skill negativo aparece em vermelho e não é escondido: o modelo só é útil onde supera os baselines."
      >
        <TabelaHorizontes hz={hz} />
      </OCard>

      <div className="grid g2" style={{ margin: '14px 0' }}>
        <OCard
          title="Métricas por patamar operativo"
          note="Uma melhoria de MAE global que piora a ponta noturna é uma piora operacional. Por isso o recorte é obrigatório."
        >
          <TabelaPatamar hz={hz} />
        </OCard>
        <OCard
          title="Calibração probabilística"
          note="Um P90 que cobre 60% dos casos não é um P90. Desvio sistemático engana a decisão mais que um MAE alto."
        >
          <Grafico
            deps={[cal]}
            desenhar={(el) =>
              scatter(el, {
                points: cal
                  .filter((c) => c.empirical !== null)
                  .map((c) => ({
                    x: c.nominal,
                    y: c.empirical,
                    label: 'quantil P' + Math.round(c.nominal * 100),
                    color: Math.abs((c.empirical || 0) - c.nominal) > 0.07 ? 'crimson' : 'teal',
                  })),
                xDomain: [0, 1],
                yDomain: [0, 1],
                diagonal: true,
                height: 240,
                xLabel: 'nominal',
                yLabel: 'empírico',
                digits: 2,
                xDigits: 2,
                xAxisLabel: 'quantil nominal → cobertura observada',
              })
            }
          />
        </OCard>
      </div>

      <div className="grid g2" style={{ marginBottom: 14 }}>
        <OCard
          title="Efeito da perda assimétrica (3 h)"
          note="É isto que transforma o argumento em evidência: o mesmo conjunto de teste, com e sem os pesos por patamar. Observe o sinal do viés na ponta noturna."
        >
          <TabelaAssimetria eff={eff} v={v} />
        </OCard>
        <OCard title="Série de teste · horizonte 3 h" note="Observado contra P50 e banda P10–P90, nas duas primeiras semanas do conjunto de teste.">
          {series.index && series.index.length ? (
            <Grafico
              deps={[series]}
              desenhar={(el) =>
                lineChart(el, {
                  index: series.index,
                  height: 240,
                  compact: true,
                  bands: [{ lower: series.p10, upper: series.p90, color: 'teal', opacity: 0.18, label: 'P10–P90' }],
                  series: [
                    { label: 'Observado', values: series.observed, color: 'ink', width: 2 },
                    { label: 'P50', values: series.p50, color: 'teal' },
                    { label: 'Persistência', values: series.persistencia, color: 'muted', style: 'dash' },
                  ],
                })
              }
            />
          ) : (
            <div className="empty">Série de teste indisponível.</div>
          )}
        </OCard>
      </div>

      <OCard title="Baselines avaliados no mesmo conjunto de teste">
        <TabelaBaselines hz={hz} />
      </OCard>
      <Proveniencia body={body} />
    </>
  )
}

function Skill({ v }: { v: number | null | undefined }) {
  if (v === null || v === undefined || !Number.isFinite(v)) return <>—</>
  return <span className={v > 0 ? 'pos' : 'neg'}>{signed(v, 3)}</span>
}

function TabelaHorizontes({ hz }: { hz: Dado[] }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Horizonte</th>
            <th className="num">MAE</th>
            <th className="num">RMSE</th>
            <th className="num">MAPE %</th>
            <th className="num">Viés</th>
            <th className="num">Pinball</th>
            <th className="num">Banda MW</th>
            <th className="num">Rampa MAE</th>
            <th className="num">skill persist.</th>
            <th className="num">skill diário</th>
            <th className="num">skill semanal</th>
          </tr>
        </thead>
        <tbody>
          {hz.map((x) => (
            <tr key={x.horizon}>
              <td>
                <strong>{label(x.horizon)}</strong> <span className="small faint">{num(x.steps)}h à frente</span>
              </td>
              <td className="num">{num(x.mae, 1)}</td>
              <td className="num">{num(x.rmse, 1)}</td>
              <td className="num">{num(x.mape, 2)}</td>
              <td className="num">{signed(x.bias, 1)}</td>
              <td className="num">{num(x.pinball, 2)}</td>
              <td className="num">{num(x.interval_width_mw, 0)}</td>
              <td className="num">{num(x.ramp_mae_mw_h, 1)}</td>
              <td className="num">
                <Skill v={(x.skill || {}).persistencia} />
              </td>
              <td className="num">
                <Skill v={(x.skill || {}).sazonal_diario} />
              </td>
              <td className="num">
                <Skill v={(x.skill || {}).sazonal_semanal} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function CelulasMaeVies({ m }: { m: Dado }) {
  return (
    <>
      <td className="num">{num(m.mae, 0)}</td>
      <td className="num">{signed(m.bias, 0)}</td>
    </>
  )
}

function TabelaPatamar({ hz }: { hz: Dado[] }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th rowSpan={2}>Patamar</th>
            {hz.map((x) => (
              <th className="num" colSpan={2} key={x.horizon}>
                {label(x.horizon)}
              </th>
            ))}
          </tr>
          <tr>
            {hz.map((x) => [
              <th className="num" key={x.horizon + '-m'}>
                MAE
              </th>,
              <th className="num" key={x.horizon + '-v'}>
                viés
              </th>,
            ])}
          </tr>
        </thead>
        <tbody>
          {PATS.map((p) => (
            <tr key={p}>
              <td>{p.replace(/_/g, ' ')}</td>
              {hz.map((x) => (
                <CelulasMaeVies key={x.horizon} m={(x.by_patamar || {})[p] || {}} />
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function TabelaAssimetria({ eff, v }: { eff: Dado; v: Dado }) {
  const keys = ['assimetrica', 'simetrica']
  const w = v.weights || {}
  return (
    <>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th rowSpan={2}>Perda</th>
              <th className="num" rowSpan={2}>
                MAE
              </th>
              <th className="num" rowSpan={2}>
                Pinball
              </th>
              {PATS.map((p) => (
                <th className="num" colSpan={2} key={p}>
                  {p.replace(/_/g, ' ')}
                </th>
              ))}
            </tr>
            <tr>
              {PATS.map((p) => [
                <th className="num" key={p + '-m'}>
                  MAE
                </th>,
                <th className="num" key={p + '-v'}>
                  viés
                </th>,
              ])}
            </tr>
          </thead>
          <tbody>
            {keys.map((k) => {
              const e = eff[k] || {}
              return (
                <tr key={k}>
                  <td>
                    <strong>{k}</strong>
                  </td>
                  <td className="num">{num(e.mae, 1)}</td>
                  <td className="num">{num(e.pinball, 2)}</td>
                  {PATS.map((p) => (
                    <CelulasMaeVies key={p} m={(e.by_patamar || {})[p] || {}} />
                  ))}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      <div className="chips" style={{ marginTop: 10 }}>
        {Object.keys(w)
          .filter((k) => k !== 'base')
          .map((k) => (
            <Chip key={k} cor="amber">
              {k.replace(/_/g, ' ') + ' · sub ' + w[k].subestimacao + ' / super ' + w[k].superestimacao}
            </Chip>
          ))}
      </div>
    </>
  )
}

function TabelaBaselines({ hz }: { hz: Dado[] }) {
  const names = ['persistencia', 'sazonal_diario', 'sazonal_semanal']
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th rowSpan={2}>Baseline</th>
            {hz.map((x) => (
              <th className="num" colSpan={2} key={x.horizon}>
                {label(x.horizon)}
              </th>
            ))}
          </tr>
          <tr>
            {hz.map((x) => [
              <th className="num" key={x.horizon + '-m'}>
                MAE
              </th>,
              <th className="num" key={x.horizon + '-r'}>
                RMSE
              </th>,
            ])}
          </tr>
        </thead>
        <tbody>
          {names.map((n) => {
            const lbl = ((hz[0] || {}).baselines || {})[n]
            return (
              <tr key={n}>
                <td>{(lbl && lbl.label) || n}</td>
                {hz.map((x) => {
                  const b = (x.baselines || {})[n] || {}
                  return [
                    <td className="num" key={x.horizon + '-m'}>
                      {num(b.mae, 1)}
                    </td>,
                    <td className="num" key={x.horizon + '-r'}>
                      {num(b.rmse, 1)}
                    </td>,
                  ]
                })}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
