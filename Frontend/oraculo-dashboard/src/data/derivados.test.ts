import { describe, expect, it } from 'vitest'
import { getCarga, getExcedentes, getPrevisao, getRiscos } from './dataSource'
import { composicaoCarga, ordenarExcedentes, ordenarPorSeveridade, riscoAgregadoPct, severidadePorProbabilidade, trechoDeRampa } from './derivados'

describe('derivados', () => {
  it('risco agregado = média das probabilidades ponderada por MW', async () => {
    // (87·312 + 64·249 + 45·98 + 42·134 + 38·67 + 24·120 + 21·52) / 1032 = 59636 / 1032
    expect(riscoAgregadoPct(await getRiscos())).toBeCloseTo(59636 / 1032, 6)
  })

  it('sem riscos -> null (não 0%)', () => {
    expect(riscoAgregadoPct([])).toBeNull()
  })

  it('limiares de severidade', () => {
    expect([0, 24.9, 25, 49.9, 50, 74.9, 75, 100].map(severidadePorProbabilidade)).toEqual([
      'low', 'low', 'medium', 'medium', 'high', 'high', 'critical', 'critical',
    ])
  })

  it('composição da carga fecha 100% da carga global', async () => {
    const partes = composicaoCarga(await getCarga())
    expect(partes.reduce((s, p) => s + p.pct, 0)).toBeCloseTo(100, 6)
  })

  it('trecho de rampa bate com rampaProjetadaMw de cada curva', async () => {
    for (const c of await getPrevisao()) {
      const t = trechoDeRampa(c.pontos, c.janelaRampaHoras)
      expect(t, c.horizonte).not.toBeNull()
      expect(t!.variacaoMw).toBe(c.rampaProjetadaMw)
      expect(t!.fim - t!.inicio).toBe(c.janelaRampaHoras * 2)
    }
  })

  it('curva mais curta que a janela -> null', () => {
    expect(trechoDeRampa([{ timestamp: '2026-09-25T18:00:00Z', p10: 1, p50: 2, p90: 3 }], 3)).toBeNull()
  })

  it('ordenação: severidade primeiro, depois probabilidade', async () => {
    const riscos = await getRiscos()
    const base = riscos[0]
    // caso construído: severidade vence probabilidade
    const alto = { ...base, id: 'a', severidade: 'high' as const, probabilidadePct: 10 }
    const medio = { ...base, id: 'b', severidade: 'medium' as const, probabilidadePct: 99 }
    expect(ordenarPorSeveridade([medio, alto]).map((r) => r.id)).toEqual(['a', 'b'])

    const ordem = ordenarPorSeveridade(riscos).map((r) => r.severidade)
    expect(ordem).toEqual(['critical', 'high', 'medium', 'medium', 'low', 'low', 'low'])
  })

  it('excedentes: prioridade, depois MW', async () => {
    const e = ordenarExcedentes(await getExcedentes())
    expect(e.map((x) => [x.prioridade, x.excedenteMw])).toEqual([
      ['high', 245],
      ['high', 189],
      ['medium', 134],
      ['medium', 98],
      ['low', 67],
    ])
  })
})
