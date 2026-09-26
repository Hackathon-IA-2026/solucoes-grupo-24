import { RISK_STYLES, type RiskLevel } from '../../theme/severity'

interface SeverityBadgeProps {
  level: RiskLevel
  /** texto exibido; padrão é o rótulo do nível (Baixo, Médio...) */
  label?: string
  className?: string
}

/** Etiqueta compacta de severidade (listas, tabelas, popups do mapa). Cantos retos (console). */
export function SeverityBadge({ level, label, className = '' }: SeverityBadgeProps) {
  const s = RISK_STYLES[level]
  return (
    <span
      className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-sm border px-1.5 py-px font-mono text-[10px] font-semibold uppercase tracking-wider ${s.chip} ${className}`}
    >
      <span className={`size-1.5 rounded-full ${s.dot}`} aria-hidden />
      {label ?? s.label}
    </span>
  )
}
