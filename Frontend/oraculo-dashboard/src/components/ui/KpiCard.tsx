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
  /** borda superior de identidade (ver Card.accent), ex.: 'border-t-chart-1' */
  accent?: string
  /** classe de cor do número (padrão: text-ink) */
  valueClass?: string
}

/**
 * Número de destaque estilo painel de operação ("31,8 GW"). Mono com algarismos tabulares;
 * unidade menor e apagada para o valor dominar a leitura. Tamanho de console (text-kpi, 30px),
 * não de pôster: quatro KPIs cabem numa faixa sem roubar a tela dos gráficos.
 *
 * Os selos (`actions`, ex.: MOCK) ficam na linha do número, não no cabeçalho: com quatro KPIs
 * lado a lado, selo no cabeçalho cortava o rótulo ("CARGA SUPERVIS…").
 */
export function KpiCard({ label, value, unit, hint, actions, accent, valueClass = 'text-ink' }: KpiCardProps) {
  return (
    <Card title={label} accent={accent}>
      <div className="flex items-start justify-between gap-2">
        <p className={`kpi flex items-baseline gap-1.5 ${valueClass}`}>
          <span className="text-kpi font-semibold">{value}</span>
          {unit && <span className="text-body text-ink-muted">{unit}</span>}
        </p>
        {actions && <div className="flex shrink-0 items-center gap-1.5">{actions}</div>}
      </div>
      {hint && <p className="mt-2 text-xs text-ink-muted">{hint}</p>}
    </Card>
  )
}
