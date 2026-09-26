import { NavLink } from 'react-router-dom'
import { MODULES } from '../../modules'

/** Navegação lateral fixa, gerada do registro de módulos (ordem = ordem do array). */
export function Sidebar() {
  return (
    <aside className="fixed inset-y-0 left-0 z-30 flex w-64 flex-col border-r border-line bg-surface">
      <div className="flex h-16 items-center gap-3 border-b border-line px-5">
        <span className="grid size-8 place-items-center rounded-sm border border-accent/50 bg-accent/10 font-mono text-sm font-bold text-accent">
          O
        </span>
        <div className="leading-tight">
          <p className="font-mono text-sm font-bold tracking-widest text-ink">ORÁCULO</p>
          <p className="text-[10px] uppercase tracking-widest text-ink-faint">Sala de controle</p>
        </div>
      </div>

      <nav aria-label="Módulos" className="flex-1 overflow-y-auto py-3">
        <ul className="space-y-0.5 px-2">
          {MODULES.map(({ path, label, icon: Icon }, i) => (
            <li key={path}>
              <NavLink
                to={path}
                className={({ isActive }) =>
                  `group flex items-center gap-3 rounded-sm border-l-2 px-3 py-2 text-sm transition-colors ${
                    isActive
                      ? 'border-accent bg-accent/10 text-accent'
                      : 'border-transparent text-ink-muted hover:bg-surface-raised hover:text-ink'
                  }`
                }
              >
                {/* numeração de console: 01, 02... */}
                <span className="font-mono text-[10px] text-ink-faint group-hover:text-ink-muted">
                  {String(i + 1).padStart(2, '0')}
                </span>
                <Icon className="size-4 shrink-0" aria-hidden />
                <span className="truncate">{label}</span>
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>

      <footer className="border-t border-line px-5 py-3 font-mono text-[10px] text-ink-faint">
        Hackathon IA COPPE/UFRJ 2026
      </footer>
    </aside>
  )
}
