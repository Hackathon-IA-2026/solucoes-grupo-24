/**
 * Decomposição SHAP em barras horizontais DIVERGENTES a partir de um eixo central:
 * à direita (quente) o que aumenta a probabilidade de curtailment, à esquerda (frio) o que
 * reduz. Comprimento = peso relativo da variável.
 *
 * Decisões (guia de dataviz):
 * - Polaridade usa o par divergente shap-up/shap-down, não cores de risco nem de razão.
 * - Identidade nunca só por cor: sinal "+/−" no rótulo de valor e legenda com seta.
 * - Escala pelo MAIOR peso (a maior barra ocupa a meia-largura toda) para as diferenças
 *   entre variáveis ficarem legíveis; o valor exato vai no rótulo.
 * - HTML puro (sem Recharts): são poucas barras estáticas, e assim a tela não baixa a lib.
 */
import type { ShapValue } from '../../data/types'
import { formatPct } from '../../utils/format'

export function BarrasShap({ valores }: { valores: readonly ShapValue[] }) {
  const maxPeso = Math.max(...valores.map((v) => v.peso), 0.0001)
  return (
    <figure>
      <ul className="space-y-2" aria-label="Contribuição de cada variável para a probabilidade">
        {valores.map((v) => {
          const larg = `${(v.peso / maxPeso) * 100}%`
          const sobe = v.direcao === 'aumenta'
          const rotulo = `${sobe ? '+' : '−'}${formatPct(v.peso * 100)}%`
          return (
            <li
              key={v.variavel}
              title={`${v.variavel}: ${sobe ? 'aumenta' : 'reduz'} o risco (${rotulo} do peso total)`}
              className="grid grid-cols-[minmax(9rem,14rem)_1fr_1fr] items-center gap-x-0 rounded px-1 py-1 hover:bg-surface-raised"
            >
              <span className="truncate pr-3 text-body text-ink-muted">{v.variavel}</span>
              {/* metade esquerda: "reduz" cresce da direita (eixo) para a esquerda */}
              <div className="flex h-5 items-center justify-end border-r border-ink-faint">
                {!sobe && (
                  <>
                    <span className="kpi mr-2 text-xs text-ink">{rotulo}</span>
                    <div className="h-full rounded-l bg-shap-down" style={{ width: larg }} />
                  </>
                )}
              </div>
              {/* metade direita: "aumenta" cresce do eixo para a direita */}
              <div className="flex h-5 items-center">
                {sobe && (
                  <>
                    <div className="h-full rounded-r bg-shap-up" style={{ width: larg }} />
                    <span className="kpi ml-2 text-xs text-ink">{rotulo}</span>
                  </>
                )}
              </div>
            </li>
          )
        })}
      </ul>
      <figcaption className="mt-4 flex flex-wrap justify-end gap-x-6 gap-y-1 text-xs text-ink-muted">
        <span className="flex items-center gap-2">
          <span className="size-2.5 rounded-sm bg-shap-down" aria-hidden /> ▼ reduz o risco
        </span>
        <span className="flex items-center gap-2">
          <span className="size-2.5 rounded-sm bg-shap-up" aria-hidden /> ▲ aumenta o risco
        </span>
      </figcaption>
    </figure>
  )
}
