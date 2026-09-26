/**
 * Ordenação por coluna das tabelas (clique no cabeçalho). Função pura + tipos; o estado fica no
 * hook useOrdenacao (state/useOrdenacao.ts).
 *
 * Decisão: cada tabela declara um comparador por coluna (Record chave -> comparador) e a
 * ordenação padrão da tela é só mais uma entrada. Assim "voltar à ordem padrão" e "ordenar por
 * MW" usam o mesmo caminho, e o desempate (id/nome) fica dentro de cada comparador, para a ordem
 * nunca depender da chegada dos dados.
 */
export type Direcao = 'asc' | 'desc'
export type Comparador<T> = (a: T, b: T) => number
export interface Ordenacao<K extends string> {
  chave: K
  direcao: Direcao
}

export function ordenar<T, K extends string>(
  itens: readonly T[],
  comparadores: Record<K, Comparador<T>>,
  { chave, direcao }: Ordenacao<K>,
): T[] {
  const cmp = comparadores[chave]
  const sinal = direcao === 'asc' ? 1 : -1
  return [...itens].sort((a, b) => sinal * cmp(a, b))
}

/** Comparadores de apoio (texto em pt-BR, com acentos na ordem certa). */
export const porTexto = (a: string, b: string) => a.localeCompare(b, 'pt-BR')
export const porNumero = (a: number, b: number) => a - b

/** Ordem natural dos horizontes (não alfabética: 30min < 1h < 3h < D+1). */
const ORDEM_HORIZONTE: Record<string, number> = { '30min': 0, '1h': 1, '3h': 2, 'D+1': 3 }
export const porHorizonte = (a: string, b: string) => (ORDEM_HORIZONTE[a] ?? 9) - (ORDEM_HORIZONTE[b] ?? 9)

/** Normaliza texto para busca: minúsculas e sem acento ("Piauí" casa com "piaui"). */
export const normalizar = (s: string) => s.normalize('NFD').replace(/\p{Diacritic}/gu, '').toLowerCase()

/** Todos os termos da busca aparecem em algum dos campos (ordem livre). */
export function casaBusca(busca: string, campos: readonly string[]): boolean {
  const termos = normalizar(busca).split(/\s+/).filter(Boolean)
  if (!termos.length) return true
  const alvo = normalizar(campos.join(' '))
  return termos.every((t) => alvo.includes(t))
}
