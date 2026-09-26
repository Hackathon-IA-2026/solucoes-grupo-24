import type { ReactNode } from 'react'
import { Card } from './Card'

interface KpiCardProps {
  label: string
  /** número já formatado (ex.: "31,8") */
  value: string
  unit?: string
  /** linha de apoio abaixo do número (valor exato, contexto) */
  hint?: ReactNode
  /** badge/selo no canto do cabeçalho */
  actions?: ReactNode
}

/**
 * Número de destaque estilo painel de operação ("63,5 GW"). Número grande em mono com
 * algarismos tabulares; unidade menor e apagada para o valor dominar a leitura.
 */
export function KpiCard({ label, value, unit, hint, actions }: KpiCardProps) {
  return (
    <Card title={label} actions={actions}>
      <p className="kpi flex items-baseline gap-2 text-ink">
        <span className="text-5xl font-semibold">{value}</span>
        {unit && <span className="text-xl text-ink-muted">{unit}</span>}
      </p>
      {hint && <p className="mt-2 text-xs text-ink-muted">{hint}</p>}
    </Card>
  )
}
