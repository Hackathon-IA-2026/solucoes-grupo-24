/**
 * Download de um arquivo gerado no navegador. Um lugar só para o mecanismo (Blob + <a download>),
 * usado pelo CSV das tabelas (utils/csv.ts) e pela exportação da documentação
 * (oraculo/documentacao/exportar.tsx).
 */

/** Data de hoje (AAAA-MM-DD), sufixo padrão dos arquivos exportados. */
export const hojeIso = () => new Date().toISOString().slice(0, 10)

/** Dispara o download de `conteudo` com o nome e o tipo MIME dados. */
export function baixarArquivo(nome: string, conteudo: string, mime: string): void {
  const url = URL.createObjectURL(new Blob([conteudo], { type: mime }))
  const a = document.createElement('a')
  a.href = url
  a.download = nome
  a.click()
  URL.revokeObjectURL(url)
}
