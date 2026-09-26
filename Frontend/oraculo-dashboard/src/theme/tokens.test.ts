/**
 * Trava da classe de bug "utilitário Tailwind ambíguo": no Tailwind v4, `text-X` serve tanto
 * para cor (--color-X) quanto para tamanho de fonte (--text-X). Se os dois existirem com o
 * mesmo nome, `text-X` aplica as duas coisas. Aconteceu com `base`: o tamanho padrão do
 * Tailwind e a cor de fundo da página — o texto ficava quase preto sobre o fundo escuro.
 */
import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

/** Tamanhos de fonte padrão do Tailwind v4 (sempre existem, mesmo sem @theme). */
const TAMANHOS_PADRAO = ['xs', 'sm', 'base', 'lg', 'xl', '2xl', '3xl', '4xl', '5xl', '6xl', '7xl', '8xl', '9xl']

describe('tokens de index.css', () => {
  const css = readFileSync(new URL('../index.css', import.meta.url), 'utf-8')
  const nomes = (prefixo: string) =>
    [...css.matchAll(new RegExp(`--${prefixo}-([a-z0-9-]+?)(?:--[a-z-]+)?\\s*:`, 'g'))].map((m) => m[1])

  it('nenhuma cor tem nome de tamanho de fonte (padrão do Tailwind ou do projeto)', () => {
    const cores = new Set(nomes('color'))
    const tamanhos = new Set([...TAMANHOS_PADRAO, ...nomes('text')])
    expect(cores.size).toBeGreaterThan(5) // o parser achou as cores (teste não passa por vazio)
    expect([...cores].filter((c) => tamanhos.has(c))).toEqual([])
  })
})
