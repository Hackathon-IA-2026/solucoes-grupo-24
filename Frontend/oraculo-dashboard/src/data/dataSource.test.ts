/**
 * Testes do contrato mockado: todo JSON passa no schema, está marcado como mock e os
 * seeds pedidos estão exatamente como especificados.
 */
import { describe, expect, it } from 'vitest'
import {
  DATA_SOURCE_MODE,
  DataSourceError,
  getAlerta,
  getCarga,
  getDensidadeMmgd,
  getExcedentes,
  getPrevisao,
  getRiscos,
  getValidacao,
  validar,
} from './dataSource'
import { CargaSnapshotSchema, PontoPrevisaoSchema, RiscoUsinaSchema } from './types'

describe('dataSource (modo mock)', () => {
  it("roda em modo mock nos testes (vite.config.ts: test.env)", () => {
    expect(DATA_SOURCE_MODE).toBe('mock')
  })

  it('carga: seed exato e coerente (global − MMGD = supervisionada)', async () => {
    const c = await getCarga()
    expect(c).toMatchObject({
      mock: true,
      cargaGlobalMw: 57973,
      mmgdEstimadaMw: 26169,
      cargaSupervisionadaMw: 31804,
      percentualMmgdNaGeracao: 44.8,
    })
  })

  it('previsão: três horizontes, filtro por horizonte', async () => {
    const todas = await getPrevisao()
    expect(todas.map((c) => c.horizonte)).toEqual(['30min', '3h', 'D+1'])
    const d1 = await getPrevisao('D+1')
    expect(d1).toHaveLength(1)
    expect(d1[0].pontos.length).toBe(48)
  })

  it('riscos: os 7 seeds, ordenados por probabilidade', async () => {
    const r = await getRiscos()
    expect(r.map((x) => [x.uf, x.nome, x.razao, x.probabilidadePct, x.montanteMw, x.horizonte, x.severidade])).toEqual([
      ['CE', 'Complexo do Litoral Eólico', 'REL', 87, 312, '3h', 'critical'],
      ['PI', 'Chapada Gaúcha Solar', 'ENE', 64, 249, 'D+1', 'high'],
      ['RN', 'Lagoa Seigada', 'REL', 45, 98, 'D+1', 'medium'],
      ['GO', 'Solar Camaleão', 'CNF', 42, 134, 'D+1', 'medium'],
      ['MA', 'Eólico Parnaíba IV', 'ENE', 38, 67, 'D+1', 'low'],
      ['RS', 'Ventos do Sul', 'REL', 24, 120, 'D+1', 'low'],
      ['SP', 'Solar Paulista', 'CNF', 21, 52, 'D+1', 'low'],
    ])
    expect(new Set(r.map((x) => x.id)).size).toBe(r.length) // ids únicos
  })

  it('alertas: um por risco, coerentes com o risco de origem', async () => {
    for (const risco of await getRiscos()) {
      const a = await getAlerta(risco.id)
      expect(a, risco.id).not.toBeNull()
      expect(a!.probabilidadePct).toBe(risco.probabilidadePct)
      expect(a!.montanteMw).toBe(risco.montanteMw)
      expect(a!.janelaPrevisao).toBe(risco.horizonte)
      expect(a!.motivos[0].razao).toBe(risco.razao) // razão principal = a do risco
      // texto gerado pelo Backend cita a usina certa (alertas.json vem do pipeline Python)
      expect(a!.textoAlerta).toContain(`em ${risco.nome},`)
    }
    expect(await getAlerta('nao-existe')).toBeNull()
  })

  it('excedentes: os 5 seeds', async () => {
    const e = await getExcedentes()
    expect(e.map((x) => [x.areaConcessao, x.distribuidora, x.excedenteMw, x.prioridade, x.horizonte])).toEqual([
      ['Bahia Costa', 'NEOENERGIA BA', 245, 'high', '3h'],
      ['Piauí Central', 'EQUATORIAL PI', 189, 'high', '1h'],
      ['Rio Grande do Norte', 'COSERN', 98, 'medium', 'D+1'],
      ['Goiás Cerrado', 'ENEL GO', 134, 'medium', 'D+1'],
      ['Maranhão Litoral', 'EQUATORIAL MA', 67, 'low', 'D+1'],
    ])
  })

  it('validação: 30 dias consecutivos de histórico', async () => {
    const v = await getValidacao()
    expect(v.historicoErro30d).toHaveLength(30)
    const dias = v.historicoErro30d.map((h) => Date.parse(h.data))
    dias.slice(1).forEach((d, i) => expect(d - dias[i]).toBe(86_400_000))
    // skill coerente com o próprio histórico: 1 − MAE_modelo / MAE_baseline
    const media = (k: 'mae' | 'maeBaseline') => v.historicoErro30d.reduce((s, h) => s + h[k], 0) / 30
    expect(v.skillVsClimatologia).toBeCloseTo(1 - media('mae') / media('maeBaseline'), 2)
  })
})

describe('mapa', () => {
  it('densidade de MMGD sintética e marcada como mock', async () => {
    const d = await getDensidadeMmgd()
    expect(d.mock).toBe(true)
    expect(d.pontos.length).toBeGreaterThan(100)
  })

  it('coordenada trocada (lat↔lon) é recusada pelo schema', async () => {
    const [r] = await getRiscos()
    expect(() => validar('riscos', RiscoUsinaSchema, { ...r, lat: r.lon, lon: r.lat })).toThrow(DataSourceError)
  })
})

describe('guardas do contrato', () => {
  const cargaOk = {
    mock: true,
    timestampUtc: '2026-09-25T17:30:00Z',
    cargaGlobalMw: 100,
    mmgdEstimadaMw: 40,
    cargaSupervisionadaMw: 60,
    percentualMmgdNaGeracao: 10,
    mmgdSobreCapacidadeInstalada: 0.5,
  }

  it('mock sem "mock: true" é rejeitado', () => {
    expect(() => validar('carga', CargaSnapshotSchema, { ...cargaOk, mock: false }, 'mock')).toThrow(DataSourceError)
  })

  it('no modo api, mock: false é aceito', () => {
    expect(validar('carga', CargaSnapshotSchema, { ...cargaOk, mock: false }, 'api').mock).toBe(false)
  })

  it('carga supervisionada incoerente é rejeitada', () => {
    expect(() => validar('carga', CargaSnapshotSchema, { ...cargaOk, cargaSupervisionadaMw: 90 })).toThrow(/cargaSupervisionadaMw/)
  })

  it('quantis cruzados são rejeitados', () => {
    const r = PontoPrevisaoSchema.safeParse({ timestamp: '2026-09-25T18:00:00Z', p10: 5, p50: 4, p90: 6 })
    expect(r.success).toBe(false)
  })
})
