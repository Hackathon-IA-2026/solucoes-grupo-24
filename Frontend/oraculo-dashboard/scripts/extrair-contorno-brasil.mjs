/**
 * Extrai o contorno do Brasil do world-atlas (Natural Earth 1:50m, domínio público) para
 * src/data/geo/brasil.geo.json.
 *
 * Uso: npm run geo:brasil
 *
 * Por quê: o Mapa Híbrido precisa de um fundo que funcione SEM internet (tiles externos podem
 * estar bloqueados na rede do ONS ou numa demo offline). O contorno local é sempre desenhado;
 * os tiles, quando carregam, ficam por baixo. Só o Brasil é gravado (~50 kB, não o mundo todo).
 * Dado REAL (não mock): fronteira oficial do Natural Earth.
 */
import { readFileSync, writeFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { feature } from 'topojson-client'

const require = createRequire(import.meta.url)
const topo = JSON.parse(readFileSync(require.resolve('world-atlas/countries-50m.json'), 'utf8'))
const paises = feature(topo, topo.objects.countries)
const brasil = paises.features.find((f) => f.properties.name === 'Brazil')
if (!brasil) throw new Error('Brasil não encontrado no world-atlas')

// 4 casas decimais (~11 m): precisão de sobra para o zoom do mapa, arquivo bem menor.
const arred = (c) => (typeof c[0] === 'number' ? c.map((v) => Math.round(v * 1e4) / 1e4) : c.map(arred))
const saida = {
  type: 'Feature',
  properties: { nome: 'Brasil', fonte: 'Natural Earth 1:50m via world-atlas' },
  geometry: { type: brasil.geometry.type, coordinates: arred(brasil.geometry.coordinates) },
}
const destino = join(dirname(fileURLToPath(import.meta.url)), '..', 'src', 'data', 'geo', 'brasil.geo.json')
writeFileSync(destino, JSON.stringify(saida) + '\n')
console.log(`gerado ${destino}`)
