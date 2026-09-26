import { describe, expect, it } from 'vitest'
import { ticksRedondos } from './escala'

describe('ticksRedondos', () => {
  it('erro em MW: passos redondos a partir de zero', () => {
    const { dominio, ticks } = ticksRedondos(0, 1722)
    expect(dominio[0]).toBe(0)
    expect(dominio[1]).toBeGreaterThanOrEqual(1722)
    ticks.forEach((t) => expect(t % 250).toBe(0))
  })

  it('carga em MW: cobre min e max com passo 1/2/2,5/5 × 10^n', () => {
    const { dominio, ticks } = ticksRedondos(24000, 61000)
    expect(dominio[0]).toBeLessThanOrEqual(24000)
    expect(dominio[1]).toBeGreaterThanOrEqual(61000)
    const passo = ticks[1] - ticks[0]
    expect([5000, 10000]).toContain(passo)
  })
})
