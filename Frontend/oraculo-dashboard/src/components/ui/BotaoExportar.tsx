import { Download } from 'lucide-react'
import { baixarCsv, type ColunaCsv } from '../../utils/csv'
import { Botao } from './Botao'

/** "Exportar CSV" do que está na tela (já filtrado e ordenado). Formato em utils/csv.ts. */
export function BotaoExportar<T>({ nome, colunas, linhas }: { nome: string; colunas: readonly ColunaCsv<T>[]; linhas: readonly T[] }) {
  return (
    <Botao onClick={() => baixarCsv(nome, colunas, linhas)} disabled={!linhas.length} title={`Baixar ${linhas.length} linha(s) em CSV`}>
      <Download className="size-3" aria-hidden /> CSV
    </Botao>
  )
}
