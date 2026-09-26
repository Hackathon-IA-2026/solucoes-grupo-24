import { Suspense } from 'react'
import type { ModuleDef } from '../../modules'
import { Carregando } from '../ui/Estado'

/**
 * Cabeçalho padrão de cada módulo (título + descrição vindos do registro), seguido do
 * conteúdo da página. Centralizado aqui para as páginas não repetirem o próprio título.
 *
 * Faixa compacta de uma linha (padrão do Figma: o espaço vertical vai para os dados, não
 * para o título); a descrição some antes de quebrar em tela estreita.
 */
export function ModuleFrame({ module }: { module: ModuleDef }) {
  const { label, description, Page } = module
  return (
    <>
      <div className="flex items-baseline gap-3 border-b border-line px-5 py-2.5">
        <h2 className="shrink-0 text-[15px] font-semibold text-ink">{label}</h2>
        <p className="hidden truncate text-body text-ink-muted md:block">{description}</p>
      </div>
      <div className="p-4 lg:p-5">
        <Suspense fallback={<Carregando altura="h-64" />}>
          <Page />
        </Suspense>
      </div>
    </>
  )
}
