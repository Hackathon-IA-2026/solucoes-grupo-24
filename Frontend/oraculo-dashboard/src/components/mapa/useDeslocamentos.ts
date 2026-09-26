/**
 * Posições de EXIBIÇÃO dos marcadores, com os de mesma coordenada espalhados em anel (em pixels,
 * recalculado a cada zoom) — ver utils/geo.ts. Devolve, por id, a posição exibida, o ponto real
 * e o tamanho do grupo; a camada desenha uma linha do ponto real até o marcador deslocado.
 */
import { useMemo, useState } from 'react'
import L from 'leaflet'
import { useMap, useMapEvents } from 'react-leaflet'
import { agruparPorPosicao, offsetsEmAnel } from '../../utils/geo'

export interface PosicaoExibida {
  exibida: L.LatLng
  real: L.LatLng
  tamanhoGrupo: number
}

export function useDeslocamentos<T>(itens: readonly T[], id: (t: T) => string, pos: (t: T) => [number, number]) {
  const mapa = useMap()
  const [zoom, setZoom] = useState(() => mapa.getZoom())
  useMapEvents({ zoomend: () => setZoom(mapa.getZoom()) })

  return useMemo(() => {
    const out = new Map<string, PosicaoExibida>()
    for (const grupo of agruparPorPosicao(itens, pos).values()) {
      const real = L.latLng(...pos(grupo[0]))
      const offsets = offsetsEmAnel(grupo.length)
      const centro = mapa.project(real, zoom)
      grupo.forEach((it, k) => {
        const [dx, dy] = offsets[k]
        out.set(id(it), { exibida: mapa.unproject(centro.add(L.point(dx, dy)), zoom), real, tamanhoGrupo: grupo.length })
      })
    }
    return out
    // `pos`/`id` são funções estáveis de quem chama (definidas fora do componente)
  }, [itens, zoom, mapa]) // eslint-disable-line react-hooks/exhaustive-deps
}
