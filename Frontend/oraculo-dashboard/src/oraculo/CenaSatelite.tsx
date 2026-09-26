/**
 * Cena de satélite com as detecções de painel fotovoltaico, para a tela Visão computacional
 * (/visao) e a tabela de detecções do detalhe em Perfis por subestação.
 *
 * Duas origens de cena, o mesmo desenho:
 * - REAL: imagem de satélite da Esri (o fundo do mapa) e o detector do protótipo rodado nela pelo
 *   backend (/api/mapa/vision/real); cada detecção já vem com o polígono em lat/lon;
 * - SINTÉTICA (banco de ensaio): ortoimagem gerada, sobreposta ao mapa; as detecções vêm com a
 *   caixa em pixels da cena e viram polígonos pelo pixelParaLatLon (vision.geo).
 *
 * Painel = bounding box só com contorno (a imagem por baixo continua visível); a selecionada é
 * a borda grossa âmbar.
 */
import type { ReactNode } from 'react'
import { Pane, Polygon, Rectangle, Tooltip, useMapEvents } from 'react-leaflet'
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
export function limitesDoEntorno(lim: Limites, fator = 10): Limites {
  const [[la0, lo0], [la1, lo1]] = lim
  const dla = ((la1 - la0) * (fator - 1)) / 2
  const dlo = ((lo1 - lo0) * (fator - 1)) / 2
  return [
    [la0 - dla, lo0 - dlo],
    [la1 + dla, lo1 + dlo],
  ]
}

/** Vistas da imagem sintética servidas pela API (sufixo da URL da cena). */
export const MODOS_IMAGEM: [string, string][] = [
  ['', 'vista padrão'],
  ['?truth=1&tiles=1', 'verdade + ladrilhos'],
  ['?channel=azul', 'índice de azul'],
  ['?channel=borda', 'densidade de borda'],
]

/** Anel [lat, lon] da detecção: o polígono pronto (cena real) ou a caixa em pixels + geo (sintética). */
function anelDaDeteccao(x: Dado, geo: GeoCena | null): [number, number][] | null {
  if (Array.isArray(x.poligono) && x.poligono.length >= 4) return x.poligono as [number, number][]
  const b = x.box
  if (!geo || !Array.isArray(b) || b.length < 4) return null
  const [x0, y0, x1, y1] = b as number[]
  return [pixelParaLatLon(geo, x0, y0), pixelParaLatLon(geo, x1, y0), pixelParaLatLon(geo, x1, y1), pixelParaLatLon(geo, x0, y1)]
}

/**
 * Camadas da cena para ir DENTRO de um MapaOsm: imagem sintética opcional (num pane abaixo dos
 * vetores), contorno tracejado da cena e as bounding boxes das detecções.
 */
export function CamadaCena({
  url = null,
  geo = null,
  limites,
  dets,
  opacidade = 1,
  sel,
  onSel,
  mostrarDets = true,
}: {
  /** imagem sintética sobreposta; null na cena real (a imagem é o próprio fundo de satélite) */
  url?: string | null
  geo?: GeoCena | null
  /** extensão da cena; sem ela, vem da geo */
  limites?: Limites
  dets: Dado[]
  opacidade?: number
  sel?: number | null
  onSel?: (i: number) => void
  mostrarDets?: boolean
}) {
  const lim = limites ?? (geo ? limitesDaCena(geo) : null)
  const teal = color('teal')
  const ambar = color('amber')
  return (
    <>
      {url && lim && (
        <Pane name="cena" style={{ zIndex: 380 }}>
          <ImagemGeo key={url} url={url} limites={lim} opacidade={opacidade} />
        </Pane>
      )}
      {lim && <Rectangle bounds={lim} interactive={false} pathOptions={{ color: ambar, weight: 1.5, dashArray: '5 4', fill: false }} />}
      {mostrarDets &&
        dets.map((x, i) => {
          const anel = anelDaDeteccao(x, geo)
          if (!anel) return null
          const on = sel === i
          return (
            <Polygon
              // a chave inclui a seleção: o react-leaflet não reestiliza o polígono pelas props
              key={i + (on ? '-on' : '')}
              positions={anel}
              eventHandlers={onSel ? { click: () => onSel(i) } : undefined}
              // bounding box: só o contorno; o preenchimento transparente mantém o clique na caixa toda.
              // bubblingMouseEvents: false — o clique na caixa não chega ao mapa (lá ele analisaria outro ponto)
              pathOptions={{ color: on ? ambar : teal, weight: on ? 4 : 2, opacity: 1, fill: true, fillOpacity: 0, bubblingMouseEvents: false }}
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

/** Clique no mapa devolve o ponto (para analisar outro local na imagem real). */
export function CliqueNoMapa({ onClique }: { onClique: (lat: number, lon: number) => void }) {
  useMapEvents({ click: (e) => onClique(e.latlng.lat, e.latlng.lng) })
  return null
}

/** Legenda sobre o mapa da cena (MapaOsm `sobreposicao`). */
export function LegendaCena({ sintetica = false }: { sintetica?: boolean }) {
  return (
    <div className="osm-legenda">
      {/* a cena sintética é gerada (não é foto): o aviso fica no próprio mapa, onde a imagem aparece */}
      {sintetica ? (
        <strong style={{ color: 'var(--o-amber)' }}>Imagem sintética de demonstração</strong>
      ) : (
        <strong>Imagem de satélite real · Esri</strong>
      )}
      <span>
        <i style={{ border: '2px solid var(--o-teal)', background: 'transparent' }} /> painel detectado (bounding box)
      </span>
      <span>
        <i style={{ border: '3px solid var(--o-amber)', background: 'transparent' }} /> selecionado
      </span>
      <span>
        <i style={{ border: '1.5px dashed var(--o-amber)', background: 'transparent' }} /> área analisada
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
  /** sem opacidade (cena real, sem imagem sobreposta) o controle some */
  opacidade?: number
  setOpacidade?: (v: number) => void
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
      {modos.length > 0 && (
      <div className="chips" style={{ marginTop: 8 }}>
        {modos.map(([q, rot]) => (
          <Chip key={q} on={modo === q} onClick={() => setModo(q)}>
            {rot}
          </Chip>
        ))}
      </div>
      )}
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
            {opacidade !== undefined && setOpacidade && (
            <label className="chip" style={{ gap: 6 }}>
              opacidade da imagem
              <input type="range" min={0} max={1} step={0.05} value={opacidade} style={{ width: 90 }} onChange={(e) => setOpacidade(parseFloat(e.target.value))} />
              <span>{pct(opacidade, 0)}</span>
            </label>
            )}
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
