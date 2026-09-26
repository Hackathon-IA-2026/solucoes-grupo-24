/**
 * Ajuda contextual (tecla F1): abre, sem sair da tela, a página da documentação da tela corrente.
 *
 * Decisão (2026-09-26): antes, o quadro mostrava num iframe a documentação Sphinx gerada por
 * script Python e servida pelo backend (/api/docs/status + /docs). Sem o build ou sem o backend,
 * a ajuda ficava vazia. Agora o conteúdo é código do frontend (./documentacao/): funciona sempre,
 * acompanha as telas React e pode ser exportado (Markdown, HTML, impressão/PDF).
 *
 * Este arquivo só cuida do atalho, do bloqueio de rolagem e do foco; o quadro em si
 * (./documentacao/QuadroAjuda.tsx, com o texto das 31 páginas) é carregado sob demanda na
 * primeira vez que a ajuda abre, para não pesar no carregamento inicial do dashboard.
 *
 * Painel → página: o campo `ajuda` do módulo (src/modules.ts) é o id da página.
 * F1 abre e fecha; Esc fecha; o botão "?" da topbar chama abrirAjuda().
 */
import { Suspense, lazy, useCallback, useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'

const QuadroAjuda = lazy(() => import('./documentacao/QuadroAjuda'))

const EVENTO = 'oraculo:ajuda'
export const abrirAjuda = () => window.dispatchEvent(new Event(EVENTO))

export function AjudaF1() {
  // null = fechada; senão, a URL em que a ajuda foi aberta. A URL vem do navegador, não do
  // `pathname` do React: o React Router navega em transição e, enquanto a tela nova (lazy)
  // carrega, o `pathname` do React ainda é o da tela anterior — F1 logo após navegar abriria a
  // página errada (achado na verificação no navegador).
  const [rota, setRota] = useState<string | null>(null)
  const ultimoFoco = useRef<Element | null>(null)
  const aberta = rota !== null

  const fechar = useCallback(() => setRota(null), [])
  const alternar = useCallback(() => {
    if (!aberta) ultimoFoco.current = document.activeElement
    setRota(aberta ? null : window.location.pathname)
  }, [aberta])

  useEffect(() => {
    const onKey = (ev: KeyboardEvent) => {
      // preventDefault no F1: sem ele o navegador abre a própria ajuda numa aba nova
      if (ev.key === 'F1') {
        ev.preventDefault()
        alternar()
      } else if (ev.key === 'Escape') fechar()
    }
    window.addEventListener('keydown', onKey)
    window.addEventListener(EVENTO, alternar)
    return () => {
      window.removeEventListener('keydown', onKey)
      window.removeEventListener(EVENTO, alternar)
    }
  }, [alternar, fechar])

  // rolagem da página travada enquanto a ajuda está aberta; ao fechar, o foco volta para onde estava
  useEffect(() => {
    if (aberta) document.body.classList.add('help-locked')
    else {
      document.body.classList.remove('help-locked')
      const f = ultimoFoco.current as HTMLElement | null
      f?.focus?.()
    }
  }, [aberta])

  if (!aberta) return null
  return createPortal(
    <div className="oraculo">
      <Suspense
        fallback={
          <div className="help-overlay">
            <div className="help-panel help-carregando">Carregando a documentação…</div>
          </div>
        }
      >
        <QuadroAjuda rotaInicial={rota} fechar={fechar} />
      </Suspense>
    </div>,
    document.body,
  )
}
