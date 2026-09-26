/**
 * Investimento: projeção do corte por razão energética e do BESS que ele justifica (protótipo,
 * painel "projecao"). Porte de 02-PROTOTIPO/web/js/views/projecao.js. A interface não calcula
 * nada: as taxas do cenário vão ao servidor.
 */
import { useEffect, useState } from 'react'
import { Api, ApiError, type Envelope } from '../api'
import { lineChart } from '../charts'
import { usePersistido } from '../estado'
import { num, pct, signed } from '../format'
import { BarRow, Carregando, Chip, Conteudo, ErroBloco, Grafico, Kpi, OCard, Pagina, Proveniencia, StatLines, Vazio, useApi } from '../ui'

/* eslint-disable @typescript-eslint/no-explicit-any */
type Dado = any
type Taxas = Record<string, number>

const REF = 'PLAN 2026-2030 (2ª RQ)'
const SC_COLOR: Record<string, string> = {
  'PLAN 2026-2030 (2ª RQ)': 'amber',
  'PAR/PEL 2025': 'green',
  'tendência observada': 'crimson',
  personalizado: 'purple',
}
const SLIDERS: [string, string, number, number, number, string][] = [
  ['g_vre', 'Eólica + solar centralizadas', 0, 0.4, 0.01, '%/ano'],
  ['g_mmgd', 'MMGD', 0, 0.6, 0.01, '%/ano'],
  ['g_load', 'Carga', 0, 0.08, 0.005, '%/ano'],
  ['flex_gw', 'Nova transmissão / flexibilidade', 0, 10, 0.5, 'GW/ano'],
]

const pctv = (v: number | null | undefined) => (v === null || v === undefined ? '—' : pct(v, 1))
const fmtSlider = (k: string, v: number) => (k === 'flex_gw' ? num(v, 1) + ' GW/ano' : num(v * 100, 1) + '%/ano')

export default function Projecao() {
  const [pronto, setPronto] = useState(false)
  return <Pagina>{pronto ? <Projetado /> : <Montagem onPronto={() => setPronto(true)} />}</Pagina>
}

/** Enquanto o histórico é montado no servidor: mostra o progresso e consulta a cada 3 s. */
function Montagem({ onPronto }: { onPronto: () => void }) {
  const [st, setSt] = useState<Dado>(null)
  const [erro, setErro] = useState<ApiError | null>(null)
  useEffect(() => {
    let vivo = true
    let t: ReturnType<typeof setTimeout> | undefined
    const consultar = async () => {
      try {
        const body = await Api.get<Dado>('ene/status', null, { fresh: true })
        if (!vivo) return
        const s = body.data
        if (s.state === 'ready') return onPronto()
        setSt(s)
        if (s.state !== 'error') t = setTimeout(consultar, 3000)
      } catch (e) {
        if (vivo) setErro(e instanceof ApiError ? e : new ApiError('INTERNAL', String(e)))
      }
    }
    consultar()
    return () => {
      vivo = false
      clearTimeout(t)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
  if (erro) return <ErroBloco erro={erro} />
  if (!st) return <Carregando texto="Calibrando o modelo da carga líquida e projetando os cenários…" />
  return (
    <>
      <div className={'note-strip' + (st.state === 'error' ? ' warn' : '')}>
        {st.state === 'error' ? (
          <>
            <strong>Falha ao montar o histórico.</strong> {st.error}
          </>
        ) : (
          <>
            <strong>Montando o histórico completo de constrained-off</strong> (eólica desde 10/2021, fotovoltaica desde 04/2024), o balanço horário do ONS e a série de conexões de
            MMGD da ANEEL. Meses já agregados vêm do cache.
          </>
        )}
      </div>
      <OCard title="Progresso">
        <BarRow label="etapas" frac={st.overall || 0} value={num(st.done) + ' de ' + num(st.total)} color="teal" />
        <div className="card-note">
          Agora: {st.stage || '—'}
          {st.elapsed_s ? ' · ' + num(st.elapsed_s, 0) + ' s' : ''}
        </div>
      </OCard>
    </>
  )
}

function Projetado() {
  const [custom, setCustom] = usePersistido<Taxas | null>('oraculo.eneCustom', null)
  const estado = useApi(() => Api.get<Dado>('ene/projecao', custom), [custom ? JSON.stringify(custom) : ''])
  return (
    <Conteudo estado={estado} texto="Calibrando o modelo da carga líquida e projetando os cenários…">
      {(body) => <Corpo body={body} custom={custom} setCustom={setCustom} />}
    </Conteudo>
  )
}

function Corpo({ body, custom, setCustom }: { body: Envelope<Dado>; custom: Taxas | null; setCustom: (c: Taxas | null) => void }) {
  const d = body.data
  const bt = d.backtest || {}
  const ref = d.reference || {}
  const rs = d.rates || {}
  const scen: Dado[] = d.scenarios || []
  const years: Dado[] = d.years || []
  const refS = scen.find((s) => s.name === REF) || scen[0] || { years: [] }
  const lastY = refS.years[refS.years.length - 1] || {}
  const lb = lastY.bess || {}
  const cust: Taxas = custom || (scen.find((s) => s.name === REF) || {}).params || {}
  const yUlt = years.slice(-1)[0]

  return (
    <>
      <div className="note-strip">
        <strong>Por que um modelo físico.</strong> O corte ENE cresceu em saltos; uma tendência ajustada a isso projeta o salto para sempre. O que o gera é mensurável hora a hora: a{' '}
        <strong>carga líquida</strong> (carga supervisionada − eólica − solar centralizadas potenciais). Quando ela cai abaixo do piso que o sistema absorve, a sobra vira corte. A
        MMGD reduz a carga supervisionada e aprofunda a curva do pato: cresce a MMGD, cresce o corte — nas usinas centralizadas.
      </div>

      <div className="grid g4" style={{ marginBottom: 14 }}>
        <Kpi
          label="Corte ENE+SIS · referência"
          value={num(ref.ene_twh, 1)}
          unit="TWh/ano"
          foot={
            String(ref.from || '').slice(0, 7) +
            ' a ' +
            String(ref.to || '').slice(0, 7) +
            ' · ' +
            (d.observed_growth === null ? '—' : signed(d.observed_growth * 100, 0) + '% sobre os 12 meses anteriores')
          }
          accent="crimson"
        />
        <Kpi
          label="Erro fora da amostra"
          value={pct(bt.mape_model, 0)}
          unit="MAPE mensal"
          foot={'ingênuo (mesmo mês do ano anterior): ' + pctv(bt.mape_naive) + ' · viés ' + signed((bt.test_bias || 0) * 100, 0) + '%'}
          accent="teal"
        />
        <Kpi
          label={'Corte ENE+SIS em ' + yUlt}
          value={num(lastY.ene_twh, 1)}
          unit="TWh/ano"
          foot={'PLAN 2026-2030 · dos quais ' + num(lastY.ene_twh - lastY.ene_sem_mmgd_twh, 1) + ' TWh pelo crescimento da MMGD'}
          accent="amber"
        />
        <Kpi
          label={'Potencial técnico de BESS em ' + yUlt}
          value={num(lb.e_gwh, 0)}
          unit="GWh"
          foot={
            num(lb.p_gw, 0) + ' GW × ' + num(lb.hours, 0) + ' h · recupera ' + num(lb.delivered_twh, 1) + ' TWh/ano' + (lb.at_grid_limit ? ' · no limite da grade' : '')
          }
          accent="navy"
        />
      </div>

      <Leitura scen={scen} years={years} />

      <div style={{ marginBottom: 14 }}>
        <OCard
          title="Histórico e projeção · corte ENE+SIS"
          hint="TWh por mês · projeção = ano de referência escalado"
          note={'A série fotovoltaica só é publicada a partir de ' + (d.fv_start ?? '') + ': antes disso o total do SIN está incompleto, e o modelo não é calibrado ali.'}
        >
          <Grafico deps={[d]} desenhar={(el) => drawHist(el, d, scen)} />
        </OCard>
      </div>

      <div style={{ marginBottom: 14 }}>
        <OCard
          title="Cenários"
          hint="corte ENE+SIS e potencial técnico de BESS por ano"
          note={
            'Referência: carga global e MMGD da 2ª Revisão Quadrimestral do PLAN 2026-2030 (ONS/EPE/CCEE, 07/08/2026), ano a ano; eólica + solar centralizadas do PAR/PEL 2025 (+2,3% a.a.). ' +
            '“Tendência observada” extrapola as séries e serve só de contraste. ' +
            'Potencial técnico: maior BESS em que o GWh adicional ainda cicla ≥ 200 vezes/ano, dimensionado no SIN (o corte ENE+SIS é sistêmico). ' +
            'Não inclui receita nem soluções concorrentes (transmissão, flexibilidade) — é o teto de uso, não uma recomendação de investimento.'
          }
        >
          <TabelaCenarios scen={scen} years={years} />
        </OCard>
      </div>

      <div className="grid g3" style={{ marginBottom: 14 }}>
        <OCard
          title="Validação fora da amostra"
          hint={'ajuste até ' + (bt.split ?? '') + ' · teste depois'}
          note={
            'Correlação horária no teste: ' +
            num(bt.hourly_corr, 2) +
            '. Total do teste: ' +
            num(bt.test_total_obs_twh, 1) +
            ' TWh observados × ' +
            num(bt.test_total_model_twh, 1) +
            ' modelados.'
          }
        >
          <Grafico deps={[bt]} desenhar={(el) => drawBacktest(el, bt)} />
        </OCard>
        <OCard
          title="A curva do pato que se aprofunda"
          hint="SIN · perfil médio horário · MW"
          note="Carga líquida no ano de referência e o corte ENE+SIS. A MMGD desloca a curva para baixo ao meio-dia; a eólica e a solar centralizadas, idem."
        >
          <Grafico deps={[d.duck_ref]} desenhar={(el) => drawDuck(el, d.duck_ref)} />
        </OCard>
        <OCard
          title="MMGD conectada (ANEEL)"
          hint="GW acumulados por data de conexão"
          note={
            'Crescimento em 12 meses até ' + (rs.mmgd_until || '—') + ': ' + pctv(rs.mmgd_12m) + ' (desacelerando). Os últimos meses são sub-registrados pela defasagem de cadastro.'
          }
        >
          <Grafico deps={[d.mmgd_series]} desenhar={(el) => drawMmgd(el, d.mmgd_series)} />
        </OCard>
      </div>

      <div className="grid g2" style={{ marginBottom: 14 }}>
        <OCard
          title="Cenário personalizado"
          note="Parte das taxas médias do PLAN 2026-2030. Nova transmissão ou flexibilidade reduz o piso de carga líquida θ a cada ano."
        >
          <PainelTaxas key={JSON.stringify(cust)} cust={cust} onAplicar={setCustom} onReset={() => setCustom(null)} />
        </OCard>
        <OCard
          title="Onde o BESS do último ano entraria"
          hint="rateio indicativo pelo corte ENE+SIS dos sítios"
          note="O corte ENE+SIS é sistêmico: o armazenamento pode estar em qualquer ponto do SIN. O rateio pelos sítios de maior corte é a leitura de onde ele recupera mais sem depender de rede."
        >
          <TabelaRateio rows={d.allocation} />
        </OCard>
      </div>

      <div className="grid g2">
        <OCard title="Taxas observadas" note="Eólica e solar do balanço são geração verificada (já descontado o corte): subestimam o crescimento da capacidade.">
          <StatLines
            pares={[
              ['Eólica + solar, último ano', pctv(rs.vre_last)],
              ['Eólica + solar, 2 anos (a.a.)', pctv(rs.vre_2y)],
              ['Carga, último ano', pctv(rs.load_last)],
              ['Carga, série completa (a.a.)', pctv(rs.load_6y)],
              ['MMGD, 12 meses', pctv(rs.mmgd_12m)],
              ['MMGD, 24 meses (a.a.)', pctv(rs.mmgd_24m)],
              ['MMGD conectada', num(rs.mmgd_gw, 1) + ' GW'],
              ['Parâmetros do modelo', 'α = ' + num((d.params || {}).alpha, 2)],
              [
                'MMGD média oficial ' + ((d.plan || {}).ano_base || ''),
                num((d.reference || {}).mmgd_plan_mwmed, 0) + ' MWmed (estimativa: ' + num((d.reference || {}).mmgd_est_mwmed, 0) + ')',
              ],
            ]}
          />
        </OCard>
        <OCard
          title="Premissas"
          note="Limites: um único ano de referência (clima e hidrologia daquele ano); θ constante sem expansão; o corte é a decisão operativa observada; o perfil horário da MMGD é o do envelope, com o nível oficial do PLAN."
        >
          <StatLines pares={(d.premises || []).map((p: Dado) => [p.k, p.v] as [string, string])} />
        </OCard>
      </div>
      <Proveniencia body={body} />
    </>
  )
}

/** A leitura que decide o investimento, tirada dos próprios cenários. */
function Leitura({ scen, years }: { scen: Dado[]; years: Dado[] }) {
  const ref = scen.find((s) => s.name === REF)
  const tend = scen.find((s) => s.name === 'tendência observada')
  if (!ref || !tend) return null
  const r = ref.years[ref.years.length - 1] || {}
  const t = tend.years[tend.years.length - 1] || {}
  const y = years.slice(-1)[0]
  const mm = r.ene_twh ? (r.ene_twh - r.ene_sem_mmgd_twh) / r.ene_twh : null
  return (
    <div className="note-strip warn" style={{ marginBottom: 14 }}>
      <strong>Leitura.</strong> Na trajetória oficial, a carga global (+{pct(ref.params.g_load, 1)} a.a., com datacenters) cresce mais que a eólica e solar centralizadas (+
      {pct(ref.params.g_vre, 1)} a.a., a expansão considerada no PAR/PEL): o corte ENE+SIS cai para {num(r.ene_twh, 1)} TWh em {y}, mas {pct(mm, 0)} dele passa a ser devido ao
      crescimento da MMGD. Se a expansão centralizada seguir o ritmo observado, o corte vai a {num(t.ene_twh, 0)} TWh.{' '}
      <strong>O caso de investimento em BESS depende sobretudo do ritmo da expansão centralizada frente à carga</strong> — use o cenário personalizado para testar.
    </div>
  )
}

function PainelTaxas({ cust, onAplicar, onReset }: { cust: Taxas; onAplicar: (c: Taxas) => void; onReset: () => void }) {
  const [vals, setVals] = useState<Taxas>(() => {
    const o: Taxas = {}
    SLIDERS.forEach((s) => (o[s[0]] = Number(cust[s[0]]) || 0))
    return o
  })
  return (
    <>
      {SLIDERS.map((s) => (
        <div className="bar-row" style={{ gridTemplateColumns: '190px 1fr 80px' }} key={s[0]}>
          <span>{s[1]}</span>
          <input
            type="range"
            min={s[2]}
            max={s[3]}
            step={s[4]}
            value={vals[s[0]]}
            onChange={(e) => {
              const v = parseFloat(e.target.value)
              setVals((a) => ({ ...a, [s[0]]: v }))
            }}
          />
          <span className="v">{fmtSlider(s[0], vals[s[0]])}</span>
        </div>
      ))}
      <div style={{ marginTop: 10, display: 'flex', gap: 8 }}>
        <button onClick={() => onAplicar({ ...vals })}>Aplicar</button>
        <button className="ghost" onClick={onReset}>
          Só os padrões
        </button>
      </div>
    </>
  )
}

function TabelaCenarios({ scen, years }: { scen: Dado[]; years: Dado[] }) {
  return (
    <>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Cenário</th>
              <th>Ano</th>
              <th className="num">Corte TWh</th>
              <th className="num" title="diferença para a MMGD mantida no nível de referência: atribuição, não cenário">
                da MMGD TWh
              </th>
              <th className="num">% da VRE</th>
              <th className="num">BESS GWh</th>
              <th className="num">Recupera TWh</th>
            </tr>
          </thead>
          <tbody>
            {scen.map((s) =>
              (s.years as Dado[]).map((y, i) => (
                <tr key={s.name + '-' + i}>
                  {i === 0 ? (
                    <td rowSpan={s.years.length}>
                      <Chip cor={SC_COLOR[s.name] || ''}>{s.name}</Chip>
                      <div className="small faint" style={{ marginTop: 4 }}>
                        VRE {pct(s.params.g_vre, 0)} · MMGD {pct(s.params.g_mmgd, 0)} · carga {pct(s.params.g_load, 1)}
                        {s.params.flex_gw ? ' · flex ' + num(s.params.flex_gw, 1) + ' GW' : ''}
                        {s.source ? (
                          <>
                            <br />
                            <span className="faint">{s.source}</span>
                          </>
                        ) : null}
                      </div>
                    </td>
                  ) : null}
                  <td>{years[i] || ''}</td>
                  <td className="num">{num(y.ene_twh, 1)}</td>
                  <td className="num">{num(y.ene_twh - y.ene_sem_mmgd_twh, 1)}</td>
                  <td className={'num ' + (y.implausible ? 'neg' : '')} title={y.implausible ? 'acima do plausível: sem realimentação econômica' : ''}>
                    {pct(y.cut_share, 0)}
                    {y.implausible ? ' ⚠' : ''}
                  </td>
                  <td className="num" title={y.bess && y.bess.p_gw ? num(y.bess.p_gw, 0) + ' GW × ' + num(y.bess.hours, 0) + ' h' : ''}>
                    {y.bess && y.bess.e_gwh ? num(y.bess.e_gwh, 0) + (y.bess.at_grid_limit ? ' ▲' : '') : '—'}
                  </td>
                  <td className="num">{num((y.bess || {}).delivered_twh, 1)}</td>
                </tr>
              )),
            )}
          </tbody>
        </table>
      </div>
      <div className="card-note">
        “da MMGD”: quanto do corte do ano se deve ao crescimento da MMGD — a diferença para a mesma projeção com a MMGD no nível de referência. É atribuição, não cenário: a MMGD
        continua crescendo. % da VRE: corte ÷ eólica + solar potenciais. ⚠ acima de 25%: cenário economicamente inconsistente — o modelo não tem realimentação (ninguém segue
        construindo nesse ritmo com esse corte). ▲ no limite da grade (60 GW × 6 h). Passe o mouse no GWh para ver potência × duração.
      </div>
    </>
  )
}

function TabelaRateio({ rows }: { rows: Dado[] | undefined }) {
  if (!rows || !rows.length) return <Vazio>Requer a base da seção BESS.</Vazio>
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Sítio</th>
            <th className="num">Parcela do ENE+SIS</th>
            <th className="num">GW</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={(r.code || r.name) + '-' + i}>
              <td>
                {r.name} <span className="small faint">{r.uf}</span>
              </td>
              <td className="num">{pct(r.share, 1)}</td>
              <td className="num">{num(r.gw, 2)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function drawHist(host: HTMLElement, d: Dado, scen: Dado[]) {
  const hist: Dado[] = d.history || []
  const labels: string[] = hist.map((h) => h.label)
  const years: Dado[] = d.years || []
  const nh = hist.length
  // projeção mensal: perfil do ano de referência escalado pelo total anual
  const refMonths = hist.slice(-12)
  const refTot = refMonths.reduce((a, h) => a + h.es_eol_twh + h.es_fv_twh, 0) || 1
  years.forEach((y) => refMonths.forEach((h) => labels.push(String(h.label).slice(0, 3) + '/' + String(y).slice(2))))
  const vazio = new Array(years.length * 12).fill(null)
  const series: Dado[] = [
    { label: 'ENE+SIS eólica (obs.)', color: 'navy', values: hist.map((h) => h.es_eol_twh).concat(vazio) },
    { label: 'ENE+SIS fotovoltaica (obs.)', color: 'amber', values: hist.map((h) => h.es_fv_twh).concat(vazio) },
  ]
  scen.forEach((s) => {
    const vals: (number | null)[] = new Array(nh).fill(null)
    ;(s.years as Dado[]).forEach((y) =>
      refMonths.forEach((h) => {
        vals.push((y.ene_twh * (h.es_eol_twh + h.es_fv_twh)) / refTot)
      }),
    )
    series.push({ label: 'projeção · ' + s.name, color: SC_COLOR[s.name] || 'teal', values: vals, style: s.name === REF ? undefined : 'dash' })
  })
  const idx = labels.map((_, i) => i)
  lineChart(host, { index: idx, series, height: 290, compact: true, formatTime: (i) => labels[i as number] || '' })
}

function drawBacktest(host: HTMLElement, bt: Dado) {
  if (!bt.monthly) {
    host.innerHTML = ''
    return
  }
  const m: Dado[] = bt.monthly
  const idx = m.map((_, i) => i)
  lineChart(host, {
    index: idx,
    height: 220,
    compact: true,
    formatTime: (i) => (m[i as number] || {}).month || '',
    series: [
      { label: 'observado', color: 'navy', values: m.map((x) => x.observed_twh) },
      { label: 'modelo', color: 'crimson', style: 'dash', values: m.map((x) => x.model_twh) },
    ],
    spans: [{ from: m.findIndex((x) => x.test), to: m.length - 1, color: 'teal', label: 'teste' }],
  })
}

function drawDuck(host: HTMLElement, dr: Dado) {
  if (!dr) {
    host.innerHTML = ''
    return
  }
  const idx: string[] = []
  for (let h = 0; h < 24; h++) idx.push('2026-01-01T' + String(h).padStart(2, '0') + ':00:00')
  lineChart(host, {
    index: idx,
    height: 220,
    compact: true,
    formatTime: (v) => String(v).slice(11, 13) + 'h',
    series: [
      { label: 'carga líquida', color: 'teal', values: dr.nl_mw },
      { label: 'piso médio θ', color: 'muted', style: 'dash', values: new Array(24).fill(dr.theta_mean_mw) },
      { label: 'corte ENE+SIS', color: 'crimson', values: dr.es_mw },
    ],
  })
}

function drawMmgd(host: HTMLElement, ms: Dado) {
  if (!ms) {
    host.innerHTML = ''
    return
  }
  const idx = (ms.months as Dado[]).map((_, i) => i)
  lineChart(host, {
    index: idx,
    height: 220,
    compact: true,
    formatTime: (i) => ms.months[i as number] || '',
    series: [{ label: 'MMGD conectada (GW)', color: 'amber', values: ms.cumulative_gw }],
  })
}
