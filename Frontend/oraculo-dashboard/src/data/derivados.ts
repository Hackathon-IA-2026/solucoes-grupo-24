/**
 * Indicadores DERIVADOS dos dados do contrato (funções puras, testadas em
 * derivados.test.ts). As telas calculam por aqui para que o mesmo KPI nunca tenha duas
 * fórmulas diferentes em telas diferentes.
 */
import { SEVERIDADE_STATUS, type OperationalStatus } from '../theme/severity'
import { horaDecimalBrt } from '../utils/format'
import type { CargaSnapshot, ExcedenteTsoDso, PontoPrevisao, Razao, RiscoUsina, Severidade } from './types'

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

/**
 * Trechos CONTÍGUOS da curva cujos pontos caem num intervalo de horas BRT [ini, fim)
 * (patamar da curva de carga). Devolve índices [inicio, fim] inclusivos; uma curva D+1 que
 * começa às 21h e passa pela ponta de novo no fim gera dois trechos, nunca um só atravessando
 * a madrugada.
 */
export function trechosNoIntervalo(
  pontos: readonly PontoPrevisao[],
  [ini, fim]: readonly [number, number],
): { inicio: number; fim: number }[] {
  const trechos: { inicio: number; fim: number }[] = []
  pontos.forEach((p, i) => {
    const h = horaDecimalBrt(p.timestamp)
    if (h < ini || h >= fim) return
    const ultimo = trechos.at(-1)
    if (ultimo && ultimo.fim === i - 1) ultimo.fim = i
    else trechos.push({ inicio: i, fim: i })
  })
  return trechos
}

/**
 * Aplica os filtros de severidade da topbar a uma lista. Devolve também quantos itens ficaram
 * ocultos: as telas mostram esse número, para dado filtrado nunca parecer dado inexistente.
 */
export function filtrarPorSeveridade<T>(
  itens: readonly T[],
  severidade: (item: T) => Severidade,
  ativos: ReadonlySet<OperationalStatus>,
): { visiveis: T[]; ocultos: number } {
  const visiveis = itens.filter((it) => ativos.has(SEVERIDADE_STATUS[severidade(it)]))
  return { visiveis, ocultos: itens.length - visiveis.length }
}

/**
 * Resumo de uma curva prevista (painel "Resumo da curva" do Despacho e cabeçalho da curva na
 * Visão Geral): mínima e máxima do P50 com o instante, amplitude (máx − mín, a "amplitude
 * diária" do PAR/PEL) e incerteza (largura P90 − P10, média e máxima). null para curva vazia.
 */
export function resumoCurva(pontos: readonly PontoPrevisao[]) {
  if (!pontos.length) return null
  let iMin = 0
  let iMax = 0
  let iBanda = 0
  let somaBanda = 0
  pontos.forEach((p, i) => {
    if (p.p50 < pontos[iMin].p50) iMin = i
    if (p.p50 > pontos[iMax].p50) iMax = i
    const banda = p.p90 - p.p10
    somaBanda += banda
    if (banda > pontos[iBanda].p90 - pontos[iBanda].p10) iBanda = i
  })
  return {
    minimo: { mw: pontos[iMin].p50, timestamp: pontos[iMin].timestamp },
    maximo: { mw: pontos[iMax].p50, timestamp: pontos[iMax].timestamp },
    amplitudeMw: pontos[iMax].p50 - pontos[iMin].p50,
    bandaMediaMw: somaBanda / pontos.length,
    bandaMaxima: { mw: pontos[iBanda].p90 - pontos[iBanda].p10, timestamp: pontos[iBanda].timestamp },
  }
}

/**
 * P50 e largura de banda médios dentro de um patamar (horas BRT [ini, fim)), sobre todos os
 * trechos da curva que caem nele. null se a curva não passa pelo patamar.
 */
export function resumoPatamar(pontos: readonly PontoPrevisao[], horas: readonly [number, number]) {
  const idx = trechosNoIntervalo(pontos, horas).flatMap((t) =>
    Array.from({ length: t.fim - t.inicio + 1 }, (_, k) => t.inicio + k),
  )
  if (!idx.length) return null
  const media = (f: (p: PontoPrevisao) => number) => idx.reduce((s, i) => s + f(pontos[i]), 0) / idx.length
  return { p50MedioMw: media((p) => p.p50), bandaMediaMw: media((p) => p.p90 - p.p10), pontos: idx.length }
}

/**
 * Resumo do erro diário num período (tela Validação): médias do modelo e do baseline, em
 * quantos dias o modelo errou menos e o pior dia do modelo. Usa os últimos `dias` do histórico.
 */
export function resumoValidacao(
  historico: readonly { data: string; mae: number; maeBaseline: number }[],
  dias: number,
) {
  const janela = historico.slice(-dias)
  if (!janela.length) return null
  const media = (f: (h: (typeof janela)[number]) => number) => janela.reduce((s, h) => s + f(h), 0) / janela.length
  const pior = janela.reduce((a, h) => (h.mae > a.mae ? h : a))
  return {
    dias: janela.length,
    maeMedio: media((h) => h.mae),
    maeBaselineMedio: media((h) => h.maeBaseline),
    diasMelhorQueBaseline: janela.filter((h) => h.mae < h.maeBaseline).length,
    piorDia: { data: pior.data, mae: pior.mae },
  }
}

/** Contagem por categoria, na ordem das chaves informadas (zero para categoria ausente). */
export function contarPor<T, K extends string>(itens: readonly T[], chave: (t: T) => K, chaves: readonly K[]): Record<K, number> {
  const c = Object.fromEntries(chaves.map((k) => [k, 0])) as Record<K, number>
  for (const it of itens) c[chave(it)] = (c[chave(it)] ?? 0) + 1
  return c
}

/** Montante previsto (MW) por razão, com zero para razão sem risco (ordem fixa ENE, CNF, REL). */
export function montantePorRazao(riscos: readonly RiscoUsina[]): Record<Razao, number> {
  const total: Record<Razao, number> = { ENE: 0, CNF: 0, REL: 0 }
  for (const r of riscos) total[r.razao] += r.montanteMw
  return total
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
