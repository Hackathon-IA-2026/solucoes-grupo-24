/**
 * Excedentes TSO-DSO: excedente de geração projetado por área de concessão, com prioridade,
 * horizonte, ação recomendada e um botão "Executar".
 *
 * O botão é SÓ interface por enquanto: não chama API nem altera nada. Ao clicar, a linha
 * mostra "simulado" para deixar explícito que nenhuma ação foi enviada.
 *
 * Alinhamento com o pitch (slide 7, "uma interface precisa de um payload"): a faixa do topo
 * descreve O QUE esta tela troca entre ONS e distribuidora (grandeza, granularidade,
 * antecedência, formato). Do Figma veio o painel de barras por área; o botão "→ Gerdin" e a
 * contagem de "geradores monitorados" do protótipo NÃO vieram (não existem no contrato).
 */
import { useState } from 'react'
import { Play } from 'lucide-react'
import { AvisoFiltro } from '../components/ui/AvisoFiltro'
import { Card } from '../components/ui/Card'
import { Carregando, ErroDados } from '../components/ui/Estado'
import { KpiCard } from '../components/ui/KpiCard'
import { MockTag } from '../components/ui/MockTag'
import { SeverityBadge } from '../components/ui/SeverityBadge'
import { CELULA, LINHA, Tabela, type ColunaTabela } from '../components/ui/Tabela'
import { getExcedentes } from '../data/dataSource'
import { ordenarExcedentes } from '../data/derivados'
import { HorizonteSchema, type ExcedenteTsoDso, type Severidade } from '../data/types'
import { useDados } from '../data/useDados'
import { useFiltradosPorSeveridade } from '../state/useSeverityFilter'
import { RISK_STYLES } from '../theme/severity'
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

/**
 * Conteúdo informacional da interface ONS–DSO proposto no pitch (slide 7). Texto fixo de
 * produto, não dado; os horizontes vêm do schema para não divergirem do contrato.
 */
const PAYLOAD: readonly [string, string][] = [
  ['Grandeza', 'carga supervisionada + MMGD estimada'],
  ['Granularidade', 'área de concessão + fronteira'],
  ['Antecedência', HorizonteSchema.options.join(' · ')],
  ['Formato', 'probabilístico + rastreável'],
]

/** Chave estável de linha: o contrato não tem id; área + distribuidora identificam o excedente. */
const chave = (e: ExcedenteTsoDso) => `${e.areaConcessao}|${e.distribuidora}`

export default function ExcedentesTsoDso() {
  const dados = useDados(getExcedentes)
  if (dados.status === 'erro') return <ErroDados erro={dados.erro} />
  if (dados.status === 'loading') return <Carregando altura="h-96" />
  return <Excedentes excedentes={ordenarExcedentes(dados.data)} />
}

function Excedentes({ excedentes }: { excedentes: ExcedenteTsoDso[] }) {
  const { visiveis, ocultos } = useFiltradosPorSeveridade(excedentes, (e) => e.prioridade)
  const mock = excedentes.some((e) => e.mock)
  // KPIs de sistema: sobre todas as áreas (o filtro muda a lista, não a medida).
  const totalMw = excedentes.reduce((s, e) => s + e.excedenteMw, 0)
  const altaMw = excedentes.filter((e) => e.prioridade === 'high' || e.prioridade === 'critical').reduce((s, e) => s + e.excedenteMw, 0)

  return (
    <div className="space-y-4">
      <Payload />

      {/*
        Faixa superior: dois KPIs + barras por área (painel lateral do Figma). As barras ficam AQUI,
        e não ao lado da tabela, para a tabela ter a largura toda (ao lado, a 1440px o botão
        "Executar" era cortado). O antigo KPI "Áreas monitoradas" virou a linha de apoio do total.
      */}
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-[1fr_1fr_1.4fr]">
        {/* em MW (não GW): os excedentes por área são de centenas de MW, "0,7 GW" esconderia a escala */}
        <KpiCard label="Excedente projetado total" value={formatMw(totalMw)} unit="MW" accent="border-t-chart-2" actions={<MockTag mock={mock} />} hint={<>soma de {excedentes.length} áreas de concessão monitoradas</>} />
        <KpiCard label="Prioridade alta" value={formatMw(altaMw)} unit="MW" accent={RISK_STYLES.high.topo} actions={<SeverityBadge level="high" label="High" />} hint="áreas que pedem ação no horizonte mais curto" />
        <div className="md:col-span-2 xl:col-span-1">
          <BarrasPorArea excedentes={visiveis} />
        </div>
      </div>

      <div>
        <Card flush title="Excedentes por área de concessão" actions={<MockTag mock={mock} />}>
          <Tabela colunas={COLUNAS}>
            {visiveis.map((e) => (
              <LinhaExcedente key={chave(e)} e={e} />
            ))}
          </Tabela>
          <AvisoFiltro ocultos={ocultos} className="border-t border-line px-4 py-2" />
          <p className="border-t border-line px-4 py-2 text-xs text-ink-faint">
            Apoio à decisão: o botão “Executar” não envia comando; o produto não automatiza o despacho nem substitui
            procedimentos operativos.
          </p>
        </Card>
      </div>
    </div>
  )
}

/** Faixa "payload da interface ONS–DSO" (slide 7 do pitch). */
function Payload() {
  return (
    <section aria-label="Payload da interface ONS–DSO" className="grid border border-line bg-surface sm:grid-cols-[auto_repeat(4,minmax(0,1fr))]">
      <div className="flex flex-col justify-center border-b border-line px-4 py-2.5 sm:border-r sm:border-b-0">
        <p className="rotulo text-accent">Interface ONS–DSO</p>
        <p className="text-xs text-ink-muted">payload proposto</p>
      </div>
      {PAYLOAD.map(([k, v]) => (
        <div key={k} className="border-b border-line/60 px-4 py-2.5 last:border-b-0 sm:border-r sm:border-b-0 sm:last:border-r-0">
          <p className="rotulo text-[10px]">{k}</p>
          <p className="mt-0.5 text-body text-ink">{v}</p>
        </div>
      ))}
    </section>
  )
}

function LinhaExcedente({ e }: { e: ExcedenteTsoDso }) {
  // Estado só visual: marca a linha como "simulado" depois do clique.
  const [simulado, setSimulado] = useState(false)
  return (
    <tr className={LINHA}>
      <td className={`${CELULA} border-l-2 font-medium text-ink ${RISK_STYLES[e.prioridade].barra}`}>{e.areaConcessao}</td>
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
            className="inline-flex items-center gap-1.5 rounded-sm border border-accent/50 bg-accent/10 px-2.5 py-1 font-mono text-[11px] font-semibold tracking-wider text-accent transition-colors hover:bg-accent/20"
          >
            <Play className="size-3" aria-hidden /> Executar
          </button>
        )}
      </td>
    </tr>
  )
}

/**
 * Excedente por área em barras horizontais (painel lateral do Figma), em HTML puro: poucas
 * barras estáticas não justificam baixar o Recharts nesta tela. Comprimento relativo ao maior
 * excedente; cor = prioridade (a mesma do badge), com o valor escrito ao lado.
 */
function BarrasPorArea({ excedentes }: { excedentes: ExcedenteTsoDso[] }) {
  const max = Math.max(...excedentes.map((e) => e.excedenteMw), 1)
  return (
    <Card title="Excedente por área · MW" className="h-full">
      <ul className="space-y-2" aria-label="Excedente projetado por área de concessão">
        {excedentes.map((e) => (
          <li key={chave(e)}>
            <p className="flex justify-between gap-2 text-xs">
              <span className="truncate text-ink-muted">{e.areaConcessao}</span>
              <span className="kpi text-ink">{formatMw(e.excedenteMw)}</span>
            </p>
            <div className="mt-1 h-1.5 bg-line" aria-hidden>
              <div className={`h-full ${RISK_STYLES[e.prioridade].dot}`} style={{ width: `${(e.excedenteMw / max) * 100}%` }} />
            </div>
          </li>
        ))}
      </ul>
    </Card>
  )
}
