/**
 * Camada de polígonos das áreas de influência das subestações (recurso areas_influencia).
 *
 * Cor: UMA família (violeta, token chart-2, a identidade da MMGD no dashboard). A opacidade do
 * preenchimento cresce com a raiz da capacidade de MMGD da área (raiz para a área maior não
 * apagar as outras), então dá para ler "onde tem mais MMGD" sem arco-íris.
 * Contorno: fino e neutro; laranja (token risk-high) e mais grosso quando a subestação tem
 * excedente previsto > 0 nas próximas 24 h — o fluxo reverso na fronteira TSO–DSO. Laranja
 * TRACEJADO nas satélites dessa subestação: a carga e a MMGD que geram o excedente estão nelas
 * (a área própria da subestação de fronteira costuma ser pequena, ex.: SETD Influência).
 * Passar o mouse destaca a área e mostra os números que vieram da API (nada é recalculado aqui).
 * Opcional (tela Perfis por subestação): `onClicar` seleciona a área e `selecionada` a destaca.
 */
import { useMemo } from 'react'
import type { Layer, LeafletMouseEvent, Path } from 'leaflet'
import { GeoJSON } from 'react-leaflet'
import type { AreasInfluencia, PropriedadesArea } from '../../data/types'
import { corToken } from '../../theme/tokens'
import { formatNum } from '../../utils/format'

export function CamadaAreas({
  areas,
  selecionada = null,
  onClicar,
}: {
  areas: AreasInfluencia
  selecionada?: string | null
  onClicar?: (p: PropriedadesArea) => void
}) {
  const cores = useMemo(
    () => ({
      mmgd: corToken('--color-chart-2'),
      contorno: corToken('--color-ink-faint'),
      excedente: corToken('--color-risk-high'),
      destaque: corToken('--color-ink'),
    }),
    [],
  )
  const maxMw = useMemo(() => Math.max(...areas.features.map((f) => f.properties.capacidadeMmgdMw), 0.001), [areas])
  // areaId -> nome, para o tooltip dizer QUEM alimenta uma satélite (e não só o código)
  const nomes = useMemo(() => new Map(areas.features.map((f) => [f.properties.areaId, f.properties.nome])), [areas])
  // fronteiras com excedente previsto: as satélites delas ganham o contorno tracejado
  const exportadoras = useMemo(
    () => new Set(areas.features.filter((f) => (f.properties.excedenteMw ?? 0) > 0).map((f) => f.properties.areaId)),
    [areas],
  )

  // O Leaflet entrega o Feature genérico do GeoJSON; as propriedades já passaram pelo schema
  // (AreasInfluenciaSchema) no dataSource, então a conversão aqui é segura.
  const estilo = (f?: GeoJSON.Feature) => {
    const p = f!.properties as PropriedadesArea
    const exporta = exportadoras.has(p.areaId)
    const satelite = !exporta && p.areaMae !== null && exportadoras.has(p.areaMae)
    if (p.areaId === selecionada)
      return { color: cores.destaque, weight: 3, opacity: 1, dashArray: undefined, fillColor: cores.mmgd, fillOpacity: 0.06 + 0.74 * Math.sqrt(p.capacidadeMmgdMw / maxMw) }
    return {
      color: exporta || satelite ? cores.excedente : cores.contorno,
      weight: exporta ? 2.5 : satelite ? 1.5 : 0.5,
      opacity: exporta || satelite ? 1 : 0.6,
      dashArray: satelite ? '4 3' : undefined,
      fillColor: cores.mmgd,
      fillOpacity: 0.06 + 0.74 * Math.sqrt(p.capacidadeMmgdMw / maxMw),
    }
  }

  const aoCriar = (f: GeoJSON.Feature, camada: Layer) => {
    const p = f.properties as PropriedadesArea
    camada.bindTooltip(textoTooltip(p, nomes), { sticky: true, direction: 'top' })
    // Área com excedente por cima das vizinhas: senão o contorno laranja some sob as bordas delas.
    if (exportadoras.has(p.areaId) || (p.areaMae !== null && exportadoras.has(p.areaMae)) || p.areaId === selecionada)
      camada.on('add', () => (camada as Path).bringToFront())
    camada.on({
      mouseover: (e: LeafletMouseEvent) => (e.target as Path).setStyle({ weight: 3, color: cores.destaque }).bringToFront(),
      mouseout: (e: LeafletMouseEvent) => (e.target as Path).setStyle(estilo(f)),
      ...(onClicar ? { click: () => onClicar(p) } : {}),
    })
  }

  // key: o GeoJSON do react-leaflet não redesenha quando `data` muda; trocar a chave força.
  return (
    <GeoJSON key={areas.features.length + '|' + (selecionada ?? '')} data={areas as GeoJSON.FeatureCollection} style={estilo} onEachFeature={aoCriar} />
  )
}

/** Tooltip em HTML simples (o Leaflet recebe string); só texto vindo da API, escapado. */
function textoTooltip(p: PropriedadesArea, nomes: Map<string, string>): string {
  const linhas = [
    `<strong>${esc(p.nome)}</strong> · ${esc(p.distribuidora)}`,
    `${esc(p.classificacao)}${p.areaMae ? ` · alimentada por ${esc(nomes.get(p.areaMae) ?? p.areaMae)}` : ''}`,
    `MMGD: <strong>${formatNum(p.capacidadeMmgdMw)} MW</strong>` +
      (p.capacidadeLagMw > 0 ? ` (${formatNum(p.capacidadeLagMw)} MW ainda fora da BDGD)` : ''),
    p.excedenteMw === null
      ? 'sem alimentadores próprios (não é fronteira)'
      : `Excedente previsto 24 h: <strong>${formatNum(p.excedenteMw)} MW</strong>${p.excedenteMw > 0 ? ` · ${p.horizonteExcedente}` : ''}`,
    `${p.areaKm2.toLocaleString('pt-BR', { maximumFractionDigits: 1 })} km² · ${esc(p.areaId)}`,
  ]
  if (p.fatorCorrecao !== null) linhas.splice(3, 0, `fator do satélite: ${p.fatorCorrecao.toFixed(2)}`)
  return linhas.join('<br/>')
}

const esc = (s: string) => s.replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`)
