import { useEffect, useState } from 'react'

/**
 * Relógio do canto direito da barra superior.
 *
 * Decisão: exibe sempre o horário de Brasília (America/Sao_Paulo), o mesmo referencial
 * das bases do ONS, independente do fuso do navegador de quem está olhando.
 */
const FUSO = 'America/Sao_Paulo'
const fmtData = new Intl.DateTimeFormat('pt-BR', { timeZone: FUSO, day: '2-digit', month: '2-digit', year: 'numeric' })
const fmtHora = new Intl.DateTimeFormat('pt-BR', { timeZone: FUSO, hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })

export function Clock() {
  const [agora, setAgora] = useState(() => new Date())

  useEffect(() => {
    const id = window.setInterval(() => setAgora(new Date()), 1000)
    return () => window.clearInterval(id)
  }, [])

  return (
    <time dateTime={agora.toISOString()} className="kpi flex flex-col items-end leading-tight">
      <span className="text-lg font-semibold text-accent">{fmtHora.format(agora)}</span>
      <span className="text-[11px] text-ink-muted">{fmtData.format(agora)} · BRT</span>
    </time>
  )
}
