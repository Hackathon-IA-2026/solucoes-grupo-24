/**
 * Trava da classe de bug "o dashboard depende de um serviço externo em tempo de execução".
 *
 * Origem: em 2026-09 os tiles da CARTO do Mapa Híbrido passaram a exigir chave e cobriram o mapa
 * com "API KEY REQUIRED". O fundo do mapa virou 100% local (IBGE + Natural Earth, versionados em
 * src/data/geo/). Este teste falha se alguém voltar a pôr camada de tiles remota ou fonte/CSS
 * carregados de CDN — a demo precisa funcionar offline e na rede do ONS.
 *
 * Exceção única e deliberada (2026-09-26): src/oraculo/MapaOsm.tsx, o fundo OpenStreetMap das
 * telas do protótipo com imagem georreferenciada. Ali o tile é contexto (o dado é vetorial por
 * cima) e, sem rede, o mapa continua funcionando e avisa. O teste abaixo trava a regra: tile
 * remoto só naquele arquivo e só do OSM (nada de provedor com chave, como a CARTO).
 *
 * 2026-09-26: o mesmo arquivo passou a oferecer o fundo de satélite do mapa do RDX (Backend/RDX/main.py)
 * com a Esri World Imagery — sem chave, uso permitido com atribuição. É o único outro endereço aceito.
 */
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

// fileURLToPath (e não .pathname): caminho com espaço viraria %20 e o readdirSync falharia
const SRC = fileURLToPath(new URL('..', import.meta.url))

function arquivos(dir: string): string[] {
  return readdirSync(dir).flatMap((n: string) => {
    const p = join(dir, n)
    if (statSync(p).isDirectory()) return arquivos(p)
    return /\.(tsx?|css)$/.test(n) && !n.endsWith('.test.ts') ? [p] : []
  })
}

describe('nenhuma dependência de serviço externo em tempo de execução', () => {
  const fontes = arquivos(SRC).map((p) => ({ p, s: readFileSync(p, 'utf-8') }))

  const MAPA_OSM = /[\\/]oraculo[\\/]MapaOsm\.tsx$/

  it('sem camada de tiles remota no mapa (exceto o fundo OSM de oraculo/MapaOsm.tsx)', () => {
    for (const { p, s } of fontes) {
      if (MAPA_OSM.test(p)) continue
      expect(s, p).not.toMatch(/\bTileLayer\b/)
      expect(s, p).not.toMatch(/\{z\}\/\{x\}\/\{y\}/)
    }
  })

  it('sem fonte ou CSS de CDN (fontes vêm do @fontsource, empacotadas)', () => {
    for (const { p, s } of fontes) expect(s, p).not.toMatch(/fonts\.googleapis|@import\s+url\(\s*['"]?https?:/)
  })

  it('os únicos tiles remotos são o do OpenStreetMap e o de satélite da Esri, num arquivo só', () => {
    const comTile = fontes.filter(({ s }) => /\bTileLayer\b/.test(s)).map(({ p }) => p)
    expect(comTile.length).toBe(1)
    expect(comTile[0]).toMatch(MAPA_OSM)
    const osm = fontes.find(({ p }) => MAPA_OSM.test(p))!.s
    for (const url of osm.match(/https?:\/\/[^'"\s]*\{z\}[^'"\s]*/g) || []) expect(url).toMatch(/^https:\/\/(tile\.openstreetmap\.org|server\.arcgisonline\.com\/ArcGIS\/rest\/services\/World_Imagery)\//)
  })
})
