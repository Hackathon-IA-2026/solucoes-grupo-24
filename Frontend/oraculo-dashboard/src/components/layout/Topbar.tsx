import { OraculoBarra } from '../../oraculo/Barra'
import { StatusPill } from '../ui/StatusPill'
import { Clock } from './Clock'
import { FonteDados } from './FonteDados'
import { SeverityFilters } from './SeverityFilters'

/**
 * Barra superior de largura total (arranjo do Figma): marca na coluna da sidebar, título,
 * status do SIN, origem dos dados, filtros de severidade e relógio.
 *
 * Tudo em uma linha e sem quebra (`whitespace-nowrap` nos itens): antes, a 1440px o título
 * era cortado e "NO-RISK" e a data quebravam em duas linhas. Em tela estreita o que sai
 * primeiro é o texto secundário (subtítulo), nunca o status.
 */
export function Topbar() {
  return (
    <header className="col-span-2 flex items-center overflow-hidden border-b border-line bg-surface">
      {/* Bloco da marca, na largura da coluna da sidebar (AppLayout). aria-hidden: a marca é
          visual; o nome completo é lido no <h1> ao lado. */}
      <div
        aria-hidden
        className="flex h-full w-14 shrink-0 items-center justify-center gap-2.5 border-r border-line lg:w-52 lg:justify-start lg:px-4"
      >
        <span className="grid size-6 shrink-0 place-items-center bg-accent font-mono text-xs font-bold text-surface">O</span>
        <span className="hidden font-mono text-[13px] font-bold tracking-[0.12em] text-ink lg:inline">O.R.A.C.U.L.O.</span>
      </div>

      <div className="flex min-w-0 flex-1 items-center gap-4 px-4">
        {/* título pedido no Prompt 1: "O.R.A.C.U.L.O. · ONS – Previsão de Curtailment" */}
        {/* visível a partir de xl (antes disso sobra só "O.."); sempre presente para leitor de tela */}
        <h1 className="sr-only min-w-0 truncate text-body text-ink-muted xl:not-sr-only">
          <span className="sr-only">O.R.A.C.U.L.O. · </span>
          ONS – Previsão de Curtailment
        </h1>

        {/*
          Status estático por enquanto: ainda não há fonte de dados de estado do SIN no
          Backend. Quando houver, este pill passa a ser derivado dela.
        */}
        <StatusPill level="low" label="SIN OPERANDO" pulse className="max-sm:hidden" />
        {/* origem dos dados exibidos (mock × API) e o instante a que se referem */}
        <FonteDados />

        <div className="ml-auto flex shrink-0 items-center gap-4">
          {/* telas do protótipo: modo dos dados, área, ajuda F1 e recarregar */}
          <OraculoBarra />
          <SeverityFilters />
          <div className="h-7 w-px bg-line max-sm:hidden" aria-hidden />
          <div className="max-sm:hidden">
            <Clock />
          </div>
        </div>
      </div>
    </header>
  )
}
