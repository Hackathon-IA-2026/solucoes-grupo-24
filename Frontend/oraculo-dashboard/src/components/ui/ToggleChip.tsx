/**
 * Botão liga/desliga compacto (filtros de severidade, camadas do mapa). Desligado fica
 * claramente apagado (texto riscado + ponto vazado), para que o estado seja legível mesmo
 * quando a cor "ligada" já é neutra (ex.: NO-RISK).
 */
interface ToggleChipProps {
  label: string
  ativo: boolean
  onToggle: () => void
  /** classes do estado ligado (texto/borda/fundo) */
  classeAtivo: string
  /** classe do ponto no estado ligado */
  classePonto: string
}

export function ToggleChip({ label, ativo, onToggle, classeAtivo, classePonto }: ToggleChipProps) {
  return (
    <button
      type="button"
      aria-pressed={ativo}
      onClick={onToggle}
      className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-sm border px-2 py-0.5 font-mono text-[10px] font-semibold tracking-wider transition-colors ${
        ativo ? classeAtivo : 'border-line text-ink-faint line-through decoration-ink-faint/60 hover:text-ink-muted'
      }`}
    >
      <span
        className={`size-1.5 rounded-full ${ativo ? classePonto : 'border border-ink-faint bg-transparent'}`}
        aria-hidden
      />
      {label}
    </button>
  )
}
