/**
 * Exportação da documentação: Markdown, HTML autocontido e impressão (PDF pelo navegador).
 *
 * - Markdown: serializador próprio do modelo de blocos (função pura, testada em
 *   documentacao.test.ts). Avisos viram citações ("> "), fórmulas e diagramas viram blocos de
 *   código, links internos viram âncoras quando o arquivo tem mais de uma página.
 * - HTML e impressão: o MESMO Renderizador da tela, em modo estático, passado ao
 *   renderToStaticMarkup, com o CSS da documentação embutido (estilo.ts). O arquivo abre em
 *   qualquer navegador, sem servidor e sem rede. `react-dom/server` é importado sob demanda:
 *   só desce quando alguém exporta.
 * - Imprimir: o HTML vai para um iframe invisível e o diálogo de impressão do navegador abre
 *   (dali se salva em PDF), sem abrir aba nova.
 */
import { baixarArquivo, hojeIso } from '../../utils/download'
import { CSS_DOC, PALETA_IMPRESSAO } from './estilo'
import { PAGINAS, paginaPorId, paginasPorGrupo, telasDaPagina } from './indice'
import { ROTULO_TOM, ancora, interpretarInline, type Bloco, type PaginaDoc } from './modelo'
import { PaginaRender } from './Renderizador'

const TITULO_DOC = 'O.R.A.C.U.L.O. — Documentação'

// ------------------------------------------------------------------ Markdown

/** `|` quebraria a célula da tabela; quebra de linha também. */
const celulaMd = (s: string) => s.replace(/\|/g, '\\|').replace(/\n/g, ' ')

function inlineMd(texto: string, comAncoras: boolean): string {
  return interpretarInline(texto)
    .map((t) => {
      switch (t.k) {
        case 'texto':
          return t.v
        case 'negrito':
          return `**${t.v}**`
        case 'italico':
          return `*${t.v}*`
        case 'codigo':
          return '`' + t.v + '`'
        case 'externo':
          return `[${t.v}](${t.href})`
        case 'interno': {
          const rotulo = t.v || paginaPorId(t.alvo)?.titulo || t.alvo
          // num arquivo de página única o destino não está no arquivo: fica só o nome
          return comAncoras ? `[${rotulo}](#${ancora(t.alvo)})` : `*${rotulo}*`
        }
      }
    })
    .join('')
}

function blocoMd(b: Bloco, ancoras: boolean): string {
  switch (b.t) {
    case 'p':
      return inlineMd(b.texto, ancoras)
    case 'sub':
      return `#### ${b.titulo}`
    case 'formula':
    case 'codigo':
      return '```text\n' + b.texto + '\n```'
    case 'lista':
      return b.itens.map((it, i) => (b.ordenada ? `${i + 1}. ` : '- ') + inlineMd(it, ancoras)).join('\n')
    case 'tabela':
      return [
        '| ' + b.cab.map((c) => celulaMd(inlineMd(c, ancoras))).join(' | ') + ' |',
        '| ' + b.cab.map(() => '---').join(' | ') + ' |',
        ...b.linhas.map((l) => '| ' + l.map((c) => celulaMd(inlineMd(c, ancoras))).join(' | ') + ' |'),
      ].join('\n')
    case 'aviso': {
      const corpo = [`**${ROTULO_TOM[b.tom]} — ${inlineMd(b.titulo, ancoras)}**`, ...b.blocos.map((x) => blocoMd(x, ancoras))].join('\n\n')
      return corpo
        .split('\n')
        .map((l) => (l ? '> ' + l : '>'))
        .join('\n')
    }
  }
}

/** Uma página em Markdown. `nivel` é o nível do título da página (1 sozinha, 2 dentro do documento completo). */
export function paginaParaMarkdown(pg: PaginaDoc, { nivel = 1, ancoras = false } = {}): string {
  const h = (n: number) => '#'.repeat(Math.min(nivel + n, 6))
  const partes: string[] = []
  if (ancoras) partes.push(`<a id="${ancora(pg.id)}"></a>`)
  partes.push(`${h(0)} ${pg.titulo}`, `*${pg.grupo}* — ${inlineMd(pg.resumo, ancoras)}`)
  const telas = telasDaPagina(pg.id)
  if (telas.length) partes.push('Tela: ' + telas.map((m) => `**${m.label}** (\`${m.path}\`)`).join(', '))
  if (pg.pergunta) partes.push(`> **Pergunta que a tela responde:** ${inlineMd(pg.pergunta, ancoras)}`)
  if (pg.rotas?.length) partes.push('Rotas da API: ' + pg.rotas.map((r) => '`' + r + '`').join(' · '))
  for (const s of pg.secoes) {
    partes.push(`${h(1)} ${s.titulo}`)
    for (const b of s.blocos) partes.push(blocoMd(b, ancoras))
  }
  return partes.join('\n\n') + '\n'
}

/** A documentação inteira em um Markdown, com sumário e links internos por âncora. */
export function documentacaoParaMarkdown(paginas: readonly PaginaDoc[] = PAGINAS): string {
  const sumario = paginasPorGrupo(paginas)
    .map(([g, pgs]) => `**${g}**\n\n` + pgs.map((pg) => `- [${pg.titulo}](#${ancora(pg.id)})`).join('\n'))
    .join('\n\n')
  return [`# ${TITULO_DOC}`, `Gerado em ${hojeIso()} a partir do frontend (src/oraculo/documentacao).`, '## Sumário', sumario, ...paginas.map((pg) => paginaParaMarkdown(pg, { nivel: 2, ancoras: true }))].join(
    '\n\n',
  )
}

// ------------------------------------------------------------------ HTML e impressão

const escaparHtml = (s: string) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')

/** HTML autocontido (uma página ou a documentação completa, com sumário). */
export async function documentoHtml(paginas: readonly PaginaDoc[]): Promise<string> {
  const { renderToStaticMarkup } = await import('react-dom/server')
  const completo = paginas.length > 1
  const titulo = completo ? TITULO_DOC : `${paginas[0].titulo} — ${TITULO_DOC}`
  const corpo = renderToStaticMarkup(
    <main className="doc-export">
      {completo && (
        <header className="doc doc-capa">
          <h1>{TITULO_DOC}</h1>
          <p>Gerado em {hojeIso()} a partir da ajuda embutida no dashboard (tecla F1).</p>
          <nav className="doc-sumario">
            {paginasPorGrupo(paginas).map(([g, pgs]) => (
              <div key={g}>
                <h3>{g}</h3>
                {pgs.map((pg) => (
                  <a key={pg.id} href={'#' + ancora(pg.id)}>
                    {pg.titulo}
                  </a>
                ))}
              </div>
            ))}
          </nav>
        </header>
      )}
      {paginas.map((pg) => {
        const telas = telasDaPagina(pg.id)
        return (
          <PaginaRender
            key={pg.id}
            pagina={pg}
            estatico
            telas={
              telas.length > 0 ? (
                <p className="doc-telas">
                  Tela:{' '}
                  {telas.map((m) => (
                    <code key={m.path}>
                      {m.label} ({m.path})
                    </code>
                  ))}
                </p>
              ) : undefined
            }
          />
        )
      })}
    </main>,
  )
  return `<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${escaparHtml(titulo)}</title>
<style>${PALETA_IMPRESSAO}${CSS_DOC}</style>
</head>
<body>${corpo}</body>
</html>
`
}

/** Nome de arquivo: "oraculo-doc-<id ou completa>_<data>.<ext>". */
const nomeArquivo = (paginas: readonly PaginaDoc[], ext: string) => `oraculo-doc-${paginas.length > 1 ? 'completa' : paginas[0].id}_${hojeIso()}.${ext}`

export function baixarMarkdown(paginas: readonly PaginaDoc[]): void {
  const md = paginas.length > 1 ? documentacaoParaMarkdown(paginas) : paginaParaMarkdown(paginas[0])
  baixarArquivo(nomeArquivo(paginas, 'md'), md, 'text/markdown;charset=utf-8')
}

export async function baixarHtml(paginas: readonly PaginaDoc[]): Promise<void> {
  baixarArquivo(nomeArquivo(paginas, 'html'), await documentoHtml(paginas), 'text/html;charset=utf-8')
}

/** Abre o diálogo de impressão com o documento (dali, "Salvar como PDF"). */
export async function imprimir(paginas: readonly PaginaDoc[]): Promise<void> {
  const html = await documentoHtml(paginas)
  const quadro = document.createElement('iframe')
  quadro.setAttribute('aria-hidden', 'true')
  quadro.style.cssText = 'position:fixed;right:0;bottom:0;width:0;height:0;border:0;visibility:hidden'
  quadro.onload = () => {
    const w = quadro.contentWindow
    if (!w) return
    // o iframe só é removido depois que o diálogo fecha; sem isso o Chrome imprime em branco
    w.addEventListener('afterprint', () => setTimeout(() => quadro.remove(), 0))
    w.focus()
    w.print()
  }
  quadro.srcdoc = html
  document.body.appendChild(quadro)
}
