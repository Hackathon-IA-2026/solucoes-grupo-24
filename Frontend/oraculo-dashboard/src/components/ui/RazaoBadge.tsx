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
      className={`inline-flex items-center gap-1.5 rounded-sm border bg-surface-raised px-2 py-0.5 font-mono text-[11px] font-semibold tracking-wider text-ink ${r.borda}`}
    >
      <span className={`size-1.5 rounded-full ${r.dot}`} aria-hidden />
      {razao}
    </span>
  )
}
