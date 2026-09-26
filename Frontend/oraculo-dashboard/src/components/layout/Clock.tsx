import { useEffect, useState } from 'react'

/**
 * Relógio do canto direito da barra superior.
 *
 * Decisão: exibe sempre o horário de Brasília (America/Sao_Paulo), o mesmo referencial
 * das bases do ONS, independente do fuso do navegador de quem está olhando.
 * Hora numa linha e data abreviada embaixo (padrão do Figma), ambas sem quebra.
 */
const FUSO = 'America/Sao_Paulo'
const fmtData = new Intl.DateTimeFormat('pt-BR', { timeZone: FUSO, weekday: 'short', day: '2-digit', month: '2-digit', year: 'numeric' })
const fmtHora = new Intl.DateTimeFormat('pt-BR', { timeZone: FUSO, hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })

export function Clock() {
  const [agora, setAgora] = useState(() => new Date())

  useEffect(() => {
    const id = window.setInterval(() => setAgora(new Date()), 1000)
    return () => window.clearInterval(id)
  }, [])

  return (
    <time dateTime={agora.toISOString()} className="kpi flex flex-col items-end whitespace-nowrap leading-tight">
      <span className="text-[15px] font-semibold text-ink">{fmtHora.format(agora)}</span>
      {/* "sáb., 26/09/2026" -> "SÁB 26/09/2026" */}
      <span className="text-[10px] uppercase tracking-wider text-ink-faint">
        {fmtData.format(agora).replace('.,', '').replace(',', '')} · BRT
      </span>
    </time>
  )
}
