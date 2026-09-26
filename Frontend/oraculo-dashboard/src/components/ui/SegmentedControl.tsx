/**
 * Seletor de opção única em botões lado a lado (horizonte, período...). Genérico no tipo
 * da opção, então `onChange` já devolve o valor tipado (ex.: Horizonte), sem cast.
 */
interface SegmentedControlProps<T extends string> {
  label: string
  options: readonly T[]
  value: T
  onChange: (v: T) => void
}

export function SegmentedControl<T extends string>({ label, options, value, onChange }: SegmentedControlProps<T>) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex gap-px rounded-sm border border-line bg-fundo p-0.5">
      {options.map((o) => {
        const on = o === value
        return (
          <button
            key={o}
            type="button"
            role="radio"
            aria-checked={on}
            onClick={() => onChange(o)}
            className={`rounded-sm px-3 py-1 font-mono text-[11px] font-semibold tracking-wider transition-colors ${
              on ? 'bg-accent/15 text-accent' : 'text-ink-muted hover:bg-surface-raised hover:text-ink'
            }`}
          >
            {o}
          </button>
        )
      })}
    </div>
  )
}
