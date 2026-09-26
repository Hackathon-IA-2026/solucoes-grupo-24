/**
 * Cliente da API do protótipo O.R.A.C.U.L.O. (pacote Backend/oraculo, rotas /api/...).
 *
 * Porte de 02-PROTOTIPO/web/js/api.js. Toda resposta traz o ENVELOPE de proveniência
 * `{ok, data, mode, provenance, notes}`; resposta sem `provenance` é falha de contrato (RNF-04
 * da especificação) e nunca chega à tela. A interface não calcula grandeza analítica: só
 * apresenta e navega. As rotas do contrato do dashboard (/api/carga/snapshot...) continuam em
 * src/data/dataSource.ts.
 */

export interface Proveniencia {
  dataset: string
  resource?: string
  mode: string
  rows?: number
  bytes_read?: number
  fetched_at?: string
  lag_note?: string
}

export interface Envelope<T = unknown> {
  ok: true
  data: T
  mode?: string
  provenance: Proveniencia[]
  notes?: string[]
}

export class ApiError extends Error {
  readonly code: string
  readonly hint: string
  constructor(code: string, message: string, hint = '') {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.hint = hint
  }
}

type Params = Record<string, string | number | boolean | null | undefined>

const CACHE = new Map<string, Envelope>()

function qs(params?: Params | null): string {
  if (!params) return ''
  const p: string[] = []
  for (const k in params) {
    const v = params[k]
    if (v === undefined || v === null || v === '') continue
    p.push(encodeURIComponent(k) + '=' + encodeURIComponent(String(v)))
  }
  return p.length ? '?' + p.join('&') : ''
}

interface Corpo {
  ok?: boolean
  error?: { code?: string; message?: string; hint?: string }
  provenance?: unknown
}

/** GET /api/<path>. `fresh` ignora o cache (a mesma URL é reaproveitada entre telas). */
export async function get<T = unknown>(path: string, params?: Params | null, opts?: { fresh?: boolean }): Promise<Envelope<T>> {
  const url = '/api/' + path + qs(params)
  if (!opts?.fresh && CACHE.has(url)) return CACHE.get(url) as Envelope<T>
  let res: Response
  let body: Corpo
  try {
    res = await fetch(url, { headers: { Accept: 'application/json' } })
  } catch {
    throw new ApiError('NETWORK', 'Não foi possível falar com o serviço.', 'Verifique se o Backend está em execução: `python main.py` em Backend/.')
  }
  try {
    body = (await res.json()) as Corpo
  } catch {
    throw new ApiError('PARSE', 'Resposta inválida do serviço.', `HTTP ${res.status} em ${url}`)
  }
  if (!body || body.ok !== true) {
    const e = body?.error || {}
    throw new ApiError(e.code || 'INTERNAL', e.message || 'Falha desconhecida.', e.hint || '')
  }
  if (!Array.isArray(body.provenance)) {
    throw new ApiError('CONTRACT', 'Resposta sem envelope de proveniência — falha de contrato.', 'Ver RNF-04 na especificação.')
  }
  CACHE.set(url, body as Envelope)
  return body as Envelope<T>
}

/** POST /api/<path>. Limpa o cache: reconstruções mudam o que as outras rotas devolvem. */
export async function post<T = unknown>(path: string, payload?: unknown): Promise<Envelope<T>> {
  let body: Corpo
  try {
    const res = await fetch('/api/' + path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload || {}),
    })
    body = (await res.json()) as Corpo
  } catch {
    throw new ApiError('NETWORK', 'Não foi possível falar com o serviço.', '')
  }
  if (!body || body.ok !== true) {
    const e = body?.error || {}
    throw new ApiError(e.code || 'INTERNAL', e.message || 'Falha.', e.hint || '')
  }
  CACHE.clear()
  return body as Envelope<T>
}

export function clearCache(): void {
  CACHE.clear()
}

/** Atalhos das rotas mais usadas (mesmos nomes do api.js original). */
export const Api = {
  get,
  post,
  clearCache,
  meta: () => get('meta'),
  health: (fresh?: boolean) => get('health', null, { fresh }),
  catalog: (refresh?: boolean) => get('catalog', refresh ? { refresh: 1 } : null, { fresh: !!refresh }),
  packageDetail: (pkg: string) => get('catalog/' + encodeURIComponent(pkg)),
  series: (area: string, hours: number) => get('series', { area, hours }),
  decomposition: (area: string, hours: number) => get('decomposition', { area, hours }),
  forecast: (area: string, horizon: string, asymmetric: boolean) => get('forecast', { area, horizon, asymmetric: asymmetric ? 1 : 0 }),
  profiles: (area: string) => get('profiles', { area }),
  risk: (horizon: string, level?: string, minProb?: number) => get('risk', { horizon, level, min_probability: minProb }),
  validation: (area: string, asymmetric: boolean) => get('validation', { area, asymmetric: asymmetric ? 1 : 0 }),
  triangulation: () => get('triangulation'),
  provenance: () => get('provenance', null, { fresh: true }),
  ingest: (payload?: unknown) => post('ingest', payload),
}
