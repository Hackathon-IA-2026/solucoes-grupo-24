/**
 * Camada de calor (leaflet.heat) para react-leaflet.
 *
 * O leaflet.heat é um plugin antigo que se pendura no `L` GLOBAL; por isso o `window.L` é
 * definido e o plugin é importado dinamicamente aqui dentro — o hack fica isolado neste
 * arquivo e o plugin só é baixado quando a camada é ligada.
 * Gradiente de UMA cor (violeta = identidade da MMGD no dashboard, token chart-2), do
 * transparente ao claro: magnitude sequencial, nunca arco-íris.
 */
import { useEffect } from 'react'
import L from 'leaflet'
import { useMap } from 'react-leaflet'
import { corToken } from '../../theme/tokens'

type PontoCalor = [number, number, number]

export function CamadaCalor({ pontos }: { pontos: readonly PontoCalor[] }) {
  const mapa = useMap()

  useEffect(() => {
    let camada: L.Layer | null = null
    let ativo = true
    ;(window as unknown as { L: typeof L }).L = L
    import('leaflet.heat').then(() => {
      if (!ativo) return
      const violeta = corToken('--color-chart-2')
      const pico = corToken('--color-mmgd-pico')
      const heat = (L as unknown as { heatLayer: (p: readonly PontoCalor[], o: object) => L.Layer }).heatLayer
      camada = heat(pontos, {
        radius: 28,
        blur: 22,
        maxZoom: 7,
        minOpacity: 0.15,
        gradient: { 0.2: `${violeta}33`, 0.5: `${violeta}99`, 0.8: violeta, 1: pico },
      })
      camada.addTo(mapa)
    })
    return () => {
      ativo = false
      camada?.remove()
    }
  }, [mapa, pontos])

  return null
}
