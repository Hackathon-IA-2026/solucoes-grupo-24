/**
 * Moldura de tabela compartilhada (Lista de Riscos, Excedentes...): rolagem horizontal em
 * tela estreita, cabeçalho padronizado e células sem quebra de linha — exceto as colunas
 * marcadas com `quebra` (textos longos como "Ação recomendada").
 *
 * Centralizado para as tabelas do dashboard terem exatamente o mesmo visual e o mesmo
 * comportamento; cada página só descreve colunas e linhas. Vai dentro de <Card flush>
 * (a tabela encosta nas bordas do painel, como num console).
 *
 * Ordenação: coluna com `ordem` vira botão no cabeçalho (seta indica a direção, `aria-sort`
 * informa o leitor de tela). O estado vem de state/useOrdenacao.ts.
 */
import type { ReactNode } from 'react'
import { ArrowDown, ArrowUp, ArrowUpDown } from 'lucide-react'
import type { Ordenacao } from '../../utils/ordenacao'

export interface ColunaTabela {
  rotulo: string
  /** numérica: alinha à direita (leitura por casa decimal) */
  num?: boolean
  /** oculta visualmente o rótulo (ex.: coluna de ícone/botão), mantendo-o para leitores de tela */
  semRotulo?: boolean
  /** chave de ordenação (presente = coluna ordenável) */
  ordem?: string
}

interface TabelaProps {
  colunas: readonly ColunaTabela[]
  children: ReactNode
  ordenacao?: Ordenacao<string>
  onOrdenar?: (chave: string) => void
}

export function Tabela({ colunas, children, ordenacao, onOrdenar }: TabelaProps) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-body">
        <thead>
          <tr className="border-b border-line bg-fundo/60 text-left">
            {colunas.map((c) => {
              const ativa = c.ordem !== undefined && ordenacao?.chave === c.ordem
              const Seta = !ativa ? ArrowUpDown : ordenacao?.direcao === 'asc' ? ArrowUp : ArrowDown
              return (
                <th
                  key={c.rotulo}
                  scope="col"
                  aria-sort={ativa ? (ordenacao?.direcao === 'asc' ? 'ascending' : 'descending') : undefined}
                  className={`rotulo px-3 py-2 align-bottom ${c.num ? 'text-right' : ''}`}
                >
                  {c.ordem && onOrdenar ? (
                    <button
                      type="button"
                      onClick={() => onOrdenar(c.ordem!)}
                      className={`inline-flex items-center gap-1 uppercase hover:text-ink ${ativa ? 'text-accent' : ''} ${c.num ? 'flex-row-reverse' : ''}`}
                    >
                      {c.rotulo}
                      <Seta className={`size-3 ${ativa ? '' : 'opacity-40'}`} aria-hidden />
                    </button>
                  ) : (
                    <span className={c.semRotulo ? 'sr-only' : undefined}>{c.rotulo}</span>
                  )}
                </th>
              )
            })}
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
export const CELULA = 'px-3 py-2.5'

/** Linha "nenhum resultado" ocupando todas as colunas (busca/filtro sem resultado). */
export function LinhaVazia({ colunas, texto }: { colunas: number; texto: string }) {
  return (
    <tr>
      <td colSpan={colunas} className="px-4 py-8 text-center text-body text-ink-muted">
        {texto}
      </td>
    </tr>
  )
}
