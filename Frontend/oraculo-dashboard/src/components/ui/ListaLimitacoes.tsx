import type { Limitacao } from '../../content/limitacoes'

/**
 * Lista numerada de limitações declaradas (Validação e Metodologia usam a mesma peça, com
 * textos de src/content/limitacoes.ts). `inicio` continua a numeração entre listas.
 */
export function ListaLimitacoes({ itens, inicio = 1 }: { itens: readonly Limitacao[]; inicio?: number }) {
  return (
    <ol className="space-y-3">
      {itens.map((l, i) => (
        <li key={l.titulo} className="flex gap-3">
          <span className="kpi mt-0.5 text-xs text-ink-faint">{String(inicio + i).padStart(2, '0')}</span>
          <div>
            <p className="text-body font-medium text-ink">{l.titulo}</p>
            <p className="mt-0.5 text-xs text-ink-muted">{l.detalhe}</p>
          </div>
        </li>
      ))}
    </ol>
  )
}
