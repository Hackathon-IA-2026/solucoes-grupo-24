/**
 * Baixa a malha das 27 UFs da API de malhas do IBGE e grava src/data/geo/ufs.geo.json.
 *
 * Uso: npm run geo:ufs   (precisa de internet SÓ aqui; o arquivo gerado é versionado)
 *
 * Por quê: o Mapa Híbrido usava tiles da CARTO como fundo e, em 2026-09, a CARTO passou a
 * responder "API KEY REQUIRED" (marca d'água por cima do mapa inteiro). Em vez de trocar de
 * provedor (e esperar o próximo quebrar), o fundo passou a ser 100% local: contorno do país
 * (npm run geo:brasil) + divisas estaduais daqui. Dado REAL, não mock: malha oficial do IBGE.
 *
 * Fonte: https://servicodados.ibge.gov.br/api/docs/malhas?versao=3 (qualidade "minima": ~100 kB,
 * suficiente para o zoom de país; divisas não são usadas para cálculo, só para orientação).
 */
import { writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const URL_IBGE =
  'https://servicodados.ibge.gov.br/api/v3/malhas/paises/BR?formato=application/vnd.geo+json&qualidade=minima&intrarregiao=UF'

// Código IBGE da UF -> sigla (tabela oficial e estável do IBGE).
const SIGLA = {
  11: 'RO', 12: 'AC', 13: 'AM', 14: 'RR', 15: 'PA', 16: 'AP', 17: 'TO',
  21: 'MA', 22: 'PI', 23: 'CE', 24: 'RN', 25: 'PB', 26: 'PE', 27: 'AL', 28: 'SE', 29: 'BA',
  31: 'MG', 32: 'ES', 33: 'RJ', 35: 'SP', 41: 'PR', 42: 'SC', 43: 'RS',
  50: 'MS', 51: 'MT', 52: 'GO', 53: 'DF',
}

const resp = await fetch(URL_IBGE)
if (!resp.ok) throw new Error(`IBGE respondeu ${resp.status} ${resp.statusText}`)
const malha = await resp.json()

// 3 casas decimais (~110 m): de sobra para divisas desenhadas no zoom de país.
const arred = (c) => (typeof c[0] === 'number' ? c.map((v) => Math.round(v * 1e3) / 1e3) : c.map(arred))
const features = malha.features.map((f) => {
  const sigla = SIGLA[Number(f.properties.codarea)]
  if (!sigla) throw new Error(`código de UF desconhecido: ${f.properties.codarea}`)
  return { type: 'Feature', properties: { uf: sigla }, geometry: { type: f.geometry.type, coordinates: arred(f.geometry.coordinates) } }
})
// Falha alto se a malha vier incompleta: um estado sem divisa passaria despercebido no mapa.
if (features.length !== 27) throw new Error(`esperadas 27 UFs, vieram ${features.length}`)

const saida = { type: 'FeatureCollection', properties: { fonte: 'IBGE — API de malhas v3, qualidade mínima' }, features }
const destino = join(dirname(fileURLToPath(import.meta.url)), '..', 'src', 'data', 'geo', 'ufs.geo.json')
writeFileSync(destino, JSON.stringify(saida) + '\n')
console.log(`gerado ${destino} (${features.length} UFs)`)
