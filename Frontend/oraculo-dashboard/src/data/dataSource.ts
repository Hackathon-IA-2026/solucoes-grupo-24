/**
 * Camada de acesso a dados do dashboard. As telas SÓ consomem dados por aqui.
 *
 * Padrão: busca no Backend (FastAPI, Backend/main.py) em VITE_API_BASE_URL (padrão /api, que o
 * Vite repassa ao Backend — ver vite.config.ts). Com VITE_DATA_SOURCE=mock (`npm run dev:mock`)
 * lê os JSONs de src/data/mock/. Decisão: mock é opt-in explícito, nunca o que se vê sem
 * configurar nada — regra "nunca inventar dados". As assinaturas (todas assíncronas, retornando os tipos de ./types) são as mesmas nos
 * dois modos, então trocar mock por API não muda nenhum componente.
 *
 * Decisões que tornam classes de bug impossíveis:
 * - Todo dado passa por `schema.parse` (./types), venha do JSON ou da API. Resposta fora
 *   do contrato falha aqui, com o caminho do campo, e nunca chega meio quebrada à tela.
 * - No modo mock, todo registro precisa ter `mock: true`. Um mock sem a flag (que poderia
 *   ser confundido com dado real) derruba a leitura — regra "nunca inventar dados".
 * - Mocks carregados por import() dinâmico: viram chunks separados e só são baixados no
 *   modo mock.
 */
import { z } from 'zod'
import {
  AlertaDetalhadoSchema,
  AreasInfluenciaSchema,
  CargaSnapshotSchema,
  DensidadeMmgdSchema,
  ExcedenteTsoDsoSchema,
  MetricasValidacaoSchema,
  PrevisaoCurvaSchema,
  RiscoUsinaSchema,
  SaudeApiSchema,
  type AlertaDetalhado,
  type AreasInfluencia,
  type CargaSnapshot,
  type DensidadeMmgd,
  type ExcedenteTsoDso,
  type Horizonte,
  type MetricasValidacao,
  type PrevisaoCurva,
  type RiscoUsina,
  type SaudeApi,
} from './types'

export type DataSourceMode = 'mock' | 'api'

export const DATA_SOURCE_MODE: DataSourceMode = import.meta.env.VITE_DATA_SOURCE === 'mock' ? 'mock' : 'api'
const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? '/api').replace(/\/$/, '')

/**
 * Rotas da API, num lugar só (espelham Backend/src/api/app.py). Mudou lá, ajustar aqui e em
 * nenhum outro arquivo.
 */
const ENDPOINTS = {
  carga: '/carga/snapshot',
  previsao: '/previsao',
  riscos: '/riscos',
  alerta: (id: string) => `/alertas/${encodeURIComponent(id)}`,
  excedentes: '/excedentes',
  validacao: '/validacao',
  saude: '/saude',
  mmgdDensidade: '/mmgd/densidade',
  areasInfluencia: '/areas-influencia',
} as const

/** Erro de leitura com contexto (qual recurso e por quê). */
export class DataSourceError extends Error {
  readonly recurso: string
  readonly status?: number
  constructor(recurso: string, message: string, status?: number) {
    super(`[dataSource:${recurso}] ${message}`)
    this.name = 'DataSourceError'
    this.recurso = recurso
    this.status = status
  }
}

/**
 * Valida `bruto` contra o schema e, no modo mock, exige `mock: true` em todo registro.
 * Exportada para os testes provarem que um mock sem flag é rejeitado.
 */
export function validar<S extends z.ZodType>(
  recurso: string,
  schema: S,
  bruto: unknown,
  modo: DataSourceMode = DATA_SOURCE_MODE,
): z.infer<S> {
  const r = schema.safeParse(bruto)
  if (!r.success) throw new DataSourceError(recurso, `fora do contrato:\n${z.prettifyError(r.error)}`)

  if (modo === 'mock') {
    const registros = Array.isArray(r.data) ? r.data : [r.data]
    const semFlag = registros.findIndex((x) => (x as { mock?: boolean }).mock !== true)
    if (semFlag >= 0) throw new DataSourceError(recurso, `registro ${semFlag} do mock sem "mock: true"`)
  }
  return r.data
}

/**
 * GET na API. Erro HTTP vira DataSourceError com o `detail` do FastAPI na mensagem: o 503
 * de banco não publicado já diz o que rodar (`python run_heavywork.py`), e isso aparece na
 * tela em vez de um "HTTP 503" mudo. Backend desligado (fetch rejeita, ou o proxy do Vite
 * devolve 5xx sem JSON) também vira DataSourceError com a instrução de subir a API.
 */
async function buscarApi(recurso: string, caminho: string): Promise<unknown> {
  const url = `${API_BASE}${caminho}`
  let resp: Response
  try {
    resp = await fetch(url, { headers: { Accept: 'application/json' } })
  } catch (e) {
    throw new DataSourceError(recurso, `API inacessível em ${url} (${String(e)}). ${SUBIR_API}`)
  }
  if (!resp.ok) {
    const detalhe = await detalheErro(resp)
    throw new DataSourceError(recurso, `HTTP ${resp.status} em ${url}: ${detalhe}`, resp.status)
  }
  return resp.json()
}

const SUBIR_API = 'Suba o Backend: `python main.py` em Backend/ (ou use `npm run dev:mock`).'

/** Extrai o `detail` do FastAPI; sem JSON (proxy sem Backend atrás), devolve a instrução. */
async function detalheErro(resp: Response): Promise<string> {
  try {
    const corpo = (await resp.json()) as { detail?: unknown }
    if (corpo.detail !== undefined) return typeof corpo.detail === 'string' ? corpo.detail : JSON.stringify(corpo.detail)
  } catch {
    // corpo não é JSON: cai na instrução abaixo
  }
  return resp.status >= 500 ? `sem resposta do Backend. ${SUBIR_API}` : resp.statusText
}

/**
 * Leitor genérico: escolhe a origem pelo modo e valida sempre com o mesmo schema.
 * `mock` é uma função (e não o dado) para o import() só acontecer quando necessário.
 */
async function ler<S extends z.ZodType>(
  recurso: string,
  schema: S,
  origem: { mock: () => Promise<{ default: unknown }>; api: string },
): Promise<z.infer<S>> {
  const bruto = DATA_SOURCE_MODE === 'mock' ? (await origem.mock()).default : await buscarApi(recurso, origem.api)
  return validar(recurso, schema, bruto)
}

// ---------------------------------------------------------------------------
// API pública
// ---------------------------------------------------------------------------

export function getCarga(): Promise<CargaSnapshot> {
  return ler('carga', CargaSnapshotSchema, { mock: () => import('./mock/carga.json'), api: ENDPOINTS.carga })
}

/** Curvas de previsão; sem argumento devolve os três horizontes (30min, 3h, D+1). */
export async function getPrevisao(horizonte?: Horizonte): Promise<PrevisaoCurva[]> {
  const curvas = await ler('previsao', z.array(PrevisaoCurvaSchema), {
    mock: () => import('./mock/previsao.json'),
    api: ENDPOINTS.previsao,
  })
  return horizonte ? curvas.filter((c) => c.horizonte === horizonte) : curvas
}

/** Riscos por usina, do maior para o menor (probabilidade, depois montante). */
export async function getRiscos(): Promise<RiscoUsina[]> {
  const riscos = await ler('riscos', z.array(RiscoUsinaSchema), {
    mock: () => import('./mock/riscos.json'),
    api: ENDPOINTS.riscos,
  })
  return [...riscos].sort((a, b) => b.probabilidadePct - a.probabilidadePct || b.montanteMw - a.montanteMw)
}

/** Detalhe do alerta de um RiscoUsina; `null` se não houver alerta para o id. */
export async function getAlerta(riscoUsinaId: string): Promise<AlertaDetalhado | null> {
  if (DATA_SOURCE_MODE === 'mock') {
    const alertas = await ler('alerta', z.array(AlertaDetalhadoSchema), {
      mock: () => import('./mock/alertas.json'),
      api: '', // não usado no modo mock
    })
    return alertas.find((a) => a.riscoUsinaId === riscoUsinaId) ?? null
  }
  try {
    return validar('alerta', AlertaDetalhadoSchema, await buscarApi('alerta', ENDPOINTS.alerta(riscoUsinaId)))
  } catch (e) {
    if (e instanceof DataSourceError && e.status === 404) return null
    throw e
  }
}

export function getExcedentes(): Promise<ExcedenteTsoDso[]> {
  return ler('excedentes', z.array(ExcedenteTsoDsoSchema), {
    mock: () => import('./mock/excedentes.json'),
    api: ENDPOINTS.excedentes,
  })
}

export function getValidacao(): Promise<MetricasValidacao> {
  return ler('validacao', MetricasValidacaoSchema, {
    mock: () => import('./mock/validacao.json'),
    api: ENDPOINTS.validacao,
  })
}

/**
 * Estado da publicação servida pela API (rota /saude, fora do contrato dos recursos).
 * `null` no modo mock: não há execução publicada por trás dos JSONs.
 */
export async function getSaude(): Promise<SaudeApi | null> {
  if (DATA_SOURCE_MODE === 'mock') return null
  return validar('saude', SaudeApiSchema, await buscarApi('saude', ENDPOINTS.saude))
}

/** Pontos de densidade de MMGD para o heatmap do Mapa Híbrido (capacidade por área de influência). */
export function getDensidadeMmgd(): Promise<DensidadeMmgd> {
  return ler('mmgdDensidade', DensidadeMmgdSchema, {
    mock: () => import('./mock/mmgd_densidade.json'),
    api: ENDPOINTS.mmgdDensidade,
  })
}

/** Polígonos das áreas de influência das subestações da área piloto (camada do Mapa Híbrido). */
export function getAreasInfluencia(): Promise<AreasInfluencia> {
  return ler('areasInfluencia', AreasInfluenciaSchema, {
    mock: () => import('./mock/areas_influencia.json'),
    api: ENDPOINTS.areasInfluencia,
  })
}
