/**
 * Mapa Híbrido: usinas em risco (círculos por severidade) e excedentes TSO-DSO (losangos por
 * prioridade) sobre o Brasil, com camada opcional de densidade de MMGD e painel lateral
 * "Subestações em Risco" sincronizado com os marcadores.
 *
 * Interações:
 * - passar o mouse num item do painel destaca o marcador (e vice-versa);
 * - clicar num item do painel centraliza o mapa nele;
 * - clicar no marcador de risco abre o Detalhe do Alerta; no de excedente, a tela Excedentes.
 *
 * Fundo: o contorno do Brasil (GeoJSON local, Natural Earth) é sempre desenhado, então o mapa
 * funciona offline. Os tiles escuros da CARTO ficam por baixo quando a rede permite.
 */
import 'leaflet/dist/leaflet.css'
import { useMemo, useRef, useState } from 'react'
import { ChevronRight } from 'lucide-react'
import L from 'leaflet'
import { CircleMarker, GeoJSON, MapContainer, Marker, TileLayer, Tooltip } from 'react-leaflet'
import { useNavigate } from 'react-router-dom'
import { CamadaCalor } from '../components/mapa/CamadaCalor'
import { Card } from '../components/ui/Card'
import { Carregando, ErroDados } from '../components/ui/Estado'
import { MockTag } from '../components/ui/MockTag'
import { SeverityBadge } from '../components/ui/SeverityBadge'
import { ToggleChip } from '../components/ui/ToggleChip'
import { getDensidadeMmgd, getExcedentes, getRiscos } from '../data/dataSource'
import { ordenarExcedentes, ordenarPorSeveridade } from '../data/derivados'
import brasil from '../data/geo/brasil.geo.json'
import type { DensidadeMmgd, ExcedenteTsoDso, RiscoUsina } from '../data/types'
import { useDados } from '../data/useDados'
import { MODULES, rotaDetalheAlerta } from '../modules'
import { RISK_STYLES } from '../theme/severity'
import { corToken } from '../theme/tokens'
import { formatMw, formatPct } from '../utils/format'

/** Caixa do Brasil: enquadramento inicial e limite de arraste. */
const LIMITES_BR: L.LatLngBoundsExpression = [
  [-34.5, -74.5],
  [6, -32],
]
const EXCEDENTES_PATH = MODULES.find((m) => m.label === 'Excedentes TSO-DSO')!.path

/** Camadas ligáveis (a de MMGD começa desligada: é sintética). */
type Camada = 'riscos' | 'excedentes' | 'mmgd'
const ROTULO_CAMADA: Record<Camada, string> = {
  riscos: 'Usinas em risco',
  excedentes: 'Excedentes TSO-DSO',
  mmgd: 'Densidade MMGD (sintético)',
}

export default function MapaHibrido() {
  const riscos = useDados(getRiscos)
  const excedentes = useDados(getExcedentes)
  const mmgd = useDados(getDensidadeMmgd)

  for (const d of [riscos, excedentes, mmgd]) if (d.status === 'erro') return <ErroDados erro={d.erro} />
  if (riscos.status !== 'ok' || excedentes.status !== 'ok' || mmgd.status !== 'ok') return <Carregando altura="h-[32rem]" />

  return <Mapa riscos={ordenarPorSeveridade(riscos.data)} excedentes={ordenarExcedentes(excedentes.data)} mmgd={mmgd.data} />
}

function Mapa({ riscos, excedentes, mmgd }: { riscos: RiscoUsina[]; excedentes: ExcedenteTsoDso[]; mmgd: DensidadeMmgd }) {
  const navigate = useNavigate()
  const mapaRef = useRef<L.Map | null>(null)
  // id do risco em destaque — estado ÚNICO compartilhado por marcadores e painel (sincronia).
  const [destaque, setDestaque] = useState<string | null>(null)
  const [camadas, setCamadas] = useState<Record<Camada, boolean>>({ riscos: true, excedentes: true, mmgd: false })
  const alternar = (c: Camada) => setCamadas((v) => ({ ...v, [c]: !v[c] }))

  // Cores lidas das tokens uma vez (Leaflet desenha em SVG/canvas, sem classes Tailwind).
  const cores = useMemo(
    () => ({
      contorno: corToken('--color-ink-faint'),
      preenchimento: corToken('--color-surface-raised'),
      anel: corToken('--color-ink'),
      risco: (r: RiscoUsina) => corToken(RISK_STYLES[r.severidade].token),
    }),
    [],
  )

  const centralizar = (r: RiscoUsina) => mapaRef.current?.flyTo([r.lat, r.lon], 7, { duration: 0.6 })
  const mock = riscos.some((r) => r.mock) || excedentes.some((e) => e.mock)

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        {(Object.keys(ROTULO_CAMADA) as Camada[]).map((c) => (
          <ToggleChip
            key={c}
            label={ROTULO_CAMADA[c]}
            ativo={camadas[c]}
            onToggle={() => alternar(c)}
            classeAtivo={c === 'mmgd' ? 'border-chart-2/60 bg-chart-2/10 text-ink' : 'border-accent/50 bg-accent/10 text-accent'}
            classePonto={c === 'mmgd' ? 'bg-chart-2' : 'bg-accent'}
          />
        ))}
        {camadas.mmgd && <MockTag mock={mmgd.mock} />}
      </div>

      <div className="grid gap-4 xl:grid-cols-[1fr_20rem]">
        <Card title="Brasil · usinas, excedentes e MMGD" actions={<MockTag mock={mock} />} className="overflow-hidden">
          <div className="relative -m-4 h-[calc(100vh-15rem)] min-h-[30rem]">
            <MapContainer
              ref={mapaRef}
              bounds={LIMITES_BR}
              maxBounds={LIMITES_BR}
              maxBoundsViscosity={0.8}
              minZoom={3}
              zoomSnap={0.25}
              className="size-full"
              attributionControl
            >
              <TileLayer
                url="https://{s}.basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}{r}.png"
                attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/">CARTO</a> · Natural Earth'
              />
              <GeoJSON
                data={brasil as GeoJSON.Feature}
                style={{ color: cores.contorno, weight: 1, fillColor: cores.preenchimento, fillOpacity: 0.9 }}
                interactive={false}
              />

              {camadas.mmgd && <CamadaCalor pontos={mmgd.pontos} />}

              {camadas.excedentes &&
                excedentes.map((e) => (
                  <Marker
                    key={`${e.areaConcessao}|${e.distribuidora}`}
                    position={[e.lat, e.lon]}
                    icon={iconeLosango(corToken(RISK_STYLES[e.prioridade].token))}
                    eventHandlers={{ click: () => navigate(EXCEDENTES_PATH) }}
                  >
                    <Tooltip direction="top" offset={[0, -8]}>
                      <strong>{e.areaConcessao}</strong> · {e.distribuidora}
                      <br />
                      Excedente {formatMw(e.excedenteMw)} MW · {e.horizonte}
                    </Tooltip>
                  </Marker>
                ))}

              {camadas.riscos &&
                riscos.map((r) => {
                  const foco = destaque === r.id
                  return (
                    <CircleMarker
                      key={`${r.id}-${foco}`} // remonta ao mudar o foco: traz o marcador para a frente
                      center={[r.lat, r.lon]}
                      // raio cresce com o montante (MW em risco) e com o foco
                      radius={raio(r.montanteMw) + (foco ? 4 : 0)}
                      pathOptions={{
                        color: foco ? cores.anel : cores.risco(r),
                        weight: foco ? 3 : 1.5,
                        fillColor: cores.risco(r),
                        fillOpacity: foco ? 0.95 : 0.7,
                      }}
                      eventHandlers={{
                        click: () => navigate(rotaDetalheAlerta(r.id)),
                        mouseover: () => setDestaque(r.id),
                        mouseout: () => setDestaque(null),
                      }}
                    >
                      <Tooltip direction="top" offset={[0, -6]} permanent={foco}>
                        <strong>
                          {r.uf} · {r.nome}
                        </strong>
                        <br />
                        {formatPct(r.probabilidadePct, 0)}% · {formatMw(r.montanteMw)} MW · {r.razao} · {r.horizonte}
                      </Tooltip>
                    </CircleMarker>
                  )
                })}
            </MapContainer>
            <Legenda mmgd={camadas.mmgd} />
          </div>
        </Card>

        <PainelRiscos
          riscos={riscos}
          destaque={destaque}
          onDestaque={setDestaque}
          onSelecionar={centralizar}
          onAbrir={(r) => navigate(rotaDetalheAlerta(r.id))}
        />
      </div>
    </div>
  )
}

/** Raio do círculo (px) proporcional à raiz do montante: área ∝ MW. */
const raio = (mw: number) => 5 + Math.sqrt(mw) * 0.6

/** Losango (quadrado girado) para excedentes: forma diferente dos círculos de risco. */
function iconeLosango(cor: string): L.DivIcon {
  return L.divIcon({
    className: '',
    iconSize: [14, 14],
    html: `<div style="width:12px;height:12px;transform:rotate(45deg);background:${cor};border:1.5px solid var(--color-base);opacity:.9"></div>`,
  })
}

function PainelRiscos({
  riscos,
  destaque,
  onDestaque,
  onSelecionar,
  onAbrir,
}: {
  riscos: RiscoUsina[]
  destaque: string | null
  onDestaque: (id: string | null) => void
  onSelecionar: (r: RiscoUsina) => void
  onAbrir: (r: RiscoUsina) => void
}) {
  return (
    <Card title="Subestações em risco" actions={<span className="kpi text-xs text-ink-muted">{riscos.length}</span>}>
      <ul className="-mx-4 -my-4 divide-y divide-line">
        {riscos.map((r) => (
          <li
            key={r.id}
            onMouseEnter={() => onDestaque(r.id)}
            onMouseLeave={() => onDestaque(null)}
            className={`flex items-center gap-2 px-3 py-2.5 transition-colors ${destaque === r.id ? 'bg-surface-raised' : ''}`}
          >
            <button type="button" onClick={() => onSelecionar(r)} className="flex flex-1 flex-col items-start gap-1 text-left" title="Centralizar no mapa">
              <span className="flex items-center gap-2">
                <SeverityBadge level={r.severidade} />
                <span className="font-mono text-[11px] text-ink-muted">{r.uf}</span>
              </span>
              <span className="text-sm text-ink">{r.nome}</span>
              <span className="kpi text-xs text-ink-muted">
                {formatPct(r.probabilidadePct, 0)}% · {formatMw(r.montanteMw)} MW · {r.horizonte}
              </span>
            </button>
            <button
              type="button"
              onClick={() => onAbrir(r)}
              aria-label={`Abrir alerta de ${r.nome}`}
              className="rounded p-1 text-ink-faint hover:bg-base hover:text-accent"
            >
              <ChevronRight className="size-4" aria-hidden />
            </button>
          </li>
        ))}
      </ul>
    </Card>
  )
}

/** Legenda sobre o mapa (canto inferior esquerdo). */
function Legenda({ mmgd }: { mmgd: boolean }) {
  const niveis = ['critical', 'high', 'medium', 'low'] as const
  return (
    <div className="pointer-events-none absolute bottom-6 left-3 z-[1000] space-y-2 rounded border border-line bg-base/90 px-3 py-2 text-[11px] text-ink-muted">
      <p className="flex flex-wrap items-center gap-x-3 gap-y-1">
        {niveis.map((n) => (
          <span key={n} className="flex items-center gap-1.5">
            <span className={`size-2.5 rounded-full ${RISK_STYLES[n].dot}`} aria-hidden /> {RISK_STYLES[n].label}
          </span>
        ))}
      </p>
      <p className="flex items-center gap-3">
        <span className="flex items-center gap-1.5">
          <span className="size-2.5 rounded-full border border-ink-muted" aria-hidden /> usina (tamanho ∝ MW)
        </span>
        <span className="flex items-center gap-1.5">
          <span className="size-2 rotate-45 border border-ink-muted" aria-hidden /> excedente TSO-DSO
        </span>
      </p>
      {mmgd && (
        <p className="flex items-center gap-2">
          <span className="h-2 w-16 rounded-full bg-gradient-to-r from-chart-2/20 via-chart-2 to-mmgd-pico" aria-hidden />
          densidade MMGD (sintética)
        </p>
      )}
    </div>
  )
}
