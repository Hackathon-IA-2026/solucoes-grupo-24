import { OPERATIONAL_STATUSES, RISK_STYLES, STATUS_RISK } from '../../theme/severity'
import { useSeverityFilter } from '../../state/useSeverityFilter'
import { ToggleChip } from '../ui/ToggleChip'

/**
 * Filtros NORMAL / LOADING / CRITICAL / NO-RISK. Cada botão liga/desliga um status;
 * desligado fica apagado e riscado (ToggleChip), legível à distância como num console.
 *
 * Os filtros AGEM nas telas com listas de risco (Visão Geral, Mapa Híbrido, Lista de Riscos,
 * Excedentes): a correspondência severidade → filtro está em SEVERIDADE_STATUS
 * (theme/severity.ts) e a filtragem em filtrarPorSeveridade() (data/derivados.ts).
 */
export function SeverityFilters() {
  const { isActive, toggle } = useSeverityFilter()

  return (
    <div
      role="group"
      aria-label="Filtros de severidade"
      className="hidden items-center gap-1 rounded-sm border border-line bg-fundo p-0.5 md:flex"
    >
      {OPERATIONAL_STATUSES.map((status) => {
        const s = RISK_STYLES[STATUS_RISK[status]]
        return (
          <ToggleChip
            key={status}
            label={status}
            ativo={isActive(status)}
            onToggle={() => toggle(status)}
            classeAtivo={s.chip}
            classePonto={s.dot}
          />
        )
      })}
    </div>
  )
}
