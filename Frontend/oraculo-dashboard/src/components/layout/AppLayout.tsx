import { Outlet } from 'react-router-dom'
import { SeverityFilterProvider } from '../../state/severityFilter'
import { Sidebar } from './Sidebar'
import { Topbar } from './Topbar'

/** Casca do app: sidebar fixa (w-64) + topbar + área de conteúdo da rota atual. */
export function AppLayout() {
  return (
    <SeverityFilterProvider>
      <Sidebar />
      {/* ml-64 casa com a largura da sidebar fixa */}
      <div className="ml-64 flex min-h-full flex-col">
        <Topbar />
        <main className="flex-1 p-6">
          <Outlet />
        </main>
      </div>
    </SeverityFilterProvider>
  )
}
