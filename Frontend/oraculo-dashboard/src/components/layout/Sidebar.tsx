import { NavLink } from 'react-router-dom'
import { HorizonteSchema } from '../../data/types'
import { MODULES } from '../../modules'

/**
 * Navegação lateral, gerada do registro de módulos (ordem = ordem do array). A ordem segue o
 * fluxo do pitch (slide 10): mapa híbrido → lista por severidade → alerta rastreável →
 * coordenação TSO–DSO.
 *
 * Abaixo de `lg` mostra só número + ícone (o rótulo vira tooltip e continua no leitor de tela).
 */
export function Sidebar() {
  return (
    <aside className="flex flex-col border-r border-line bg-surface">
      
      <nav aria-label="Módulos" className="flex-1 overflow-y-auto py-2 lg:py-0">
        <ul>
          {MODULES.map(({ path, label, icon: Icon, grupo }, i) => (
            <li key={path}>
              {/* título do grupo (Operação, Análise, ... Dashboard do contrato) quando muda */}
              {grupo && grupo !== MODULES[i - 1]?.grupo && (
                <p className="rotulo hidden px-4 pt-3 pb-1 text-[10px] text-ink-faint lg:block">{grupo}</p>
              )}
              <NavLink
                to={path}
                title={label}
                className={({ isActive }) =>
                  `group flex h-9 items-center justify-center gap-2.5 border-l-2 px-3 transition-colors lg:justify-start ${
                    isActive
                      ? 'border-accent bg-accent/10 text-accent'
                      : 'border-transparent text-ink-muted hover:bg-surface-raised hover:text-ink'
                  }`
                }
              >
                {/* numeração de console: 01, 02... */}
                <span className="hidden font-mono text-[10px] text-ink-faint group-hover:text-ink-muted lg:inline">
                  {String(i + 1).padStart(2, '0')}
                </span>
                <Icon className="size-4 shrink-0" aria-hidden />
                <span className="sr-only whitespace-nowrap lg:not-sr-only">{label}</span>
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>

      {/*
        Rodapé com a cadência operacional da solução (planejamento v2: horizontes 30 min, 3 h e
        D+1, atualização a cada 30 min). Os horizontes vêm do schema do contrato, não de texto
        solto: um horizonte novo aparece aqui sozinho.
      */}
      <footer className="hidden space-y-2.5 border-t border-line px-4 py-3 lg:block">
        <div>
          <p className="rotulo text-[10px]">Horizontes</p>
          <p className="kpi mt-0.5 text-xs text-accent">{HorizonteSchema.options.join(' · ')}</p>
        </div>
        <div>
          <p className="rotulo text-[10px]">Atualização</p>
          <p className="kpi mt-0.5 text-xs text-ink-muted">a cada 30 min</p>
        </div>
        <p className="pt-1 font-mono text-[10px] text-ink-faint">Hackathon IA COPPE/UFRJ 2026</p>
      </footer>
    </aside>
  )
}
