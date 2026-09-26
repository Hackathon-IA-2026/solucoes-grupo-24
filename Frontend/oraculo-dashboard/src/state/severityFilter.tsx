/**
 * Estado global dos filtros de severidade da barra superior.
 *
 * Decisão: Context em vez de estado local no Topbar, porque os filtros ficam no layout
 * mas quem os consome são as páginas (Lista de Riscos, Mapa...). Assim qualquer tela lê
 * `useSeverityFilter()` sem prop drilling. Todos começam ativos (nada escondido por padrão).
 */
import { useCallback, useMemo, useState, type ReactNode } from 'react'
import { OPERATIONAL_STATUSES, type OperationalStatus } from '../theme/severity'
import { SeverityFilterContext } from './useSeverityFilter'

export function SeverityFilterProvider({ children }: { children: ReactNode }) {
  const [active, setActive] = useState<ReadonlySet<OperationalStatus>>(
    () => new Set(OPERATIONAL_STATUSES),
  )

  const toggle = useCallback((s: OperationalStatus) => {
    setActive((prev) => {
      const next = new Set(prev)
      if (next.has(s)) next.delete(s)
      else next.add(s)
      return next
    })
  }, [])

  const value = useMemo(
    () => ({ active, isActive: (s: OperationalStatus) => active.has(s), toggle }),
    [active, toggle],
  )

  return <SeverityFilterContext.Provider value={value}>{children}</SeverityFilterContext.Provider>
}
