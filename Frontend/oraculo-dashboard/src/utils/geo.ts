/**
 * Geometria do Mapa Híbrido, em funções puras (testadas em geo.test.ts).
 *
 * - UF de um ponto: o ExcedenteTsoDso não tem campo de UF no contrato, só lat/lon; a UF sai da
 *   malha do IBGE (data/geo/ufs.geo.json) por ponto-em-polígono. Nada é suposto pelo nome.
 * - Marcadores sobrepostos: várias usinas podem vir com a MESMA coordenada (hoje o Backend
 *   publica a sede da UF enquanto não há coordenada por usina). Em vez de empilhar 10 círculos
 *   num ponto só, o mapa os espalha num anel em PIXELS em volta do ponto verdadeiro, ligados a ele
 *   por uma linha — a posição real continua marcada, só a leitura fica possível.
 */

type Anel = number[][] // [lon, lat][]
type GeometriaUf = { type: 'Polygon'; coordinates: Anel[] } | { type: 'MultiPolygon'; coordinates: Anel[][] }
export interface ColecaoUfs {
  features: { properties: { uf: string }; geometry: GeometriaUf }[]
}

/** Ray casting num anel (lon, lat). Borda conta como fora (ponto exatamente na divisa é raro). */
function dentroDoAnel(lon: number, lat: number, anel: Anel): boolean {
  let dentro = false
  for (let i = 0, j = anel.length - 1; i < anel.length; j = i++) {
    const [xi, yi] = anel[i]
    const [xj, yj] = anel[j]
    if (yi > lat !== yj > lat && lon < ((xj - xi) * (lat - yi)) / (yj - yi) + xi) dentro = !dentro
  }
  return dentro
}

/** Polígono com buracos: dentro do anel externo e fora de todos os internos. */
const dentroDoPoligono = (lon: number, lat: number, aneis: Anel[]) =>
  dentroDoAnel(lon, lat, aneis[0]) && !aneis.slice(1).some((a) => dentroDoAnel(lon, lat, a))

export function pontoNaGeometria(lat: number, lon: number, g: GeometriaUf): boolean {
  return g.type === 'Polygon'
    ? dentroDoPoligono(lon, lat, g.coordinates)
    : g.coordinates.some((p) => dentroDoPoligono(lon, lat, p))
}

/** Sigla da UF que contém o ponto, ou null (ponto no mar / fora do Brasil). */
export function ufDoPonto(lat: number, lon: number, ufs: ColecaoUfs): string | null {
  return ufs.features.find((f) => pontoNaGeometria(lat, lon, f.geometry))?.properties.uf ?? null
}

/** Chave de "mesma posição" (5 casas ≈ 1 m: coordenadas iguais de fato, não vizinhas). */
export const chavePosicao = (lat: number, lon: number) => `${lat.toFixed(5)},${lon.toFixed(5)}`

/** Agrupa itens pela posição; a ordem dentro do grupo é a ordem de entrada (determinística). */
export function agruparPorPosicao<T>(itens: readonly T[], pos: (t: T) => [number, number]): Map<string, T[]> {
  const grupos = new Map<string, T[]>()
  for (const it of itens) {
    const k = chavePosicao(...pos(it))
    grupos.set(k, [...(grupos.get(k) ?? []), it])
  }
  return grupos
}

/**
 * Deslocamentos em pixels para `n` marcadores no mesmo ponto: um sozinho fica no centro; vários
 * ficam num anel cujo raio cresce com n (para não encostarem), começando ao norte e girando no
 * sentido horário.
 */
export function offsetsEmAnel(n: number, raioBasePx = 18, espacoPx = 30): [number, number][] {
  if (n <= 1) return [[0, 0]]
  // circunferência ≥ n × espaço mínimo entre marcadores
  const raio = Math.max(raioBasePx, (n * espacoPx) / (2 * Math.PI))
  return Array.from({ length: n }, (_, k) => {
    const ang = -Math.PI / 2 + (2 * Math.PI * k) / n
    return [raio * Math.cos(ang), raio * Math.sin(ang)]
  })
}
