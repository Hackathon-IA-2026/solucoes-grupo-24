/**
 * Contexto + hook dos filtros de severidade. Separado do provider (severityFilter.tsx)
 * porque o Fast Refresh do Vite só recarrega arquivos que exportam apenas componentes.
 */
import { createContext, useContext } from 'react'
import type { OperationalStatus } from '../theme/severity'

export interface SeverityFilterValue {
  active: ReadonlySet<OperationalStatus>
  isActive: (s: OperationalStatus) => boolean
  toggle: (s: OperationalStatus) => void
}

export const SeverityFilterContext = createContext<SeverityFilterValue | null>(null)

export function useSeverityFilter(): SeverityFilterValue {
  const ctx = useContext(SeverityFilterContext)
  // Falha alta em vez de devolver um default silencioso: usar fora do provider é bug de montagem.
  if (!ctx) throw new Error('useSeverityFilter precisa estar dentro de <SeverityFilterProvider>')
  return ctx
}
