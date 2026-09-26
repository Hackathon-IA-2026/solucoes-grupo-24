/**
 * Fonte ÚNICA das severidades do dashboard.
 *
 * Dois conceitos distintos, deliberadamente separados:
 * - RiskLevel: escala de risco dos dados (baixo → crítico), usada em badges, mapas e listas.
 * - OperationalStatus: os filtros da barra superior (NORMAL / LOADING / CRITICAL / NO-RISK).
 *
 * Cada status aponta para um RiskLevel (ou "none"), então a cor de um filtro e a de um
 * badge nunca divergem. As classes Tailwind ficam escritas por extenso (e não montadas com
 * template string) porque o Tailwind só gera utilitários que encontra literalmente no código.
 */

export type RiskLevel = 'low' | 'medium' | 'high' | 'critical' | 'none'

interface RiskStyle {
  label: string
  /** texto + borda + fundo translúcido (badge/pill) */
  chip: string
  /** ponto sólido indicador */
  dot: string
  /** borda esquerda grossa (blocos de destaque, ex.: texto do alerta) */
  barra: string
  /** nome da CSS var da cor (para canvas/Leaflet, que não usam classes Tailwind) */
  token: string
}

export const RISK_STYLES: Record<RiskLevel, RiskStyle> = {
  low: {
    label: 'Baixo',
    chip: 'text-risk-low border-risk-low/40 bg-risk-low/10',
    dot: 'bg-risk-low',
    barra: 'border-l-risk-low',
    token: '--color-risk-low',
  },
  medium: {
    label: 'Médio',
    chip: 'text-risk-medium border-risk-medium/40 bg-risk-medium/10',
    dot: 'bg-risk-medium',
    barra: 'border-l-risk-medium',
    token: '--color-risk-medium',
  },
  high: {
    label: 'Alto',
    chip: 'text-risk-high border-risk-high/40 bg-risk-high/10',
    dot: 'bg-risk-high',
    barra: 'border-l-risk-high',
    token: '--color-risk-high',
  },
  critical: {
    label: 'Crítico',
    chip: 'text-risk-critical border-risk-critical/40 bg-risk-critical/10',
    dot: 'bg-risk-critical',
    barra: 'border-l-risk-critical',
    token: '--color-risk-critical',
  },
  none: {
    label: 'Sem risco',
    chip: 'text-ink-muted border-risk-none/40 bg-risk-none/10',
    dot: 'bg-risk-none',
    barra: 'border-l-risk-none',
    token: '--color-risk-none',
  },
}

/** Filtros de severidade da barra superior, na ordem em que aparecem. */
export const OPERATIONAL_STATUSES = ['NORMAL', 'LOADING', 'CRITICAL', 'NO-RISK'] as const
export type OperationalStatus = (typeof OPERATIONAL_STATUSES)[number]

/**
 * Decisão de mapeamento status → cor (ajustável só aqui):
 * - NORMAL: operação dentro do esperado → verde (baixo).
 * - LOADING: carregamento elevado da rede, atenção → âmbar (médio).
 * - CRITICAL: corte iminente/ativo → vermelho (crítico).
 * - NO-RISK: ativo sem exposição a curtailment → neutro.
 * O laranja (alto) fica reservado para a escala de risco dos dados.
 */
export const STATUS_RISK: Record<OperationalStatus, RiskLevel> = {
  NORMAL: 'low',
  LOADING: 'medium',
  CRITICAL: 'critical',
  'NO-RISK': 'none',
}
