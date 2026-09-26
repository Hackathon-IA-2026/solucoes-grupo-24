/**
 * Identidade visual das razões de constrained-off (REL / CNF / ENE).
 *
 * Razão é CATEGORIA, não nível de risco: usa as cores categóricas de gráfico (chart-*),
 * nunca as de severidade — um "REL" vermelho seria lido como "crítico". Ordem fixa por
 * razão (ENE = chart-1 porque é o foco do Desafio 1), então a mesma razão tem a mesma cor
 * em tabela, gráfico e mapa. Classes por extenso para o Tailwind encontrá-las.
 */
import type { Razao } from '../data/types'

export const RAZAO_INFO: Record<Razao, { nome: string; dot: string; borda: string }> = {
  ENE: { nome: 'Razão energética', dot: 'bg-chart-1', borda: 'border-chart-1/60' },
  CNF: { nome: 'Confiabilidade elétrica', dot: 'bg-chart-2', borda: 'border-chart-2/60' },
  REL: { nome: 'Indisponibilidade externa', dot: 'bg-chart-3', borda: 'border-chart-3/60' },
}
