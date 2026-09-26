/**
 * Cena de satélite com as detecções de painel fotovoltaico, sobre o OpenStreetMap. Peças usadas
 * por duas telas (DRY — antes cada uma tinha a sua cópia):
 * - Visão computacional (/visao): a cena de referência do banco de ensaio, num mapa próprio;
 * - Perfis por subestação (/mapa): a cena de cada subestação, desenhada no MESMO mapa do
 *   Brasil → UF → subestação.
 *
 * A cena é sintética e georreferenciada (vision.geo: centro, extensão em metros, tamanho em
 * pixels); as detecções vêm com a caixa em pixels da cena e viram polígonos pelo pixelParaLatLon.
 */
import type { ReactNode } from 'react'
import { Pane, Polygon, Rectangle, Tooltip } from 'react-leaflet'
import { color } from './charts'
import { num, pct } from './format'
import { ImagemGeo, limitesDaCena, pixelParaLatLon, type Limites } from './MapaOsm'
import { Chip } from './ui'

/* eslint-disable @typescript-eslint/no-explicit-any */
type Dado = any

/** Georreferência de uma cena (o formato de vision.geo na API do protótipo). */
export interface GeoCena {
  center_lat: number
  center_lon: number
  extent_m: [number, number]
  width_px: number
  height_px: number
  gsd_m?: number
}

export function geoValida(g: Dado): g is GeoCena {
  return (
    !!g &&
    Number.isFinite(g.center_lat) &&
    Number.isFinite(g.center_lon) &&
    Array.isArray(g.extent_m) &&
    g.extent_m.length === 2 &&
    g.width_px > 0 &&
    g.height_px > 0
  )
}

/** Enquadramento do entorno da cena: a cena sozinha (~230 m) não mostra onde ela está. */
export function limitesDoEntorno(geo: GeoCena, fator = 10): Limites {
  const [[la0, lo0], [la1, lo1]] = limitesDaCena(geo)
  const dla = ((la1 - la0) * (fator - 1)) / 2
  const dlo = ((lo1 - lo0) * (fator - 1)) / 2
  return [
    [la0 - dla, lo0 - dlo],
    [la1 + dla, lo1 + dlo],
  ]
}

/** Vistas da imagem servidas pela API (sufixo da URL da cena). */
export const MODOS_IMAGEM: [string, string][] = [
  ['', 'vista padrão'],
  ['?truth=1&tiles=1', 'verdade + ladrilhos'],
  ['?channel=azul', 'índice de azul'],
  ['?channel=borda', 'densidade de borda'],
]

/**
 * Camadas da cena para ir DENTRO de um MapaOsm: imagem (num pane abaixo dos vetores, para as
 * detecções e marcadores ficarem por cima dela em qualquer ordem de montagem), contorno
 * tracejado da cena e as detecções. A detecção selecionada ganha contorno âmbar.
 */
export function CamadaCena({
  url,
  geo,
  dets,
  opacidade,
  sel,
  onSel,
  mostrarDets = true,
}: {
  url: string | null
  geo: GeoCena
  dets: Dado[]
  opacidade: number
  sel?: number | null
  onSel?: (i: number) => void
  mostrarDets?: boolean
}) {
  const lim = limitesDaCena(geo)
  const teal = color('teal')
  const ambar = color('amber')
  return (
    <>
      {url && (
        <Pane name="cena" style={{ zIndex: 380 }}>
          <ImagemGeo key={url} url={url} limites={lim} opacidade={opacidade} />
        </Pane>
      )}
      <Rectangle bounds={lim} interactive={false} pathOptions={{ color: ambar, weight: 1.5, dashArray: '5 4', fill: false }} />
      {mostrarDets &&
        dets.map((x, i) => {
          const b = x.box
          if (!Array.isArray(b) || b.length < 4) return null
          const [x0, y0, x1, y1] = b as number[]
          const anel = [pixelParaLatLon(geo, x0, y0), pixelParaLatLon(geo, x1, y0), pixelParaLatLon(geo, x1, y1), pixelParaLatLon(geo, x0, y1)]
          // a confiança pinta a detecção: quanto mais certa, mais opaca
          const sc = Math.max(0, Math.min(1, Number(x.score) || 0))
          const on = sel === i
          return (
            <Polygon
              // a chave inclui a seleção: o react-leaflet não reestiliza o polígono pelas props
              key={i + (on ? '-on' : '')}
              positions={anel}
              eventHandlers={onSel ? { click: () => onSel(i) } : undefined}
              pathOptions={{
                color: on ? ambar : teal,
                weight: on ? 3 : 2,
                opacity: 0.6 + 0.4 * sc,
                fillColor: teal,
                fillOpacity: 0.1 + 0.45 * sc,
              }}
            >
              <Tooltip direction="top">
                #{i + 1} · {num(x.area_m2, 1)} m² · {num(x.kwp, 2)} kWp · confiança {num(x.score, 3)}
              </Tooltip>
            </Polygon>
          )
        })}
    </>
  )
}

/** Legenda sobre o mapa da cena (MapaOsm `sobreposicao`). */
export function LegendaCena() {
  return (
    <div className="osm-legenda">
      <span>
        <i style={{ background: 'var(--o-teal)', opacity: 0.8 }} /> painel detectado (mais opaco = mais confiança)
      </span>
      <span>
        <i style={{ border: '2px solid var(--o-amber)', background: 'transparent' }} /> selecionado
      </span>
      <span>
        <i style={{ border: '1.5px dashed var(--o-amber)', background: 'transparent' }} /> extensão da cena
      </span>
    </div>
  )
}

/** Controles da cena: vista da imagem, opacidade, detecções e enquadramento (cena × entorno). */
export function ControlesCena({
  modos = MODOS_IMAGEM,
  modo,
  setModo,
  opacidade,
  setOpacidade,
  mostrarDets,
  setMostrarDets,
  entorno,
  setEntorno,
  extra,
  mapa = true,
}: {
  modos?: [string, string][]
  modo: string
  setModo: (m: string) => void
  opacidade: number
  setOpacidade: (v: number) => void
  mostrarDets: boolean
  setMostrarDets: (v: boolean) => void
  entorno?: boolean
  setEntorno?: (v: boolean) => void
  extra?: ReactNode
  /** false = só a imagem (sem mapa): esconde enquadramento, detecções e opacidade */
  mapa?: boolean
}) {
  return (
    <>
      <div className="chips" style={{ marginTop: 8 }}>
        {modos.map(([q, rot]) => (
          <Chip key={q} on={modo === q} onClick={() => setModo(q)}>
            {rot}
          </Chip>
        ))}
      </div>
      <div className="chips" style={{ marginTop: 6 }}>
        {extra}
        {mapa && setEntorno && (
          <>
            <Chip on={!entorno} onClick={() => setEntorno(false)} title="aproxima na cena analisada">
              cena
            </Chip>
            <Chip on={!!entorno} onClick={() => setEntorno(true)} title="afasta para ver onde a cena está">
              entorno
            </Chip>
          </>
        )}
        {mapa && (
          <>
            <Chip on={mostrarDets} onClick={() => setMostrarDets(!mostrarDets)} title="liga/desliga os polígonos das detecções sobre o mapa">
              contornos das detecções
            </Chip>
            <label className="chip" style={{ gap: 6 }}>
              opacidade da imagem
              <input type="range" min={0} max={1} step={0.05} value={opacidade} style={{ width: 90 }} onChange={(e) => setOpacidade(parseFloat(e.target.value))} />
              <span>{pct(opacidade, 0)}</span>
            </label>
          </>
        )}
      </div>
    </>
  )
}

/** Atributos de uma detecção (a selecionada no mapa ou na tabela). */
export function DetalheDeteccao({ det, i }: { det: Dado; i: number }) {
  return (
    <div className="det-detalhe">
      <strong>Detecção #{i + 1}</strong>
      <span>confiança {num(det.score, 3)}</span>
      <span>{num(det.area_m2, 1)} m²</span>
      <span>{num(det.kwp, 2)} kWp</span>
      <span>retangularidade {num(det.rectangularity, 3)}</span>
      <span>azul {num(det.blue_index, 3)}</span>
      <span>borda {num(det.edge_density, 3)}</span>
      <span className="mono">
        {num(det.lat, 5)}, {num(det.lon, 5)}
      </span>
    </div>
  )
}

/** Tabela das detecções, sincronizada com o mapa: clicar numa linha seleciona o polígono. */
export function TabelaDeteccoes({ dets, sel, onSel, max = 50 }: { dets: Dado[]; sel: number | null; onSel: (i: number) => void; max?: number }) {
  const lista = dets.slice(0, max)
  return (
    <div className="table-wrap scroll-y">
      <table>
        <thead>
          <tr>
            <th className="num">#</th>
            <th className="num">conf.</th>
            <th>lat, lon</th>
            <th className="num">área m²</th>
            <th className="num">kWp</th>
            <th className="num">retang.</th>
            <th className="num">azul</th>
            <th className="num">borda</th>
          </tr>
        </thead>
        <tbody>
          {lista.length ? (
            lista.map((x, i) => (
              <tr key={i} className={sel === i ? 'sel' : ''} style={{ cursor: 'pointer' }} onClick={() => onSel(i)}>
                  <td className="num">{i + 1}</td>
                  <td className="num">{num(x.score, 3)}</td>
                  <td className="mono small">
                    {num(x.lat, 5)}, {num(x.lon, 5)}
                  </td>
                  <td className="num">{num(x.area_m2, 1)}</td>
                  <td className="num">{num(x.kwp, 2)}</td>
                  <td className="num">{num(x.rectangularity, 3)}</td>
                  <td className="num">{num(x.blue_index, 3)}</td>
                  <td className="num">{num(x.edge_density, 3)}</td>
              </tr>
            ))
          ) : (
            <tr>
              <td colSpan={8}>nenhuma detecção nesta cena</td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  )
}
