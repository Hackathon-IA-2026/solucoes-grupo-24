import type { Razao } from '../../data/types'
import { RAZAO_INFO } from '../../theme/razao'

/**
 * Badge da razão de curtailment. A cor fica no ponto e na borda; o texto continua em cor
 * de texto (legibilidade) e a sigla sempre aparece — identidade nunca só por cor.
 */
export function RazaoBadge({ razao }: { razao: Razao }) {
  const r = RAZAO_INFO[razao]
  return (
    <span
      title={r.nome}
      className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-sm border bg-surface-raised px-1.5 py-px font-mono text-[10px] font-semibold tracking-wider text-ink ${r.borda}`}
    >
      <span className={`size-1.5 rounded-full ${r.dot}`} aria-hidden />
      {razao}
    </span>
  )
}
