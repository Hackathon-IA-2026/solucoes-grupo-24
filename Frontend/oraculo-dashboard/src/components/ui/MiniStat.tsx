import type { LucideIcon } from 'lucide-react'

/**
 * Linha de um único valor (painéis laterais): ícone + rótulo à esquerda, número à direita.
 * Formato de lista de console (Figma "Fatores climáticos"), mais denso que um card por valor.
 */
export function MiniStat({ icon: Icon, label, value, unit }: { icon: LucideIcon; label: string; value: string; unit: string }) {
  return (
    <div className="flex items-center justify-between gap-3 px-4 py-2.5">
      <p className="flex items-center gap-2 text-body text-ink-muted">
        <Icon className="size-3.5 shrink-0 text-accent" aria-hidden />
        {label}
      </p>
      <p className="kpi flex items-baseline gap-1 text-ink">
        <span className="text-lg font-semibold">{value}</span>
        <span className="text-[11px] text-ink-muted">{unit}</span>
      </p>
    </div>
  )
}
