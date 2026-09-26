/**
 * Índice da documentação: a ordem das páginas (a mesma do menu, com "Geral" na frente) e as
 * buscas por id, por tela e por texto. É o único lugar que junta as páginas.
 *
 * Painel → página: o `ajuda` de cada módulo em src/modules.ts É o id da página. Não há mapa
 * separado para manter em sincronia; o teste documentacao.test.ts exige que todo módulo do menu
 * tenha página e que todo [[link]] aponte para uma página existente.
 */
import { MODULES, type ModuleDef } from '../../modules'
import { normalizar } from '../../utils/ordenacao'
import { textoDaPagina, type PaginaDoc } from './modelo'
import { PAGINAS_ANALISE } from './paginas/analise'
import { PAGINAS_CONFIANCA } from './paginas/confianca'
import { PAGINAS_CONTRATO } from './paginas/contrato'
import { PAGINAS_FRONTEIRA } from './paginas/fronteira'
import { PAGINAS_GERAIS } from './paginas/geral'
import { PAGINAS_INVESTIMENTO } from './paginas/investimento'
import { PAGINAS_MAPA } from './paginas/mapa'
import { PAGINAS_OPERACAO } from './paginas/operacao'

export const PAGINAS: readonly PaginaDoc[] = [
  ...PAGINAS_GERAIS,
  ...PAGINAS_OPERACAO,
  ...PAGINAS_ANALISE,
  ...PAGINAS_MAPA,
  ...PAGINAS_FRONTEIRA,
  ...PAGINAS_INVESTIMENTO,
  ...PAGINAS_CONFIANCA,
  ...PAGINAS_CONTRATO,
]

/** Página de capa: aberta quando a tela corrente não tem página própria. */
export const ID_INICIO = 'inicio'

const POR_ID = new Map(PAGINAS.map((pg) => [pg.id, pg]))

export const paginaPorId = (id: string | null | undefined): PaginaDoc | undefined => (id ? POR_ID.get(id) : undefined)

/** A página da tela (ou a capa). */
export const paginaDoModulo = (m: ModuleDef | undefined): PaginaDoc => paginaPorId(m?.ajuda) ?? POR_ID.get(ID_INICIO)!

/** Telas do menu documentadas por uma página (uma página pode cobrir mais de uma tela). */
export const telasDaPagina = (id: string): ModuleDef[] => MODULES.filter((m) => m.ajuda === id)

/** Grupos na ordem em que aparecem (para o índice lateral). */
export function paginasPorGrupo(paginas: readonly PaginaDoc[] = PAGINAS): [string, PaginaDoc[]][] {
  const grupos = new Map<string, PaginaDoc[]>()
  for (const pg of paginas) grupos.set(pg.grupo, [...(grupos.get(pg.grupo) ?? []), pg])
  return [...grupos]
}

// Texto normalizado de cada página, calculado uma vez (a busca roda a cada tecla).
const TEXTO = new Map(PAGINAS.map((pg) => [pg.id, normalizar(textoDaPagina(pg))]))

/**
 * Páginas que contêm TODOS os termos da busca (sem acento, sem caixa), título antes de corpo.
 * Busca vazia devolve todas.
 */
export function buscar(consulta: string): PaginaDoc[] {
  const termos = normalizar(consulta).split(/\s+/).filter(Boolean)
  if (!termos.length) return [...PAGINAS]
  const casa = PAGINAS.filter((pg) => termos.every((t) => TEXTO.get(pg.id)!.includes(t)))
  const noTitulo = (pg: PaginaDoc) => termos.every((t) => normalizar(pg.titulo).includes(t))
  return [...casa.filter(noTitulo), ...casa.filter((pg) => !noTitulo(pg))]
}
