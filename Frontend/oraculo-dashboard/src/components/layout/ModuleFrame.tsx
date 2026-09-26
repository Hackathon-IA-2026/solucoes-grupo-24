import { Suspense } from 'react'
import type { ModuleDef } from '../../modules'
import { Carregando } from '../ui/Estado'

/**
 * Cabeçalho padrão de cada módulo (título + descrição vindos do registro), seguido do
 * conteúdo da página. Centralizado aqui para as páginas não repetirem o próprio título.
 */
export function ModuleFrame({ module }: { module: ModuleDef }) {
  const { label, description, Page } = module
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold text-ink">{label}</h2>
        <p className="mt-1 text-sm text-ink-muted">{description}</p>
      </div>
      <Suspense fallback={<Carregando altura="h-64" />}>
        <Page />
      </Suspense>
    </div>
  )
}
