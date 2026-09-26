import { OPERATIONAL_STATUSES, RISK_STYLES, STATUS_RISK } from '../../theme/severity'
import { useSeverityFilter } from '../../state/useSeverityFilter'
import { ToggleChip } from '../ui/ToggleChip'

/**
 * Filtros NORMAL / LOADING / CRITICAL / NO-RISK. Cada botão liga/desliga um status;
 * desligado fica apagado e riscado (ToggleChip), legível à distância como num console.
 */
export function SeverityFilters() {
  const { isActive, toggle } = useSeverityFilter()

  return (
    <div role="group" aria-label="Filtros de severidade" className="flex items-center gap-1.5">
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
