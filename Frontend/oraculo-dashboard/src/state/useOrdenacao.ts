/**
 * Estado de ordenação de uma tabela: `const { ordenados, ordenacao, alternar } =
 * useOrdenacao(itens, COMPARADORES, { chave: 'severidade', direcao: 'desc' })`.
 * Clicar de novo na mesma coluna inverte a direção; coluna nova começa na direção padrão dela
 * (texto sobe A→Z, números descem do maior — o que o operador quer ver primeiro).
 */
import { useMemo, useState } from 'react'
import { ordenar, type Comparador, type Direcao, type Ordenacao } from '../utils/ordenacao'

export function useOrdenacao<T, K extends string>(
  itens: readonly T[],
  comparadores: Record<K, Comparador<T>>,
  // NoInfer: as chaves válidas vêm SÓ dos comparadores (senão a ordenação inicial restringiria K)
  inicial: Ordenacao<NoInfer<K>>,
  direcaoPadrao: Partial<Record<NoInfer<K>, Direcao>> = {},
) {
  const [ordenacao, setOrdenacao] = useState<Ordenacao<K>>(inicial)
  const ordenados = useMemo(() => ordenar(itens, comparadores, ordenacao), [itens, comparadores, ordenacao])
  const alternar = (chave: K) =>
    setOrdenacao((o) =>
      o.chave === chave
        ? { chave, direcao: o.direcao === 'asc' ? 'desc' : 'asc' }
        : { chave, direcao: direcaoPadrao[chave] ?? 'desc' },
    )
  return { ordenados, ordenacao, alternar }
}
