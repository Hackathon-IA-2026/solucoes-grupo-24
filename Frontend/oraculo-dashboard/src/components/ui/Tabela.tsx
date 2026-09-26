/**
 * Moldura de tabela compartilhada (Lista de Riscos, Excedentes...): rolagem horizontal em
 * tela estreita, cabeçalho padronizado e células sem quebra de linha — exceto as colunas
 * marcadas com `quebra` (textos longos como "Ação recomendada").
 *
 * Centralizado para as tabelas do dashboard terem exatamente o mesmo visual e o mesmo
 * comportamento; cada página só descreve colunas e linhas.
 */
import type { ReactNode } from 'react'

export interface ColunaTabela {
  rotulo: string
  /** numérica: alinha à direita (leitura por casa decimal) */
  num?: boolean
  /** oculta visualmente o rótulo (ex.: coluna de ícone/botão), mantendo-o para leitores de tela */
  semRotulo?: boolean
}

export function Tabela({ colunas, children }: { colunas: readonly ColunaTabela[]; children: ReactNode }) {
  return (
    // -mx/-my anulam o padding do Card: a tabela encosta nas bordas como num console.
    <div className="-mx-4 -my-4 overflow-x-auto">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="border-b border-line text-left">
            {colunas.map((c) => (
              <th
                key={c.rotulo}
                scope="col"
                className={`px-3 py-2.5 align-bottom text-[11px] font-semibold uppercase tracking-widest text-ink-muted ${
                  c.num ? 'text-right' : ''
                }`}
              >
                <span className={c.semRotulo ? 'sr-only' : undefined}>{c.rotulo}</span>
              </th>
            ))}
          </tr>
        </thead>
        {/* células em uma linha; a classe `quebra` numa <td> libera a quebra naquela coluna */}
        <tbody className="[&_td]:whitespace-nowrap [&_td.quebra]:whitespace-normal">{children}</tbody>
      </table>
    </div>
  )
}

/** Classes padrão de linha e célula, para as páginas não repetirem espaçamento e bordas. */
export const LINHA = 'border-b border-line/60 last:border-b-0'
export const CELULA = 'px-3 py-3'
