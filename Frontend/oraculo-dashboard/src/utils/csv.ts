/**
 * Exportação CSV das tabelas do dashboard (Lista de Riscos, Excedentes, curva do Despacho,
 * histórico da Validação). Um formato só para todas as telas.
 *
 * Decisões:
 * - Separador `;` e decimal com vírgula: é o que o Excel em pt-BR abre direto em colunas
 *   (o público são analistas do setor, que abrem no Excel).
 * - BOM UTF-8 no início: sem ele o Excel mostra "Ã©" no lugar de "é".
 * - Campo com `;`, aspas ou quebra de linha vai entre aspas, com aspas dobradas (RFC 4180).
 * - Exporta exatamente o que está na tela (já filtrado/ordenado): quem exporta vê o que baixou.
 */
import { baixarArquivo, hojeIso } from './download'

export interface ColunaCsv<T> {
  rotulo: string
  valor: (linha: T) => string | number | boolean | null | undefined
}

const escapar = (v: string) => (/[";\n\r]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v)

function celula(v: string | number | boolean | null | undefined): string {
  if (v === null || v === undefined) return ''
  if (typeof v === 'number') return Number.isFinite(v) ? String(v).replace('.', ',') : ''
  if (typeof v === 'boolean') return v ? 'sim' : 'não'
  return escapar(v)
}

/** Texto CSV (sem BOM) — função pura, testada. */
export function paraCsv<T>(colunas: readonly ColunaCsv<T>[], linhas: readonly T[]): string {
  const cab = colunas.map((c) => escapar(c.rotulo)).join(';')
  const corpo = linhas.map((l) => colunas.map((c) => celula(c.valor(l))).join(';'))
  return [cab, ...corpo].join('\r\n') + '\r\n'
}

/** Dispara o download no navegador. Nome sem extensão; ganha a data de hoje e ".csv". */
export function baixarCsv<T>(nome: string, colunas: readonly ColunaCsv<T>[], linhas: readonly T[]): void {
  baixarArquivo(`${nome}_${hojeIso()}.csv`, '﻿' + paraCsv(colunas, linhas), 'text/csv;charset=utf-8')
}
