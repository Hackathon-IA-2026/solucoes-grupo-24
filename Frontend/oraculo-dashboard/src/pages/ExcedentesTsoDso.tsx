/**
 * Excedentes TSO-DSO: excedente de geração projetado por área de concessão, com prioridade,
 * horizonte, ação recomendada e um botão "Executar".
 *
 * O botão é SÓ interface por enquanto: não chama API nem altera nada. Ao clicar, a linha
 * mostra "simulado" para deixar explícito que nenhuma ação foi enviada.
 */
import { useState } from 'react'
import { Play } from 'lucide-react'
import { Card } from '../components/ui/Card'
import { Carregando, ErroDados } from '../components/ui/Estado'
import { KpiCard } from '../components/ui/KpiCard'
import { MockTag } from '../components/ui/MockTag'
import { SeverityBadge } from '../components/ui/SeverityBadge'
import { CELULA, LINHA, Tabela, type ColunaTabela } from '../components/ui/Tabela'
import { getExcedentes } from '../data/dataSource'
import { ordenarExcedentes } from '../data/derivados'
import type { ExcedenteTsoDso, Severidade } from '../data/types'
import { useDados } from '../data/useDados'
import { formatMw } from '../utils/format'

const COLUNAS: ColunaTabela[] = [
  { rotulo: 'Área de concessão' },
  { rotulo: 'Distribuidora' },
  { rotulo: 'Fonte' },
  { rotulo: 'Excedente projetado', num: true },
  { rotulo: 'Prioridade' },
  { rotulo: 'Horizonte' },
  { rotulo: 'Ação recomendada' },
  { rotulo: 'Executar', semRotulo: true },
]

/**
 * Rótulo do badge de prioridade como no protótipo (High/Medium/Low). A cor continua vindo da
 * escala de severidade (SeverityBadge), só o texto muda.
 */
const ROTULO_PRIORIDADE: Record<Severidade, string> = {
  critical: 'Critical',
  high: 'High',
  medium: 'Medium',
  low: 'Low',
}

/** Chave estável de linha: o contrato não tem id; área + distribuidora identificam o excedente. */
const chave = (e: ExcedenteTsoDso) => `${e.areaConcessao}|${e.distribuidora}`

export default function ExcedentesTsoDso() {
  const dados = useDados(getExcedentes)
  if (dados.status === 'erro') return <ErroDados erro={dados.erro} />
  if (dados.status === 'loading') return <Carregando altura="h-96" />

  const excedentes = ordenarExcedentes(dados.data)
  const mock = excedentes.some((e) => e.mock)
  const totalMw = excedentes.reduce((s, e) => s + e.excedenteMw, 0)
  const altaMw = excedentes.filter((e) => e.prioridade === 'high' || e.prioridade === 'critical').reduce((s, e) => s + e.excedenteMw, 0)

  return (
    <div className="space-y-4">
      <div className="grid gap-4 md:grid-cols-3">
        {/* em MW (não GW): os excedentes por área são de centenas de MW, "0,7 GW" esconderia a escala */}
        <KpiCard label="Excedente projetado total" value={formatMw(totalMw)} unit="MW" actions={<MockTag mock={mock} />} hint={<>soma de {excedentes.length} áreas de concessão</>} />
        <KpiCard label="Prioridade alta" value={formatMw(altaMw)} unit="MW" actions={<SeverityBadge level="high" label="High" />} hint="áreas que pedem ação no horizonte mais curto" />
        <KpiCard label="Áreas monitoradas" value={String(excedentes.length)} hint="áreas de concessão com excedente TSO-DSO" />
      </div>

      <Card title="Excedentes por área de concessão" actions={<MockTag mock={mock} />}>
        <Tabela colunas={COLUNAS}>
          {excedentes.map((e) => (
            <LinhaExcedente key={chave(e)} e={e} />
          ))}
        </Tabela>
      </Card>
    </div>
  )
}

function LinhaExcedente({ e }: { e: ExcedenteTsoDso }) {
  // Estado só visual: marca a linha como "simulado" depois do clique.
  const [simulado, setSimulado] = useState(false)
  return (
    <tr className={LINHA}>
      <td className={`${CELULA} font-medium text-ink`}>{e.areaConcessao}</td>
      <td className={`${CELULA} text-ink-muted`}>{e.distribuidora}</td>
      <td className={`${CELULA} text-ink-muted`}>{e.fonte}</td>
      <td className={`${CELULA} kpi text-right text-ink`}>
        {formatMw(e.excedenteMw)} <span className="text-xs text-ink-muted">MW</span>
      </td>
      <td className={CELULA}>
        <SeverityBadge level={e.prioridade} label={ROTULO_PRIORIDADE[e.prioridade]} />
      </td>
      <td className={`${CELULA} kpi text-ink-muted`}>{e.horizonte}</td>
      <td className={`${CELULA} quebra min-w-40 text-ink-muted`}>{e.acaoRecomendada}</td>
      <td className={`${CELULA} text-right`}>
        {simulado ? (
          <span className="font-mono text-[11px] uppercase tracking-widest text-ink-faint" role="status">
            simulado · nada enviado
          </span>
        ) : (
          <button
            type="button"
            onClick={() => setSimulado(true)}
            title="Apenas interface: nenhuma ação é enviada ao sistema"
            className="inline-flex items-center gap-1.5 rounded border border-accent/50 bg-accent/10 px-3 py-1 font-mono text-xs font-semibold tracking-wider text-accent transition-colors hover:bg-accent/20"
          >
            <Play className="size-3" aria-hidden /> Executar
          </button>
        )}
      </td>
    </tr>
  )
}
