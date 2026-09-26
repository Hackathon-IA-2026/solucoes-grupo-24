import type { LucideIcon } from 'lucide-react'

/** Card pequeno de um único valor (painéis laterais): ícone + rótulo + número + unidade. */
export function MiniStat({ icon: Icon, label, value, unit }: { icon: LucideIcon; label: string; value: string; unit: string }) {
  return (
    <div className="rounded-md border border-line bg-surface p-3">
      <p className="flex items-center gap-2 text-[11px] uppercase tracking-widest text-ink-muted">
        <Icon className="size-3.5 text-accent" aria-hidden />
        {label}
      </p>
      <p className="kpi mt-1.5 flex items-baseline gap-1.5 text-ink">
        <span className="text-2xl font-semibold">{value}</span>
        <span className="text-xs text-ink-muted">{unit}</span>
      </p>
    </div>
  )
}
