/**
 * Peças de interface das telas do protótipo (os utilitários `U.*` de 02-PROTOTIPO/web/js/app.js
 * em JSX): Kpi, OCard, BarRow, StatLines, Proveniencia, ErroBloco, Carregando, ReasonTag,
 * <Grafico> (hospeda os gráficos SVG de ./charts.ts), <Pagina> (raiz .oraculo) e o hook useApi.
 * Classes CSS: ./oraculo.css (escopadas em .oraculo).
 */
import { useEffect, useLayoutEffect, useRef, useState, type DependencyList, type ReactNode } from 'react'
import { ApiError, type Envelope } from './api'
import { hideTip } from './charts'
import { bytes, esc, num, when } from './format'
import { useOraculo } from './estado'

// ------------------------------------------------------------------ dados
export type EstadoApi<T> =
  | { status: 'carregando'; dado: null; erro: null }
  | { status: 'ok'; dado: T; erro: null }
  | { status: 'erro'; dado: null; erro: ApiError }

/**
 * Executa `carregar` quando as dependências (ou o "recarregar" global) mudam. Ignora a
 * resposta de uma leitura antiga que chega depois de uma nova (troca rápida de área).
 */
export function useApi<T>(carregar: () => Promise<T>, deps: DependencyList): EstadoApi<T> & { recarregar: () => void } {
  const { versao } = useOraculo()
  const [local, setLocal] = useState(0)
  const [estado, setEstado] = useState<EstadoApi<T>>({ status: 'carregando', dado: null, erro: null })
  useEffect(() => {
    let vivo = true
    setEstado({ status: 'carregando', dado: null, erro: null })
    carregar()
      .then((d) => vivo && setEstado({ status: 'ok', dado: d, erro: null }))
      .catch((e: unknown) => {
        if (!vivo) return
        const erro = e instanceof ApiError ? e : new ApiError('INTERNAL', e instanceof Error ? e.message : String(e))
        if (!(e instanceof ApiError)) console.error(e)
        setEstado({ status: 'erro', dado: null, erro })
      })
    return () => {
      vivo = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, versao, local])
  return { ...estado, recarregar: () => setLocal((v) => v + 1) }
}

// ------------------------------------------------------------------ moldura
/** Raiz de toda tela do protótipo: aplica o escopo de estilo e esconde o tooltip ao sair. */
export function Pagina({ children }: { children: ReactNode }) {
  useEffect(() => () => hideTip(), [])
  return <div className="oraculo">{children}</div>
}

/**
 * Renderiza conforme o estado de useApi: spinner, bloco de erro ou o conteúdo.
 * `texto` = mensagem de carregamento da tela (loadingText do protótipo).
 */
export function Conteudo<T>({ estado, texto, children }: { estado: EstadoApi<T>; texto?: string; children: (dado: T) => ReactNode }) {
  if (estado.status === 'carregando') return <Carregando texto={texto} />
  if (estado.status === 'erro') return <ErroBloco erro={estado.erro} />
  return <>{children(estado.dado)}</>
}

export function Carregando({ texto }: { texto?: string }) {
  return (
    <div className="loading">
      <div className="spinner" />
      {texto || 'Carregando dados do Portal do ONS…'}
    </div>
  )
}

export function ErroBloco({ erro }: { erro: { code?: string; message: string; hint?: string } }) {
  return (
    <div className="error">
      <h4>{erro.code || 'ERRO'}</h4>
      <div>{erro.message}</div>
      {erro.hint ? <div className="hint">{erro.hint}</div> : null}
    </div>
  )
}

export function Vazio({ children = 'Sem dados.' }: { children?: ReactNode }) {
  return <div className="empty">{children}</div>
}

// ------------------------------------------------------------------ blocos
export type Accent = 'teal' | 'green' | 'amber' | 'crimson' | undefined

export function Kpi({ label, value, unit, foot, accent }: { label: ReactNode; value: ReactNode; unit?: string; foot?: ReactNode; accent?: Accent | string }) {
  return (
    <div className="card">
      <div className={'okpi' + (accent ? ' accent-' + accent : '')}>
        <div className="okpi-label">{label}</div>
        <div className="okpi-value">
          {value}
          {unit ? <span className="unit">{unit}</span> : null}
        </div>
        {foot ? <div className="okpi-foot">{foot}</div> : null}
      </div>
    </div>
  )
}

export function OCard({
  title,
  hint,
  note,
  flush,
  className,
  children,
}: {
  title?: ReactNode
  hint?: ReactNode
  note?: ReactNode
  flush?: boolean
  className?: string
  children?: ReactNode
}) {
  return (
    <div className={'card' + (flush ? ' flush' : '') + (className ? ' ' + className : '')}>
      {title ? (
        <div className="card-head">
          <h3>{title}</h3>
          {hint ? <span className="hint">{hint}</span> : null}
        </div>
      ) : null}
      {children}
      {note ? <div className="card-note">{note}</div> : null}
    </div>
  )
}

export function BarRow({ label, frac, value, color }: { label: ReactNode; frac: number | null | undefined; value: ReactNode; color?: string }) {
  const f = Math.max(0, Math.min(1, frac || 0))
  return (
    <div className="bar-row">
      <span>{label}</span>
      <span className="bar-track">
        <span className="bar-fill" style={{ width: (f * 100).toFixed(1) + '%', background: color ? `var(--o-${color}, ${color})` : 'var(--o-teal)' }} />
      </span>
      <span className="v">{value}</span>
    </div>
  )
}

export function StatLines({ pares }: { pares: [ReactNode, ReactNode][] }) {
  return (
    <>
      {pares.map(([k, v], i) => (
        <div className="stat-line" key={i}>
          <span className="k">{k}</span>
          <span className="v">{v}</span>
        </div>
      ))}
    </>
  )
}

export function modeClass(mode: string | undefined): string {
  return mode === 'live' ? 'green' : mode === 'cache' ? 'teal' : 'amber'
}

export function ReasonTag({ code }: { code: string | null | undefined }) {
  const c = String(code || '').toLowerCase()
  return <span className={'tag tag-' + (['ene', 'cnf', 'rel', 'par'].includes(c) ? c : 'par')}>{code || '—'}</span>
}

export function Chip({ on, cor, onClick, title, children }: { on?: boolean; cor?: string; onClick?: () => void; title?: string; children: ReactNode }) {
  return (
    <span
      className={'chip' + (on ? ' on' : '') + (cor ? ' ' + cor : '') + (onClick ? ' clickable' : '')}
      onClick={onClick}
      title={title}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      onKeyDown={onClick ? (e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), onClick()) : undefined}
    >
      {children}
    </span>
  )
}

/** Bloco "Proveniência e notas" que acompanha toda tela (envelope da resposta). */
export function Proveniencia({ body }: { body: Pick<Envelope, 'provenance' | 'notes' | 'mode'> | null | undefined }) {
  const prov = body?.provenance || []
  const notes = body?.notes || []
  if (!prov.length && !notes.length) return null
  return (
    <details className="prov">
      <summary>Proveniência e notas ({prov.length})</summary>
      <div className="prov-body">
        {notes.length ? <div className={'note-strip' + (body?.mode === 'demo' ? ' warn' : '')}>{notes.join(' · ')}</div> : null}
        {prov.length ? (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Conjunto</th>
                  <th>Recurso</th>
                  <th>Modo</th>
                  <th className="num">Linhas</th>
                  <th className="num">Bytes</th>
                  <th>Extraído</th>
                  <th>Defasagem declarada</th>
                </tr>
              </thead>
              <tbody>
                {prov.map((p, i) => (
                  <tr key={i}>
                    <td>{p.dataset}</td>
                    <td>{p.resource}</td>
                    <td>
                      <span className={'chip ' + modeClass(p.mode)}>{p.mode}</span>
                    </td>
                    <td className="num">{num(p.rows)}</td>
                    <td className="num">{bytes(p.bytes_read)}</td>
                    <td>{when(p.fetched_at)}</td>
                    <td className="small muted">{p.lag_note || ''}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </div>
    </details>
  )
}

/**
 * Hospeda um gráfico imperativo de ./charts.ts. `desenhar` recebe o elemento e desenha; roda
 * de novo quando `deps` mudam ou quando a largura do hospedeiro muda (os gráficos medem a
 * largura para montar o viewBox, como no protótipo).
 */
export function Grafico({ desenhar, deps = [], className, style }: { desenhar: (host: HTMLElement) => void; deps?: DependencyList; className?: string; style?: React.CSSProperties }) {
  const ref = useRef<HTMLDivElement>(null)
  const fn = useRef(desenhar)
  fn.current = desenhar
  useLayoutEffect(() => {
    const host = ref.current
    if (!host) return
    fn.current(host)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)
  useEffect(() => {
    const host = ref.current
    if (!host || typeof ResizeObserver === 'undefined') return
    let largura = host.clientWidth
    let t: ReturnType<typeof setTimeout> | undefined
    const ro = new ResizeObserver(() => {
      if (Math.abs(host.clientWidth - largura) < 2) return
      largura = host.clientWidth
      clearTimeout(t)
      t = setTimeout(() => fn.current(host), 160)
    })
    ro.observe(host)
    return () => {
      clearTimeout(t)
      ro.disconnect()
    }
  }, [])
  return <div ref={ref} className={className} style={style} />
}

/** HTML confiável gerado pelo próprio front (ex.: trechos portados que montam markup). */
export function Html({ html, className, tag = 'div' }: { html: string; className?: string; tag?: 'div' | 'span' }) {
  const Tag = tag
  return <Tag className={className} dangerouslySetInnerHTML={{ __html: html }} />
}

export { esc }
