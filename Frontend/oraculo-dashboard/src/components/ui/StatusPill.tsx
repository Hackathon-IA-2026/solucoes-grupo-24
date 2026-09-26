import { RISK_STYLES, type RiskLevel } from '../../theme/severity'

interface StatusPillProps {
  level: RiskLevel
  label: string
  /** ponto pulsante, para status "ao vivo" (ex.: SIN OPERANDO) */
  pulse?: boolean
  className?: string
}

/** Indicador de estado arredondado, mais chamativo que o SeverityBadge. Nunca quebra linha. */
export function StatusPill({ level, label, pulse = false, className = '' }: StatusPillProps) {
  const s = RISK_STYLES[level]
  return (
    <span
      className={`inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full border px-2.5 py-0.5 font-mono text-[11px] font-semibold uppercase tracking-widest ${s.chip} ${className}`}
    >
      <span className="relative flex size-1.5" aria-hidden>
        {pulse && (
          <span className={`absolute inline-flex size-full animate-ping rounded-full opacity-75 ${s.dot}`} />
        )}
        <span className={`relative inline-flex size-1.5 rounded-full ${s.dot}`} />
      </span>
      {label}
    </span>
  )
}
