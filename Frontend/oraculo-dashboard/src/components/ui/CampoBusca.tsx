import { Search, X } from 'lucide-react'

/**
 * Campo de busca das tabelas. A regra de casamento (todos os termos, sem acento) fica em
 * utils/ordenacao.ts::casaBusca — aqui é só a caixa de texto, com botão de limpar.
 */
export function CampoBusca({ valor, onChange, placeholder }: { valor: string; onChange: (v: string) => void; placeholder: string }) {
  return (
    <label className="relative flex min-w-48 flex-1 items-center sm:max-w-72">
      <Search className="pointer-events-none absolute left-2 size-3.5 text-ink-faint" aria-hidden />
      <input
        type="search"
        value={valor}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        aria-label={placeholder}
        className="w-full rounded-sm border border-line bg-fundo py-1 pr-7 pl-7 text-body text-ink placeholder:text-ink-faint focus:border-accent/60 focus:outline-none [&::-webkit-search-cancel-button]:hidden"
      />
      {valor && (
        <button type="button" onClick={() => onChange('')} aria-label="Limpar busca" className="absolute right-1.5 text-ink-faint hover:text-ink">
          <X className="size-3.5" aria-hidden />
        </button>
      )}
    </label>
  )
}
