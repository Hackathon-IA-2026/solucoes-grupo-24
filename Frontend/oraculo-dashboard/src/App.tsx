import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AppLayout } from './components/layout/AppLayout'
import { ModuleFrame } from './components/layout/ModuleFrame'
import { MODULES } from './modules'
import NotFound from './pages/NotFound'

/** Rotas geradas do registro de módulos; "/" abre o primeiro módulo (Visão Geral). */
export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppLayout />}>
          <Route index element={<Navigate to={MODULES[0].path} replace />} />
          {MODULES.map((m) => (
            <Route key={m.path} path={m.routePattern ?? m.path} element={<ModuleFrame module={m} />} />
          ))}
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
