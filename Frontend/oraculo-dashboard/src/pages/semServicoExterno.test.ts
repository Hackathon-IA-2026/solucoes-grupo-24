/**
 * Trava da classe de bug "o dashboard depende de um serviço externo em tempo de execução".
 *
 * Origem: em 2026-09 os tiles da CARTO do Mapa Híbrido passaram a exigir chave e cobriram o mapa
 * com "API KEY REQUIRED". O fundo do mapa virou 100% local (IBGE + Natural Earth, versionados em
 * src/data/geo/). Este teste falha se alguém voltar a pôr camada de tiles remota ou fonte/CSS
 * carregados de CDN — a demo precisa funcionar offline e na rede do ONS.
 */
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'

const SRC = new URL('..', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1')

function arquivos(dir: string): string[] {
  return readdirSync(dir).flatMap((n: string) => {
    const p = join(dir, n)
    if (statSync(p).isDirectory()) return arquivos(p)
    return /\.(tsx?|css)$/.test(n) && !n.endsWith('.test.ts') ? [p] : []
  })
}

describe('nenhuma dependência de serviço externo em tempo de execução', () => {
  const fontes = arquivos(SRC).map((p) => ({ p, s: readFileSync(p, 'utf-8') }))

  it('sem camada de tiles remota no mapa', () => {
    for (const { p, s } of fontes) {
      expect(s, p).not.toMatch(/\bTileLayer\b/)
      expect(s, p).not.toMatch(/\{z\}\/\{x\}\/\{y\}/)
    }
  })

  it('sem fonte ou CSS de CDN (fontes vêm do @fontsource, empacotadas)', () => {
    for (const { p, s } of fontes) expect(s, p).not.toMatch(/fonts\.googleapis|@import\s+url\(\s*['"]?https?:/)
  })
})
