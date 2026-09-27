/**
 * Risco de curtailment e excedentes (protótipo, painel "risco"). Porte de V.risco em
 * 02-PROTOTIPO/web/js/views/operacao.js: mapa do Brasil por UF, eventos priorizados por
 * severidade, alerta explicado com evidências e probabilidade horária da área selecionada.
 *
 * Mapa: divisas reais das UFs (IBGE, src/data/geo/ufs.geo.json, a mesma malha do Mapa Híbrido),
 * coloridas pela severidade. Decisão: sem camada de tiles — o fundo é 100% local e a tela funciona
 * offline (regra travada em src/pages/semServicoExterno.test.ts). Substitui a grade esquemática
 * de quadrados do protótipo, que não parecia o Brasil.
 */
import 'leaflet/dist/leaflet.css'
import { useEffect, useMemo, useRef } from 'react'
import L from 'leaflet'
import { GeoJSON, MapContainer, useMap } from 'react-leaflet'
import ufsGeo from '../../data/geo/ufs.geo.json'
import { Api, type Envelope } from '../api'
import { lineChart } from '../charts'
import { usePersistido } from '../estado'
import { num, pct } from '../format'
import { Conteudo, Grafico, Kpi, OCard, Pagina, Proveniencia, ReasonTag, Vazio, useApi } from '../ui'

/* eslint-disable @typescript-eslint/no-explicit-any */
type Dado = any

const UFS = ufsGeo as unknown as GeoJSON.FeatureCollection<GeoJSON.Geometry, { uf: string }>
// Enquadramento: a caixa da própria malha (calculada uma vez).
const LIMITES_UFS = L.geoJSON(UFS).getBounds()

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
          title="Mapa do Brasil · severidade por área"
          note="Divisas das UFs (IBGE); clique numa UF para ver o alerta e a probabilidade horária. A granularidade-alvo em produção é área de concessão e transformação de fronteira, que exige a BDGD."
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

/** Cor resolvida de uma variável CSS do protótipo (`--o-*` tem escopo em .oraculo, não no :root). */
function corDe(el: Element | null, nome: string, reserva: string): string {
  const v = el ? getComputedStyle(el).getPropertyValue(nome).trim() : ''
  return v || reserva
}

function Mapa({ areas, selArea, onSel }: { areas: Dado[]; selArea: string; onSel: (uf: string) => void }) {
  const caixa = useRef<HTMLDivElement | null>(null)
  const camada = useRef<L.GeoJSON | null>(null)
  const porUf = useMemo(() => new Map<string, Dado>(areas.map((a) => [a.area, a])), [areas])
  // refs: os handlers do Leaflet são criados uma vez e precisam ler o valor atual
  const estado = useRef({ porUf, selArea, onSel })
  useEffect(() => {
    estado.current = { porUf, selArea, onSel }
  })

  const estilo = (uf: string | undefined): L.PathOptions => {
    const el = caixa.current
    const a = uf ? estado.current.porUf.get(uf) : undefined
    const sel = uf !== undefined && uf === estado.current.selArea
    // Divisas em --o-muted (não --o-line): --o-line é quase igual ao fundo do mapa (--o-panel-2)
    // nos dois temas e as UFs sem área modelada sumiam. --o-muted tem contraste no claro e no escuro.
    const linha = corDe(el, '--o-muted', '#7f8db0')
    // UF sem área modelada: preenchimento em --o-bg-2 (difere do fundo --o-panel-2) e opaco,
    // para o contorno do Brasil continuar legível mesmo sem cor de severidade.
    if (!a) return { color: linha, weight: 0.8, fillColor: corDe(el, '--o-bg-2', '#101832'), fillOpacity: 0.9 }
    const cor = corDe(el, `--o-${sevColor(a.severity)}`, '#f0b030')
    return {
      color: sel ? corDe(el, '--o-teal', '#4fd1c5') : linha,
      weight: sel ? 2.4 : 0.9,
      fillColor: cor,
      // mesma escala da grade antiga: mais severa, mais opaca
      fillOpacity: 0.2 + 0.6 * Math.min(1, a.severity),
    }
  }

  // o GeoJSON do react-leaflet não reestiliza sozinho: reaplica quando muda a seleção ou os dados
  useEffect(() => {
    camada.current?.setStyle((f) => estilo(f?.properties?.uf))
    camada.current?.eachLayer((l) => {
      const uf = (l as L.GeoJSON & { feature?: GeoJSON.Feature }).feature?.properties?.uf
      if (uf === selArea) (l as L.Path).bringToFront()
    })
  }, [selArea, porUf]) // eslint-disable-line react-hooks/exhaustive-deps

  // as cores vêm das variáveis do tema: ao trocar claro/escuro (data-theme no <html>) reestiliza
  useEffect(() => {
    const obs = new MutationObserver(() => camada.current?.setStyle((f) => estilo(f?.properties?.uf)))
    obs.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })
    return () => obs.disconnect()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div ref={caixa} className="mapa-brasil" style={{ height: 380 }}>
      <MapContainer
        bounds={LIMITES_UFS}
        maxBounds={LIMITES_UFS.pad(0.3)}
        zoomSnap={0.25}
        scrollWheelZoom={false}
        attributionControl={false}
        style={{ height: '100%', width: '100%', background: 'transparent' }}
      >
        <GeoJSON
          ref={camada}
          data={UFS}
          style={(f) => estilo(f?.properties?.uf)}
          onEachFeature={(f, layer) => {
            const uf: string = f.properties?.uf
            layer.bindTooltip(() => {
              const a = estado.current.porUf.get(uf)
              return a
                ? `<strong>${uf}</strong> · ${num(a.expected_mw)} MW esperados<br/>P = ${pct(a.probability, 0)} · severidade ${num(a.severity, 2)} · ${a.reason}`
                : `<strong>${uf}</strong> · sem área modelada`
            }, { sticky: true })
            layer.on('click', () => {
              if (estado.current.porUf.has(uf)) estado.current.onSel(uf)
            })
          }}
        />
        <Reenquadrar />
      </MapContainer>
    </div>
  )
}

/**
 * O MapContainer calcula o zoom de `bounds` uma vez, ao nascer. Se o card ainda não tinha tamanho
 * (aba em segundo plano, layout em transição) o Brasil ficava minúsculo. Refaz o enquadramento
 * sempre que o contêiner muda de tamanho (e ganha largura > 0).
 */
function Reenquadrar() {
  const map = useMap()
  useEffect(() => {
    const el = map.getContainer()
    if (typeof ResizeObserver === 'undefined') return
    const ro = new ResizeObserver(() => {
      if (el.clientWidth === 0 || el.clientHeight === 0) return
      map.invalidateSize()
      map.fitBounds(LIMITES_UFS, { animate: false })
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [map])
  return null
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
