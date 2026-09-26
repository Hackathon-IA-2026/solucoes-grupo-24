/**
 * Ajuda contextual (tecla F1): abre, sem sair da tela, a página da documentação Sphinx do
 * painel corrente. Porte da ajuda de 02-PROTOTIPO/web/js/app.js.
 *
 * O mapeamento painel -> página vem do SERVIDOR (/api/docs/status), não daqui: um único lugar a
 * corrigir quando uma página é renomeada. Telas sem página própria (dashboard do contrato)
 * abrem a capa da documentação. F1 abre e fecha; Esc fecha.
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { useLocation } from 'react-router-dom'
import { MODULES } from '../modules'
import { get } from './api'

interface DocsInfo {
  disponivel?: boolean
  construida?: boolean
  prefixo?: string
  paineis?: Record<string, string>
  geral?: Record<string, string>
  paginas_faltando?: unknown[]
  diretorio?: string
  como_construir?: string
  nota?: string
}

const EVENTO = 'oraculo:ajuda'
export const abrirAjuda = () => window.dispatchEvent(new Event(EVENTO))

const ATALHOS: [string, string][] = [
  ['como_ler', 'Como ler os painéis'],
  ['proveniencia', 'Proveniência'],
  ['limitacoes', 'Limitações'],
  ['glossario', 'Glossário'],
  ['api', 'API'],
  ['referencia', 'Código'],
]

let INFO: DocsInfo | null = null
async function carregarInfo(): Promise<DocsInfo> {
  if (INFO) return INFO
  try {
    INFO = (await get<DocsInfo>('docs/status')).data
  } catch {
    INFO = { disponivel: false, construida: false, prefixo: '/docs', paineis: {}, geral: {}, nota: 'Não foi possível consultar o estado da documentação.' }
  }
  return INFO
}

export function AjudaF1() {
  const { pathname } = useLocation()
  const [aberta, setAberta] = useState(false)
  const [info, setInfo] = useState<DocsInfo | null>(null)
  const [destino, setDestino] = useState<string | null>(null)
  const ultimoFoco = useRef<Element | null>(null)
  const fechar = useRef<HTMLButtonElement>(null)

  const modulo = MODULES.find((m) => pathname === m.path || pathname.startsWith(m.path + '/'))
  const pref = String(info?.prefixo || '/docs').replace(/\/$/, '')
  const rel = (modulo?.ajuda && info?.paineis?.[modulo.ajuda]) || info?.geral?.inicio || 'index.html'
  const url = destino || pref + '/' + rel

  const alternar = useCallback(() => {
    setAberta((a) => {
      if (!a) {
        ultimoFoco.current = document.activeElement
        setDestino(null)
      }
      return !a
    })
  }, [])

  useEffect(() => {
    void carregarInfo().then(setInfo) // aquece o mapeamento, sem bloquear a primeira tela
    const onKey = (ev: KeyboardEvent) => {
      // preventDefault no F1: sem ele o navegador abre a própria ajuda numa aba nova
      if (ev.key === 'F1') {
        ev.preventDefault()
        alternar()
      } else if (ev.key === 'Escape') setAberta(false)
    }
    window.addEventListener('keydown', onKey)
    window.addEventListener(EVENTO, alternar)
    return () => {
      window.removeEventListener('keydown', onKey)
      window.removeEventListener(EVENTO, alternar)
    }
  }, [alternar])

  useEffect(() => {
    if (aberta) {
      document.body.classList.add('help-locked')
      fechar.current?.focus()
    } else {
      document.body.classList.remove('help-locked')
      const f = ultimoFoco.current as HTMLElement | null
      f?.focus?.()
    }
  }, [aberta])

  if (!aberta) return null
  const geral = info?.geral || {}
  const faltando = info?.paginas_faltando || []

  return createPortal(
    <div className="oraculo">
      <div className="help-overlay" role="dialog" aria-modal="true" aria-label="Documentação do painel" onClick={(e) => e.target === e.currentTarget && setAberta(false)}>
        <div className="help-panel">
          <div className="help-head">
            <div className="help-title">
              <strong>Documentação</strong>
              <span className="help-ctx">{modulo?.label || 'O.R.A.C.U.L.O.'}</span>
            </div>
            <div className="help-actions">
              {ATALHOS.filter(([k]) => geral[k]).map(([k, rotulo]) => (
                <button key={k} className="ghost small" onClick={() => setDestino(pref + '/' + geral[k])}>
                  {rotulo}
                </button>
              ))}
              <a className="ghost small" href={url} target="_blank" rel="noopener" title="Abrir em nova aba">
                &#8599;
              </a>
              <button ref={fechar} className="ghost small" title="Fechar (Esc)" onClick={() => setAberta(false)}>
                &#10005;
              </button>
            </div>
          </div>
          {info?.construida ? (
            <iframe src={url} title="Documentação" />
          ) : (
            <div className="help-missing">
              <h3>Documentação ainda não construída</h3>
              <p>{info?.nota || ''}</p>
              <p>
                <code>{info?.como_construir || 'cd docs/oraculo/documentacao_sphinx && python build_docs.py'}</code>
              </p>
              {info?.diretorio && (
                <p className="small muted">
                  Diretório esperado: <code>{info.diretorio}</code>
                </p>
              )}
            </div>
          )}
          <div className="help-foot">
            <span>
              <kbd>F1</kbd> abre e fecha · <kbd>Esc</kbd> fecha
            </span>
            {faltando.length > 0 && <span className="chip crimson">{faltando.length} página(s) de painel ausente(s)</span>}
          </div>
        </div>
      </div>
    </div>,
    document.body,
  )
}
