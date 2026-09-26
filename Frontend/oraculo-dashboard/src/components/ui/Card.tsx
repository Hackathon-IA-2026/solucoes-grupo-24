import type { ReactNode } from 'react'

interface CardProps {
  /** título em caixa alta, estilo rótulo de painel */
  title?: string
  /** conteúdo à direita do título (badge, botão, timestamp...) */
  actions?: ReactNode
  /**
   * Classe de BORDA SUPERIOR colorida (ex.: 'border-t-chart-1'): identidade da grandeza do
   * card, como os KPIs do protótipo Figma. Sem ela, o card é neutro.
   */
  accent?: string
  /** corpo sem padding (tabelas e mapas que encostam na borda) */
  flush?: boolean
  className?: string
  children?: ReactNode
}

/**
 * Painel base de todas as telas. Cabeçalho opcional com título + ações; o corpo é livre.
 * Borda fina, cantos retos e fundo "surface" imitam os quadros de um console SCADA.
 */
export function Card({ title, actions, accent, flush = false, className = '', children }: CardProps) {
  return (
    <section
      className={`flex flex-col border border-line bg-surface ${accent ? `border-t-2 ${accent}` : ''} ${className}`}
    >
      {(title || actions) && (
        <header className="flex min-h-9 flex-wrap items-center justify-between gap-x-3 gap-y-1 border-b border-line px-4 py-1.5">
          {title && <h2 className="rotulo truncate">{title}</h2>}
          {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
        </header>
      )}
      <div className={`flex-1 ${flush ? '' : 'p-4'}`}>{children}</div>
    </section>
  )
}
