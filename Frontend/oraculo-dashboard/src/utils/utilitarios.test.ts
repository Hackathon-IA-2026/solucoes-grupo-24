/**
 * Testes das peças compartilhadas da revisão das telas (2026-09-26): CSV, busca/ordenação,
 * geometria do mapa e resumos da curva/validação.
 */
import { describe, expect, it } from 'vitest'
import ufsGeo from '../data/geo/ufs.geo.json'
import { getPrevisao, getValidacao } from '../data/dataSource'
import { resumoCurva, resumoPatamar, resumoValidacao } from '../data/derivados'
import { lerSelecaoMapa, rotaMapa } from '../modules'
import { paraCsv } from './csv'
import { offsetsEmAnel, ufDoPonto, type ColecaoUfs } from './geo'
import { casaBusca, ordenar, porHorizonte } from './ordenacao'

describe('CSV', () => {
  it('separador ;, decimal com vírgula e escape de aspas/;', () => {
    const csv = paraCsv(
      [
        { rotulo: 'nome', valor: (l: { n: string; v: number }) => l.n },
        { rotulo: 'valor', valor: (l) => l.v },
      ],
      [{ n: 'Conj. "Caju"; RN', v: 99.1 }],
    )
    expect(csv).toBe('nome;valor\r\n"Conj. ""Caju""; RN";99,1\r\n')
  })
})

describe('busca e ordenação', () => {
  it('busca sem acento e com vários termos em qualquer ordem', () => {
    expect(casaBusca('piaui solar', ['Chapada Gaúcha Solar', 'Piauí'])).toBe(true)
    expect(casaBusca('rn eolica', ['Conj. Caju', 'RN', 'Eólica'])).toBe(true)
    expect(casaBusca('bahia', ['Conj. Caju', 'RN'])).toBe(false)
    expect(casaBusca('   ', ['qualquer'])).toBe(true)
  })

  it('horizontes em ordem natural (não alfabética)', () => {
    expect(['D+1', '3h', '30min', '1h'].sort(porHorizonte)).toEqual(['30min', '1h', '3h', 'D+1'])
  })

  it('ordenar respeita a direção e não altera a entrada', () => {
    const itens = [{ v: 2 }, { v: 3 }, { v: 1 }]
    const cmp = { v: (a: { v: number }, b: { v: number }) => a.v - b.v }
    expect(ordenar(itens, cmp, { chave: 'v', direcao: 'desc' }).map((i) => i.v)).toEqual([3, 2, 1])
    expect(itens.map((i) => i.v)).toEqual([2, 3, 1])
  })
})

describe('mapa', () => {
  const ufs = ufsGeo as unknown as ColecaoUfs

  it('UF de um ponto pela malha do IBGE', () => {
    expect(ufDoPonto(-5.79, -35.21, ufs)).toBe('RN') // Natal
    expect(ufDoPonto(-15.6, -56.1, ufs)).toBe('MT') // Cuiabá
    expect(ufDoPonto(-23.55, -46.63, ufs)).toBe('SP') // São Paulo
    expect(ufDoPonto(-20, -30, ufs)).toBeNull() // Atlântico
  })

  it('anel: um marcador fica no centro; vários ficam equidistantes e sem encostar', () => {
    expect(offsetsEmAnel(1)).toEqual([[0, 0]])
    const anel = offsetsEmAnel(10, 18, 30)
    const raios = anel.map(([x, y]) => Math.hypot(x, y))
    expect(Math.max(...raios) - Math.min(...raios)).toBeLessThan(1e-9)
    const dist = Math.hypot(anel[0][0] - anel[1][0], anel[0][1] - anel[1][1])
    expect(dist).toBeGreaterThanOrEqual(29) // corda entre vizinhos ≈ espaço pedido
  })

  it('seleção do mapa na URL: ida e volta', () => {
    const sel = { tipo: 'excedente' as const, id: 'Bahia Costa|NEOENERGIA BA' }
    const valor = new URL(`http://x${rotaMapa(sel)}`).searchParams.get('sel')
    expect(lerSelecaoMapa(valor)).toEqual(sel)
    expect(lerSelecaoMapa('lixo')).toBeNull()
    expect(lerSelecaoMapa(null)).toBeNull()
  })
})

describe('resumos', () => {
  it('resumo da curva: mín ≤ máx, amplitude = máx − mín, banda positiva', async () => {
    for (const c of await getPrevisao()) {
      const r = resumoCurva(c.pontos)!
      expect(r.minimo.mw).toBeLessThanOrEqual(r.maximo.mw)
      expect(r.amplitudeMw).toBeCloseTo(r.maximo.mw - r.minimo.mw)
      expect(r.bandaMediaMw).toBeGreaterThan(0)
    }
    expect(resumoCurva([])).toBeNull()
  })

  it('resumo do patamar só com pontos dentro das horas', async () => {
    const d1 = (await getPrevisao()).find((c) => c.horizonte === 'D+1')!
    const r = resumoPatamar(d1.pontos, [9, 16])!
    expect(r.pontos).toBe(14) // 09:00..15:30 = 14 semi-horas
    expect(resumoPatamar(d1.pontos.slice(0, 2), [19, 22])).toBeNull()
  })

  it('resumo da validação conta os dias em que o modelo venceu o baseline', async () => {
    const v = await getValidacao()
    const r = resumoValidacao(v.historicoErro30d, 7)!
    expect(r.dias).toBe(7)
    const janela = v.historicoErro30d.slice(-7)
    expect(r.diasMelhorQueBaseline).toBe(janela.filter((h) => h.mae < h.maeBaseline).length)
    expect(r.piorDia.mae).toBe(Math.max(...janela.map((h) => h.mae)))
  })
})
