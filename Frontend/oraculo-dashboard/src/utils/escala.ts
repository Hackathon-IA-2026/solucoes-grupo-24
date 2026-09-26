/**
 * Ticks "redondos" para eixos de gráfico. O Recharts divide o intervalo em partes iguais e
 * gera ticks como 350/1.050 MW ou 34/43/52 GW; aqui o passo é sempre 1, 2, 2,5 ou 5 × 10^n.
 * Todos os gráficos usam esta função (uma regra de eixo só).
 */
export function ticksRedondos(min: number, max: number, alvo = 5): { dominio: [number, number]; ticks: number[] } {
  const bruto = (max - min) / Math.max(1, alvo - 1) || 1
  const mag = 10 ** Math.floor(Math.log10(bruto))
  const passo = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((p) => p >= bruto) ?? 10 * mag
  const ini = Math.floor(min / passo) * passo
  const fim = Math.ceil(max / passo) * passo
  const ticks: number[] = []
  // arredonda cada tick para não acumular erro de ponto flutuante (0,1 + 0,2...)
  for (let t = ini; t <= fim + passo / 2; t += passo) ticks.push(Math.round(t * 1e6) / 1e6)
  return { dominio: [ini, fim], ticks }
}
