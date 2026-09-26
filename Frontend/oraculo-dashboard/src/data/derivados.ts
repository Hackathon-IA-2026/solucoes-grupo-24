/**
 * Indicadores DERIVADOS dos dados do contrato (funções puras, testadas em
 * derivados.test.ts). As telas calculam por aqui para que o mesmo KPI nunca tenha duas
 * fórmulas diferentes em telas diferentes.
 */
import type { CargaSnapshot, ExcedenteTsoDso, PontoPrevisao, RiscoUsina, Severidade } from './types'

/**
 * Risco agregado de curtailment (%): média das probabilidades PONDERADA pelo montante (MW).
 * Decisão: ponderar por MW faz uma usina grande com alta probabilidade pesar mais que uma
 * pequena — o que importa para o SIN é a energia em risco, não a contagem de usinas.
 * Lista vazia (ou montante total zero) devolve null: "sem dado" não é "0% de risco".
 */
export function riscoAgregadoPct(riscos: readonly RiscoUsina[]): number | null {
  const totalMw = riscos.reduce((s, r) => s + r.montanteMw, 0)
  if (totalMw <= 0) return null
  return riscos.reduce((s, r) => s + r.probabilidadePct * r.montanteMw, 0) / totalMw
}

/** Montante total em risco (MW). */
export const montanteEmRiscoMw = (riscos: readonly RiscoUsina[]) => riscos.reduce((s, r) => s + r.montanteMw, 0)

/**
 * Limiares probabilidade -> severidade (limite inferior inclusivo). Ajustável só aqui.
 * Faixas iguais de 25 p.p.; provisórias até haver calibração com o classificador real.
 */
const LIMIARES: readonly [number, Severidade][] = [
  [75, 'critical'],
  [50, 'high'],
  [25, 'medium'],
  [0, 'low'],
]

export function severidadePorProbabilidade(pct: number): Severidade {
  return LIMIARES.find(([min]) => pct >= min)?.[1] ?? 'low'
}

/** Parcelas da carga global (MW e % do total) para o gráfico de composição. */
export function composicaoCarga(c: CargaSnapshot) {
  const pct = (mw: number) => (c.cargaGlobalMw > 0 ? (mw / c.cargaGlobalMw) * 100 : 0)
  return [
    { chave: 'supervisionada', mw: c.cargaSupervisionadaMw, pct: pct(c.cargaSupervisionadaMw) },
    { chave: 'mmgd', mw: c.mmgdEstimadaMw, pct: pct(c.mmgdEstimadaMw) },
  ] as const
}

/**
 * Trecho de maior rampa de SUBIDA do P50 numa janela de `janelaHoras` (resolução 30 min).
 * Devolve índices [inicio, fim] nos pontos e a variação em MW; null se a curva for mais
 * curta que a janela. É o mesmo cálculo que define `rampaProjetadaMw` — o teste garante
 * que o trecho destacado no gráfico e o número do rótulo nunca discordam.
 */
export function trechoDeRampa(pontos: readonly PontoPrevisao[], janelaHoras: number) {
  const passos = Math.round(janelaHoras * 2) // 2 passos de 30 min por hora
  let melhor: { inicio: number; fim: number; variacaoMw: number } | null = null
  for (let i = 0; i + passos < pontos.length; i++) {
    const variacaoMw = pontos[i + passos].p50 - pontos[i].p50
    if (!melhor || variacaoMw > melhor.variacaoMw) melhor = { inicio: i, fim: i + passos, variacaoMw }
  }
  return melhor
}

/** Peso de cada severidade na ordenação (maior = mais grave). */
const ORDEM_SEVERIDADE: Record<Severidade, number> = { critical: 3, high: 2, medium: 1, low: 0 }

/** Comparador de severidade (mais grave primeiro), comum a todas as ordenações. */
export const compararSeveridade = (a: Severidade, b: Severidade) => ORDEM_SEVERIDADE[b] - ORDEM_SEVERIDADE[a]

/**
 * Ordena riscos por severidade (critical no topo), depois probabilidade e montante —
 * desempates explícitos para a ordem nunca depender da ordem de chegada dos dados.
 * Devolve cópia; não altera o array recebido.
 */
export function ordenarPorSeveridade(riscos: readonly RiscoUsina[]): RiscoUsina[] {
  return [...riscos].sort(
    (a, b) =>
      compararSeveridade(a.severidade, b.severidade) ||
      b.probabilidadePct - a.probabilidadePct ||
      b.montanteMw - a.montanteMw ||
      a.id.localeCompare(b.id),
  )
}

/** Excedentes por prioridade (high no topo), depois maior excedente e nome da área. */
export function ordenarExcedentes(excedentes: readonly ExcedenteTsoDso[]): ExcedenteTsoDso[] {
  return [...excedentes].sort(
    (a, b) =>
      compararSeveridade(a.prioridade, b.prioridade) ||
      b.excedenteMw - a.excedenteMw ||
      a.areaConcessao.localeCompare(b.areaConcessao),
  )
}
