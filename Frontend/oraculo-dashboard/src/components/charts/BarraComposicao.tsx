import { useState } from 'react'
import { formatMw, formatPct } from '../../utils/format'

export interface Parcela {
  chave: string
  rotulo: string
  mw: number
  pct: number
  /** classe Tailwind de fundo da série (bg-chart-1, bg-chart-2...) — ordem fixa por entidade */
  cor: string
}

/**
 * Barra 100% empilhada horizontal: composição de um total em poucas parcelas.
 *
 * Decisões (guia de dataviz do projeto):
 * - Barra empilhada em vez de pizza: comparar comprimentos numa régua comum é mais
 *   preciso que comparar ângulos, e com 2–4 parcelas continua legível.
 * - Vão de 2px entre segmentos (gap) e pontas arredondadas só nas extremidades.
 * - Identidade nunca só por cor: legenda com nome + MW + % (que também serve de
 *   tabela de valores) e rótulo direto dentro do segmento quando cabe.
 * - Hover por segmento com tooltip; o texto usa as cores de texto, nunca a da série.
 */
export function BarraComposicao({ parcelas, titulo }: { parcelas: readonly Parcela[]; titulo: string }) {
  const [foco, setFoco] = useState<string | null>(null)
  const ativa = parcelas.find((p) => p.chave === foco)

  return (
    <figure className="space-y-4">
      <div className="relative">
        <div role="img" aria-label={titulo} className="flex h-12 gap-0.5 overflow-hidden rounded">
          {parcelas.map((p) => (
            <div
              key={p.chave}
              style={{ width: `${p.pct}%` }}
              onMouseEnter={() => setFoco(p.chave)}
              onMouseLeave={() => setFoco(null)}
              className={`flex items-center px-3 transition-opacity ${p.cor} ${
                foco && foco !== p.chave ? 'opacity-40' : ''
              }`}
            >
              {/* rótulo direto só se o segmento tiver largura suficiente */}
              {p.pct >= 12 && (
                <span className="kpi text-sm font-semibold text-white">{formatPct(p.pct)}%</span>
              )}
            </div>
          ))}
        </div>

        {ativa && (
          <div
            role="tooltip"
            className="pointer-events-none absolute -top-2 left-1/2 z-10 -translate-x-1/2 -translate-y-full rounded border border-line bg-base px-3 py-2 text-xs shadow-lg"
          >
            <p className="text-ink-muted">{ativa.rotulo}</p>
            <p className="kpi text-ink">
              {formatMw(ativa.mw)} MW · {formatPct(ativa.pct)}%
            </p>
          </div>
        )}
      </div>

      <figcaption>
        <ul className="grid gap-2 sm:grid-cols-2">
          {parcelas.map((p) => (
            <li
              key={p.chave}
              onMouseEnter={() => setFoco(p.chave)}
              onMouseLeave={() => setFoco(null)}
              className="flex items-center gap-3 rounded border border-line px-3 py-2"
            >
              <span className={`size-3 shrink-0 rounded-sm ${p.cor}`} aria-hidden />
              <span className="flex-1 text-sm text-ink-muted">{p.rotulo}</span>
              <span className="kpi text-sm text-ink">{formatMw(p.mw)} MW</span>
              <span className="kpi w-14 text-right text-sm text-ink-muted">{formatPct(p.pct)}%</span>
            </li>
          ))}
        </ul>
      </figcaption>
    </figure>
  )
}
