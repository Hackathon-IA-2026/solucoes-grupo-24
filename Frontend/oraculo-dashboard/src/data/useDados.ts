/**
 * Hook de leitura assíncrona para as telas: `const r = useDados(getCarga)`.
 *
 * Decisão: estado como união discriminada (loading | ok | erro). Assim o componente não
 * consegue ler `data` sem antes checar `status === 'ok'` — o TypeScript impede renderizar
 * dado indefinido. Sem biblioteca (React Query etc.) enquanto não houver cache/refetch.
 */
import { useEffect, useState } from 'react'

export type Dados<T> =
  | { status: 'loading' }
  | { status: 'ok'; data: T }
  | { status: 'erro'; erro: Error }

export function useDados<T>(carregar: () => Promise<T>): Dados<T> {
  // O resultado guarda de QUAL `carregar` veio. Se a função mudar, o resultado antigo
  // deixa de valer e o estado derivado volta a "loading" sem setState dentro do efeito
  // (nada de cascata de renders nem de mostrar dado da fonte anterior).
  const [resultado, setResultado] = useState<{ de: () => Promise<T>; dados: Dados<T> } | null>(null)

  useEffect(() => {
    let ativo = true // evita setState após desmontar ou após troca de `carregar`
    carregar().then(
      (data) => ativo && setResultado({ de: carregar, dados: { status: 'ok', data } }),
      (e: unknown) =>
        ativo &&
        setResultado({
          de: carregar,
          dados: { status: 'erro', erro: e instanceof Error ? e : new Error(String(e)) },
        }),
    )
    return () => {
      ativo = false
    }
  }, [carregar])

  return resultado?.de === carregar ? resultado.dados : { status: 'loading' }
}
