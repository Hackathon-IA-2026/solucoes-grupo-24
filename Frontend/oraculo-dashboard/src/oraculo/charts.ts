/**
 * Primitivos de gráfico em SVG puro das telas do protótipo O.R.A.C.U.L.O.
 *
 * Porte em TypeScript de 02-PROTOTIPO/web/js/charts.js, mantido imperativo de propósito: cada
 * função desenha dentro de um elemento hospedeiro (medindo a largura dele) e o componente
 * <Grafico> (./ui.tsx) chama a função num efeito e de novo quando o hospedeiro muda de
 * largura. Assim os gráficos das telas do protótipo ficam idênticos aos originais, sem
 * biblioteca externa (funciona offline). Cores: nomes da paleta (--o-* em ./oraculo.css) ou
 * qualquer cor CSS.
 */

const NS = 'http://www.w3.org/2000/svg'

type Num = number | null | undefined
type Attrs = Record<string, string | number | null | undefined>

function el(tag: string, attrs?: Attrs, parent?: Element): SVGElement {
  const n = document.createElementNS(NS, tag) as SVGElement
  if (attrs)
    for (const k in attrs) {
      const v = attrs[k]
      if (v === null || v === undefined) continue
      n.setAttribute(k, String(v))
    }
  if (parent) parent.appendChild(n)
  return n
}

function css(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || '#888'
}

const PALETTE: Record<string, string> = {
  teal: '--o-teal',
  green: '--o-green',
  amber: '--o-amber',
  crimson: '--o-crimson',
  purple: '--o-purple',
  navy: '--o-navy-2',
  ink: '--o-ink',
  ink2: '--o-ink-2',
  muted: '--o-muted',
  line: '--o-line',
}

export function color(c: string | undefined): string {
  if (!c) return css('--o-teal')
  return PALETTE[c] ? css(PALETTE[c]) : c
}

const isNum = (v: Num): v is number => v !== null && v !== undefined && Number.isFinite(v)

function finite(arr: readonly Num[] | undefined): number[] {
  return (arr || []).filter(isNum)
}

function extent(arrays: readonly (readonly Num[] | undefined)[]): [number, number] {
  let lo = Infinity
  let hi = -Infinity
  arrays.forEach((a) =>
    finite(a).forEach((v) => {
      if (v < lo) lo = v
      if (v > hi) hi = v
    }),
  )
  if (!Number.isFinite(lo)) {
    lo = 0
    hi = 1
  }
  if (lo === hi) {
    lo -= 1
    hi += 1
  }
  return [lo, hi]
}

function niceTicks(lo: number, hi: number, count: number): number[] {
  const span = hi - lo
  if (span <= 0) return [lo]
  const raw = span / Math.max(1, count)
  const mag = Math.pow(10, Math.floor(Math.log10(raw)))
  const norm = raw / mag
  const step = (norm < 1.5 ? 1 : norm < 3 ? 2 : norm < 7 ? 5 : 10) * mag
  const out: number[] = []
  for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) out.push(Math.round(v / step) * step)
  return out
}

export function fmt(v: Num, digits?: number): string {
  if (!isNum(v)) return '—'
  const d = digits === undefined ? 0 : digits
  return v.toLocaleString('pt-BR', { minimumFractionDigits: d, maximumFractionDigits: d })
}

export function fmtCompact(v: Num): string {
  if (!isNum(v)) return '—'
  const a = Math.abs(v)
  if (a >= 1e6) return (v / 1e6).toLocaleString('pt-BR', { maximumFractionDigits: 1 }) + ' M'
  if (a >= 1e3) return (v / 1e3).toLocaleString('pt-BR', { maximumFractionDigits: 1 }) + ' k'
  return fmt(v, a < 10 ? 1 : 0)
}

export function hhmm(iso: unknown): string {
  if (!iso) return ''
  return String(iso).replace('T', ' ').slice(11, 16)
}

export function dayHour(iso: unknown): string {
  if (!iso) return ''
  const t = String(iso).replace('T', ' ')
  return t.slice(8, 10) + '/' + t.slice(5, 7) + ' ' + t.slice(11, 16)
}

// ------------------------------------------------------------ tooltip
let TIP: HTMLDivElement | null = null
function tip(): HTMLDivElement {
  if (!TIP) {
    TIP = document.createElement('div')
    TIP.className = 'o-tooltip'
    document.body.appendChild(TIP)
  }
  return TIP
}
export function showTip(html: string, x: number, y: number): void {
  const t = tip()
  t.innerHTML = html
  t.classList.add('on')
  const r = t.getBoundingClientRect()
  let left = x + 14
  let top = y - r.height / 2
  if (left + r.width > window.innerWidth - 8) left = x - r.width - 14
  if (top < 8) top = 8
  if (top + r.height > window.innerHeight - 8) top = window.innerHeight - r.height - 8
  t.style.left = left + 'px'
  t.style.top = top + 'px'
}
export function hideTip(): void {
  if (TIP) TIP.classList.remove('on')
}

// ------------------------------------------------------------ frame
interface FrameOpts {
  height?: number
  padLeft?: number
  padRight?: number
  padTop?: number
  padBottom?: number
  yTicks?: number
}
interface Frame {
  svg: SVGElement
  width: number
  height: number
  x0: number
  x1: number
  y0: number
  y1: number
  o: Required<FrameOpts>
}

function frame(host: HTMLElement, opts?: FrameOpts): Frame {
  const o = { height: 240, padLeft: 52, padRight: 14, padTop: 12, padBottom: 26, yTicks: 4 }
  for (const k in opts) {
    const v = opts[k as keyof FrameOpts]
    if (v !== undefined) o[k as keyof FrameOpts] = v
  }
  host.innerHTML = ''
  const width = Math.max(320, host.clientWidth || 640)
  const svg = el(
    'svg',
    { class: 'chart', viewBox: '0 0 ' + width + ' ' + o.height, width: '100%', height: o.height, preserveAspectRatio: 'none' },
    host,
  )
  return { svg, width, height: o.height, x0: o.padLeft, x1: width - o.padRight, y0: o.padTop, y1: o.height - o.padBottom, o }
}

function yAxis(f: Frame, lo: number, hi: number, opts?: { compact?: boolean; digits?: number; label?: string }) {
  const o = opts || {}
  const ticks = niceTicks(lo, hi, f.o.yTicks)
  const sy = (v: number) => f.y1 - ((v - lo) / (hi - lo)) * (f.y1 - f.y0)
  ticks.forEach((t) => {
    el('line', { class: 'grid-line', x1: f.x0, x2: f.x1, y1: sy(t), y2: sy(t) }, f.svg)
    const lab = el('text', { class: 'tick', x: f.x0 - 7, y: sy(t) + 3.5, 'text-anchor': 'end' }, f.svg)
    lab.textContent = o.compact ? fmtCompact(t) : fmt(t, o.digits)
  })
  el('line', { class: 'axis-line', x1: f.x0, x2: f.x0, y1: f.y0, y2: f.y1 }, f.svg)
  if (o.label) {
    const t = el('text', { class: 'tick', x: f.x0 - 7, y: f.y0 - 2, 'text-anchor': 'end' }, f.svg)
    t.textContent = o.label
  }
  return sy
}

function xAxisCategorical(
  f: Frame,
  labels: readonly unknown[],
  opts?: { every?: number; count?: number; format?: (v: unknown, i: number) => string },
) {
  const o = opts || {}
  const n = labels.length
  const sx = (i: number) => (n <= 1 ? f.x0 : f.x0 + (i / (n - 1)) * (f.x1 - f.x0))
  el('line', { class: 'axis-line', x1: f.x0, x2: f.x1, y1: f.y1, y2: f.y1 }, f.svg)
  const every = o.every || Math.max(1, Math.round(n / (o.count || 7)))
  for (let i = 0; i < n; i += every) {
    const t = el('text', { class: 'tick', x: sx(i), y: f.y1 + 15, 'text-anchor': 'middle' }, f.svg)
    t.textContent = o.format ? o.format(labels[i], i) : String(labels[i])
  }
  return sx
}

function path(pts: ([number, number] | null)[]): string {
  let d = ''
  let open = false
  pts.forEach((p) => {
    if (p === null) {
      open = false
      return
    }
    d += (open ? 'L' : 'M') + p[0].toFixed(2) + ' ' + p[1].toFixed(2) + ' '
    open = true
  })
  return d.trim()
}

// ------------------------------------------------------------ hover
interface HoverRow {
  label?: string
  values: readonly Num[]
  color?: string
  unit?: string
  digits?: number
  format?: (v: number) => string
}

function attachHover(f: Frame, index: readonly unknown[], rows: HoverRow[], formatTime?: (v: unknown, i: number) => string) {
  const n = index.length
  if (!n) return
  const sx = (i: number) => (n <= 1 ? f.x0 : f.x0 + (i / (n - 1)) * (f.x1 - f.x0))
  const ch = el('line', { class: 'crosshair', x1: 0, x2: 0, y1: f.y0, y2: f.y1, opacity: 0 }, f.svg)
  const hot = el(
    'rect',
    { class: 'hot', x: f.x0, y: f.y0, width: Math.max(1, f.x1 - f.x0), height: Math.max(1, f.y1 - f.y0) },
    f.svg,
  )
  hot.addEventListener('mousemove', (ev) => {
    const e = ev as MouseEvent
    const box = f.svg.getBoundingClientRect()
    const scale = f.width / box.width
    const px = (e.clientX - box.left) * scale
    let i = Math.round(((px - f.x0) / Math.max(1, f.x1 - f.x0)) * (n - 1))
    i = Math.max(0, Math.min(n - 1, i))
    ch.setAttribute('x1', String(sx(i)))
    ch.setAttribute('x2', String(sx(i)))
    ch.setAttribute('opacity', '1')
    let html = '<div class="tt-time">' + ((formatTime ? formatTime(index[i], i) : dayHour(index[i])) || '') + '</div>'
    rows.forEach((r) => {
      const v = r.values[i]
      if (v === null || v === undefined) return
      html +=
        '<div class="tt-row"><span class="k">' +
        '<span class="tt-dot" style="background:' +
        color(r.color) +
        '"></span>' +
        (r.label || '') +
        '</span><span class="v">' +
        (r.format ? r.format(v) : fmt(v, r.digits === undefined ? 0 : r.digits)) +
        (r.unit ? ' ' + r.unit : '') +
        '</span></div>'
    })
    showTip(html, e.clientX, e.clientY)
  })
  hot.addEventListener('mouseleave', () => {
    ch.setAttribute('opacity', '0')
    hideTip()
  })
}

// ------------------------------------------------------------ lineChart
export interface Serie {
  label?: string
  values: readonly Num[]
  color?: string
  style?: 'dash' | 'line'
  unit?: string
  digits?: number
  width?: number
  area?: boolean
  areaOpacity?: number
  format?: (v: number) => string
}
export interface Banda {
  lower: readonly Num[]
  upper: readonly Num[]
  color?: string
  opacity?: number
  label?: string
  unit?: string
}
export interface Faixa {
  from: number
  to: number
  color?: string
  opacity?: number
  label?: string
}
export interface LineOpts {
  index: readonly unknown[]
  series?: (Serie | null | undefined | false)[]
  bands?: Banda[]
  spans?: Faixa[]
  height?: number
  padLeft?: number
  yLabel?: string
  compact?: boolean
  digits?: number
  yMin?: number
  zeroBase?: boolean
  xTicks?: number
  formatTime?: (v: unknown, i: number) => string
  formatTip?: (v: unknown, i: number) => string
  legend?: boolean
}

export function lineChart(host: HTMLElement, o: LineOpts): void {
  const index = o.index || []
  const series = (o.series || []).filter((s): s is Serie => !!s && !!s.values)
  const bands = o.bands || []
  const f = frame(host, { height: o.height || 250, padLeft: o.padLeft || 54 })
  if (!index.length) {
    host.innerHTML = '<div class="empty">Sem dados.</div>'
    return
  }
  const pools: (readonly Num[])[] = series.map((s) => s.values)
  bands.forEach((b) => {
    pools.push(b.lower)
    pools.push(b.upper)
  })
  let [lo, hi] = extent(pools)
  if (o.yMin !== undefined) lo = Math.min(lo, o.yMin)
  if (o.zeroBase) lo = Math.min(0, lo)
  const pad = (hi - lo) * 0.08
  lo -= pad
  hi += pad

  const sy = yAxis(f, lo, hi, { compact: o.compact, digits: o.digits, label: o.yLabel })
  const sx = xAxisCategorical(f, index, { count: o.xTicks || 7, format: o.formatTime || ((v) => dayHour(v)) })

  ;(o.spans || []).forEach((sp) => {
    const a = sx(sp.from)
    const b = sx(sp.to)
    el(
      'rect',
      {
        x: Math.min(a, b),
        y: f.y0,
        width: Math.abs(b - a),
        height: f.y1 - f.y0,
        fill: color(sp.color || 'amber'),
        opacity: sp.opacity === undefined ? 0.1 : sp.opacity,
      },
      f.svg,
    )
    if (sp.label) {
      const t = el('text', { class: 'tick', x: (a + b) / 2, y: f.y0 + 12, 'text-anchor': 'middle', fill: color(sp.color || 'amber') }, f.svg)
      t.textContent = sp.label
    }
  })

  bands.forEach((b) => {
    const up: [number, number][] = []
    const dn: [number, number][] = []
    for (let i = 0; i < index.length; i++) {
      const u = b.upper[i]
      const l = b.lower[i]
      if (!isNum(u) || !isNum(l)) continue
      up.push([sx(i), sy(u)])
      dn.unshift([sx(i), sy(l)])
    }
    if (!up.length) return
    el('path', { d: path(up.concat(dn)) + ' Z', fill: color(b.color || 'teal'), opacity: b.opacity === undefined ? 0.18 : b.opacity, stroke: 'none' }, f.svg)
  })

  series.forEach((s) => {
    const pts = index.map((_, i): [number, number] | null => {
      const v = s.values[i]
      return isNum(v) ? [sx(i), sy(v)] : null
    })
    if (s.area) {
      const filled = pts.filter((p): p is [number, number] => p !== null)
      if (filled.length) {
        el(
          'path',
          {
            d: path(filled) + ' L' + filled[filled.length - 1][0] + ' ' + f.y1 + ' L' + filled[0][0] + ' ' + f.y1 + ' Z',
            fill: color(s.color),
            opacity: s.areaOpacity || 0.16,
            stroke: 'none',
          },
          f.svg,
        )
      }
    }
    el(
      'path',
      {
        class: s.style === 'dash' ? 'series-dash' : 'series-line',
        d: path(pts),
        stroke: color(s.color),
        'stroke-width': s.width || (s.style === 'dash' ? 1.5 : 1.9),
      },
      f.svg,
    )
  })

  attachHover(
    f,
    index,
    (series as HoverRow[]).concat(
      bands.filter((b) => b.label).map((b) => ({ label: b.label, values: b.upper, color: b.color || 'teal', unit: b.unit })),
    ),
    o.formatTip || o.formatTime,
  )

  if (o.legend !== false) renderLegend(host, series, bands)
}

function renderLegend(host: HTMLElement, series: { label?: string; color?: string; style?: string }[], bands: Banda[]) {
  const items: { label: string; color?: string; dash?: boolean; block?: boolean }[] = []
  series.forEach((s) => {
    if (s.label) items.push({ label: s.label, color: s.color, dash: s.style === 'dash' })
  })
  bands.forEach((b) => {
    if (b.label) items.push({ label: b.label, color: b.color || 'teal', block: true })
  })
  if (!items.length) return
  const div = document.createElement('div')
  div.className = 'legend'
  div.innerHTML = items
    .map(
      (i) =>
        '<span class="legend-item"><span class="legend-swatch' +
        (i.dash ? ' dash' : '') +
        '" style="background:' +
        (i.dash ? 'none' : color(i.color)) +
        ';color:' +
        color(i.color) +
        (i.block ? ';opacity:.45;height:8px' : '') +
        '"></span>' +
        i.label +
        '</span>',
    )
    .join('')
  host.appendChild(div)
}

// ------------------------------------------------------------ barChart
export interface BarOpts {
  labels: readonly string[]
  values: readonly Num[]
  color?: string
  colors?: (string | undefined)[]
  height?: number
  padLeft?: number
  padBottom?: number
  unit?: string
  digits?: number
  compact?: boolean
  seriesLabel?: string
}

export function barChart(host: HTMLElement, o: BarOpts): void {
  const labels = o.labels || []
  const values = o.values || []
  if (!labels.length) {
    host.innerHTML = '<div class="empty">Sem dados.</div>'
    return
  }
  const f = frame(host, { height: o.height || 220, padLeft: o.padLeft || 54, padBottom: o.padBottom || 34 })
  let [lo, hi] = extent([values])
  lo = Math.min(0, lo)
  hi = hi + (hi - lo) * 0.1
  const sy = yAxis(f, lo, hi, { compact: o.compact, digits: o.digits })
  const n = labels.length
  const step = (f.x1 - f.x0) / n
  const bw = Math.max(3, step * 0.62)
  labels.forEach((lab, i) => {
    const v = values[i]
    if (!isNum(v)) return
    const cx = f.x0 + step * (i + 0.5)
    const y = sy(Math.max(0, v))
    const h = Math.abs(sy(v) - sy(0))
    const c = color((o.colors && o.colors[i]) || o.color || 'teal')
    const r = el('rect', { x: cx - bw / 2, y, width: bw, height: Math.max(1, h), fill: c, rx: 2, opacity: 0.9 }, f.svg)
    r.addEventListener('mousemove', (ev) => {
      const e = ev as MouseEvent
      showTip(
        '<div class="tt-time">' +
          lab +
          '</div><div class="tt-row"><span class="k">' +
          (o.seriesLabel || 'valor') +
          '</span><span class="v">' +
          fmt(v, o.digits === undefined ? 1 : o.digits) +
          (o.unit ? ' ' + o.unit : '') +
          '</span></div>',
        e.clientX,
        e.clientY,
      )
    })
    r.addEventListener('mouseleave', hideTip)
    if (n <= 24 || i % Math.ceil(n / 14) === 0) {
      const t = el('text', { class: 'tick', x: cx, y: f.y1 + 15, 'text-anchor': 'middle' }, f.svg)
      t.textContent = lab
    }
  })
  el('line', { class: 'axis-line', x1: f.x0, x2: f.x1, y1: sy(0), y2: sy(0) }, f.svg)
}

// ------------------------------------------------------------ stacked
export interface StackOpts {
  labels: readonly string[]
  stacks: { label: string; values: readonly Num[]; color?: string }[]
  height?: number
  padLeft?: number
  unit?: string
}

export function stackedBars(host: HTMLElement, o: StackOpts): void {
  const labels = o.labels || []
  const stacks = o.stacks || []
  if (!labels.length) {
    host.innerHTML = '<div class="empty">Sem dados.</div>'
    return
  }
  const totals = labels.map((_, i) => stacks.reduce((s, st) => s + (st.values[i] || 0), 0))
  const f = frame(host, { height: o.height || 230, padLeft: o.padLeft || 54, padBottom: 34 })
  const hi = Math.max(...totals, 1) * 1.1
  const sy = yAxis(f, 0, hi, { compact: true })
  const n = labels.length
  const step = (f.x1 - f.x0) / n
  const bw = Math.max(3, step * 0.64)
  labels.forEach((lab, i) => {
    let acc = 0
    const cx = f.x0 + step * (i + 0.5)
    stacks.forEach((st) => {
      const v = st.values[i] || 0
      if (v <= 0) return
      const yTop = sy(acc + v)
      const yBot = sy(acc)
      const r = el('rect', { x: cx - bw / 2, y: yTop, width: bw, height: Math.max(1, yBot - yTop), fill: color(st.color), opacity: 0.92 }, f.svg)
      r.addEventListener('mousemove', (ev) => {
        const e = ev as MouseEvent
        showTip(
          '<div class="tt-time">' +
            lab +
            '</div><div class="tt-row"><span class="k"><span class="tt-dot" style="background:' +
            color(st.color) +
            '"></span>' +
            st.label +
            '</span><span class="v">' +
            fmt(v, 1) +
            (o.unit ? ' ' + o.unit : '') +
            '</span></div>',
          e.clientX,
          e.clientY,
        )
      })
      r.addEventListener('mouseleave', hideTip)
      acc += v
    })
    if (n <= 26 || i % Math.ceil(n / 14) === 0) {
      const t = el('text', { class: 'tick', x: cx, y: f.y1 + 15, 'text-anchor': 'middle' }, f.svg)
      t.textContent = lab
    }
  })
  el('line', { class: 'axis-line', x1: f.x0, x2: f.x1, y1: f.y1, y2: f.y1 }, f.svg)
  renderLegend(host, stacks.map((s) => ({ label: s.label, color: s.color })), [])
}

// ------------------------------------------------------------ heatStrip
export interface HeatOpts {
  rows: { label: string; values: readonly Num[] }[]
  cols?: number
  color?: string
  unit?: string
  raw?: (readonly Num[])[]
  padLeft?: number
  cellH?: number
  digits?: number
  seriesLabel?: string
  colLabel?: (c: number) => string
}

export function heatStrip(host: HTMLElement, o: HeatOpts): void {
  const rows = o.rows || []
  if (!rows.length) {
    host.innerHTML = '<div class="empty">Sem dados.</div>'
    return
  }
  host.innerHTML = ''
  const width = Math.max(320, host.clientWidth || 640)
  const padL = o.padLeft || 44
  const padB = 22
  const padT = 4
  const cellH = o.cellH || 17
  const height = padT + rows.length * cellH + padB
  const svg = el('svg', { class: 'chart', viewBox: '0 0 ' + width + ' ' + height, width: '100%', height }, host)
  const cols = o.cols || (rows[0].values || []).length
  const cw = (width - padL - 8) / cols
  const base = color(o.color || 'green')
  rows.forEach((row, r) => {
    const t = el('text', { class: 'tick', x: padL - 6, y: padT + r * cellH + cellH * 0.7, 'text-anchor': 'end' }, svg)
    t.textContent = row.label
    ;(row.values || []).forEach((v, c) => {
      const val = isNum(v) ? v : null
      const rect = el(
        'rect',
        {
          x: padL + c * cw,
          y: padT + r * cellH + 1,
          width: Math.max(1, cw - 1),
          height: cellH - 2,
          rx: 1.5,
          fill: val === null ? css('--o-panel-2') : base,
          opacity: val === null ? 0.4 : Math.max(0.06, Math.min(1, val)),
        },
        svg,
      )
      const shown = o.raw && o.raw[r] ? o.raw[r][c] : val
      rect.addEventListener('mousemove', (ev) => {
        const e = ev as MouseEvent
        showTip(
          '<div class="tt-time">' +
            row.label +
            ' · ' +
            (o.colLabel ? o.colLabel(c) : c + 'h') +
            '</div><div class="tt-row"><span class="k">' +
            (o.seriesLabel || 'valor') +
            '</span><span class="v">' +
            (shown === null || shown === undefined ? '—' : fmt(shown, o.digits === undefined ? 2 : o.digits)) +
            (o.unit ? ' ' + o.unit : '') +
            '</span></div>',
          e.clientX,
          e.clientY,
        )
      })
      rect.addEventListener('mouseleave', hideTip)
    })
  })
  for (let c = 0; c < cols; c += Math.max(1, Math.round(cols / 12))) {
    const t = el('text', { class: 'tick', x: padL + c * cw + cw / 2, y: height - 7, 'text-anchor': 'middle' }, svg)
    t.textContent = o.colLabel ? o.colLabel(c) : c + 'h'
  }
}

// ------------------------------------------------------------ scatter
export interface ScatterOpts {
  points: { x: number; y: number; label?: string; color?: string }[]
  height?: number
  xLabel?: string
  yLabel?: string
  xAxisLabel?: string
  diagonal?: boolean
  xDomain?: [number, number]
  yDomain?: [number, number]
  digits?: number
  xDigits?: number
  r?: number
  color?: string
}

export function scatter(host: HTMLElement, o: ScatterOpts): void {
  const pts = o.points || []
  if (!pts.length) {
    host.innerHTML = '<div class="empty">Sem dados.</div>'
    return
  }
  const f = frame(host, { height: o.height || 230, padLeft: 46, padBottom: 32 })
  const [xlo, xhi] = o.xDomain || extent([pts.map((p) => p.x)])
  const [ylo, yhi] = o.yDomain || extent([pts.map((p) => p.y)])
  const sy = yAxis(f, ylo, yhi, { digits: o.digits === undefined ? 2 : o.digits })
  const sx = (v: number) => f.x0 + ((v - xlo) / (xhi - xlo)) * (f.x1 - f.x0)
  el('line', { class: 'axis-line', x1: f.x0, x2: f.x1, y1: f.y1, y2: f.y1 }, f.svg)
  niceTicks(xlo, xhi, 5).forEach((t) => {
    const tx = el('text', { class: 'tick', x: sx(t), y: f.y1 + 15, 'text-anchor': 'middle' }, f.svg)
    tx.textContent = fmt(t, o.xDigits === undefined ? 2 : o.xDigits)
  })
  if (o.diagonal) {
    el(
      'path',
      {
        class: 'series-dash',
        stroke: color('muted'),
        d: 'M' + sx(Math.max(xlo, ylo)) + ' ' + sy(Math.max(xlo, ylo)) + ' L' + sx(Math.min(xhi, yhi)) + ' ' + sy(Math.min(xhi, yhi)),
      },
      f.svg,
    )
  }
  pts.forEach((p) => {
    const c = el('circle', { cx: sx(p.x), cy: sy(p.y), r: o.r || 4.5, fill: color(p.color || o.color || 'teal'), opacity: 0.85 }, f.svg)
    c.addEventListener('mousemove', (ev) => {
      const e = ev as MouseEvent
      showTip(
        '<div class="tt-time">' +
          (p.label || '') +
          '</div><div class="tt-row"><span class="k">' +
          (o.xLabel || 'x') +
          '</span><span class="v">' +
          fmt(p.x, 3) +
          '</span></div><div class="tt-row"><span class="k">' +
          (o.yLabel || 'y') +
          '</span><span class="v">' +
          fmt(p.y, 3) +
          '</span></div>',
        e.clientX,
        e.clientY,
      )
    })
    c.addEventListener('mouseleave', hideTip)
  })
  if (o.xAxisLabel) {
    const t = el('text', { class: 'tick', x: (f.x0 + f.x1) / 2, y: f.y1 + 28, 'text-anchor': 'middle' }, f.svg)
    t.textContent = o.xAxisLabel
  }
}

// ------------------------------------------------------------ gauge
export interface GaugeOpts {
  value: number
  height?: number
  color?: string
  text?: string
  label?: string
}

export function gauge(host: HTMLElement, o: GaugeOpts): void {
  const v = Math.max(0, Math.min(1, o.value || 0))
  host.innerHTML = ''
  const w = Math.max(120, host.clientWidth || 180)
  const h = o.height || 96
  const svg = el('svg', { class: 'chart', viewBox: '0 0 ' + w + ' ' + h, width: '100%', height: h }, host)
  const cx = w / 2
  const cy = h - 10
  const r = Math.min(w / 2 - 8, h - 22)
  const arc = (frac: number, stroke: string, width: number) => {
    const a0 = Math.PI
    const a1 = Math.PI * (1 - frac)
    const x0 = cx + r * Math.cos(a0)
    const y0 = cy + r * Math.sin(a0) * -1
    const x1 = cx + r * Math.cos(a1)
    const y1 = cy + r * Math.sin(a1) * -1
    el('path', { d: 'M' + x0 + ' ' + y0 + ' A ' + r + ' ' + r + ' 0 0 1 ' + x1 + ' ' + y1, fill: 'none', stroke, 'stroke-width': width, 'stroke-linecap': 'round' }, svg)
  }
  arc(1, css('--o-panel-2'), 9)
  if (v > 0.001) arc(v, color(o.color || 'teal'), 9)
  const t = el('text', { x: cx, y: cy - 8, 'text-anchor': 'middle', fill: color(o.color || 'teal'), style: 'font-size:21px;font-weight:650' }, svg)
  t.textContent = o.text || Math.round(v * 100) + '%'
  if (o.label) {
    const l = el('text', { x: cx, y: cy + 8, 'text-anchor': 'middle', class: 'tick' }, svg)
    l.textContent = o.label
  }
}

export const Charts = { lineChart, barChart, stackedBars, heatStrip, scatter, gauge, fmt, fmtCompact, hhmm, dayHour, color, hideTip, showTip }
