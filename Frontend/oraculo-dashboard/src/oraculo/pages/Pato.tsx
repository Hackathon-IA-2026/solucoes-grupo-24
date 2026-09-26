/**
 * Curva do pato prevista pelo tempo (protótipo, painel "pato"). Porte de
 * 02-PROTOTIPO/web/js/views/pato.js: radiação × onde está a MMGD → carga supervisionada.
 * A interface não calcula nada: apresenta a previsão e o backtest do servidor.
 */
import { useEffect, useState } from 'react'
import { Api, ApiError, type Envelope } from '../api'
import { lineChart, stackedBars } from '../charts'
import { usePersistido, useOraculo } from '../estado'
import { num, pct, signed } from '../format'
import { Carregando, Chip, Conteudo, ErroBloco, Grafico, Kpi, OCard, Pagina, Proveniencia, StatLines, Vazio, useApi } from '../ui'

/* eslint-disable @typescript-eslint/no-explicit-any */
type Dado = any

const SSL = ['SIN', 'SE', 'S', 'NE', 'N']
const MCOL: Record<string, string> = {
  'ECMWF AIFS': 'purple',
  'ECMWF IFS': 'teal',
  'NOAA GFS': 'amber',
  'média dos modelos': 'crimson',
  persistência: 'muted',
  'ERA5 (tempo perfeito)': 'green',
  observado: 'navy',
}
const TEXTO = 'Cruzando a previsão de radiação com a MMGD…'

function hoursIdx(): string[] {
  const idx: string[] = []
  for (let h = 0; h < 24; h++) idx.push('2026-01-01T' + String(h).padStart(2, '0') + ':00:00')
  return idx
}

function dayLabel(d: string): string {
  const dt = new Date(d + 'T12:00:00')
  return ['dom', 'seg', 'ter', 'qua', 'qui', 'sex', 'sáb'][dt.getDay()] + ' ' + d.slice(8, 10) + '/' + d.slice(5, 7)
}

const fmtHora = (v: unknown) => String(v).slice(11, 13) + 'h'

export default function Pato() {
  const { versao } = useOraculo()
  const [st, setSt] = useState<Dado | null>(null)
  const [erro, setErro] = useState<ApiError | null>(null)

  // Espera o job em segundo plano (tempo/status) ficar "ready", consultando a cada 2,5 s.
  useEffect(() => {
    let vivo = true
    let t: ReturnType<typeof setTimeout> | undefined
    const consultar = () => {
      Api.get('tempo/status', null, { fresh: true })
        .then((body) => {
          if (!vivo) return
          const s = body.data as Dado
          setErro(null)
          setSt(s)
          if (s.state !== 'ready' && s.state !== 'error') t = setTimeout(consultar, 2500)
        })
        .catch((e: unknown) => {
          if (!vivo) return
          setErro(e instanceof ApiError ? e : new ApiError('INTERNAL', e instanceof Error ? e.message : String(e)))
        })
    }
    consultar()
    return () => {
      vivo = false
      clearTimeout(t)
    }
  }, [versao])

  return (
    <Pagina>
      {erro ? (
        <ErroBloco erro={erro} />
      ) : !st ? (
        <Carregando texto={TEXTO} />
      ) : st.state !== 'ready' ? (
        <>
          <div className={'note-strip' + (st.state === 'error' ? ' warn' : '')}>
            {st.state === 'error' ? (
              <>
                <strong>Falha ao montar a previsão.</strong> {st.error}
              </>
            ) : (
              <>
                <strong>Buscando o tempo</strong> — ERA5 de 12 meses para calibrar, as previsões arquivadas do AIFS, IFS e GFS para o backtest e a previsão dos próximos 7
                dias. Leva menos de um minuto.
              </>
            )}
          </div>
          <OCard title="Progresso">
            <div className="small">
              Etapa: {st.stage || '—'}
              {st.elapsed_s ? ' · ' + num(st.elapsed_s, 0) + ' s' : ''}
            </div>
          </OCard>
        </>
      ) : (
        <Pronto />
      )}
    </Pagina>
  )
}

function Pronto() {
  const estado = useApi(() => Api.get('tempo/pato'), [])
  return <Conteudo estado={estado} texto={TEXTO}>{(body) => <Corpo body={body} />}</Conteudo>
}

function Corpo({ body }: { body: Envelope }) {
  const d = body.data as Dado
  const [ptSS, setPtSS] = usePersistido('oraculo.ptSS', 'SIN')
  const [ptDayRaw, setPtDay] = usePersistido<string | null>('oraculo.ptDay', null)
  const days: Dado[] = (d.operational || {})[ptSS] || []
  const ptDay: string | undefined =
    ptDayRaw && days.some((x) => x.day === ptDayRaw) ? ptDayRaw : days.length > 1 ? days[1].day : (days[0] || {}).day
  const sel: Dado = days.find((x) => x.day === ptDay) || {}
  const met: Dado = (d.metrics || {})[ptSS] || {}
  const pers = met['persistência'] || {}
  const ens = met['média dos modelos'] || {}
  const gain = pers.mae_mid_mw ? 1 - ens.mae_mid_mw / pers.mae_mid_mw : null
  const gainR = pers.mae_ramp_mw ? 1 - ens.mae_ramp_mw / pers.mae_ramp_mw : null

  return (
    <>
      <div className="note-strip">
        <strong>Como funciona.</strong> A MMGD é a parte da curva mais sensível ao tempo: um dia nublado no Sudeste devolve gigawatts de carga à rede ao meio-dia. A
        capacidade de MMGD por município (cadastro ANEEL) vira {num((d.points || []).length)} células; em cada uma, a radiação e a temperatura previstas viram geração. A
        carga supervisionada prevista é o dia-tipo corrigido pela MMGD e pela temperatura — as duas mexem na carga, em sentidos opostos.
      </div>

      <div className="grid g4" style={{ marginBottom: 14 }}>
        <Kpi
          label={'Barriga do pato · ' + dayLabel(sel.day || '')}
          value={num(sel.min_mw / 1000, 1)}
          unit="GW"
          foot={ptSS + ' · mínimo das 10h–15h às ' + num(sel.min_hour) + 'h · incerteza entre modelos ' + num(sel.spread_min_mw / 1000, 1) + ' GW'}
          accent="teal"
        />
        <Kpi label="Rampa do fim da tarde" value={num(sel.ramp_mw / 1000, 1)} unit="GW" foot="do mínimo ao pico das 17h–21h" accent="crimson" />
        <Kpi
          label="MMGD no pico"
          value={num(sel.mmgd_peak_mw / 1000, 1)}
          unit="GW"
          foot={
            'média dos modelos · ' +
            Object.entries((sel.mmgd_models || {}) as Record<string, number>)
              .map(([k, v]) => k.replace('ECMWF ', '').replace('NOAA ', '') + ' ' + num(v / 1000, 1))
              .join(' · ')
          }
          accent="amber"
        />
        <Kpi
          label="Ganho sobre a persistência"
          value={gain === null ? '—' : pct(gain, 0)}
          foot={'backtest ' + ptSS + ' · erro 9–16h · rampa ' + (gainR === null ? '—' : pct(gainR, 0))}
          accent="green"
        />
      </div>

      <div className="chips" style={{ marginBottom: 10 }}>
        {SSL.map((k) => (
          <Chip key={k} on={ptSS === k} onClick={() => setPtSS(k)}>
            {k}
          </Chip>
        ))}
        <span style={{ width: 14 }} />
        {days.map((x) => (
          <Chip key={x.day} on={ptDay === x.day} onClick={() => setPtDay(x.day)}>
            {dayLabel(x.day)}
          </Chip>
        ))}
      </div>

      <div className="grid g-2-1" style={{ marginBottom: 14 }}>
        <OCard
          title={'Carga supervisionada prevista · ' + ptSS + ' · ' + dayLabel(sel.day || '')}
          hint="média dos modelos, faixa entre modelos e cada modelo"
          note="A faixa é a divergência entre AIFS, IFS e GFS: quando os modelos discordam sobre as nuvens, a barriga do pato fica incerta."
        >
          <Grafico deps={[sel]} desenhar={(el) => drawDay(el, sel)} />
        </OCard>
        <OCard title="Semana" hint="barriga + rampa = pico da noite · GW" note="Fim de semana: carga menor com a mesma MMGD — a barriga afunda.">
          <Grafico
            deps={[days]}
            desenhar={(el) =>
              stackedBars(el, {
                labels: days.map((x) => dayLabel(x.day)),
                stacks: [
                  { label: 'barriga (GW)', color: 'teal', values: days.map((x) => x.min_mw / 1000) },
                  { label: 'rampa (GW)', color: 'crimson', values: days.map((x) => x.ramp_mw / 1000) },
                ],
                height: 280,
                unit: 'GW',
              })
            }
          />
        </OCard>
      </div>

      <div className="grid g2" style={{ marginBottom: 14 }}>
        <OCard title={'MMGD prevista na semana · ' + ptSS} hint="geração da MMGD por hora, média dos modelos · MW">
          <Grafico
            deps={[days]}
            desenhar={(el) =>
              lineChart(el, {
                index: hoursIdx(),
                height: 240,
                compact: true,
                formatTime: fmtHora,
                series: days.map((x, i) => ({
                  label: dayLabel(x.day),
                  values: x.mmgd || [],
                  color: ['amber', 'crimson', 'teal', 'purple', 'green', 'navy', 'muted'][i % 7],
                })),
              })
            }
          />
        </OCard>
        <OCard
          title="Backtest · últimos 14 dias do teste · SIN"
          hint="observado × persistência × média dos modelos"
          note="Com as previsões ARQUIVADAS: o que cada modelo de fato previu."
        >
          <Grafico deps={[d.backtest_sample]} desenhar={(el) => drawBt(el, d.backtest_sample)} />
        </OCard>
      </div>

      <OCard
        title={'Validação fora da amostra · ' + ptSS}
        hint={'janela ' + (d.backtest_window || []).join(' a ') + ' · dias úteis e fins de semana, sem feriados'}
        note="Persistência: o mesmo dia da semana das duas últimas semanas, sem tempo nenhum. ERA5 (tempo perfeito) é o teto — o erro que sobra ali não é do tempo, é do dia-tipo. Nenhum modelo é o melhor em tudo: o AIFS acerta bem a barriga, mas erra mais a rampa da tarde."
      >
        <TabelaMetricas met={met} />
      </OCard>

      <div className="grid g3" style={{ marginTop: 14 }}>
        <OCard
          title="O tempo mexe nos dois lados"
          note="Sem controlar a temperatura, a sensibilidade da carga à MMGD sai perto de zero: dia de sol aumenta a MMGD, mas também aquece e aumenta a refrigeração. Com a temperatura, β volta a ~0,8 no Sudeste. β e γ são estimados antes da janela de teste."
        >
          <TabelaSens sens={d.sensitivity} />
        </OCard>
        <OCard title="Modelos de tempo" note="Todos pelo Open-Meteo. O NVIDIA Earth-2 segue como provedor plugável: o contrato é o mesmo, falta o runtime.">
          <TabelaProvedores ps={d.providers} />
        </OCard>
        <OCard
          title="Calibração e premissas"
          note="PR calibrado para que a MMGD reconstruída com ERA5 reproduza a MMGD média oficial de 2026 (2ª RQ do PLAN 2026-2030). Os valores, 0,64 a 0,83, são os de sistemas fotovoltaicos reais."
        >
          <StatLines
            pares={[
              ...Object.entries((d.pr || {}) as Record<string, number>).map(([k, v]) => ['PR efetivo · ' + k, num(v, 2)] as [string, string]),
              ...((d.premises || []) as Dado[]).map((p) => [p.k, p.v] as [string, string]),
            ]}
          />
        </OCard>
      </div>
      <Proveniencia body={body} />
    </>
  )
}

function TabelaMetricas({ met }: { met: Dado }) {
  const rows = Object.entries((met || {}) as Record<string, Dado>)
  if (!rows.length) return <Vazio>Sem backtest.</Vazio>
  const best = (k: string) => Math.min(...rows.filter(([m]) => !m.startsWith('ERA5')).map(([, v]) => v[k]))
  const cell = (v: Dado, k: string) => <td className={'num' + (v[k] === best(k) ? ' pos' : '')}>{num(v[k], 0)}</td>
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Método</th>
            <th className="num">Dias</th>
            <th className="num">Erro 9–16h (MW)</th>
            <th className="num">% da carga</th>
            <th className="num">Erro na barriga</th>
            <th className="num">Viés na barriga</th>
            <th className="num">Erro na rampa</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(([m, v]) => (
            <tr key={m}>
              <td>
                <span className={'chip ' + (MCOL[m] || '')}>{m}</span>
              </td>
              <td className="num">{v.days}</td>
              {cell(v, 'mae_mid_mw')}
              <td className="num">{pct(v.mape_mid, 1)}</td>
              {cell(v, 'mae_min_mw')}
              <td className="num">{signed(v.bias_min_mw, 0)}</td>
              {cell(v, 'mae_ramp_mw')}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function TabelaSens({ sens }: { sens: Dado }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th></th>
            <th className="num">β MMGD</th>
            <th className="num">γ MW/°C</th>
            <th className="num">R² só MMGD</th>
            <th className="num">R² com T</th>
          </tr>
        </thead>
        <tbody>
          {Object.entries((sens || {}) as Record<string, Dado>).map(([k, v]) => (
            <tr key={k}>
              <td>{k}</td>
              <td className="num">{num(v.beta, 2)}</td>
              <td className="num">{num(v.gamma, 0)}</td>
              <td className="num faint">{num(v.r2_mmgd_only, 2)}</td>
              <td className="num">{num(v.r2, 2)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function TabelaProvedores({ ps }: { ps: Dado[] }) {
  return (
    <div className="table-wrap">
      <table>
        <tbody>
          {(ps || []).map((p, i) => (
            <tr key={p.k || i}>
              <td>
                <strong>{p.label}</strong>
                <br />
                <span className="small faint">{p.note}</span>
              </td>
              <td>
                <span className={'chip ' + (p.kind === 'IA' ? 'purple' : 'teal')}>{p.kind}</span>
              </td>
              <td>{p.available ? <span className="chip green">em uso</span> : <span className="chip crimson">indisponível</span>}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function drawDay(host: HTMLElement, sel: Dado) {
  if (!sel.ensemble) {
    host.innerHTML = ''
    return
  }
  const series: Dado[] = [{ label: 'média dos modelos', color: 'crimson', values: sel.ensemble, width: 2.6 }]
  Object.entries((sel.models || {}) as Record<string, Dado>).forEach(([k, v]) => series.push({ label: k, color: MCOL[k] || 'teal', values: v, style: 'dash' }))
  lineChart(host, {
    index: hoursIdx(),
    height: 280,
    compact: true,
    series,
    formatTime: fmtHora,
    bands: [{ lower: sel.low, upper: sel.high, color: 'crimson', opacity: 0.12, label: 'faixa entre modelos' }],
    spans: [{ from: 10, to: 15, color: 'teal', label: 'barriga', opacity: 0.06 }],
  })
}

function drawBt(host: HTMLElement, bs: Dado) {
  if (!bs || !bs.days || !bs.days.length) {
    host.innerHTML = ''
    return
  }
  const idx: number[] = []
  const lab: string[] = []
  ;(bs.days as string[]).forEach((d) => {
    for (let h = 0; h < 24; h++) {
      idx.push(idx.length)
      lab.push(dayLabel(d) + ' ' + h + 'h')
    }
  })
  const flat = (k: string) => ([] as (number | null)[]).concat(...(bs.days as string[]).map((_, i) => ((bs.series || {})[k] || [])[i] || new Array(24).fill(null)))
  lineChart(host, {
    index: idx,
    height: 240,
    compact: true,
    formatTime: (i) => lab[i as number] || '',
    series: [
      { label: 'observado', color: 'navy', values: flat('observado') },
      { label: 'persistência', color: 'muted', style: 'dash', values: flat('persistência') },
      { label: 'média dos modelos', color: 'crimson', values: flat('média dos modelos') },
    ],
  })
}
