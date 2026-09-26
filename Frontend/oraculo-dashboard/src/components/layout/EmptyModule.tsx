import { Card } from '../ui/Card'

/** Placeholder das páginas ainda sem conteúdo. Não exibe nenhum dado (nada inventado). */
export function EmptyModule() {
  return (
    <Card>
      <div className="grid h-64 place-items-center rounded-sm border border-dashed border-line">
        <p className="font-mono text-xs uppercase tracking-widest text-ink-faint">
          Módulo em construção · sem dados conectados
        </p>
      </div>
    </Card>
  )
}
