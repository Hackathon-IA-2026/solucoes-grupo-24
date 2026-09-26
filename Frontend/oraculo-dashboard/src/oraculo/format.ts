/** Formatação pt-BR das telas do protótipo (utilitários de 02-PROTOTIPO/web/js/app.js). */

type Num = number | null | undefined

const finito = (v: Num): v is number => v !== null && v !== undefined && Number.isFinite(v)

export function esc(s: unknown): string {
  return String(s === null || s === undefined ? '' : s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

export function num(v: Num, d?: number): string {
  if (!finito(v)) return '—'
  const casas = d === undefined ? 0 : d
  return Number(v).toLocaleString('pt-BR', { minimumFractionDigits: casas, maximumFractionDigits: casas })
}

/** fração -> "12,3%" */
export function pct(v: Num, d?: number): string {
  if (!finito(v)) return '—'
  return num(v * 100, d === undefined ? 1 : d) + '%'
}

export function signed(v: Num, d?: number): string {
  if (!finito(v)) return '—'
  return (v > 0 ? '+' : '') + num(v, d === undefined ? 3 : d)
}

export function bytes(n: Num): string {
  if (!n) return '—'
  if (n > 1e6) return num(n / 1e6, 1) + ' MB'
  if (n > 1e3) return num(n / 1e3, 0) + ' kB'
  return n + ' B'
}

export function when(iso: unknown): string {
  if (!iso) return '—'
  return String(iso).replace('T', ' ').replace('Z', '').slice(0, 16)
}

export function lastFinite(arr: readonly Num[] | undefined): number | null {
  const a = arr || []
  for (let i = a.length - 1; i >= 0; i--) if (finito(a[i])) return a[i] as number
  return null
}
