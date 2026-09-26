import { ToggleChip } from './ToggleChip'

/**
 * Grupo de filtros de múltipla escolha (razão, fonte, horizonte...). Todas as opções começam
 * ligadas: nada fica escondido sem o operador pedir. Desligar a última opção religa todas
 * (um filtro que esconde tudo parece "sem dados", o que confundiria).
 */
interface FiltroChipsProps<T extends string> {
  rotulo: string
  opcoes: readonly T[]
  ativos: ReadonlySet<T>
  onChange: (ativos: Set<T>) => void
  /** texto exibido de cada opção (padrão: a própria opção) */
  rotuloOpcao?: (o: T) => string
  /** classe do ponto de cada opção quando ligada (padrão: accent) */
  pontoOpcao?: (o: T) => string
}

export function FiltroChips<T extends string>({ rotulo, opcoes, ativos, onChange, rotuloOpcao, pontoOpcao }: FiltroChipsProps<T>) {
  const alternar = (o: T) => {
    const prox = new Set(ativos)
    if (prox.has(o)) prox.delete(o)
    else prox.add(o)
    onChange(prox.size ? prox : new Set(opcoes))
  }
  return (
    <div role="group" aria-label={rotulo} className="flex flex-wrap items-center gap-1">
      <span className="rotulo mr-1 text-[10px]">{rotulo}</span>
      {opcoes.map((o) => (
        <ToggleChip
          key={o}
          label={rotuloOpcao ? rotuloOpcao(o) : o}
          ativo={ativos.has(o)}
          onToggle={() => alternar(o)}
          classeAtivo="border-line bg-surface-raised text-ink"
          classePonto={pontoOpcao ? pontoOpcao(o) : 'bg-accent'}
        />
      ))}
    </div>
  )
}
