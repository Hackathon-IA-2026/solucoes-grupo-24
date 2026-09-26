import { CircleHelp, RotateCw } from 'lucide-react'
import { useLocation } from 'react-router-dom'
import { MODULES } from '../modules'
import { GRUPO_CONTRATO } from './modulos'
import { useOraculo } from './estado'
import { abrirAjuda } from './Ajuda'

const TEXTO_MODO: Record<string, string> = { live: 'dados ao vivo', cache: 'cache local', demo: 'demonstrativo' }
const COR_MODO: Record<string, string> = {
  live: 'border-risk-low/40 bg-risk-low/10 text-risk-low',
  cache: 'border-accent/40 bg-accent/10 text-accent',
  demo: 'border-risk-medium/40 bg-risk-medium/10 text-risk-medium',
}

/**
 * Controles da topbar das telas do protótipo (a barra superior de 02-PROTOTIPO/web/js/app.js):
 * origem dos dados do serviço (ao vivo / cache / demonstrativo), seletor de área (subsistema),
 * ajuda F1 e recarregar. O seletor de área só aparece nas telas do protótipo; ajuda e modo
 * ficam sempre visíveis.
 */
export function OraculoBarra() {
  const { meta, health, erro, area, setArea, recarregar } = useOraculo()
  const { pathname } = useLocation()
  const modulo = MODULES.find((m) => pathname === m.path || pathname.startsWith(m.path + '/'))
  const doPrototipo = modulo ? modulo.grupo !== GRUPO_CONTRATO : false
  const modo = erro ? 'erro' : health?.mode || '…'
  const areas = meta?.areas || [{ id: 'SIN', name: 'SIN' }]

  return (
    <div className="flex items-center gap-2">
      <span
        title={erro ? `${erro.message} ${erro.hint}` : 'Origem dos dados das telas do protótipo'}
        className={`hidden items-center gap-1.5 rounded-sm border px-2 py-0.5 font-mono text-[10px] font-bold tracking-wider uppercase whitespace-nowrap md:inline-flex ${
          erro ? 'border-risk-critical/40 bg-risk-critical/10 text-risk-critical' : COR_MODO[modo] || 'border-line text-ink-muted'
        }`}
      >
        <span className="size-1.5 rounded-full bg-current" aria-hidden />
        {erro ? 'serviço indisponível' : TEXTO_MODO[modo] || modo}
      </span>
      {modo === 'demo' && (
        <span className="hidden rounded-sm border border-risk-medium/40 bg-risk-medium/10 px-2 py-0.5 font-mono text-[10px] font-bold tracking-wider text-risk-medium uppercase xl:inline">
          {meta?.demo_banner || 'DADOS DEMONSTRATIVOS'}
        </span>
      )}
      {doPrototipo && (
        <label className="flex items-center gap-1.5">
          <span className="rotulo hidden text-[10px] lg:inline">Área</span>
          <select
            value={area}
            onChange={(e) => setArea(e.target.value)}
            className="rounded-sm border border-line bg-fundo px-1.5 py-1 text-xs text-ink"
          >
            {areas.map((a) => (
              <option key={a.id} value={a.id}>
                {a.id} — {a.name}
              </option>
            ))}
          </select>
        </label>
      )}
      <button
        type="button"
        onClick={abrirAjuda}
        title="Documentação deste painel (F1)"
        className="grid size-7 place-items-center rounded-sm border border-line text-ink-muted hover:border-accent hover:text-accent"
      >
        <CircleHelp className="size-4" aria-hidden />
        <span className="sr-only">Ajuda (F1)</span>
      </button>
      <button
        type="button"
        onClick={() => void recarregar()}
        title="Recarregar do serviço"
        className="grid size-7 place-items-center rounded-sm border border-line text-ink-muted hover:border-accent hover:text-accent"
      >
        <RotateCw className="size-4" aria-hidden />
        <span className="sr-only">Recarregar</span>
      </button>
    </div>
  )
}
