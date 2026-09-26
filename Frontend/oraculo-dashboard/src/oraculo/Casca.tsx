/**
 * Casca da aplicação no desenho do protótipo O.R.A.C.U.L.O. (02-PROTOTIPO/web/index.html e
 * js/app.js): sidebar com marca, navegação por grupos e fontes técnicas; topbar com título e
 * subtítulo da tela, origem dos dados, área, tema claro/escuro, ajuda (F1) e recarregar.
 * Mesma marcação (#shell, #sidebar, .brand, nav, #top, #content) e mesmas classes, para o CSS
 * de ./oraculo.css valer igual ao original.
 *
 * As telas do dashboard do contrato entram como mais um grupo do menu; na topbar delas também
 * aparecem a origem da publicação (FonteDados) e os filtros de severidade, que só elas usam.
 */
import { Suspense } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { FonteDados } from '../components/layout/FonteDados'
import { SeverityFilters } from '../components/layout/SeverityFilters'
import { MODULES, moduloDaRota } from '../modules'
import { SeverityFilterProvider } from '../state/severityFilter'
import { AjudaF1, abrirAjuda } from './Ajuda'
import { OraculoProvider, useOraculo } from './estado'
import { GRUPO_CONTRATO } from './modulos'
import { Carregando } from './ui'

/** Traços dos ícones do protótipo (ICONS de app.js), 24×24, stroke 1.7. */
export const ICONES: Record<string, string> = {
  wave: 'M2 12c2.5 0 3-6 5.5-6S11 18 13.5 18 17 12 22 12',
  alert: 'M12 3 2 20h20L12 3Zm0 6v6m0 3v.5',
  cut: 'M4 20 20 4M8 6a2.5 2.5 0 1 1-3.5 3.5A2.5 2.5 0 0 1 8 6Zm12 10a2.5 2.5 0 1 1-3.5 3.5A2.5 2.5 0 0 1 20 16Z',
  layers: 'M12 3 3 8l9 5 9-5-9-5Zm-9 9 9 5 9-5m-18 4.5 9 5 9-5',
  target: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18Zm0 4.5a4.5 4.5 0 1 0 0 9 4.5 4.5 0 0 0 0-9Zm0 3.5a1 1 0 1 0 0 2 1 1 0 0 0 0-2Z',
  check: 'M4 12.5 9.5 18 20 6',
  db: 'M12 3c4.4 0 8 1.3 8 3s-3.6 3-8 3-8-1.3-8-3 3.6-3 8-3Zm8 6c0 1.7-3.6 3-8 3s-8-1.3-8-3m16 6c0 1.7-3.6 3-8 3s-8-1.3-8-3M4 6v12m16-12v12',
  pin: 'M12 21s7-6.4 7-11a7 7 0 1 0-14 0c0 4.6 7 11 7 11Zm0-8.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5Z',
  eye: 'M2 12s3.8-6.5 10-6.5S22 12 22 12s-3.8 6.5-10 6.5S2 12 2 12Zm10 2.8a2.8 2.8 0 1 0 0-5.6 2.8 2.8 0 0 0 0 5.6Z',
  pie: 'M12 3a9 9 0 1 0 9 9h-9V3Z',
  sun: 'M12 7.5a4.5 4.5 0 1 0 0 9 4.5 4.5 0 0 0 0-9ZM12 2v2.5M12 19.5V22M2 12h2.5M19.5 12H22M4.9 4.9l1.8 1.8M17.3 17.3l1.8 1.8M4.9 19.1l1.8-1.8M17.3 6.7l1.8-1.8',
  battery: 'M3 8h15v8H3zM18 11h2.5v2H18M6.5 10.5v3M9.5 10.5v3M12.5 10.5v3',
  link: 'M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1',
  sliders:
    'M4 7h10m4 0h2M4 12h3m4 0h13M4 17h8m4 0h4M14 7a2 2 0 1 0 4 0 2 2 0 0 0-4 0Zm-7 5a2 2 0 1 0 4 0 2 2 0 0 0-4 0Zm5 5a2 2 0 1 0 4 0 2 2 0 0 0-4 0Z',
}

/** Ícones, no vocabulário do protótipo, das telas do dashboard do contrato. */
const ICONE_CONTRATO: Record<string, string> = {
  '/visao-geral': 'pie',
  '/mapa-hibrido': 'pin',
  '/despacho-preditivo': 'wave',
  '/lista-riscos': 'alert',
  '/detalhe-alerta': 'alert',
  '/excedentes-tso-dso': 'link',
  '/validacao': 'check',
  '/metodologia': 'db',
}

function Icone({ nome }: { nome: string }) {
  return (
    <svg className="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d={ICONES[nome] || ''} />
    </svg>
  )
}

export function OraculoCasca() {
  return (
    <OraculoProvider>
      <SeverityFilterProvider>
        <AjudaF1 />
        <Estrutura />
      </SeverityFilterProvider>
    </OraculoProvider>
  )
}

function Estrutura() {
  const { tema } = useOraculo()
  const { pathname } = useLocation()
  return (
    <div id="shell">
      <aside id="sidebar">
        <div className="brand">
          <div className="brand-mark">
            O.R.A.C.U.L.<span>O.</span>
          </div>
          <div className="brand-sub">Observabilidade de Redes e Análise de Curtailment em Usinas e Limites Operacionais</div>
          <div className="brand-team">Equipe 24 — Linkfy</div>
        </div>
        <Navegacao />
        <div className="side-foot">
          Fontes técnicas
          <a href="https://dados.ons.org.br/" target="_blank" rel="noreferrer">
            Portal de Dados Abertos do ONS
          </a>
          <a href="https://www.ons.org.br/Paginas/energia-no-futuro/suprimento-eletrico/parpel2025/sumario-executivo/index.aspx" target="_blank" rel="noreferrer">
            PAR/PEL 2025 — Sumário Executivo
          </a>
          <a href="https://www.ons.org.br/Paginas/faq_curtailment.aspx" target="_blank" rel="noreferrer">
            FAQ Curtailment
          </a>
          <a href="/legado" target="_blank" rel="noreferrer">
            Interface original (HTML/JS)
          </a>
        </div>
      </aside>

      <div id="main">
        <Topo />
        {/* key = tema + rota: como o render() do protótipo ao trocar o tema, a tela é redesenhada
            e os gráficos SVG releem as cores da paleta nova. */}
        <main id="content" key={tema + pathname}>
          <Suspense
            fallback={
              <div className="oraculo">
                <Carregando texto="Carregando a tela…" />
              </div>
            }
          >
            <Outlet />
          </Suspense>
        </main>
      </div>
    </div>
  )
}

function Navegacao() {
  return (
    <nav id="nav">
      {MODULES.map((m, i) => (
        <div key={m.path} style={{ display: 'contents' }}>
          {m.grupo && m.grupo !== MODULES[i - 1]?.grupo && <div className="nav-group">{m.grupo}</div>}
          <NavLink to={m.path} className={({ isActive }) => (isActive ? 'active' : '')} title={m.description}>
            <Icone nome={m.icone || ICONE_CONTRATO[m.path] || 'layers'} />
            <span>{m.label}</span>
          </NavLink>
        </div>
      ))}
    </nav>
  )
}

const TEXTO_MODO: Record<string, string> = { live: 'dados ao vivo', cache: 'cache local', demo: 'demonstrativo' }

function Topo() {
  const { meta, health, erro, area, setArea, recarregar, tema, alternarTema } = useOraculo()
  const { pathname } = useLocation()
  const modulo = moduloDaRota(pathname)
  const doContrato = modulo?.grupo === GRUPO_CONTRATO
  const modo = erro ? 'demo' : health?.mode || 'demo'
  const areas = meta?.areas || [{ id: 'SIN', name: 'SIN' }]

  return (
    <header id="top">
      <div>
        <h1 id="view-title">{modulo ? modulo.titulo || modulo.label : 'Página não encontrada'}</h1>
        <div className="sub" id="view-sub">
          {modulo?.description || ''}
        </div>
      </div>
      <div className="spacer" />
      {doContrato && (
        <div className="dash-extra">
          <FonteDados />
          <SeverityFilters />
        </div>
      )}
      {erro ? (
        <span className="badge badge-demo" title={erro.message + (erro.hint ? ' — ' + erro.hint : '')}>
          <span className="badge-dot" />
          serviço indisponível
        </span>
      ) : (
        <span className={'badge badge-' + modo} title="Origem dos dados exibidos">
          <span className="badge-dot" />
          {TEXTO_MODO[modo] || modo}
        </span>
      )}
      {modo === 'demo' && !erro && <span className="badge badge-demo">{meta?.demo_banner || 'DADOS DEMONSTRATIVOS'}</span>}
      {!doContrato && (
        <div className="field">
          <label htmlFor="sel-area">Área</label>
          <select id="sel-area" value={area} onChange={(e) => setArea(e.target.value)}>
            {areas.map((a) => (
              <option key={a.id} value={a.id}>
                {a.id} — {a.name}
              </option>
            ))}
          </select>
        </div>
      )}
      <button id="btn-theme" className="ghost" title="Alternar tema" onClick={alternarTema}>
        {tema === 'dark' ? '☾' : '☀'}
      </button>
      <button id="btn-help" className="ghost" title="Documentação deste painel (F1)" onClick={abrirAjuda}>
        ?
      </button>
      <button id="btn-reload" className="ghost" title="Recarregar do serviço" onClick={() => void recarregar()}>
        ↻
      </button>
    </header>
  )
}
