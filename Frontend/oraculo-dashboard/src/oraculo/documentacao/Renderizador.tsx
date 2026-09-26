/**
 * Renderizador ÚNICO das páginas da documentação (modelo.ts → React).
 *
 * Dois modos, o mesmo componente:
 * - interativo (ajuda F1): link interno é um botão que troca a página dentro do quadro;
 * - estático (`estatico`): link interno vira âncora `#doc-<id>`; é o que exportar.ts passa ao
 *   renderToStaticMarkup para gerar o HTML autocontido e a impressão. Assim a tela e o arquivo
 *   exportado nunca divergem de formatação.
 */
import type { ReactNode } from 'react'
import { paginaPorId } from './indice'
import { ROTULO_TOM, ancora, interpretarInline, type Bloco, type PaginaDoc } from './modelo'

interface Contexto {
  estatico?: boolean
  onLink?: (id: string) => void
}

function Inline({ texto, ctx }: { texto: string; ctx: Contexto }) {
  return (
    <>
      {interpretarInline(texto).map((t, i) => {
        switch (t.k) {
          case 'texto':
            return t.v
          case 'negrito':
            return <strong key={i}>{t.v}</strong>
          case 'italico':
            return <em key={i}>{t.v}</em>
          case 'codigo':
            return <code key={i}>{t.v}</code>
          case 'externo':
            return (
              <a key={i} href={t.href} target="_blank" rel="noopener noreferrer">
                {t.v}
              </a>
            )
          case 'interno': {
            // sem texto próprio, o link mostra o título da página de destino
            const rotulo = t.v || paginaPorId(t.alvo)?.titulo || t.alvo
            return ctx.estatico ? (
              <a key={i} href={'#' + ancora(t.alvo)}>
                {rotulo}
              </a>
            ) : (
              <button key={i} type="button" className="doc-link" onClick={() => ctx.onLink?.(t.alvo)}>
                {rotulo}
              </button>
            )
          }
        }
      })}
    </>
  )
}

function BlocoDoc({ b, ctx }: { b: Bloco; ctx: Contexto }): ReactNode {
  switch (b.t) {
    case 'p':
      return (
        <p>
          <Inline texto={b.texto} ctx={ctx} />
        </p>
      )
    case 'sub':
      return <h3>{b.titulo}</h3>
    case 'formula':
      return <pre className="formula">{b.texto}</pre>
    case 'codigo':
      return <pre>{b.texto}</pre>
    case 'lista': {
      const itens = b.itens.map((it, i) => (
        <li key={i}>
          <Inline texto={it} ctx={ctx} />
        </li>
      ))
      return b.ordenada ? <ol>{itens}</ol> : <ul>{itens}</ul>
    }
    case 'tabela':
      return (
        <div className="doc-tabela">
          <table>
            <thead>
              <tr>
                {b.cab.map((c, i) => (
                  <th key={i}>
                    <Inline texto={c} ctx={ctx} />
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {b.linhas.map((l, i) => (
                <tr key={i}>
                  {l.map((c, j) => (
                    <td key={j}>
                      <Inline texto={c} ctx={ctx} />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )
    case 'aviso':
      return (
        <div className={'aviso ' + b.tom}>
          <div className="aviso-tit">
            <span>{ROTULO_TOM[b.tom]}</span>
            <Inline texto={b.titulo} ctx={ctx} />
          </div>
          {b.blocos.map((x, i) => (
            <BlocoDoc key={i} b={x} ctx={ctx} />
          ))}
        </div>
      )
  }
}

/**
 * Uma página completa. `telas` é o espaço, logo abaixo do resumo, para os atalhos às telas
 * documentadas (na ajuda, botões que navegam; no arquivo exportado, só os nomes).
 */
export function PaginaRender({ pagina, estatico, onLink, telas }: { pagina: PaginaDoc; telas?: ReactNode } & Contexto) {
  const ctx: Contexto = { estatico, onLink }
  return (
    <article className="doc" id={estatico ? ancora(pagina.id) : undefined}>
      <div className="doc-meta">{pagina.grupo}</div>
      <h1>{pagina.titulo}</h1>
      <p className="doc-resumo">
        <Inline texto={pagina.resumo} ctx={ctx} />
      </p>
      {telas}
      {pagina.pergunta && (
        <div className="doc-pergunta">
          <b>Pergunta que a tela responde</b>
          <Inline texto={pagina.pergunta} ctx={ctx} />
        </div>
      )}
      {pagina.rotas && pagina.rotas.length > 0 && (
        <p className="doc-rotas">
          Rotas da API:{' '}
          {pagina.rotas.map((r) => (
            <code key={r}>{r}</code>
          ))}
        </p>
      )}
      {pagina.secoes.map((s, i) => (
        <section key={i}>
          <h2>{s.titulo}</h2>
          {s.blocos.map((b, j) => (
            <BlocoDoc key={j} b={b} ctx={ctx} />
          ))}
        </section>
      ))}
    </article>
  )
}
