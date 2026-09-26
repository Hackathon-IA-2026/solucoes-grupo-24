import { RISK_STYLES, type RiskLevel } from '../../theme/severity'

interface StatusPillProps {
  level: RiskLevel
  label: string
  /** ponto pulsante, para status "ao vivo" (ex.: SIN OPERANDO) */
  pulse?: boolean
  className?: string
}

/** Indicador de estado arredondado, mais chamativo que o SeverityBadge. */
export function StatusPill({ level, label, pulse = false, className = '' }: StatusPillProps) {
  const s = RISK_STYLES[level]
  return (
    <span
      className={`inline-flex shrink-0 items-center gap-2 whitespace-nowrap rounded-full border px-3 py-1 font-mono text-xs font-semibold uppercase tracking-widest ${s.chip} ${className}`}
    >
      <span className="relative flex size-2" aria-hidden>
        {pulse && (
          <span className={`absolute inline-flex size-full animate-ping rounded-full opacity-75 ${s.dot}`} />
        )}
        <span className={`relative inline-flex size-2 rounded-full ${s.dot}`} />
      </span>
      {label}
    </span>
  )
}
