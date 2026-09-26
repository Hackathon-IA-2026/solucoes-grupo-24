/**
 * Divisas das UFs (IBGE) como camada INTERATIVA do Mapa Híbrido:
 * - passar o mouse destaca a UF e mostra quantas usinas em risco e excedentes ela tem;
 * - clicar dá zoom na UF e filtra o painel por ela (clicar de novo na mesma UF tira o filtro).
 *
 * O GeoJSON do react-leaflet não reestiliza sozinho quando as props mudam: o estilo é aplicado
 * por ref (setStyle) sempre que a UF selecionada muda, e o hover usa refs para não ler estado velho.
 */
import { useEffect, useRef } from 'react'
import type L from 'leaflet'
import { GeoJSON } from 'react-leaflet'
import ufs from '../../data/geo/ufs.geo.json'
import { corToken } from '../../theme/tokens'
import { formatMw } from '../../utils/format'

export interface ResumoUf {
  riscos: number
  mw: number
  excedentes: number
}

interface Props {
  selecionada: string | null
  resumo: ReadonlyMap<string, ResumoUf>
  onClicar: (uf: string, limites: L.LatLngBounds) => void
}

export function CamadaUfs({ selecionada, resumo, onClicar }: Props) {
  const camada = useRef<L.GeoJSON | null>(null)
  const sel = useRef(selecionada)
  const res = useRef(resumo)
  const clicar = useRef(onClicar)
  useEffect(() => {
    sel.current = selecionada
    res.current = resumo
    clicar.current = onClicar
  })

  const cores = useRef({
    linha: corToken('--color-line'),
    realce: corToken('--color-accent'),
    fundo: corToken('--color-surface-raised'),
  }).current

  const estilo = (uf: string | undefined): L.PathOptions => {
    const ativa = uf !== undefined && uf === sel.current
    return {
      color: ativa ? cores.realce : cores.linha,
      weight: ativa ? 1.6 : 0.8,
      fillColor: ativa ? cores.realce : cores.fundo,
      fillOpacity: ativa ? 0.12 : 0.9,
    }
  }

  // reestiliza quando a UF selecionada muda
  useEffect(() => {
    camada.current?.setStyle((f) => estilo(f?.properties?.uf))
  }, [selecionada]) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <GeoJSON
      ref={camada}
      data={ufs as GeoJSON.FeatureCollection}
      style={(f) => estilo(f?.properties?.uf)}
      attribution="Divisas: IBGE · Contorno: Natural Earth"
      onEachFeature={(feature, layer) => {
        const uf: string = feature.properties.uf
        const caminho = layer as L.Path & { getBounds: () => L.LatLngBounds }
        layer.bindTooltip(() => {
          const r = res.current.get(uf)
          return r && (r.riscos || r.excedentes)
            ? `<strong>${uf}</strong> · ${r.riscos} usina(s) em risco · ${formatMw(r.mw)} MW · ${r.excedentes} excedente(s)`
            : `<strong>${uf}</strong> · sem risco nem excedente visível`
        }, { sticky: true, direction: 'top' })
        layer.on({
          mouseover: () => caminho.setStyle({ weight: 1.6, color: cores.realce }),
          mouseout: () => caminho.setStyle(estilo(uf)),
          click: () => clicar.current(uf, caminho.getBounds()),
        })
      }}
    />
  )
}
