/**
 * Fronteira T–D (protótipo, painel "fronteira"). Porte de V.fronteira em
 * 02-PROTOTIPO/web/js/views/fronteira.js: subestações de distribuição (ANEEL) × SE de fronteira
 * da rede básica (ONS). Exporta também <BaseFronteira> e <LoadChip>, reaproveitados por
 * ./Correlacao.tsx (mesma base agregada, mesma espera de construção).
 */
/* eslint-disable @typescript-eslint/no-explicit-any */
import L from 'leaflet'
import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { CircleMarker, Pane, Polyline, Tooltip } from 'react-leaflet'
import { Link, useNavigate } from 'react-router-dom'
import { Api, ApiError, type Envelope } from '../api'
import { color, stackedBars } from '../charts'
import { usePersistido, useOraculo } from '../estado'
import { num, pct, when } from '../format'
import { MapaOsm, limitesDe } from '../MapaOsm'
import { BarRow, Carregando, Chip, Conteudo, ErroBloco, Grafico, Kpi, OCard, Pagina, Proveniencia, StatLines, Vazio, useApi } from '../ui'

type Dado = any

const CLASSES = ['residencial', 'comercial', 'industrial', 'rural']
const CLASS_COLORS: Record<string, string> = { residencial: 'teal', comercial: 'navy', industrial: 'amber', rural: 'green' }
const MONTHS = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez']
const ORDENS: [string, string][] = [
  ['energia', 'ordenar por energia'],
  ['gd', 'por penetração de MMGD'],
  ['carregamento', 'por carregamento'],
  ['ambiguidade', 'por ambiguidade'],
  ['nome', 'por nome'],
]

/**
 * Entrega ao cartão CLM (o App.STATE.clmHandoff do protótipo): gravada em
 * usePersistido('oraculo.clmHandoff') e também no location.state de /clm.
 * Formato: { subId, name, fonte: 'bdgd' }.
 */
const CLM_HANDOFF_KEY = 'oraculo.clmHandoff'

// ------------------------------------------------------------ espera da base
/*
 * A base leva ~1 min na primeira construção. Enquanto isso, a tela mostra o progresso por
 * etapa e se redesenha sozinha quando fica pronta (consulta /fronteira/status a cada 2 s).
 */
export function BaseFronteira({ children }: { children: (st: Envelope<Dado>) => ReactNode }) {
  const { versao } = useOraculo()
  const [tick, setTick] = useState(0)
  const [st, setSt] = useState<{ body: Envelope<Dado> | null; erro: ApiError | null }>({ body: null, erro: null })

  useEffect(() => {
    let vivo = true
    let parar = false
    const ler = async () => {
      if (parar) return
      try {
        const b = await Api.get<Dado>('fronteira/status', null, { fresh: true })
        if (!vivo) return
        setSt({ body: b, erro: null })
        const s = b.data?.state
        if (s === 'ready' || s === 'error') {
          parar = true
          clearInterval(id)
        }
      } catch (e) {
        if (!vivo) return
        parar = true
        clearInterval(id)
        setSt({ body: null, erro: e instanceof ApiError ? e : new ApiError('INTERNAL', String(e)) })
      }
    }
    const id = setInterval(ler, 2000)
    void ler()
    return () => {
      vivo = false
      clearInterval(id)
    }
  }, [versao, tick])

  if (st.erro) return <ErroBloco erro={st.erro} />
  if (!st.body) return <Carregando texto="Consultando a base da fronteira T–D…" />
  const s = st.body.data || {}
  if (s.state === 'ready') return <>{children(st.body)}</>

  const stages: Dado[] = s.stages || []
  const cur = stages.findIndex((x) => x.key === s.stage)
  const tentar = async () => {
    try {
      await Api.post('fronteira/reconstruir')
    } catch {
      /* status mostra */
    }
    setSt({ body: null, erro: null })
    setTick((t) => t + 1)
  }
  return (
    <>
      <div className={'note-strip' + (s.state === 'error' ? ' warn' : '')}>
        {s.state === 'error' ? (
          <>
            <strong>Falha ao construir a base da fronteira T–D.</strong> {s.error}{' '}
            <button className="ghost small" onClick={tentar}>
              tentar de novo
            </button>
          </>
        ) : (
          <>
            <strong>Construindo a base da fronteira T–D.</strong> A primeira vez baixa ~270 MB da ANEEL e do IBGE, agrega e guarda só o agregado no cache. Leva cerca de um minuto; depois,
            a resposta é imediata.
          </>
        )}
      </div>
      <OCard title="Progresso" hint={s.elapsed_s !== null && s.elapsed_s !== undefined ? num(s.elapsed_s, 0) + ' s decorridos' : ''}>
        {stages.map((x, i) => {
          const done = i < cur
          const on = i === cur
          const frac = done ? 1 : on ? s.progress || 0 : 0
          return <BarRow key={x.key} label={x.label} frac={frac} value={done ? 'concluído' : on ? pct(s.progress, 0) : '—'} color={done ? 'green' : 'teal'} />
        })}
      </OCard>
    </>
  )
}

// ------------------------------------------------------------ peças
function ClassBars({ weights }: { weights: Dado }) {
  const w = weights || {}
  return (
    <>
      {CLASSES.map((k) => (
        <BarRow key={k} label={k} frac={w[k] || 0} value={pct(w[k] || 0, 1)} color={CLASS_COLORS[k]} />
      ))}
    </>
  )
}

export function LoadChip({ f }: { f: Dado }) {
  if (f.loading === null || f.loading === undefined) return <span className="chip">—</span>
  const c = f.loading_flag === 'acima da faixa' ? 'crimson' : f.loading_flag === 'abaixo da faixa' ? 'amber' : 'green'
  return (
    <span className={'chip ' + c} title={f.loading_flag || 'dentro da faixa plausível'}>
      {pct(f.loading, 0)}
    </span>
  )
}

function probColor(p: number): string {
  return p >= 0.7 ? 'green' : p >= 0.5 ? 'teal' : p >= 0.3 ? 'amber' : 'crimson'
}

function LegendDot({ c, label }: { c: string; label: string }) {
  return (
    <span className="small muted" style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}>
      <span style={{ width: 9, height: 9, borderRadius: '50%', background: color(c) }} />
      {label}
    </span>
  )
}

// ------------------------------------------------------------ mapa
/* Projeção equiretangular com correção de cos(lat): suficiente na escala de um estado ou do
   país, e sem dependência de biblioteca. */
type ModoMapa = 'osm' | 'svg'

/** Texto do <title> (esquemático) e do tooltip (OSM): o mesmo nos dois fundos. */
function tituloSed(d: Dado, byIdx: Record<number, Dado>): string {
  return 'SED · ' + num(d.e, 1) + ' GWh/ano · p=' + num(d.p, 2) + (d.f >= 0 && byIdx[d.f] ? ' → ' + byIdx[d.f].name : ' · sem SE no raio')
}

function tituloFronteira(f: Dado): string {
  return f.name + ' · ' + num(f.mva) + ' MVA · ' + num(f.n) + ' SEDs · ' + num(f.e, 0) + ' GWh/ano'
}

function Mapa({ map, sel, onPick, modo, setModo }: { map: Dado; sel: string | null; onPick: (id: string) => void; modo: ModoMapa; setModo: (m: ModoMapa) => void }) {
  const fr: Dado[] = map?.frontier || []
  const seds: Dado[] = map?.seds || []
  if (!fr.length && !seds.length) return <Vazio>Sem pontos.</Vazio>
  return (
    <div>
      <div className="chips small" style={{ marginBottom: 8 }}>
        <Chip on={modo === 'osm'} onClick={() => setModo('osm')}>
          OpenStreetMap
        </Chip>
        <Chip on={modo === 'svg'} onClick={() => setModo('svg')}>
          Esquemático
        </Chip>
      </div>
      {modo === 'osm' ? <MapaOsmFronteira fr={fr} seds={seds} sel={sel} onPick={onPick} /> : <MapaSvg fr={fr} seds={seds} sel={sel} onPick={onPick} />}
      <div className="chips small" style={{ marginTop: 8, gap: 10 }}>
        <LegendDot c="navy" label="SE de fronteira (tamanho ∝ √MVA)" />
        <LegendDot c="green" label="SED, p ≥ 0,7" />
        <LegendDot c="teal" label="0,5–0,7" />
        <LegendDot c="amber" label="0,3–0,5" />
        <LegendDot c="crimson" label="< 0,3 ambígua" />
        <LegendDot c="muted" label="sem SE no raio" />
      </div>
    </div>
  )
}

/* Mesma semântica do esquemático, sobre o OSM: a ordem de desenho do SVG (vínculos, SEDs,
   SEs de fronteira) vira ordem de panes; as SEDs (milhares) vão num renderer canvas. */
function MapaOsmFronteira({ fr, seds, sel, onPick }: { fr: Dado[]; seds: Dado[]; sel: string | null; onPick: (id: string) => void }) {
  const byIdx: Record<number, Dado> = {}
  fr.forEach((f) => {
    byIdx[f.i] = f
  })
  const s = fr.find((f) => f.id === sel)
  const maxMva = Math.max(...fr.map((f) => f.mva || 1), 1)
  return (
    <MapaOsm limites={limitesDe(fr.concat(seds))} altura={420} maxZoom={12}>
      <Pane name="fr-vinculos" style={{ zIndex: 405 }}>
        {s
          ? seds.map((d, i) =>
              d.f !== s.i ? null : (
                <Polyline
                  key={'l' + s.i + '-' + i}
                  positions={[
                    [d.lat, d.lon],
                    [s.lat, s.lon],
                  ]}
                  interactive={false}
                  pathOptions={{ color: color(probColor(d.p)), weight: 0.8, opacity: 0.7 }}
                />
              ),
            )
          : null}
      </Pane>
      <Pane name="fr-seds" style={{ zIndex: 410 }}>
        <CamadaSeds seds={seds} s={s} byIdx={byIdx} />
      </Pane>
      <Pane name="fr-se" style={{ zIndex: 420 }}>
        {fr.map((f) => {
          const r = 3 + 7 * Math.sqrt((f.mva || 0) / maxMva)
          const on = !!s && f.i === s.i
          return (
            <CircleMarker
              key={'f' + f.id}
              center={[f.lat, f.lon]}
              radius={r}
              pathOptions={{
                fillColor: color(f.n ? 'navy' : 'muted'),
                fillOpacity: on ? 0.95 : 0.55,
                color: color(on ? 'teal' : 'navy'),
                weight: on ? 2.4 : 1,
                opacity: 1,
              }}
              eventHandlers={{ click: () => onPick(f.id) }}
            >
              <Tooltip direction="top">{tituloFronteira(f)}</Tooltip>
            </CircleMarker>
          )
        })}
      </Pane>
    </MapaOsm>
  )
}

function CamadaSeds({ seds, s, byIdx }: { seds: Dado[]; s: Dado | undefined; byIdx: Record<number, Dado> }) {
  // monta dentro do pane "fr-seds", que já existe quando o renderer é criado
  const renderer = useMemo(() => L.canvas({ pane: 'fr-seds', tolerance: 3 }), [])
  return (
    <>
      {seds.map((d, i) => {
        const on = !!s && d.f === s.i
        return <SedOsm key={'d' + i} d={d} on={on} dim={!!s && !on} texto={tituloSed(d, byIdx)} renderer={renderer} />
      })}
    </>
  )
}

/** SED no OSM; tooltip ligado direto na camada (sem um portal React por ponto). */
function SedOsm({ d, on, dim, texto, renderer }: { d: Dado; on: boolean; dim: boolean; texto: string; renderer: L.Renderer }) {
  const ref = useRef<L.CircleMarker | null>(null)
  useEffect(() => {
    ref.current?.bindTooltip(texto, { direction: 'top' })
  }, [texto])
  return (
    <CircleMarker
      ref={ref}
      center={[d.lat, d.lon]}
      radius={on ? 2.6 : 1.5}
      renderer={renderer}
      pathOptions={{ stroke: false, fillColor: color(d.f < 0 ? 'muted' : probColor(d.p)), fillOpacity: dim ? 0.35 : 0.8 }}
    />
  )
}

function MapaSvg({ fr, seds, sel, onPick }: { fr: Dado[]; seds: Dado[]; sel: string | null; onPick: (id: string) => void }) {
  const pts = fr.map((f) => [f.lat, f.lon]).concat(seds.map((s) => [s.lat, s.lon]))
  const lats = pts.map((p) => p[0])
  const lons = pts.map((p) => p[1])
  let la0 = Math.min(...lats)
  let la1 = Math.max(...lats)
  let lo0 = Math.min(...lons)
  let lo1 = Math.max(...lons)
  const padLa = (la1 - la0) * 0.05 + 0.05
  const padLo = (lo1 - lo0) * 0.05 + 0.05
  la0 -= padLa
  la1 += padLa
  lo0 -= padLo
  lo1 += padLo
  const k = Math.cos((((la0 + la1) / 2) * Math.PI) / 180)
  const W = 640
  const H = Math.max(260, Math.min(560, (W * (la1 - la0)) / ((lo1 - lo0) * k)))
  const sx = (lo: number) => ((lo - lo0) / (lo1 - lo0)) * W
  const sy = (la: number) => H - ((la - la0) / (la1 - la0)) * H
  const byIdx: Record<number, Dado> = {}
  fr.forEach((f) => {
    byIdx[f.i] = f
  })
  const s = fr.find((f) => f.id === sel)
  const maxMva = Math.max(...fr.map((f) => f.mva || 1), 1)

  return (
      <svg viewBox={'0 0 ' + W + ' ' + H.toFixed(0)} width="100%" role="img" aria-label="Mapa de SEs de fronteira e subestações de distribuição" style={{ display: 'block' }}>
        {s
          ? seds.map((d, i) =>
              d.f !== s.i ? null : (
                <line key={'l' + i} x1={sx(d.lon).toFixed(1)} y1={sy(d.lat).toFixed(1)} x2={sx(s.lon).toFixed(1)} y2={sy(s.lat).toFixed(1)} stroke={color(probColor(d.p))} strokeWidth={0.8} opacity={0.7} />
              ),
            )
          : null}
        {seds.map((d, i) => {
          const on = !!s && d.f === s.i
          return (
            <circle key={'d' + i} cx={sx(d.lon).toFixed(1)} cy={sy(d.lat).toFixed(1)} r={on ? 2.6 : 1.5} fill={color(d.f < 0 ? 'muted' : probColor(d.p))} opacity={s && !on ? 0.35 : 0.8}>
              <title>{tituloSed(d, byIdx)}</title>
            </circle>
          )
        })}
        {fr.map((f) => {
          const r = 3 + 7 * Math.sqrt((f.mva || 0) / maxMva)
          const on = !!s && f.i === s.i
          return (
            <circle
              key={'f' + f.id}
              cx={sx(f.lon).toFixed(1)}
              cy={sy(f.lat).toFixed(1)}
              r={r.toFixed(1)}
              fill={color(f.n ? 'navy' : 'muted')}
              fillOpacity={on ? 0.95 : 0.55}
              stroke={color(on ? 'teal' : 'navy')}
              strokeWidth={on ? 2.4 : 1}
              style={{ cursor: 'pointer' }}
              onClick={() => onPick(f.id)}
            >
              <title>{tituloFronteira(f)}</title>
            </circle>
          )
        })}
      </svg>
  )
}

// ------------------------------------------------------------ tela
export default function Fronteira() {
  return (
    <Pagina>
      <BaseFronteira>{(st) => <Painel st={st} />}</BaseFronteira>
    </Pagina>
  )
}

function Painel({ st }: { st: Envelope<Dado> }) {
  const [uf, setUf] = usePersistido<string>('oraculo.frUf', '')
  const [order, setOrder] = usePersistido<string>('oraculo.frOrder', 'energia')
  const estado = useApi(() => Api.get<Dado>('fronteira/resumo', { uf: uf || '', order: order || 'energia' }), [uf, order])
  return (
    <Conteudo estado={estado} texto="Correlacionando subestações de distribuição e de fronteira…">
      {(body) => <Corpo body={body} st={st} uf={uf} order={order} setUf={setUf} setOrder={setOrder} />}
    </Conteudo>
  )
}

function Corpo({
  body,
  st,
  uf,
  order,
  setUf,
  setOrder,
}: {
  body: Envelope<Dado>
  st: Envelope<Dado>
  uf: string
  order: string
  setUf: (v: string) => void
  setOrder: (v: string) => void
}) {
  const [sel, setSel] = usePersistido<string | null>('oraculo.frSel', null)
  const [modoMapa, setModoMapa] = usePersistido<ModoMapa>('oraculo.frMapa', 'osm')
  const d = body.data
  const k = d.kpis || {}
  const rows: Dado[] = d.rows || []
  let selEf = sel
  if (!selEf || !rows.some((r) => r.sub_id === selEf)) {
    const first = rows.find((r) => r.n_sed > 0) || rows[0]
    selEf = first ? first.sub_id : null
  }
  useEffect(() => {
    if (selEf !== sel) setSel(selEf)
  }, [selEf, sel, setSel])
  const sd = st.data || {}

  return (
    <>
      <div className="note-strip">
        O ONS publica a <strong>rede básica</strong>; a subestação de distribuição está na <strong>BDGD da ANEEL</strong>. Cada SED é reconstruída das unidades consumidoras de média e alta
        tensão que ela atende (código <span className="mono">SUB</span>, classe, 12 meses de energia e demanda, coordenada) e associada à SE de fronteira que a alimenta. A associação é{' '}
        <strong>inferida</strong> — a topologia de subtransmissão não é dado público — e cada vínculo sai com probabilidade e alternativas.
      </div>

      <div className="grid g4" style={{ marginBottom: 14 }}>
        <Kpi label="SEs de fronteira com carga" value={num(k.frontier_with_sed)} foot={'de ' + num(k.frontier) + ' no filtro · secundário ≤ 138 kV'} accent="teal" />
        <Kpi label="SEDs associadas" value={num(k.seds)} foot={pct(k.ambiguous_rate, 0) + ' ambíguas (p < 0,5) · distância mediana ' + num(k.median_distance_km, 1) + ' km'} accent="navy" />
        <Kpi label="Energia alocada" value={num(k.energy_twh, 1)} unit="TWh/ano" foot={pct(k.measured_share, 0) + ' medida por UC (MT/AT) · resto baixa tensão rateada'} accent="green" />
        <Kpi label="MMGD alocada" value={num(k.gd_mw, 0)} unit="MW" foot={pct(k.gd_direct_share, 0) + ' por vínculo direto CEG_GD → UC → SED'} accent="amber" />
      </div>

      <div className="chips" style={{ marginBottom: 12 }}>
        <Chip
          on={!uf}
          onClick={() => {
            setUf('')
            setSel(null)
          }}
        >
          todas as UF
        </Chip>
        {(d.ufs || []).map((u: string) => (
          <Chip
            key={u}
            on={uf === u}
            onClick={() => {
              setUf(u)
              setSel(null)
            }}
          >
            {u}
          </Chip>
        ))}
        <select className="chip clickable" style={{ marginLeft: 'auto' }} value={order || 'energia'} onChange={(e) => setOrder(e.target.value)}>
          {ORDENS.map((o) => (
            <option key={o[0]} value={o[0]}>
              {o[1]}
            </option>
          ))}
        </select>
      </div>

      <div className="grid g2" style={{ marginBottom: 14 }}>
        <OCard
          title="Mapa"
          hint="clique numa SE de fronteira"
          note={'Posição da SED = mediana das UCs de média e alta tensão que ela atende, não a coordenada do barramento.' + (modoMapa === 'osm' ? ' Fundo: © OpenStreetMap contributors.' : '')}
        >
          <Mapa map={d.map} sel={selEf} onPick={setSel} modo={modoMapa} setModo={setModoMapa} />
        </OCard>
        <OCard title="SEs de fronteira" hint={num(rows.length) + ' no filtro'}>
          <div className="table-wrap scroll-y" style={{ maxHeight: 520 }}>
            <table>
              <thead>
                <tr>
                  <th>SE de fronteira</th>
                  <th className="num">SEDs</th>
                  <th className="num">GWh/ano</th>
                  <th>Classe dominante</th>
                  <th className="num">MMGD</th>
                  <th>Carreg.</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.sub_id} className={r.sub_id === selEf ? 'sel' : ''} style={{ cursor: 'pointer' }} onClick={() => setSel(r.sub_id)}>
                    <td>
                      <strong>{r.name}</strong>
                      <br />
                      <span className="small faint">{r.uf + ' · ' + num(r.frontier_mva) + ' MVA · ' + num(r.voltage_kv) + '/' + num(r.secondary_kv) + ' kV'}</span>
                    </td>
                    <td className="num">{num(r.n_sed)}</td>
                    <td className="num">{num(r.e_total_gwh, 0)}</td>
                    <td className="small">
                      {r.dominant || '—'}
                      <br />
                      <span className="faint">{pct((r.weights || {})[r.dominant], 0)}</span>
                    </td>
                    <td className="num">
                      {num(r.gd_kw / 1000, 0)} MW
                      <br />
                      <span className="small faint">{pct(r.gd_penetration, 0)} da carga média</span>
                    </td>
                    <td>
                      <LoadChip f={r} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </OCard>
      </div>

      {selEf ? <Detalhe id={selEf} /> : null}

      <div className="grid g2" style={{ marginTop: 14 }}>
        <OCard title="Pipeline replicável" note={'Base agregada reconstruída a cada ' + num(sd.ttl_days, 0) + ' dias. Construída em ' + when(sd.built_at) + ' (' + (sd.base_mode ?? '') + ').'}>
          <ol className="actions" style={{ paddingLeft: 20 }}>
            {(d.pipeline || []).map((x: string, i: number) => (
              <li key={i}>{x}</li>
            ))}
          </ol>
        </OCard>
        <OCard
          title="Premissas da associação"
          note={
            <>
              Versionadas em <span className="mono">config.FRONTEIRA</span>. α e λ foram escolhidos pela varredura do painel <Link to="/correlacao">Qualidade da correlação</Link>.
            </>
          }
        >
          <StatLines pares={(d.premises || []).map((p: Dado) => [p.k, p.v] as [ReactNode, ReactNode])} />
        </OCard>
      </div>
      <Proveniencia body={body} />
    </>
  )
}

// ------------------------------------------------------------ detalhe da SE
function Detalhe({ id }: { id: string }) {
  const estado = useApi(() => Api.get<Dado>('fronteira/se/' + encodeURIComponent(id)), [id])
  return (
    <Conteudo estado={estado} texto="Montando o detalhe da SE…">
      {(body) => <DetalheCorpo f={body.data} />}
    </Conteudo>
  )
}

function DetalheCorpo({ f }: { f: Dado }) {
  const navigate = useNavigate()
  const [, setHandoff] = usePersistido<Dado>(CLM_HANDOFF_KEY, null)
  const cmp = f.comparison
  const clm = f.clm || {}
  const titulo = 'Detalhe · ' + f.name + ' (' + f.uf + ')'
  if (!f.n_sed) {
    return (
      <OCard title={titulo}>
        <Vazio>
          Nenhuma subestação de distribuição foi associada a esta SE. Ou ela interliga transmissão sem entregar carga local, ou a carga da área foi atraída por uma SE vizinha — confira as
          alternativas das SEDs próximas.
        </Vazio>
      </OCard>
    )
  }
  const mt = f.e_mtat_class_kwh || {}
  const bt = f.e_bt_class_kwh || {}

  return (
    <>
      <OCard title={titulo} hint={f.agent + ' · ' + num(f.voltage_kv) + '/' + num(f.secondary_kv) + ' kV · ' + num(f.pop_served) + ' habitantes rateados'}>
        <div className="grid g4" style={{ gap: 12, marginBottom: 12 }}>
          <Kpi label="SEDs associadas" value={num(f.n_sed)} foot={num(f.n_uc) + ' UCs de média/alta tensão · ' + pct(f.ambiguous_share, 0) + ' da energia medida em vínculo ambíguo'} />
          <Kpi label="Energia" value={num(f.e_total_gwh, 0)} unit="GWh/ano" foot={pct(f.measured_share, 0) + ' medida · ' + num(f.e_bt_gwh, 0) + ' GWh de baixa tensão rateada'} />
          <Kpi
            label="Carga média"
            value={num(f.mw_avg, 0)}
            unit="MW"
            foot={
              <>
                {'carregamento implícito ' + (f.loading === null ? '—' : pct(f.loading, 0)) + ' de ' + num(f.frontier_mva) + ' MVA'}
                {f.loading_flag ? (
                  <>
                    {' · '}
                    <span className="neg">{f.loading_flag}</span>
                  </>
                ) : null}
              </>
            }
          />
          <Kpi
            label="MMGD instalada"
            value={num(f.gd_kw / 1000, 1)}
            unit="MW"
            foot={num(f.gd_n) + ' unidades · ' + pct(f.gd_penetration, 0) + ' da carga média · ' + pct(f.gd_direct_share, 0) + ' vínculo direto'}
          />
        </div>
        <div className="grid g2" style={{ gap: 12 }}>
          <div>
            <div className="okpi-label" style={{ marginBottom: 6 }}>
              Composição por classe · medida (MT/AT) e rateada (BT), GWh/ano
            </div>
            <Grafico
              deps={[f]}
              desenhar={(el) =>
                stackedBars(el, {
                  labels: CLASSES,
                  stacks: [
                    { label: 'medida (MT/AT)', color: 'navy', values: CLASSES.map((c) => (mt[c] || 0) / 1e6) },
                    { label: 'rateada (BT)', color: 'teal', values: CLASSES.map((c) => (bt[c] || 0) / 1e6) },
                  ],
                  height: 220,
                  unit: 'GWh',
                })
              }
            />
          </div>
          <div>
            <div className="okpi-label" style={{ marginBottom: 6 }}>
              Sazonalidade · energia mensal, GWh
            </div>
            <Grafico
              deps={[f]}
              desenhar={(el) =>
                stackedBars(el, {
                  labels: f.months || MONTHS,
                  stacks: [
                    { label: 'medida (MT/AT)', color: 'navy', values: f.e_month_mtat_gwh || [] },
                    { label: 'rateada (BT)', color: 'teal', values: f.e_month_bt_gwh || [] },
                  ],
                  height: 220,
                  unit: 'GWh',
                })
              }
            />
          </div>
        </div>
      </OCard>

      <div className="grid g2" style={{ marginTop: 14 }}>
        <OCard
          title="Duas representações da mesma SE"
          note={
            cmp ? (
              <>
                O Mapa Inteligente estima a composição pela morfologia de ortoimagem (sintética no protótipo) com prior do subsistema. Aqui ela vem de <strong>energia faturada real</strong>. A
                diferença é o ganho de representação que esta seção entrega ao modelo de carga.
              </>
            ) : (
              'SE fora do lote do Mapa Inteligente.'
            )
          }
        >
          <Comparacao cmp={cmp} />
        </OCard>
        <OCard title="Insumo ao Modelo de Carga Composta" hint={clm.fonte || ''} note={clm.aviso || ''}>
          <StatLines
            pares={[
              ['Fração de motor estimada', num(clm.fracao_motor_estimada, 3)],
              ['MMGD instalada', num((clm.mmgd_kw_instalada || 0) / 1000, 1) + ' MW'],
              ['Pdg ao meio-dia (teto)', num(clm.pdg_mw_meio_dia, 1) + ' MW'],
              ['Penetração (GD ÷ carga média)', pct(clm.mmgd_penetracao, 0)],
              ['Carga média', num(clm.carga_media_mw, 1) + ' MW'],
              ['Parcela medida por UC', pct(clm.parcela_medida, 0)],
            ]}
          />
          <ClassBars weights={clm.composicao_classe} />
          <div style={{ marginTop: 12 }}>
            <button
              onClick={() => {
                const hand = { subId: f.sub_id, name: f.name, fonte: 'bdgd' }
                setHandoff(hand)
                navigate('/clm', { state: { clmHandoff: hand } })
              }}
            >
              Abrir no cartão CLM com esta composição →
            </button>
          </div>
        </OCard>
      </div>

      <OCard
        title="Subestações de distribuição associadas"
        hint="ordenadas por energia · p = probabilidade do vínculo"
        note="Alternativas: as SEs de fronteira seguintes no modelo gravitacional. Um vínculo ambíguo não é erro — é a informação de que ali há mais de uma SE plausível e a topologia precisa ser confirmada com a distribuidora."
      >
        <TabelaSed seds={f.seds} />
      </OCard>
    </>
  )
}

function Comparacao({ cmp }: { cmp: Dado }) {
  if (!cmp) return <Vazio>Sem comparação disponível.</Vazio>
  const m = cmp.mapa || {}
  const b = cmp.bdgd || {}
  return (
    <>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Classe</th>
              <th className="num">Mapa Inteligente</th>
              <th className="num">BDGD + SAMP</th>
              <th className="num">Δ</th>
            </tr>
          </thead>
          <tbody>
            {CLASSES.map((c) => {
              const dv = (cmp.diff || {})[c] || 0
              return (
                <tr key={c}>
                  <td>{c}</td>
                  <td className="num">{pct((m.weights || {})[c], 1)}</td>
                  <td className="num">{pct((b.weights || {})[c], 1)}</td>
                  <td className={'num ' + (Math.abs(dv) >= 0.1 ? (dv > 0 ? 'pos' : 'neg') : '')}>{(dv > 0 ? '+' : '') + num(dv * 100, 1) + ' p.p.'}</td>
                </tr>
              )
            })}
            <tr>
              <td>
                <strong>dominante</strong>
              </td>
              <td className="num">{m.dominant || '—'}</td>
              <td className="num">{b.dominant || '—'}</td>
              <td />
            </tr>
            <tr>
              <td>
                <strong>MMGD</strong>
              </td>
              <td className="num">{num((m.mmgd_kw || 0) / 1000, 1)} MW</td>
              <td className="num">{num((b.mmgd_kw || 0) / 1000, 1)} MW</td>
              <td className="num">{cmp.mmgd_ratio ? '×' + num(cmp.mmgd_ratio, 1) : <span className="small neg">amostra sem painel</span>}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div className="card-note">
        Distância entre composições (variação total): <strong>{pct(cmp.l1, 0)}</strong>. MMGD do Mapa: detecção em amostra extrapolada; aqui: cadastro homologado da ANEEL.
      </div>
    </>
  )
}

function TabelaSed({ seds }: { seds: Dado[] }) {
  return (
    <div className="table-wrap scroll-y">
      <table>
        <thead>
          <tr>
            <th>SED</th>
            <th>Distribuidora</th>
            <th className="num">UCs</th>
            <th className="num">GWh/ano</th>
            <th>Classe</th>
            <th className="num">MMGD direta</th>
            <th className="num">km</th>
            <th className="num">p</th>
            <th>Alternativas</th>
          </tr>
        </thead>
        <tbody>
          {(seds || []).slice(0, 150).map((s, i) => (
            <tr key={(s.key || s.sub) + ':' + i}>
              <td className="mono small">{s.sub}</td>
              <td className="small">
                {s.distribuidora}
                {s.agent_match ? (
                  <>
                    {' '}
                    <span className="chip teal" title="mesmo grupo econômico do agente da SE no ONS">
                      grupo
                    </span>
                  </>
                ) : null}
              </td>
              <td className="num">{num(s.n_uc)}</td>
              <td className="num">{num(s.e_gwh, 1)}</td>
              <td className="small">{s.dominant}</td>
              <td className="num">{s.gd_kw_direct ? num(s.gd_kw_direct / 1000, 2) + ' MW' : '—'}</td>
              <td className="num">{num(s.d_km, 1)}</td>
              <td className="num">
                <span className={'chip ' + probColor(s.p)}>{num(s.p, 2)}</span>
              </td>
              <td className="small faint">{(s.alternatives || []).map((a: Dado) => a.name + ' ' + num(a.p, 2)).join(' · ')}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
