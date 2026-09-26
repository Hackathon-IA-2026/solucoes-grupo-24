/**
 * O quadro da ajuda F1: índice com busca, a página, a navegação e o menu Exportar.
 *
 * Fica num arquivo próprio, carregado sob demanda por ../Ajuda.tsx (React.lazy): o texto das
 * páginas e o renderizador só descem para o navegador quando alguém aperta F1, e não pesam no
 * carregamento inicial do dashboard. Cada abertura monta o quadro de novo, então a busca e a
 * página voltam ao estado inicial sem código de "reset".
 */
import { useEffect, useMemo, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { moduloDaRota } from '../../modules'
import { CSS_DOC } from './estilo'
import { baixarHtml, baixarMarkdown, imprimir } from './exportar'
import { ID_INICIO, PAGINAS, buscar, paginaDoModulo, paginaPorId, paginasPorGrupo, telasDaPagina } from './indice'
import type { PaginaDoc } from './modelo'
import { PaginaRender } from './Renderizador'

/** Atalhos fixos da barra do quadro: as páginas de contexto geral. */
const ATALHOS: [string, string][] = [
  [ID_INICIO, 'Início'],
  ['como-ler', 'Como ler'],
  ['limitacoes', 'Limitações'],
  ['glossario', 'Glossário'],
]

/** Os três formatos do menu Exportar, na ordem em que aparecem. */
const FORMATOS: [string, (pgs: readonly PaginaDoc[]) => void | Promise<void>][] = [
  ['Markdown (.md)', baixarMarkdown],
  ['HTML (.html)', baixarHtml],
  ['Imprimir / PDF', imprimir],
]

/**
 * `rotaInicial` é a URL do navegador no instante em que F1 foi pressionado (ver ../Ajuda.tsx):
 * o quadro abre na página daquela tela.
 */
export default function QuadroAjuda({ rotaInicial, fechar }: { rotaInicial: string; fechar: () => void }) {
  const { pathname } = useLocation()
  const navigate = useNavigate()
  const [id, setId] = useState(() => paginaDoModulo(moduloDaRota(rotaInicial)).id)
  const [busca, setBusca] = useState('')
  const botaoFechar = useRef<HTMLButtonElement>(null)
  const artigo = useRef<HTMLDivElement>(null)
  const menuExportar = useRef<HTMLDetailsElement>(null)

  // a tela corrente, para "← esta tela" e o destaque no índice (segue a navegação)
  const modulo = moduloDaRota(pathname)
  const paginaDaTela = paginaDoModulo(modulo)
  const pagina: PaginaDoc = paginaPorId(id) ?? paginaDaTela
  const resultados = useMemo(() => buscar(busca), [busca])
  const posicao = PAGINAS.indexOf(pagina)
  const telas = telasDaPagina(pagina.id)

  // foco no botão de fechar ao abrir (Esc ou Enter fecham pelo teclado)
  useEffect(() => {
    botaoFechar.current?.focus()
  }, [])

  // página nova começa do topo
  useEffect(() => {
    artigo.current?.scrollTo({ top: 0 })
  }, [id])

  /** Roda uma exportação e fecha o menu (o <details> não fecha sozinho). */
  const exportar = (fn: (pgs: readonly PaginaDoc[]) => void | Promise<void>, pgs: readonly PaginaDoc[]) => {
    if (menuExportar.current) menuExportar.current.open = false
    void fn(pgs)
  }

  return (
    <>
      <style>{CSS_DOC}</style>
      <div className="help-overlay" role="dialog" aria-modal="true" aria-label="Documentação" onClick={(e) => e.target === e.currentTarget && fechar()}>
        <div className="help-panel">
          <div className="help-head">
            <div className="help-title">
              <strong>Documentação</strong>
              <span className="help-ctx">{modulo?.label || 'O.R.A.C.U.L.O.'}</span>
            </div>
            <div className="help-actions">
              {pagina.id !== paginaDaTela.id && (
                <button className="ghost small" onClick={() => setId(paginaDaTela.id)} title="Voltar à página da tela aberta">
                  ← esta tela
                </button>
              )}
              {ATALHOS.map(([alvo, rotulo]) => (
                <button key={alvo} className={'ghost small' + (pagina.id === alvo ? ' on' : '')} onClick={() => setId(alvo)}>
                  {rotulo}
                </button>
              ))}
              <details className="help-exportar" ref={menuExportar}>
                <summary className="ghost small">Exportar ▾</summary>
                <div className="help-menu" role="menu">
                  {(
                    [
                      ['Esta página', [pagina]],
                      [`Documentação completa (${PAGINAS.length} páginas)`, PAGINAS],
                    ] as const
                  ).map(([titulo, pgs]) => (
                    <div key={titulo}>
                      <div className="help-menu-tit">{titulo}</div>
                      {FORMATOS.map(([rotulo, fn]) => (
                        <button key={rotulo} role="menuitem" onClick={() => exportar(fn, pgs)}>
                          {rotulo}
                        </button>
                      ))}
                    </div>
                  ))}
                </div>
              </details>
              <button ref={botaoFechar} className="ghost small" title="Fechar (Esc)" onClick={fechar}>
                &#10005;
              </button>
            </div>
          </div>

          <div className="help-body">
            <nav className="help-nav" aria-label="Índice da documentação">
              <input
                type="search"
                className="help-busca"
                placeholder="Buscar na documentação…"
                value={busca}
                onChange={(e) => setBusca(e.target.value)}
                aria-label="Buscar na documentação"
              />
              {busca && (
                <div className="help-nav-conta">
                  {resultados.length} página{resultados.length === 1 ? '' : 's'}
                </div>
              )}
              {paginasPorGrupo(resultados).map(([grupo, pgs]) => (
                <div key={grupo} className="help-nav-grupo">
                  <div className="help-nav-tit">{grupo}</div>
                  {pgs.map((pg) => (
                    <button
                      key={pg.id}
                      className={'help-nav-item' + (pg.id === pagina.id ? ' on' : '') + (pg.id === paginaDaTela.id ? ' atual' : '')}
                      onClick={() => setId(pg.id)}
                      title={pg.resumo}
                    >
                      {pg.titulo}
                    </button>
                  ))}
                </div>
              ))}
              {busca && !resultados.length && <div className="help-nav-conta">Nada encontrado.</div>}
            </nav>

            <div className="help-doc" ref={artigo}>
              <PaginaRender
                pagina={pagina}
                onLink={setId}
                telas={
                  telas.length > 0 ? (
                    <div className="doc-telas">
                      {telas.map((m) =>
                        m === modulo ? (
                          <span key={m.path} className="chip teal">
                            você está nesta tela
                          </span>
                        ) : (
                          <button
                            key={m.path}
                            className="ghost small"
                            onClick={() => {
                              navigate(m.path)
                              fechar()
                            }}
                          >
                            Abrir a tela {m.label} →
                          </button>
                        ),
                      )}
                    </div>
                  ) : undefined
                }
              />
              <div className="help-paginacao">
                {posicao > 0 ? (
                  <button className="ghost small" onClick={() => setId(PAGINAS[posicao - 1].id)}>
                    ← {PAGINAS[posicao - 1].titulo}
                  </button>
                ) : (
                  <span />
                )}
                {posicao < PAGINAS.length - 1 && (
                  <button className="ghost small" onClick={() => setId(PAGINAS[posicao + 1].id)}>
                    {PAGINAS[posicao + 1].titulo} →
                  </button>
                )}
              </div>
            </div>
          </div>

          <div className="help-foot">
            <span>
              <kbd>F1</kbd> abre e fecha · <kbd>Esc</kbd> fecha
            </span>
            <span>
              {posicao + 1} / {PAGINAS.length}
            </span>
          </div>
        </div>
      </div>
    </>
  )
}
