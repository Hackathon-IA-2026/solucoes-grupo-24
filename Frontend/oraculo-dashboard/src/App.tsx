import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { MODULES } from './modules'
import { OraculoCasca } from './oraculo/Casca'
import NotFound from './pages/NotFound'

/**
 * Rotas geradas do registro de módulos, dentro da casca do protótipo O.R.A.C.U.L.O.
 * (sidebar + topbar do desenho original). "/" abre o primeiro módulo (Despacho preditivo).
 */
export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<OraculoCasca />}>
          <Route index element={<Navigate to={MODULES[0].path} replace />} />
          {MODULES.map((m) => (
            <Route key={m.path} path={m.routePattern ?? m.path} element={<m.Page />} />
          ))}
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
