/**
 * Formatação de números e horários para exibição (pt-BR). Único lugar que decide casas
 * decimais e unidades, para que "31,8 GW" apareça igual em todas as telas.
 */
const FUSO_EXIBICAO = 'America/Sao_Paulo' // mesmo referencial do relógio da topbar

const nf = (casas: number) =>
  new Intl.NumberFormat('pt-BR', { minimumFractionDigits: casas, maximumFractionDigits: casas })

/** 31804 -> "31.804" */
export const formatMw = (mw: number) => nf(0).format(mw)

/** 31804 -> "31,8" (valor em GW, 1 casa) */
export const formatGw = (mw: number) => nf(1).format(mw / 1000)

/** número genérico com `casas` decimais: 8.4 -> "8,4" */
export const formatNum = (v: number, casas = 1) => nf(casas).format(v)

/** 44.8 -> "44,8" (percentual já em 0–100; o "%" fica com quem exibe) */
export const formatPct = formatNum

const fmtHora = new Intl.DateTimeFormat('pt-BR', { timeZone: FUSO_EXIBICAO, hour: '2-digit', minute: '2-digit', hour12: false })
const fmtDataHora = new Intl.DateTimeFormat('pt-BR', {
  timeZone: FUSO_EXIBICAO, day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false,
})

/** ISO UTC -> "14:30" em BRT */
export const formatHoraBrt = (isoUtc: string) => fmtHora.format(new Date(isoUtc))

/** ISO UTC -> "25/09 14:30" em BRT */
export const formatDataHoraBrt = (isoUtc: string) => fmtDataHora.format(new Date(isoUtc))

/** Tempo decorrido legível: "há 12 min", "há 5 h", "há 3 dias". */
export function formatHaQuanto(isoUtc: string, agora: Date = new Date()): string {
  const min = Math.max(0, Math.floor((agora.getTime() - Date.parse(isoUtc)) / 60000))
  if (min < 60) return `há ${min} min`
  const h = Math.floor(min / 60)
  if (h < 48) return `há ${h} h`
  return `há ${Math.floor(h / 24)} dias`
}
