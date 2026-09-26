/**
 * Travas da documentação embutida (ajuda F1).
 *
 * O teste que mais importa é "toda tela do menu tem página": tela nova sem documentação reprova
 * a suíte — a alternativa é descobrir o furo quando alguém aperta F1 na apresentação. O segundo
 * é "todo [[link]] aponta para página existente": renomear um id quebra o teste, não a ajuda.
 */
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { MODULES, moduloDaRota } from '../../modules'
import { documentacaoParaMarkdown, documentoHtml, paginaParaMarkdown } from './exportar'
import { ID_INICIO, PAGINAS, buscar, paginaDoModulo, paginaPorId, telasDaPagina } from './indice'
import { interpretarInline, textosDoBloco, type PaginaDoc } from './modelo'

/** Todos os alvos de [[link]] de uma página. */
function alvos(pg: PaginaDoc): string[] {
  const textos = [pg.resumo, pg.pergunta ?? '', ...pg.secoes.flatMap((s) => s.blocos.flatMap(textosDoBloco))]
  return textos.flatMap((t) => interpretarInline(t).flatMap((x) => (x.k === 'interno' ? [x.alvo] : [])))
}

describe('cobertura: telas × páginas', () => {
  it('toda tela do menu tem página de ajuda', () => {
    const sem = MODULES.filter((m) => !m.ajuda || !paginaPorId(m.ajuda)).map((m) => m.path)
    expect(sem).toEqual([])
  })

  it('toda página de tela (com "pergunta") está ligada a pelo menos uma tela do menu', () => {
    const orfas = PAGINAS.filter((pg) => pg.pergunta && telasDaPagina(pg.id).length === 0).map((pg) => pg.id)
    expect(orfas).toEqual([])
  })

  it('ids únicos e a capa existe', () => {
    const ids = PAGINAS.map((pg) => pg.id)
    expect(new Set(ids).size).toBe(ids.length)
    expect(paginaPorId(ID_INICIO)).toBeDefined()
  })

  it('F1 numa subrota abre a página da tela; rota desconhecida cai na capa', () => {
    expect(paginaDoModulo(moduloDaRota('/detalhe-alerta/abc')).id).toBe('detalhe-alerta')
    expect(paginaDoModulo(moduloDaRota('/rota-que-nao-existe')).id).toBe(ID_INICIO)
  })
})

describe('conteúdo', () => {
  it('todo [[link]] aponta para uma página existente', () => {
    const quebrados = PAGINAS.flatMap((pg) => alvos(pg).filter((a) => !paginaPorId(a)).map((a) => `${pg.id} → ${a}`))
    expect(quebrados).toEqual([])
  })

  it('nenhuma página ou seção vazia; tabelas com linhas do tamanho do cabeçalho', () => {
    for (const pg of PAGINAS) {
      expect(pg.secoes.length, pg.id).toBeGreaterThan(0)
      for (const s of pg.secoes) {
        expect(s.blocos.length, `${pg.id} / ${s.titulo}`).toBeGreaterThan(0)
        for (const b of s.blocos)
          if (b.t === 'tabela') for (const l of b.linhas) expect(l.length, `${pg.id} / ${s.titulo}`).toBe(b.cab.length)
      }
    }
  })
})

describe('marcação inline', () => {
  it('reconhece negrito, itálico, código e os dois tipos de link', () => {
    const t = interpretarInline('a **b** *c* `d` [[mapa]] [[clm|CLM]] [ONS](https://www.ons.org.br) e')
    expect(t.map((x) => x.k)).toEqual(['texto', 'negrito', 'texto', 'italico', 'texto', 'codigo', 'texto', 'interno', 'texto', 'interno', 'texto', 'externo', 'texto'])
    expect(t.find((x) => x.k === 'interno' && x.v === 'CLM')).toMatchObject({ alvo: 'clm' })
  })

  it('texto sem marcação volta inteiro', () => {
    expect(interpretarInline('carga global − MMGD')).toEqual([{ k: 'texto', v: 'carga global − MMGD' }])
  })
})

describe('busca', () => {
  it('sem acento e sem caixa, título primeiro', () => {
    const r = buscar('validacao')
    expect(r.length).toBeGreaterThan(0)
    expect(r[0].titulo.toLowerCase()).toContain('valida')
  })
  it('busca vazia devolve tudo', () => {
    expect(buscar('  ').length).toBe(PAGINAS.length)
  })
})

describe('exportação', () => {
  it('Markdown de uma página: título, seções e tabela bem formada', () => {
    const pg = paginaPorId('clm')!
    const md = paginaParaMarkdown(pg)
    expect(md.startsWith('# ' + pg.titulo)).toBe(true)
    for (const s of pg.secoes) expect(md).toContain('## ' + s.titulo)
    expect(md).toMatch(/\n\| --- \|/)
    // página única: link interno vira nome, não âncora quebrada
    expect(md).not.toContain('](#doc-')
  })

  it('Markdown completo: toda âncora citada existe no próprio arquivo', () => {
    const md = documentacaoParaMarkdown()
    const citadas = new Set([...md.matchAll(/\]\(#(doc-[\w-]+)\)/g)].map((m) => m[1]))
    const definidas = new Set([...md.matchAll(/<a id="(doc-[\w-]+)"><\/a>/g)].map((m) => m[1]))
    expect(definidas.size).toBe(PAGINAS.length)
    for (const a of citadas) expect(definidas.has(a), a).toBe(true)
  })

  it('HTML autocontido: todas as páginas, sem botão e sem recurso externo', async () => {
    const html = await documentoHtml(PAGINAS)
    expect(html.startsWith('<!doctype html>')).toBe(true)
    for (const pg of PAGINAS) expect(html).toContain(`id="doc-${pg.id}"`)
    expect(html).not.toContain('<button')
    expect(html).not.toMatch(/<(link|script)\b/)
  })
})

describe('a ajuda não depende mais do backend', () => {
  it('Ajuda.tsx não consulta /api/docs/status nem abre iframe', () => {
    const src = readFileSync(fileURLToPath(new URL('../Ajuda.tsx', import.meta.url)), 'utf-8')
    expect(src).not.toContain("'docs/status'")
    expect(src).not.toContain('<iframe')
  })
})
