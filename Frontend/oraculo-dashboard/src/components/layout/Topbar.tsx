import { StatusPill } from '../ui/StatusPill'
import { Clock } from './Clock'
import { FonteDados } from './FonteDados'
import { SeverityFilters } from './SeverityFilters'

/** Barra superior fixa: título, status do SIN, filtros de severidade e relógio. */
export function Topbar() {
  return (
    <header className="sticky top-0 z-20 flex h-16 items-center gap-6 border-b border-line bg-surface/95 px-6 backdrop-blur">
      <h1 className="truncate text-sm font-semibold tracking-wide text-ink">
        <span className="font-mono text-accent">O.R.A.C.U.L.O.</span>
        <span className="text-ink-muted"> · ONS – Previsão de Curtailment</span>
      </h1>

      {/*
        Status estático por enquanto: ainda não há fonte de dados de estado do SIN no
        Backend. Quando houver, este pill passa a ser derivado dela.
      */}
      <StatusPill level="low" label="SIN OPERANDO" pulse />
      {/* origem dos dados exibidos (mock × API) e o instante a que se referem */}
      <FonteDados />

      <div className="ml-auto flex items-center gap-6">
        <SeverityFilters />
        <div className="h-8 w-px bg-line" aria-hidden />
        <Clock />
      </div>
    </header>
  )
}
