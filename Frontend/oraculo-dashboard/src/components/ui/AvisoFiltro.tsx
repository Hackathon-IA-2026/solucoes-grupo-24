/**
 * Aviso de itens escondidos pelos filtros de severidade da topbar. Regra: dado filtrado nunca
 * pode parecer dado inexistente — se algo foi ocultado, a tela diz quanto.
 */
export function AvisoFiltro({ ocultos, className = '' }: { ocultos: number; className?: string }) {
  if (ocultos === 0) return null
  return (
    <p role="status" className={`font-mono text-[11px] text-ink-faint ${className}`}>
      {ocultos} {ocultos === 1 ? 'item oculto' : 'itens ocultos'} pelos filtros de severidade da barra superior
    </p>
  )
}
