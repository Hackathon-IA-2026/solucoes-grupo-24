/**
 * Testes das derivações usadas pela revisão de design de 2026-09-26: patamares na curva,
 * filtros de severidade da topbar e totais por razão.
 */
import { readFileSync } from 'node:fs'
import { parse } from 'yaml'
import { describe, expect, it } from 'vitest'
import { FAIXAS_CURTAILMENT, PATAMARES } from '../content/calendario'
import { OPERATIONAL_STATUSES, SEVERIDADE_STATUS, type OperationalStatus } from '../theme/severity'
import { horaDecimalBrt } from '../utils/format'
import { getRiscos } from './dataSource'
import { filtrarPorSeveridade, montanteEmRiscoMw, montantePorRazao, trechosNoIntervalo } from './derivados'
import { SeveridadeSchema, type PontoPrevisao } from './types'

/** Curva sintética de `n` pontos de 30 min começando em `inicioUtc` (valores irrelevantes). */
function curva(inicioUtc: string, n: number): PontoPrevisao[] {
  const t0 = Date.parse(inicioUtc)
  return Array.from({ length: n }, (_, i) => ({
    timestamp: new Date(t0 + i * 30 * 60_000).toISOString().replace('.000Z', 'Z'),
    p10: 1,
    p50: 2,
    p90: 3,
  }))
}

describe('patamares (fonte única: Backend/config/processamento.yaml)', () => {
  it('o dashboard usa exatamente os horários da config do Backend', () => {
    const yaml = parse(readFileSync(new URL('../../../../Backend/config/processamento.yaml', import.meta.url), 'utf-8'))
    for (const p of PATAMARES) expect(p.horas, p.chave).toEqual(yaml.calendario.patamares[p.chave])
    expect(FAIXAS_CURTAILMENT.map((f) => f.rotulo)).toEqual(Object.keys(yaml.calendario.faixas_curtailment))
  })

  it('hora decimal em BRT (UTC−3)', () => {
    expect(horaDecimalBrt('2026-09-26T12:00:00Z')).toBe(9)
    expect(horaDecimalBrt('2026-09-26T02:30:00Z')).toBe(23.5)
    expect(horaDecimalBrt('2026-09-26T03:00:00Z')).toBe(0) // meia-noite BRT nunca vira 24
  })

  it('trecho da mínima diurna [9, 16): 09:00 até 15:30 BRT, inclusive', () => {
    // começa 00:00 BRT (03:00 UTC), 48 pontos = um dia
    const pts = curva('2026-09-26T03:00:00Z', 48)
    expect(trechosNoIntervalo(pts, [9, 16])).toEqual([{ inicio: 18, fim: 31 }])
  })

  it('curva que passa duas vezes pelo patamar gera dois trechos (nunca um atravessando a madrugada)', () => {
    // começa 20:00 BRT (23:00 UTC) e vai até 21:30 BRT do dia seguinte
    const pts = curva('2026-09-26T23:00:00Z', 52)
    const t = trechosNoIntervalo(pts, [19, 22])
    expect(t).toHaveLength(2)
    expect(t[0]).toEqual({ inicio: 0, fim: 3 }) // 20:00–21:30
    expect(horaDecimalBrt(pts[t[1].inicio].timestamp)).toBe(19)
  })
})

describe('filtros de severidade da topbar', () => {
  it('toda severidade do contrato tem um filtro que a controla', () => {
    for (const s of SeveridadeSchema.options) expect(OPERATIONAL_STATUSES).toContain(SEVERIDADE_STATUS[s])
  })

  it('todos ligados: nada oculto', async () => {
    const riscos = await getRiscos()
    const r = filtrarPorSeveridade(riscos, (x) => x.severidade, new Set(OPERATIONAL_STATUSES))
    expect(r.visiveis).toHaveLength(riscos.length)
    expect(r.ocultos).toBe(0)
  })

  it('desligar CRITICAL esconde alto e crítico, e conta os ocultos', async () => {
    const riscos = await getRiscos()
    const ativos = new Set<OperationalStatus>(['NORMAL', 'LOADING', 'NO-RISK'])
    const r = filtrarPorSeveridade(riscos, (x) => x.severidade, ativos)
    expect(r.visiveis.some((x) => x.severidade === 'high' || x.severidade === 'critical')).toBe(false)
    expect(r.visiveis.length + r.ocultos).toBe(riscos.length)
    expect(r.ocultos).toBe(riscos.filter((x) => x.severidade === 'high' || x.severidade === 'critical').length)
  })
})

describe('montante por razão', () => {
  it('soma por razão fecha o montante total e razão sem risco vale 0', async () => {
    const riscos = await getRiscos()
    const por = montantePorRazao(riscos)
    expect(por.ENE + por.CNF + por.REL).toBe(montanteEmRiscoMw(riscos))
    expect(montantePorRazao([])).toEqual({ ENE: 0, CNF: 0, REL: 0 })
  })
})
