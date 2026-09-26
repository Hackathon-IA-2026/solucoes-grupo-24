import type { ReactNode } from 'react'

interface CardProps {
  /** título em caixa alta, estilo rótulo de painel */
  title?: string
  /** conteúdo à direita do título (badge, botão, timestamp...) */
  actions?: ReactNode
  className?: string
  children?: ReactNode
}

/**
 * Painel base de todas as telas. Cabeçalho opcional com título + ações; o corpo é livre.
 * Borda fina e fundo "surface" imitam os quadros de um console SCADA.
 */
export function Card({ title, actions, className = '', children }: CardProps) {
  return (
    <section className={`rounded-md border border-line bg-surface ${className}`}>
      {(title || actions) && (
        <header className="flex items-center justify-between gap-3 border-b border-line px-4 py-2.5">
          {title && (
            <h2 className="text-xs font-semibold uppercase tracking-widest text-ink-muted">
              {title}
            </h2>
          )}
          {actions && <div className="flex items-center gap-2">{actions}</div>}
        </header>
      )}
      <div className="p-4">{children}</div>
    </section>
  )
}
