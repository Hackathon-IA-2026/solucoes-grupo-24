/**
 * Investimento: alocação de BESS pelo corte observado e pela MMGD (protótipo, painel "bess").
 * Porte de 02-PROTOTIPO/web/js/views/bess.js (V.bess). A interface não calcula nada: os pesos
 * vão ao servidor, que refaz a pontuação.
 */
import L from 'leaflet'
import { Fragment, useEffect, useState, type ReactNode } from 'react'
import { CircleMarker, Marker, Tooltip } from 'react-leaflet'
import { Api, ApiError, type Envelope } from '../api'
import { barChart, color, heatStrip, lineChart, scatter } from '../charts'
import { useOraculo, usePersistido } from '../estado'
import { num, pct } from '../format'
import { MapaOsm, limitesDe } from '../MapaOsm'
import { BarRow, Carregando, Chip, Conteudo, ErroBloco, Grafico, Kpi, OCard, Pagina, Proveniencia, StatLines, Vazio, useApi } from '../ui'

/* eslint-disable @typescript-eslint/no-explicit-any */
type Dado = any
type Pesos = Record<string, number>

const COMP: [string, string, string][] = [
  ['energia', 'Energia recuperável', 'teal'],
  ['mmgd', 'Excedente da MMGD', 'amber'],
  ['recorrencia', 'Recorrência do corte', 'purple'],
  ['local', 'Restrição local', 'green'],
]

function weightParams(w: Pesos | null): Record<string, number> {
  if (!w) return {}
  const out: Record<string, number> = {}
  COMP.forEach((c) => {
    out['w_' + c[0]] = w[c[0]]
  })
  return out
}

/**
 * Espera a base de constrained-off ficar pronta (GET bess/status, sem cache). Enquanto baixa,
 * mostra o progresso e consulta de novo a cada 3 s; em falha, oferece "tentar de novo"
 * (POST bess/reconstruir).
 */
export function ProntoBess({ texto, children }: { texto: string; children: ReactNode }) {
  const { versao } = useOraculo()
  const [st, setSt] = useState<Dado>(null)
  const [erro, setErro] = useState<ApiError | null>(null)
  const [tick, setTick] = useState(0)

  useEffect(() => {
    let vivo = true
    let t: ReturnType<typeof setTimeout> | undefined
    Api.get('bess/status', null, { fresh: true })
      .then((b) => {
        if (!vivo) return
        const s = b.data as Dado
        setSt(s)
        setErro(null)
        if (s.state !== 'ready' && s.state !== 'error') t = setTimeout(() => setTick((x) => x + 1), 3000)
      })
      .catch((e: unknown) => vivo && setErro(e instanceof ApiError ? e : new ApiError('INTERNAL', String(e))))
    return () => {
      vivo = false
      clearTimeout(t)
    }
  }, [tick, versao])

  async function retry() {
    try {
      await Api.post('bess/reconstruir')
    } catch {
      /* status mostra */
    }
    setTick((x) => x + 1)
  }

  if (erro) return <ErroBloco erro={erro} />
  if (!st) return <Carregando texto={texto} />
  if (st.state === 'ready') return <>{children}</>
  return (
    <>
      <div className={'note-strip' + (st.state === 'error' ? ' warn' : '')}>
        {st.state === 'error' ? (
          <>
            <strong>Falha ao montar a base de constrained-off.</strong> {st.error}{' '}
            <button className="ghost small" onClick={retry}>
              tentar de novo
            </button>
          </>
        ) : (
          <>
            <strong>Baixando 12 meses de constrained-off do ONS</strong> (fotovoltaica e eólica, ~800 MB). Cada mês é agregado e guardado; da próxima vez, só o
            mês novo é baixado.
          </>
        )}
      </div>
      <OCard title="Progresso">
        <BarRow label="meses agregados" frac={st.overall || 0} value={num(st.done) + ' de ' + num(st.total)} color="teal" />
        <div className="card-note">
          Agora: {st.stage || '—'}
          {st.elapsed_s ? ' · ' + num(st.elapsed_s, 0) + ' s decorridos' : ''}
        </div>
      </OCard>
    </>
  )
}

const TEXTO = 'Simulando o BESS em cada sítio de corte…'

export default function Bess() {
  return (
    <Pagina>
      <ProntoBess texto={TEXTO}>
        <Ranking />
      </ProntoBess>
    </Pagina>
  )
}

function Ranking() {
  const [uf, setUf] = usePersistido('oraculo.bsUf', '')
  const [fonte, setFonte] = usePersistido('oraculo.bsFonte', '')
  const [w, setW] = usePersistido<Pesos | null>('oraculo.bsW', null)
  const [sel, setSel] = usePersistido<string | null>('oraculo.bsSel', null)
  const wKey = JSON.stringify(w)
  const estado = useApi(() => Api.get('bess/ranking', { uf, fonte, ...weightParams(w) }), [uf, fonte, wKey])

  return (
    <Conteudo estado={estado} texto={TEXTO}>
      {(body) => (
        <Corpo
          body={body}
          uf={uf}
          fonte={fonte}
          w={w}
          sel={sel}
          setSel={setSel}
          setUf={(u) => {
            setUf(u)
            setSel(null)
          }}
          setFonte={(f) => {
            setFonte(f)
            setSel(null)
          }}
          setW={(nw) => {
            setW(nw)
            setSel(null)
          }}
        />
      )}
    </Conteudo>
  )
}

function Corpo({
  body,
  uf,
  fonte,
  w,
  sel,
  setSel,
  setUf,
  setFonte,
  setW,
}: {
  body: Envelope
  uf: string
  fonte: string
  w: Pesos | null
  sel: string | null
  setSel: (c: string | null) => void
  setUf: (u: string) => void
  setFonte: (f: string) => void
  setW: (w: Pesos | null) => void
}) {
  const d = body.data as Dado
  const k = d.kpis || {}
  const rows: Dado[] = d.rows || []
  const wEf: Pesos = w || d.default_weights || {}
  const selEf = sel && rows.some((r) => r.code === sel) ? sel : rows.length ? rows[0].code : null
  const [ss, setSs] = usePersistido('oraculo.bsSS', 'NE')

  return (
    <>
      <div className="note-strip">
        <strong>Apoio à decisão de investimento.</strong> O corte acontece nas usinas <strong>eólicas e fotovoltaicas centralizadas</strong> — 12 meses de{' '}
        <em>constrained-off</em> apurado pelo ONS, por subestação de conexão. A MMGD não é cortada: ela reduz a carga líquida ao meio-dia, aprofunda a barriga da
        curva do pato e cria o excedente que vira corte por razão energética de origem sistêmica (ENE+SIS). Em cada sítio, um BESS é simulado carregando no corte e
        devolvendo na rampa do fim da tarde.
      </div>

      <div className="grid g4" style={{ marginBottom: 14 }}>
        <Kpi
          label="Corte apurado"
          value={num(k.cut_twh_year, 2)}
          unit="TWh/ano"
          foot={'FV + eólica · ' + num(k.sites) + ' sítios · ' + pct(k.ene_share, 0) + ' por razão energética'}
          accent="crimson"
        />
        <Kpi label="Concentração" value={pct(k.cut_top10_share, 0)} foot="do corte está em 10 sítios" accent="amber" />
        <Kpi
          label="Excedente da MMGD"
          value={num(k.mmgd_induced_twh, 1)}
          unit="TWh/ano"
          foot={'até ' + pct(k.mmgd_induced_share, 0) + ' do corte · limite superior sobre o corte ENE+SIS (' + pct(k.es_share, 0) + ')'}
          accent="amber"
        />
        <Kpi
          label="Recuperável no top 10"
          value={num(k.recoverable_top10_twh, 2)}
          unit="TWh/ano"
          foot={'BESS dimensionado em cada sítio · ' + pct(k.located_share, 1) + ' do corte localizado'}
          accent="teal"
        />
      </div>

      <div className="grid g-1-2" style={{ marginBottom: 14 }}>
        <OCard
          title="Pesos da pontuação"
          note="Cada componente é um posto percentual (0 a 1) entre os sítios; os pesos são normalizados. A estabilidade do top 10 sob outros pesos está no painel Método."
        >
          <PainelPesos key={JSON.stringify(wEf)} w={wEf} aplicar={setW} />
        </OCard>
        <div className="card">
          <div className="chips" style={{ marginBottom: 10 }}>
            <span className="small muted" style={{ alignSelf: 'center' }}>
              fonte
            </span>
            {[
              ['', 'todas'],
              ['fotovoltaica', 'fotovoltaica'],
              ['eólica', 'eólica'],
            ].map((f) => (
              <Chip key={f[0] || '_'} on={(fonte || '') === f[0]} onClick={() => setFonte(f[0])}>
                {f[1]}
              </Chip>
            ))}
            <span className="small muted" style={{ alignSelf: 'center', marginLeft: 10 }}>
              UF
            </span>
            <Chip on={!uf} onClick={() => setUf('')}>
              todas
            </Chip>
            {(d.ufs || []).map((u: string) => (
              <Chip key={u} on={uf === u} onClick={() => setUf(u)}>
                {u}
              </Chip>
            ))}
          </div>
          <Mapa pts={d.map || []} sel={selEf} onPick={setSel} />
        </div>
      </div>

      <div className="grid g-2-1" style={{ marginBottom: 14 }}>
        <OCard
          title="Por que há excedente: a curva do pato"
          hint="perfil médio horário na janela do corte"
          note="Carga com MMGD − MMGD = carga supervisionada; menos eólica e solar centralizadas = carga líquida. A distância entre a primeira e a segunda curvas ao meio-dia é a MMGD, que aprofunda a barriga do pato; o corte (vermelho) acontece ali."
        >
          <div className="chips" style={{ marginBottom: 8 }}>
            {SS_ORDER.filter((s) => (d.duck || {})[s]).map((s) => (
              <Chip key={s} on={ss === s} onClick={() => setSs(s)}>
                {s} — {d.duck[s].name}
              </Chip>
            ))}
          </div>
          <Grafico deps={[d.duck, ss]} desenhar={(el) => drawDuck(el, d.duck, ss)} />
        </OCard>
        <OCard
          title="Tese 2 · BESS junto à carga"
          hint="onde a MMGD mais pesa sobre a carga"
          note="Outra decisão de investimento: armazenamento perto da MMGD achata a curva do pato na origem e suaviza a rampa. Não recupera o corte de uma usina específica — por isso não entra no ranking ao lado. MW de MMGD ÷ MW médio de carga (seção Fronteira T–D)."
        >
          <TabelaCarga rows={d.load_side} />
        </OCard>
      </div>

      <OCard
        title="Tese 1 · BESS junto à geração cortada"
        hint={'clique num sítio para o detalhe · ' + num(rows.length) + ' no filtro'}
        note="BESS sugerido: o maior tamanho da grade em que o MWh ADICIONAL ainda cicla ≥ 200 vezes/ano. Chip âmbar: nem o menor tamanho atinge esse uso."
      >
        <TabelaRanking rows={rows} sel={selEf} onPick={setSel} />
      </OCard>

      <div style={{ marginTop: 14 }}>{selEf ? <Detalhe code={selEf} w={w} /> : null}</div>

      <div className="grid g2" style={{ marginTop: 14 }}>
        <OCard title="Pipeline replicável" note={'Meses na janela: ' + (d.months || []).join(', ')}>
          <ol className="actions" style={{ paddingLeft: 20 }}>
            {(d.pipeline || []).map((x: string, i: number) => (
              <li key={i}>{x}</li>
            ))}
          </ol>
        </OCard>
        <OCard
          title="Premissas"
          note={
            <>
              Versionadas em <span className="mono">config.BESS</span>.
            </>
          }
        >
          <StatLines pares={(d.premises || []).map((p: Dado) => [p.k, p.v])} />
        </OCard>
      </div>
      <Proveniencia body={body} />
    </>
  )
}

function PainelPesos({ w, aplicar }: { w: Pesos; aplicar: (w: Pesos | null) => void }) {
  const [rascunho, setRascunho] = useState<Pesos>(() => {
    const o: Pesos = {}
    COMP.forEach((c) => {
      o[c[0]] = (w || {})[c[0]] || 0
    })
    return o
  })
  return (
    <>
      {COMP.map((c) => (
        <div key={c[0]} className="bar-row" style={{ gridTemplateColumns: '150px 1fr 44px' }}>
          <span>{c[1]}</span>
          <input
            type="range"
            min={0}
            max={1}
            step={0.05}
            value={rascunho[c[0]]}
            onChange={(e) => {
              const v = parseFloat(e.target.value)
              setRascunho((r) => ({ ...r, [c[0]]: v }))
            }}
            style={{ accentColor: `var(--o-${c[2]})` }}
          />
          <span className="v">{num(rascunho[c[0]], 2)}</span>
        </div>
      ))}
      <div style={{ marginTop: 10, display: 'flex', gap: 8 }}>
        <button onClick={() => aplicar({ ...rascunho })}>Aplicar</button>
        <button className="ghost" onClick={() => aplicar(null)}>
          Padrão
        </button>
      </div>
    </>
  )
}

// ------------------------------------------------------------ mapa
function Legenda({ cor, label }: { cor: string; label: string }) {
  return (
    <span className="small muted" style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}>
      <span style={{ width: 9, height: 9, borderRadius: '50%', background: color(cor) }} />
      {label}
    </span>
  )
}

type ModoMapa = 'osm' | 'svg'

/** Regras comuns aos dois fundos: cor, raio e texto do hover. */
const corSitio = (p: Dado): string => (p.rank <= 10 ? 'crimson' : p.score >= 0.5 ? 'amber' : 'teal')
const raioSitio = (p: Dado, maxE: number): number => 3 + 16 * Math.sqrt((p.cut_gwh || 0) / maxE)
const tituloSitio = (p: Dado): string => '#' + p.rank + ' ' + p.name + ' · ' + num(p.cut_gwh, 0) + ' GWh/ano cortados · pontuação ' + num(p.score, 2)

function Mapa({ pts, sel, onPick }: { pts: Dado[]; sel: string | null; onPick: (c: string) => void }) {
  const [modo, setModo] = usePersistido<ModoMapa>('oraculo.bsMapa', 'osm')
  if (!pts.length) return <Vazio>Sem sítios localizados.</Vazio>
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
      {modo === 'osm' ? <MapaOsmSitios pts={pts} sel={sel} onPick={onPick} /> : <MapaSvg pts={pts} sel={sel} onPick={onPick} />}
      <div className="chips small" style={{ marginTop: 8, gap: 10 }}>
        <Legenda cor="crimson" label="top 10 da pontuação" />
        <Legenda cor="amber" label="pontuação ≥ 0,5" />
        <Legenda cor="teal" label="demais" />
        <span className="small muted">tamanho ∝ √ energia cortada</span>
      </div>
      {modo === 'osm' ? <div className="card-note">Fundo: © OpenStreetMap contributors.</div> : null}
    </div>
  )
}

/** Rótulo do posto (top 10) sobre o círculo, como o <text> do esquemático. */
function rotuloRank(rank: number): L.DivIcon {
  return L.divIcon({
    className: '',
    iconSize: [24, 12],
    iconAnchor: [12, 6],
    html: '<span style="display:block;text-align:center;line-height:12px;font:700 9px var(--o-mono);color:#fff;pointer-events:none">' + rank + '</span>',
  })
}

/* Mesma semântica do esquemático sobre o OSM: maiores primeiro (os menores ficam por cima) e
   rótulo do posto nos 10 primeiros. A chave pela ordem refaz as camadas quando o filtro muda,
   para a ordem de desenho acompanhar a do SVG. */
function MapaOsmSitios({ pts, sel, onPick }: { pts: Dado[]; sel: string | null; onPick: (c: string) => void }) {
  const maxE = Math.max(...pts.map((p) => p.cut_gwh || 0).concat([1]))
  const sorted = pts.slice().sort((a, b) => (b.cut_gwh || 0) - (a.cut_gwh || 0))
  const ordem = sorted.map((p) => p.code).join('|')
  return (
    <MapaOsm limites={limitesDe(pts)} altura={420} maxZoom={11}>
      <Fragment key={ordem}>
        {sorted.map((p) => {
          const col = corSitio(p)
          const on = p.code === sel
          return (
            <CircleMarker
              key={p.code}
              center={[p.lat, p.lon]}
              radius={raioSitio(p, maxE)}
              pathOptions={{ fillColor: color(col), fillOpacity: on ? 0.95 : 0.55, color: color(on ? 'teal' : col), weight: on ? 2.6 : 1, opacity: 1 }}
              eventHandlers={{ click: () => onPick(p.code) }}
            >
              <Tooltip direction="top">{tituloSitio(p)}</Tooltip>
            </CircleMarker>
          )
        })}
        {sorted
          .filter((p) => p.rank <= 10)
          .map((p) => (
            <Marker key={'r' + p.code} position={[p.lat, p.lon]} icon={rotuloRank(p.rank)} interactive={false} keyboard={false} />
          ))}
      </Fragment>
    </MapaOsm>
  )
}

function MapaSvg({ pts, sel, onPick }: { pts: Dado[]; sel: string | null; onPick: (c: string) => void }) {
  const lats = pts.map((p) => p.lat)
  const lons = pts.map((p) => p.lon)
  let la0 = Math.min(...lats)
  let la1 = Math.max(...lats)
  let lo0 = Math.min(...lons)
  let lo1 = Math.max(...lons)
  const pl = (la1 - la0) * 0.08 + 0.3
  const pn = (lo1 - lo0) * 0.08 + 0.3
  la0 -= pl
  la1 += pl
  lo0 -= pn
  lo1 += pn
  const k = Math.cos((((la0 + la1) / 2) * Math.PI) / 180)
  const W = 640
  const H = Math.max(280, Math.min(560, (W * (la1 - la0)) / ((lo1 - lo0) * k)))
  const sx = (lo: number) => ((lo - lo0) / (lo1 - lo0)) * W
  const sy = (la: number) => H - ((la - la0) / (la1 - la0)) * H
  const maxE = Math.max(...pts.map((p) => p.cut_gwh || 0).concat([1]))
  const sorted = pts.slice().sort((a, b) => (b.cut_gwh || 0) - (a.cut_gwh || 0))
  return (
      <svg viewBox={'0 0 ' + W + ' ' + H.toFixed(0)} width="100%" role="img" aria-label="Mapa de sítios de corte" style={{ display: 'block' }}>
        {sorted.map((p) => {
          const r = raioSitio(p, maxE)
          const col = corSitio(p)
          const on = p.code === sel
          const x = sx(p.lon)
          const y = sy(p.lat)
          return (
            <g key={p.code}>
              <circle
                cx={x.toFixed(1)}
                cy={y.toFixed(1)}
                r={r.toFixed(1)}
                fill={color(col)}
                fillOpacity={on ? 0.95 : 0.55}
                stroke={color(on ? 'teal' : col)}
                strokeWidth={on ? 2.6 : 1}
                style={{ cursor: 'pointer' }}
                onClick={() => onPick(p.code)}
              >
                <title>{tituloSitio(p)}</title>
              </circle>
              {p.rank <= 10 ? (
                <text x={x.toFixed(1)} y={(y + 3.5).toFixed(1)} textAnchor="middle" style={{ font: '700 9px var(--o-mono)', fill: '#fff', pointerEvents: 'none' }}>
                  {p.rank}
                </text>
              ) : null}
            </g>
          )
        })}
      </svg>
  )
}

// ------------------------------------------------------------ tabelas
function ScoreBar({ v }: { v: number }) {
  const f = Math.max(0, Math.min(1, v || 0))
  return (
    <>
      <span className="bar-track" style={{ display: 'inline-block', width: 70, verticalAlign: 'middle' }}>
        <span className="bar-fill" style={{ width: (f * 100).toFixed(0) + '%' }} />
      </span>{' '}
      {num(v, 2)}
    </>
  )
}

function UtilChip({ g }: { g: Dado }) {
  if (!g || !g.p_mw) return <span className="chip">—</span>
  const c = g.utilization === 'adequada' ? 'green' : 'amber'
  return <span className={'chip ' + c}>{num(g.p_mw) + ' MW · ' + num(g.hours) + ' h'}</span>
}

function TabelaRanking({ rows, sel, onPick }: { rows: Dado[]; sel: string | null; onPick: (c: string) => void }) {
  return (
    <div className="table-wrap scroll-y" style={{ maxHeight: 460 }}>
      <table>
        <thead>
          <tr>
            <th className="num">#</th>
            <th>Sítio (SE de conexão)</th>
            <th className="num">Corte GWh/ano</th>
            <th className="num">Dias com corte</th>
            <th className="num">Origem local</th>
            <th>BESS sugerido</th>
            <th className="num">Entrega GWh/ano</th>
            <th className="num">Excedente MMGD</th>
            <th>Pontuação</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const g = r.suggested || {}
            return (
              <tr key={r.code} className={r.code === sel ? 'sel' : ''} style={{ cursor: 'pointer' }} onClick={() => onPick(r.code)}>
                <td className="num">
                  <strong>{r.rank}</strong>
                </td>
                <td>
                  <strong>{r.name}</strong>
                  <br />
                  <span className="small faint">{r.uf + ' · ' + (r.sources || []).join(' + ') + ' · ' + num(r.disp_max_mw) + ' MW disponíveis'}</span>
                </td>
                <td className="num">
                  {num(r.cut_gwh_year, 0)}
                  <br />
                  <span className="small faint">{pct(r.cut_rate, 0)} da geração</span>
                </td>
                <td className="num">{pct(r.recurrence, 0)}</td>
                <td className="num">{pct(r.local_share, 0)}</td>
                <td>
                  <UtilChip g={g} />
                </td>
                <td className="num">{num((g.delivered_mwh || 0) / 1000, 0)}</td>
                <td className="num">{pct(r.induced_share, 0)}</td>
                <td>
                  <ScoreBar v={r.score} />
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function TabelaCarga({ rows }: { rows: Dado[] | undefined }) {
  if (!rows || !rows.length) return <Vazio>Requer a base da seção Fronteira T–D.</Vazio>
  return (
    <div className="table-wrap scroll-y" style={{ maxHeight: 290 }}>
      <table>
        <thead>
          <tr>
            <th>SE de fronteira</th>
            <th className="num">MMGD MW</th>
            <th className="num">carga MW</th>
            <th className="num">MMGD ÷ carga</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={(r.sub_id || r.name) + '-' + i}>
              <td>
                <strong>{r.name}</strong> <span className="small faint">{r.uf + ' · ' + r.subsystem}</span>
              </td>
              <td className="num">{num(r.gd_mw, 0)}</td>
              <td className="num">{num(r.load_mw, 0)}</td>
              <td className="num">{num(r.penetration, 2)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ------------------------------------------------------------ curva do pato
const SS_ORDER = ['NE', 'SE', 'S', 'N']

function drawDuck(host: HTMLElement, duck: Dado, ss: string) {
  const d = (duck || {})[ss || 'NE']
  if (!d) {
    host.innerHTML = '<div class="empty">Sem série para o subsistema.</div>'
    return
  }
  const idx: string[] = []
  for (let h = 0; h < 24; h++) idx.push('2026-01-01T' + String(h).padStart(2, '0') + ':00:00')
  lineChart(host, {
    index: idx,
    height: 250,
    compact: true,
    formatTime: (v) => String(v).slice(11, 13) + 'h',
    series: [
      { label: 'carga com MMGD', values: d.carga_global, color: 'muted', style: 'dash' },
      { label: 'carga supervisionada', values: d.supervisionada, color: 'navy' },
      { label: 'carga líquida (− eólica e solar centralizadas)', values: d.liquida, color: 'teal' },
      { label: 'corte apurado', values: d.corte, color: 'crimson', width: 2.4 },
    ],
  })
}

// ------------------------------------------------------------ detalhe do sítio
function Detalhe({ code, w }: { code: string; w: Pesos | null }) {
  const estado = useApi(() => Api.get('bess/sitio/' + encodeURIComponent(code), weightParams(w)), [code, JSON.stringify(w)])
  return (
    <Conteudo estado={estado} texto="Montando o detalhe do sítio…">
      {(body) => <CorpoDetalhe r={body.data as Dado} />}
    </Conteudo>
  )
}

function ReasonBars({ obj }: { obj: Record<string, number> | undefined }) {
  const e = Object.entries(obj || {}).sort((a, b) => b[1] - a[1])
  const tot = e.reduce((s, x) => s + x[1], 0) || 1
  if (!e.length) return <Vazio>—</Vazio>
  return (
    <>
      {e.map(([k, v]) => (
        <BarRow key={k} label={k} frac={v / tot} value={num(v, 0)} color={k === 'ENE' ? 'amber' : k === 'LOC' ? 'crimson' : 'teal'} />
      ))}
    </>
  )
}

function CorpoDetalhe({ r }: { r: Dado }) {
  const g = r.suggested || {}
  const c = r.components || {}
  return (
    <>
      <OCard title={'#' + r.rank + ' · ' + r.name + ' (' + r.uf + ')'} hint={r.location_method + ' · ' + num(r.n_usinas) + ' usinas · ' + (r.sources || []).join(' + ')}>
        <div className="grid g4" style={{ gap: 12, marginBottom: 12 }}>
          <Kpi label="Corte apurado" value={num(r.cut_gwh_year, 0)} unit="GWh/ano" foot={pct(r.cut_rate, 0) + ' da geração · pico ' + num(r.peak_cut_mw, 0) + ' MW'} />
          <Kpi
            label="BESS sugerido"
            value={g.p_mw ? num(g.p_mw) + ' MW / ' + num(g.hours) + ' h' : '—'}
            foot={num(g.cycles, 0) + ' ciclos/ano · MWh marginal ' + num(g.marginal_cycles, 0)}
          />
          <Kpi label="Energia recuperada" value={num((g.delivered_mwh || 0) / 1000, 0)} unit="GWh/ano" foot={pct(g.capture, 0) + ' do corte do sítio'} />
          <Kpi
            label="Excedente da MMGD"
            value={pct(r.induced_share, 0)}
            foot={'até ' + num(r.induced_gwh_year, 0) + ' GWh/ano · corte ENE+SIS ' + pct(r.es_share, 0)}
          />
        </div>
        <div className="grid g2" style={{ gap: 12 }}>
          <div>
            <div className="okpi-label" style={{ marginBottom: 6 }}>
              Por que este sítio
            </div>
            <ul className="actions" style={{ paddingLeft: 18 }}>
              {(r.reasoning || []).map((x: string, i: number) => (
                <li key={i}>{x}</li>
              ))}
            </ul>
            <div className="okpi-label" style={{ margin: '12px 0 6px' }}>
              Componentes da pontuação
            </div>
            {COMP.map((cc) => (
              <BarRow key={cc[0]} label={cc[1]} frac={c[cc[0]] || 0} value={num(c[cc[0]], 2)} color={cc[2]} />
            ))}
          </div>
          <div>
            <div className="okpi-label" style={{ marginBottom: 6 }}>
              Curva de dimensionamento · energia entregue × energia instalada
            </div>
            <Grafico
              deps={[r]}
              desenhar={(el) =>
                scatter(el, {
                  points: (r.grid || []).map((x: Dado) => ({
                    x: x.e_mwh,
                    y: x.delivered_mwh / 1000,
                    label: num(x.p_mw) + ' MW × ' + num(x.hours) + ' h · ' + num(x.cycles, 0) + ' ciclos/ano',
                    color: g.p_mw === x.p_mw && g.hours === x.hours ? 'crimson' : x.hours === 2 ? 'teal' : x.hours === 4 ? 'amber' : 'navy',
                  })),
                  xLabel: 'MWh instalados',
                  yLabel: 'GWh/ano entregues',
                  height: 220,
                  xDigits: 0,
                  digits: 0,
                  r: 5,
                })
              }
            />
            <div className="card-note">
              Cada ponto é um BESS da grade (potência × duração). A curva achata quando o MWh adicional quase não é usado — é ali que o investimento marginal deixa
              de se pagar.
            </div>
          </div>
        </div>
      </OCard>

      <div className="grid g2" style={{ marginTop: 14 }}>
        <OCard
          title="Quando o corte acontece"
          hint="MW médio de corte · mês × hora do dia"
          note="Corte concentrado ao meio-dia é o perfil que a MMGD agrava e que um BESS de 4 a 6 h desloca para a rampa do fim da tarde."
        >
          <Grafico
            deps={[r]}
            desenhar={(el) => {
              const heat: Dado[] = r.heat || []
              const maxH = Math.max(...heat.map((h) => Math.max(...h.values.concat([0]))).concat([1]))
              heatStrip(el, {
                rows: heat.map((h) => ({ label: h.label, values: h.values.map((v: number) => v / maxH) })),
                raw: heat.map((h) => h.values),
                color: 'crimson',
                unit: 'MW',
                seriesLabel: 'corte médio',
                digits: 0,
                padLeft: 50,
                colLabel: (cc) => String(Math.floor(cc / 2)).padStart(2, '0') + (cc % 2 ? ':30' : 'h'),
              })
            }}
          />
        </OCard>
        <OCard title="Perfil médio diário" hint="MWh cortados por meia hora, média da janela">
          <Grafico
            deps={[r]}
            desenhar={(el) =>
              barChart(el, {
                labels: (r.profile_mwh || []).map((_: unknown, i: number) => (i % 2 ? '' : String(i / 2).padStart(2, '0') + 'h')),
                values: r.profile_mwh || [],
                color: 'crimson',
                height: 200,
                digits: 1,
                unit: 'MWh',
                seriesLabel: 'corte médio',
              })
            }
          />
        </OCard>
      </div>
      <div className="grid g3" style={{ marginTop: 14 }}>
        <OCard title="Razão da restrição" hint="GWh/ano">
          <ReasonBars obj={r.e_reason_gwh} />
        </OCard>
        <OCard title="Origem" hint="GWh/ano · LOC local, SIS sistêmica" note="Corte LOCAL só é aliviado por armazenamento no próprio ponto.">
          <ReasonBars obj={r.e_origin_gwh} />
        </OCard>
        <OCard title="Usinas no sítio" hint={num(r.n_usinas) + ' usinas · ' + num((r.points || []).length) + ' ponto(s) de conexão'}>
          <div className="small" style={{ maxHeight: 170, overflow: 'auto' }}>
            {(r.usinas || []).map((u: string, i: number) => (
              <div key={i}>{u}</div>
            ))}
          </div>
        </OCard>
      </div>
    </>
  )
}
