/**
 * Mapa de fundo OpenStreetMap para as telas do protótipo com dado georreferenciado (cena de
 * satélite por subestação, detecções de painel, SE × SED da fronteira, sítios de BESS, painéis
 * da auditoria MMGD). Leaflet + react-leaflet, que o dashboard já empacota.
 *
 * Decisões:
 * - ÚNICO arquivo com camada de tiles remota (src/pages/semServicoExterno.test.ts libera só
 *   este): os tiles são contexto; o dado continua vetorial por cima. Sem rede para o OSM, o mapa
 *   segue funcionando com as camadas vetoriais e avisa, em vez de ficar em branco.
 * - Tema: no escuro, os tiles passam por um filtro (inversão + tom) para não estourar o painel
 *   escuro do protótipo; no claro, OSM original.
 * - Atribuição obrigatória do OSM sempre visível.
 */
import 'leaflet/dist/leaflet.css'
import L from 'leaflet'
import { useEffect, useMemo, useRef, useState, type CSSProperties, type ReactNode } from 'react'
import { ImageOverlay, MapContainer, TileLayer, useMap } from 'react-leaflet'
import { useOraculo } from './estado'

export const OSM_URL = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png'
export const OSM_ATRIBUICAO = '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap</a> contributors'

export type Limites = [[number, number], [number, number]]

/** Limites [[latS, lonO], [latN, lonL]] de um conjunto de pontos, com folga. */
export function limitesDe(pontos: { lat: number; lon: number }[], folga = 0.08): Limites | null {
  const v = pontos.filter((p) => Number.isFinite(p.lat) && Number.isFinite(p.lon))
  if (!v.length) return null
  let la0 = Math.min(...v.map((p) => p.lat))
  let la1 = Math.max(...v.map((p) => p.lat))
  let lo0 = Math.min(...v.map((p) => p.lon))
  let lo1 = Math.max(...v.map((p) => p.lon))
  const dla = Math.max(la1 - la0, 0.002) * folga
  const dlo = Math.max(lo1 - lo0, 0.002) * folga
  la0 -= dla
  la1 += dla
  lo0 -= dlo
  lo1 += dlo
  return [
    [la0, lo0],
    [la1, lo1],
  ]
}

/**
 * Limites de uma cena georreferenciada do protótipo (vision.geo: centro, extensão em metros).
 * Equirretangular local: exato o bastante para uma cena de algumas centenas de metros.
 */
export function limitesDaCena(geo: { center_lat: number; center_lon: number; extent_m: [number, number] }): Limites {
  const [w, h] = geo.extent_m
  const dLat = h / 2 / 111_320
  const dLon = w / 2 / (111_320 * Math.cos((geo.center_lat * Math.PI) / 180))
  return [
    [geo.center_lat - dLat, geo.center_lon - dLon],
    [geo.center_lat + dLat, geo.center_lon + dLon],
  ]
}

/** Pixel (x, y) da cena -> [lat, lon], com a origem no canto superior esquerdo. */
export function pixelParaLatLon(
  geo: { center_lat: number; center_lon: number; extent_m: [number, number]; width_px: number; height_px: number },
  x: number,
  y: number,
): [number, number] {
  const [[la0, lo0], [la1, lo1]] = limitesDaCena(geo)
  return [la1 - (y / geo.height_px) * (la1 - la0), lo0 + (x / geo.width_px) * (lo1 - lo0)]
}

function Enquadrar({ limites, maxZoom, animar }: { limites: Limites | null; maxZoom?: number; animar?: boolean }) {
  const map = useMap()
  const chave = limites ? limites.flat().map((v) => v.toFixed(5)).join(',') : ''
  const primeira = useRef(true)
  const atual = useRef({ limites, maxZoom })
  atual.current = { limites, maxZoom }
  useEffect(() => {
    if (!limites) return
    const opcoes = { padding: [12, 12] as [number, number], maxZoom: maxZoom ?? 17 }
    // o enquadramento inicial é seco; os seguintes voam até o destino quando `animar`
    if (animar && !primeira.current) map.flyToBounds(limites, { ...opcoes, duration: 1.2 })
    else map.fitBounds(limites, opcoes)
    primeira.current = false
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chave, map, maxZoom])
  // o mapa pode nascer num card com largura ainda indefinida: recalcula o tamanho e refaz o
  // enquadramento inicial, que foi calculado com a largura errada
  useEffect(() => {
    const t = setTimeout(() => {
      map.invalidateSize()
      const { limites: l, maxZoom: z } = atual.current
      if (l) map.fitBounds(l, { padding: [12, 12], maxZoom: z ?? 17 })
    }, 120)
    return () => clearTimeout(t)
  }, [map])
  return null
}

export function MapaOsm({
  limites,
  altura = 360,
  maxZoom,
  children,
  estilo,
  rolagem = false,
  animar = false,
  zoomMin,
}: {
  limites: Limites | null
  altura?: number
  maxZoom?: number
  children?: ReactNode
  estilo?: CSSProperties
  /** zoom pela roda do mouse (desligado por padrão: a página rola por cima do mapa) */
  rolagem?: boolean
  /** trocar `limites` voa (flyToBounds) até o novo enquadramento em vez de saltar */
  animar?: boolean
  zoomMin?: number
}) {
  const { tema } = useOraculo()
  const [semTiles, setSemTiles] = useState(false)
  const eventos = useMemo(() => ({ tileerror: () => setSemTiles(true), tileload: () => setSemTiles(false) }), [])
  const centro = limites ? L.latLngBounds(limites).getCenter() : L.latLng(-15.8, -47.9)
  return (
    <div className={'osm-mapa' + (tema === 'dark' ? ' osm-escuro' : '')} style={{ height: altura, ...estilo }}>
      <MapContainer center={centro} zoom={limites ? 12 : 4} scrollWheelZoom={rolagem} minZoom={zoomMin} style={{ height: '100%', width: '100%' }} attributionControl>
        <TileLayer url={OSM_URL} attribution={OSM_ATRIBUICAO} maxZoom={19} eventHandlers={eventos} />
        <Enquadrar limites={limites} maxZoom={maxZoom} animar={animar} />
        {children}
      </MapContainer>
      {semTiles && <div className="osm-aviso">OpenStreetMap indisponível nesta rede: exibindo só as camadas georreferenciadas.</div>}
    </div>
  )
}

/** Imagem georreferenciada (cena do protótipo) sobre o OSM, com opacidade ajustável. */
export function ImagemGeo({ url, limites, opacidade = 0.85 }: { url: string; limites: Limites; opacidade?: number }) {
  return <ImageOverlay url={url} bounds={limites} opacity={opacidade} />
}
