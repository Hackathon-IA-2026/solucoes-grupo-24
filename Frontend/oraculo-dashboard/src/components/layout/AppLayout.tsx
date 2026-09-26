import { Outlet } from 'react-router-dom'
import { SeverityFilterProvider } from '../../state/severityFilter'
import { Sidebar } from './Sidebar'
import { Topbar } from './Topbar'

/**
 * Casca do app, no arranjo do protótipo Figma: topbar de largura total (marca à esquerda),
 * sidebar abaixo dela e conteúdo com rolagem própria — a moldura de console fica sempre
 * visível, só o miolo rola.
 *
 * Decisão: grid em vez de sidebar `fixed` + margem. A largura da coluna da sidebar existe num
 * lugar só (aqui), então topbar, sidebar e conteúdo nunca desalinham. Abaixo de `lg` a
 * sidebar vira uma coluna de ícones (3.5rem): o layout deixa de esmagar o conteúdo em tela
 * estreita (era um problema conhecido do STATUS de 2026-09-25).
 */
export function AppLayout() {
  return (
    <SeverityFilterProvider>
      <div className="grid h-full grid-cols-[3.5rem_minmax(0,1fr)] grid-rows-[3rem_minmax(0,1fr)] lg:grid-cols-[13rem_minmax(0,1fr)]">
        <Topbar />
        <Sidebar />
        <main className="overflow-y-auto">
          <Outlet />
        </main>
      </div>
    </SeverityFilterProvider>
  )
}
