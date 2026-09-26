/**
 * Selo "MOCK" exibido junto de qualquer dado ilustrativo (registros com `mock: true`).
 * Regra do projeto: dado sintético nunca pode parecer real na tela.
 */
export function MockTag({ mock }: { mock: boolean }) {
  if (!mock) return null
  return (
    <span
      title="Dado ilustrativo (mock) — ver docs/real_vs_mock.md"
      className="rounded-sm border border-dashed border-ink-faint px-1.5 py-0.5 font-mono text-[10px] font-semibold tracking-widest text-ink-muted"
    >
      MOCK
    </span>
  )
}
