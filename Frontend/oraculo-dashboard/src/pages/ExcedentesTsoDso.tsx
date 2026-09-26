/**
 * Excedentes TSO-DSO: excedente de geração projetado por área, com prioridade, horizonte,
 * ação recomendada e o fluxo "antecipar → priorizar → coordenar" do pitch (slide 7):
 * - faixa do "payload da interface ONS–DSO" (o que esta tela troca entre ONS e distribuidora);
 * - KPIs e barras por área; busca, filtro de horizonte, ordenação por coluna e CSV;
 * - "Executar" registra a ação no REGISTRO DE COORDENAÇÃO da sessão, marcado como simulado:
 *   nada é enviado a sistema nenhum (o produto apoia a decisão, não automatiza o despacho).
 *   O registro vive só na memória da aba (some ao recarregar) — é demonstração do fluxo.
 * - "Ver no mapa" abre o Mapa Híbrido com a área selecionada.
 */
import { useMemo, useState } from 'react'
import { MapPin, Play, RotateCcw } from 'lucide-react'
import { AvisoFiltro } from '../components/ui/AvisoFiltro'
import { Botao, BotaoLink } from '../components/ui/Botao'
import { BotaoExportar } from '../components/ui/BotaoExportar'
import { CampoBusca } from '../components/ui/CampoBusca'
import { Card } from '../components/ui/Card'
import { Carregando, ErroDados } from '../components/ui/Estado'
import { FiltroChips } from '../components/ui/FiltroChips'
import { KpiCard } from '../components/ui/KpiCard'
import { MockTag } from '../components/ui/MockTag'
import { SeverityBadge } from '../components/ui/SeverityBadge'
import { CELULA, LINHA, LinhaVazia, Tabela, type ColunaTabela } from '../components/ui/Tabela'
import { getExcedentes } from '../data/dataSource'
import { compararSeveridade } from '../data/derivados'
import { HorizonteExcedenteSchema, HorizonteSchema, type ExcedenteTsoDso, type HorizonteExcedente, type Severidade } from '../data/types'
import { useDados } from '../data/useDados'
import { idExcedente, rotaMapa } from '../modules'
import { useOrdenacao } from '../state/useOrdenacao'
import { useFiltradosPorSeveridade } from '../state/useSeverityFilter'
import { RISK_STYLES } from '../theme/severity'
import type { ColunaCsv } from '../utils/csv'
import { formatHoraBrt, formatMw } from '../utils/format'
import { casaBusca, porHorizonte, porNumero, porTexto } from '../utils/ordenacao'

type ChaveOrdem = 'area' | 'distribuidora' | 'fonte' | 'excedente' | 'prioridade' | 'horizonte'

const COLUNAS: ColunaTabela[] = [
  { rotulo: 'Área', ordem: 'area' },
  { rotulo: 'Distribuidora', ordem: 'distribuidora' },
  { rotulo: 'Fonte', ordem: 'fonte' },
  { rotulo: 'Excedente projetado', num: true, ordem: 'excedente' },
  { rotulo: 'Prioridade', ordem: 'prioridade' },
  { rotulo: 'Horizonte', ordem: 'horizonte' },
  { rotulo: 'Ação recomendada' },
  { rotulo: 'Ações', semRotulo: true },
]

/** Comparadores em ordem CRESCENTE (desempate pelo maior excedente e pela área). */
const desempate = (a: ExcedenteTsoDso, b: ExcedenteTsoDso) => b.excedenteMw - a.excedenteMw || porTexto(a.areaConcessao, b.areaConcessao)
const COMPARADORES: Record<ChaveOrdem, (a: ExcedenteTsoDso, b: ExcedenteTsoDso) => number> = {
  area: (a, b) => porTexto(a.areaConcessao, b.areaConcessao),
  distribuidora: (a, b) => porTexto(a.distribuidora, b.distribuidora) || desempate(a, b),
  fonte: (a, b) => porTexto(a.fonte, b.fonte) || desempate(a, b),
  excedente: (a, b) => porNumero(a.excedenteMw, b.excedenteMw),
  prioridade: (a, b) => -compararSeveridade(a.prioridade, b.prioridade) || -desempate(a, b),
  horizonte: (a, b) => porHorizonte(a.horizonte, b.horizonte) || desempate(a, b),
}
const DIRECAO_PADRAO = { area: 'asc', distribuidora: 'asc', fonte: 'asc', horizonte: 'asc' } as const

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
  ['Granularidade', 'área + fronteira TSO–DSO'],
  ['Antecedência', HorizonteSchema.options.join(' · ')],
  ['Formato', 'probabilístico + rastreável'],
]

const CSV: ColunaCsv<ExcedenteTsoDso>[] = [
  { rotulo: 'area', valor: (e) => e.areaConcessao },
  { rotulo: 'distribuidora', valor: (e) => e.distribuidora },
  { rotulo: 'fonte', valor: (e) => e.fonte },
  { rotulo: 'excedente_mw', valor: (e) => e.excedenteMw },
  { rotulo: 'prioridade', valor: (e) => e.prioridade },
  { rotulo: 'horizonte', valor: (e) => e.horizonte },
  { rotulo: 'acao_recomendada', valor: (e) => e.acaoRecomendada },
  { rotulo: 'lat', valor: (e) => e.lat },
  { rotulo: 'lon', valor: (e) => e.lon },
  { rotulo: 'mock', valor: (e) => e.mock },
]

/** Entrada do registro de coordenação (simulado, só em memória). */
interface Acionamento {
  id: string
  area: string
  acao: string
  quando: string // ISO
}

export default function ExcedentesTsoDso() {
  const dados = useDados(getExcedentes)
  if (dados.status === 'erro') return <ErroDados erro={dados.erro} />
  if (dados.status === 'loading') return <Carregando altura="h-96" />
  return <Excedentes excedentes={dados.data} />
}

function Excedentes({ excedentes }: { excedentes: ExcedenteTsoDso[] }) {
  const { visiveis, ocultos } = useFiltradosPorSeveridade(excedentes, (e) => e.prioridade)
  const [busca, setBusca] = useState('')
  const [horizontes, setHorizontes] = useState<Set<HorizonteExcedente>>(() => new Set(HorizonteExcedenteSchema.options))
  const filtrados = useMemo(
    () => visiveis.filter((e) => horizontes.has(e.horizonte) && casaBusca(busca, [e.areaConcessao, e.distribuidora, e.fonte, e.acaoRecomendada])),
    [visiveis, horizontes, busca],
  )
  const { ordenados, ordenacao, alternar } = useOrdenacao(filtrados, COMPARADORES, { chave: 'prioridade', direcao: 'desc' }, DIRECAO_PADRAO)
  const [registro, setRegistro] = useState<Acionamento[]>([])
  const executar = (e: ExcedenteTsoDso) =>
    setRegistro((r) => [{ id: idExcedente(e), area: e.areaConcessao, acao: e.acaoRecomendada, quando: new Date().toISOString() }, ...r])
  const desfazer = (id: string) => setRegistro((r) => r.filter((a) => a.id !== id))
  const acionados = new Set(registro.map((a) => a.id))

  const mock = excedentes.some((e) => e.mock)
  // KPIs de sistema: sobre todas as áreas (o filtro muda a lista, não a medida).
  const totalMw = excedentes.reduce((s, e) => s + e.excedenteMw, 0)
  const altaMw = excedentes.filter((e) => e.prioridade === 'high' || e.prioridade === 'critical').reduce((s, e) => s + e.excedenteMw, 0)

  return (
    <div className="space-y-4">
      <Payload />

      {/*
        Faixa superior: dois KPIs + barras por área (painel lateral do Figma). As barras ficam AQUI,
        e não ao lado da tabela, para a tabela ter a largura toda.
      */}
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-[1fr_1fr_1.4fr]">
        {/* em MW (não GW): os excedentes por área são de centenas de MW, "0,7 GW" esconderia a escala */}
        <KpiCard label="Excedente projetado total" value={formatMw(totalMw)} unit="MW" accent="border-t-chart-2" actions={<MockTag mock={mock} />} hint={<>soma de {excedentes.length} áreas monitoradas</>} />
        <KpiCard label="Prioridade alta" value={formatMw(altaMw)} unit="MW" accent={RISK_STYLES.high.topo} actions={<SeverityBadge level="high" label="High" />} hint="áreas que pedem ação no horizonte mais curto" />
        <div className="md:col-span-2 xl:col-span-1">
          <BarrasPorArea excedentes={ordenados} />
        </div>
      </div>

      <div className="grid gap-4 2xl:grid-cols-[minmax(0,1fr)_20rem]">
        <Card
          flush
          title="Excedentes por área"
          actions={
            <>
              <MockTag mock={mock} />
              <BotaoExportar nome="excedentes_tso_dso" colunas={CSV} linhas={ordenados} />
            </>
          }
        >
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-line px-4 py-2.5">
            <CampoBusca valor={busca} onChange={setBusca} placeholder="Buscar área, distribuidora, ação…" />
            <FiltroChips rotulo="Horizonte" opcoes={HorizonteExcedenteSchema.options} ativos={horizontes} onChange={setHorizontes} />
          </div>
          <Tabela colunas={COLUNAS} ordenacao={ordenacao} onOrdenar={(k) => alternar(k as ChaveOrdem)}>
            {ordenados.map((e) => (
              <LinhaExcedente key={idExcedente(e)} e={e} acionado={acionados.has(idExcedente(e))} onExecutar={() => executar(e)} />
            ))}
            {!ordenados.length && <LinhaVazia colunas={COLUNAS.length} texto="Nenhuma área com os filtros atuais." />}
          </Tabela>
          <AvisoFiltro ocultos={ocultos} className="border-t border-line px-4 py-2" />
          <p className="border-t border-line px-4 py-2 text-xs text-ink-faint">
            Apoio à decisão: “Executar” só registra a ação abaixo (simulado); o produto não automatiza o despacho nem
            substitui procedimentos operativos.
          </p>
        </Card>

        <RegistroCoordenacao registro={registro} onDesfazer={desfazer} />
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

function LinhaExcedente({ e, acionado, onExecutar }: { e: ExcedenteTsoDso; acionado: boolean; onExecutar: () => void }) {
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
        <span className="inline-flex items-center gap-1.5">
          <BotaoLink variante="fantasma" to={rotaMapa({ tipo: 'excedente', id: idExcedente(e) })} title="Ver no mapa" aria-label={`Ver ${e.areaConcessao} no mapa`}>
            <MapPin className="size-3.5" aria-hidden />
          </BotaoLink>
          {acionado ? (
            <span className="font-mono text-[11px] uppercase tracking-widest text-ink-faint" role="status">
              registrado · simulado
            </span>
          ) : (
            <Botao variante="primario" onClick={onExecutar} title="Registra no registro de coordenação (simulado): nada é enviado">
              <Play className="size-3" aria-hidden /> Executar
            </Botao>
          )}
        </span>
      </td>
    </tr>
  )
}

/** Registro de coordenação da sessão (simulado): o que foi acionado, quando, e desfazer. */
function RegistroCoordenacao({ registro, onDesfazer }: { registro: Acionamento[]; onDesfazer: (id: string) => void }) {
  return (
    <Card title="Registro de coordenação" actions={<span className="border border-dashed border-ink-faint px-1.5 font-mono text-[10px] text-ink-muted">SIMULADO</span>}>
      {registro.length === 0 ? (
        <p className="text-xs text-ink-muted">
          Nenhuma ação registrada nesta sessão. “Executar” numa área registra aqui a ação combinada com a distribuidora
          (só nesta aba; nada é enviado).
        </p>
      ) : (
        <ol className="space-y-2.5">
          {registro.map((a) => (
            <li key={`${a.id}-${a.quando}`} className="border-l-2 border-accent/50 pl-2.5">
              <p className="flex items-center justify-between gap-2 text-body text-ink">
                {a.area}
                <span className="kpi text-[11px] text-ink-faint">{formatHoraBrt(a.quando)}</span>
              </p>
              <p className="text-xs text-ink-muted">{a.acao}</p>
              <Botao variante="fantasma" className="-ml-1.5" onClick={() => onDesfazer(a.id)}>
                <RotateCcw className="size-3" aria-hidden /> desfazer
              </Botao>
            </li>
          ))}
        </ol>
      )}
    </Card>
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
      <ul className="space-y-2" aria-label="Excedente projetado por área">
        {excedentes.map((e) => (
          <li key={idExcedente(e)}>
            <p className="flex justify-between gap-2 text-xs">
              <span className="truncate text-ink-muted">{e.areaConcessao}</span>
              <span className="kpi text-ink">{formatMw(e.excedenteMw)}</span>
            </p>
            <div className="mt-1 h-1.5 bg-line" aria-hidden>
              <div className={`h-full ${RISK_STYLES[e.prioridade].dot}`} style={{ width: `${(e.excedenteMw / max) * 100}%` }} />
            </div>
          </li>
        ))}
        {!excedentes.length && <li className="text-xs text-ink-muted">Nenhuma área com os filtros atuais.</li>}
      </ul>
    </Card>
  )
}
