/**
 * Modelo da documentação embutida (ajuda F1).
 *
 * Decisão (2026-09-26): a documentação das telas deixou de ser gerada por script Python
 * (Sphinx em docs/oraculo/documentacao_sphinx, servida em /docs pelo backend) e passou a ser
 * ESCRITA AQUI, no frontend. Motivos: (1) a ajuda não depende mais de o backend estar de pé nem
 * de alguém ter rodado `build_docs.py`; (2) quem muda uma tela muda a página dela no mesmo
 * lugar do código; (3) o texto acompanha o que a tela React realmente mostra hoje.
 *
 * O conteúdo é DADO ESTRUTURADO (blocos), não JSX nem Markdown solto, porque o mesmo texto
 * precisa sair em três formatos sem ser escrito três vezes:
 * - na tela (Renderizador.tsx, React);
 * - em HTML autocontido e impressão/PDF (o mesmo Renderizador em modo estático);
 * - em Markdown (exportar.ts).
 *
 * Marcação inline aceita dentro de qualquer texto (interpretada por `interpretarInline`, uma só
 * implementação para os três formatos):
 *   **negrito** · *itálico* · `código` · [[id-da-pagina]] ou [[id-da-pagina|texto]] (link interno)
 *   · [texto](https://...) (link externo)
 */

/** Tom de um aviso: mesma convenção de cor da tela (ver página "Como ler os painéis"). */
export type Tom = 'nota' | 'premissa' | 'medido' | 'limite'

export const ROTULO_TOM: Record<Tom, string> = {
  nota: 'Importante',
  premissa: 'Premissa declarada',
  medido: 'Medido / corrigido',
  limite: 'Limite',
}

export type Bloco =
  | { t: 'p'; texto: string }
  | { t: 'lista'; itens: string[]; ordenada?: boolean }
  | { t: 'tabela'; cab: string[]; linhas: string[][] }
  | { t: 'aviso'; tom: Tom; titulo: string; blocos: Bloco[] }
  /** fórmula em texto (monoespaçada): sem MathJax, para não depender de biblioteca externa */
  | { t: 'formula'; texto: string }
  /** bloco de código ou diagrama em texto */
  | { t: 'codigo'; texto: string }
  /** subtítulo dentro de uma seção */
  | { t: 'sub'; titulo: string }

export interface Secao {
  titulo: string
  blocos: Bloco[]
}

export interface PaginaDoc {
  /** identificador estável: é o `ajuda` dos módulos (src/modules.ts) e o alvo de [[links]] */
  id: string
  titulo: string
  /** grupo do índice lateral (os mesmos grupos do menu, mais "Geral") */
  grupo: string
  /** uma frase: aparece no índice, na busca e no topo da página */
  resumo: string
  /** a pergunta que a tela responde, quando é página de tela */
  pergunta?: string
  /** rotas da API que a tela consome (documentação do contrato de dados da tela) */
  rotas?: string[]
  secoes: Secao[]
}

// ------------------------------------------------------------------ construtores de bloco
// Funções curtas para o conteúdo ficar legível nos arquivos de páginas (paginas/*.ts).

export const p = (texto: string): Bloco => ({ t: 'p', texto })
export const lista = (...itens: string[]): Bloco => ({ t: 'lista', itens })
export const passos = (...itens: string[]): Bloco => ({ t: 'lista', itens, ordenada: true })
export const tabela = (cab: string[], linhas: string[][]): Bloco => ({ t: 'tabela', cab, linhas })
export const formula = (texto: string): Bloco => ({ t: 'formula', texto })
export const codigo = (texto: string): Bloco => ({ t: 'codigo', texto })
export const sub = (titulo: string): Bloco => ({ t: 'sub', titulo })
/** Aviso com tom; strings viram parágrafos, para o caso comum de aviso só com texto. */
export const aviso = (tom: Tom, titulo: string, ...conteudo: (string | Bloco)[]): Bloco => ({
  t: 'aviso',
  tom,
  titulo,
  blocos: conteudo.map((c) => (typeof c === 'string' ? p(c) : c)),
})
export const secao = (titulo: string, ...blocos: (string | Bloco)[]): Secao => ({
  titulo,
  blocos: blocos.map((b) => (typeof b === 'string' ? p(b) : b)),
})

/** Âncora de uma página no HTML e no Markdown exportados (links internos e sumário). */
export const ancora = (id: string) => 'doc-' + id

// ------------------------------------------------------------------ marcação inline

export type Trecho =
  | { k: 'texto'; v: string }
  | { k: 'negrito'; v: string }
  | { k: 'italico'; v: string }
  | { k: 'codigo'; v: string }
  | { k: 'interno'; v: string; alvo: string }
  | { k: 'externo'; v: string; href: string }

/*
 * Uma alternativa por marcação, na ordem de prioridade: link interno antes do externo (ambos
 * começam com "["), negrito antes de itálico (ambos com "*"). Sem aninhamento, de propósito:
 * mantém o parser trivial e o texto previsível nos três formatos.
 */
const RE_INLINE = /\[\[([^\]|]+)(?:\|([^\]]+))?\]\]|\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)|\*\*([^*]+)\*\*|`([^`]+)`|\*([^*\s][^*]*)\*/g

/** Quebra um texto com marcação inline em trechos tipados. */
export function interpretarInline(texto: string): Trecho[] {
  const out: Trecho[] = []
  let ultimo = 0
  for (const m of texto.matchAll(RE_INLINE)) {
    const i = m.index ?? 0
    if (i > ultimo) out.push({ k: 'texto', v: texto.slice(ultimo, i) })
    if (m[1] !== undefined) out.push({ k: 'interno', alvo: m[1].trim(), v: (m[2] ?? '').trim() })
    else if (m[3] !== undefined) out.push({ k: 'externo', v: m[3], href: m[4] })
    else if (m[5] !== undefined) out.push({ k: 'negrito', v: m[5] })
    else if (m[6] !== undefined) out.push({ k: 'codigo', v: m[6] })
    else if (m[7] !== undefined) out.push({ k: 'italico', v: m[7] })
    ultimo = i + m[0].length
  }
  if (ultimo < texto.length) out.push({ k: 'texto', v: texto.slice(ultimo) })
  return out
}

/** Todos os textos de um bloco (para busca e para checar links nos testes). */
export function textosDoBloco(b: Bloco): string[] {
  switch (b.t) {
    case 'p':
    case 'formula':
    case 'codigo':
      return [b.texto]
    case 'sub':
      return [b.titulo]
    case 'lista':
      return b.itens
    case 'tabela':
      return [...b.cab, ...b.linhas.flat()]
    case 'aviso':
      return [b.titulo, ...b.blocos.flatMap(textosDoBloco)]
  }
}

/** Texto integral de uma página, sem marcação de bloco (para a busca). */
export function textoDaPagina(pg: PaginaDoc): string {
  return [
    pg.titulo,
    pg.resumo,
    pg.pergunta ?? '',
    ...(pg.rotas ?? []),
    ...pg.secoes.flatMap((s) => [s.titulo, ...s.blocos.flatMap(textosDoBloco)]),
  ].join('\n')
}
