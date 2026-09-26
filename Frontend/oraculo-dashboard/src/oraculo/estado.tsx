/**
 * Estado compartilhado das telas do protótipo (o STATE de 02-PROTOTIPO/web/js/app.js):
 * metadados do serviço, saúde (modo live/cache/demo), área selecionada e um contador de
 * "recarregar" que invalida o cache e refaz as leituras de todas as telas abertas.
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { Api, ApiError } from './api'

export interface AreaMeta {
  id: string
  name: string
}
export interface Meta {
  areas?: AreaMeta[]
  demo_banner?: string
  [k: string]: unknown
}
export interface Health {
  mode?: 'live' | 'cache' | 'demo' | string
  [k: string]: unknown
}

interface Ctx {
  meta: Meta | null
  health: Health | null
  erro: ApiError | null
  area: string
  setArea: (a: string) => void
  /** muda a cada "recarregar": entra nas dependências de useApi */
  versao: number
  recarregar: () => Promise<void>
  /** tema do protótipo ('dark' | 'light'), no atributo data-theme do <html> */
  tema: Tema
  alternarTema: () => void
}

export type Tema = 'dark' | 'light'

function lerTema(): Tema {
  try {
    return localStorage.getItem('oraculo.theme') === 'light' ? 'light' : 'dark'
  } catch {
    return 'dark'
  }
}

const OraculoCtx = createContext<Ctx | null>(null)

function lerArea(): string {
  try {
    return localStorage.getItem('oraculo.area') || 'SIN'
  } catch {
    return 'SIN'
  }
}

export function OraculoProvider({ children }: { children: ReactNode }) {
  const [meta, setMeta] = useState<Meta | null>(null)
  const [health, setHealth] = useState<Health | null>(null)
  const [erro, setErro] = useState<ApiError | null>(null)
  const [area, setAreaState] = useState(lerArea)
  const [versao, setVersao] = useState(0)
  const [tema, setTema] = useState<Tema>(lerTema)

  // Mesmo mecanismo do protótipo: data-theme no <html> e escolha lembrada em oraculo.theme.
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', tema)
    try {
      localStorage.setItem('oraculo.theme', tema)
    } catch {
      // armazenamento indisponível: o tema vale só nesta sessão
    }
  }, [tema])
  const alternarTema = useCallback(() => setTema((t) => (t === 'dark' ? 'light' : 'dark')), [])

  useEffect(() => {
    let vivo = true
    Promise.all([Api.meta(), Api.health()])
      .then(([m, h]) => {
        if (!vivo) return
        setMeta(m.data as Meta)
        setHealth(h.data as Health)
      })
      .catch((e: unknown) => vivo && setErro(e instanceof ApiError ? e : new ApiError('BOOT', String(e), 'Suba o Backend: python main.py')))
    return () => {
      vivo = false
    }
  }, [])

  const setArea = useCallback((a: string) => {
    setAreaState(a)
    try {
      localStorage.setItem('oraculo.area', a)
    } catch {
      // armazenamento indisponível: a área vale só nesta sessão
    }
  }, [])

  const recarregar = useCallback(async () => {
    Api.clearCache()
    try {
      setHealth((await Api.health(true)).data as Health)
      setErro(null)
    } catch (e) {
      setErro(e instanceof ApiError ? e : new ApiError('NETWORK', String(e)))
    }
    setVersao((v) => v + 1)
  }, [])

  const valor = useMemo(
    () => ({ meta, health, erro, area, setArea, versao, recarregar, tema, alternarTema }),
    [meta, health, erro, area, setArea, versao, recarregar, tema, alternarTema],
  )
  return <OraculoCtx.Provider value={valor}>{children}</OraculoCtx.Provider>
}

export function useOraculo(): Ctx {
  const c = useContext(OraculoCtx)
  if (!c) throw new Error('useOraculo fora do <OraculoProvider>')
  return c
}

/**
 * useState que sobrevive à troca de tela (o STATE global do protótipo guardava seleção de
 * subestação, horizonte, filtros...). Vive só na memória da aba.
 */
const MEMORIA = new Map<string, unknown>()
export function usePersistido<T>(chave: string, inicial: T): [T, (v: T | ((a: T) => T)) => void] {
  const [v, setV] = useState<T>(() => (MEMORIA.has(chave) ? (MEMORIA.get(chave) as T) : inicial))
  const set = useCallback(
    (nv: T | ((a: T) => T)) => {
      setV((ant) => {
        const val = typeof nv === 'function' ? (nv as (a: T) => T)(ant) : nv
        MEMORIA.set(chave, val)
        return val
      })
    },
    [chave],
  )
  return [v, set]
}
