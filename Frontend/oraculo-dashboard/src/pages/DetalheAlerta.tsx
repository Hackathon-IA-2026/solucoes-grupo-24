/**
 * Detalhe do Alerta: texto do alerta (gerado no Backend), decomposição SHAP, motivos por
 * razão e rastreabilidade até o dataset de origem.
 *
 * Rota: /detalhe-alerta/:alertId? — o id é o de RiscoUsina (vem da Lista de Riscos).
 * Sem id, a página lista os alertas disponíveis para escolher.
 */
import { useCallback, useState } from 'react'
import { ArrowLeft, Check, ChevronLeft, ChevronRight, Copy, Database, MapPin } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'
import { BarrasShap } from '../components/charts/BarrasShap'
import { Botao, BotaoLink } from '../components/ui/Botao'
import { Card } from '../components/ui/Card'
import { Carregando, ErroDados } from '../components/ui/Estado'
import { MockTag } from '../components/ui/MockTag'
import { RazaoBadge } from '../components/ui/RazaoBadge'
import { SeverityBadge } from '../components/ui/SeverityBadge'
import { getAlerta, getRiscos } from '../data/dataSource'
import { ordenarPorSeveridade } from '../data/derivados'
import type { AlertaDetalhado, RiscoUsina } from '../data/types'
import { useDados } from '../data/useDados'
import { MODULES, rotaDetalheAlerta, rotaMapa } from '../modules'
import { RAZAO_INFO } from '../theme/razao'
import { RISK_STYLES } from '../theme/severity'
import { formatDataHoraBrt, formatMw, formatPct } from '../utils/format'

// Link de volta para a Lista de Riscos, pelo registro (sem caminho escrito à mão).
const LISTA = MODULES.find((m) => m.label === 'Lista de Riscos')!

/** Nome legível do método de explicação que veio do Backend. */
const METODOS: Record<string, string> = {
  ExplicadorPrecomputado: 'SHAP pré-computado (stub — modelo real ainda não integrado)',
  ExplicadorShap: 'SHAP calculado sobre o modelo',
  ExplicadorLightGBM: 'SHAP exato do LightGBM (TreeSHAP do próprio modelo)',
}

export default function DetalheAlerta() {
  const { alertId } = useParams()
  const riscos = useDados(getRiscos)
  // useCallback: a função só muda quando o id muda, então o hook só rebusca nessa hora.
  const carregarAlerta = useCallback(() => (alertId ? getAlerta(alertId) : Promise.resolve(null)), [alertId])
  const alerta = useDados(carregarAlerta)

  if (riscos.status === 'erro') return <ErroDados erro={riscos.erro} />
  if (alerta.status === 'erro') return <ErroDados erro={alerta.erro} />
  if (riscos.status === 'loading' || alerta.status === 'loading') return <Carregando altura="h-96" />

  if (!alertId) return <EscolherAlerta riscos={riscos.data} />

  const risco = riscos.data.find((r) => r.id === alertId)
  if (!alerta.data || !risco) {
    return (
      <Card title="Alerta não encontrado">
        <p className="text-body text-ink-muted">
          Não há alerta para <span className="font-mono text-ink">{alertId}</span>.
        </p>
        <VoltarLista />
      </Card>
    )
  }
  // vizinhos na MESMA ordem da Lista de Riscos (triagem sequencial sem voltar à lista)
  const ordem = ordenarPorSeveridade(riscos.data)
  const i = ordem.findIndex((r) => r.id === risco.id)
  return <Alerta alerta={alerta.data} risco={risco} anterior={ordem[i - 1]} proximo={ordem[i + 1]} posicao={[i + 1, ordem.length]} />
}

function Alerta({ alerta, risco, anterior, proximo, posicao }: {
  alerta: AlertaDetalhado
  risco: RiscoUsina
  anterior?: RiscoUsina
  proximo?: RiscoUsina
  posicao: [number, number]
}) {
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <VoltarLista />
        <span className="text-ink-faint">/</span>
        <span className="font-mono text-xs text-ink-muted">{risco.uf}</span>
        <span className="font-medium text-ink">{risco.nome}</span>
        <SeverityBadge level={risco.severidade} />
        <RazaoBadge razao={risco.razao} />
        <MockTag mock={alerta.mock} />
        <span className="ml-auto flex items-center gap-1.5">
          <BotaoLink to={rotaMapa({ tipo: 'risco', id: risco.id })}>
            <MapPin className="size-3" aria-hidden /> Ver no mapa
          </BotaoLink>
          <NavVizinho r={anterior} rotulo="Anterior" Icone={ChevronLeft} />
          <span className="kpi px-1 text-[11px] text-ink-faint">
            {posicao[0]}/{posicao[1]}
          </span>
          <NavVizinho r={proximo} rotulo="Próximo" Icone={ChevronRight} depois />
        </span>
      </div>

      <FaixaKpis alerta={alerta} risco={risco} />

      <TextoAlerta texto={alerta.textoAlerta} barra={RISK_STYLES[risco.severidade].barra} />

      <div className="grid gap-4 xl:grid-cols-[1fr_22rem]">
        <Card title="Decomposição SHAP · peso por variável" actions={<MockTag mock={alerta.mock} />}>
          <BarrasShap valores={alerta.shapValues} />
        </Card>

        <div className="space-y-4">
          <AcaoRecomendada risco={risco} />
          <Motivos alerta={alerta} />
          <Rastreabilidade alerta={alerta} risco={risco} />
        </div>
      </div>
    </div>
  )
}

/** Anterior/Próximo na ordem da Lista de Riscos (desabilitado nas pontas). */
function NavVizinho({ r, rotulo, Icone, depois = false }: { r?: RiscoUsina; rotulo: string; Icone: typeof ChevronLeft; depois?: boolean }) {
  if (!r)
    return (
      <Botao disabled aria-label={`${rotulo}: não há`}>
        {!depois && <Icone className="size-3" aria-hidden />} {rotulo} {depois && <Icone className="size-3" aria-hidden />}
      </Botao>
    )
  return (
    <BotaoLink to={rotaDetalheAlerta(r.id)} title={`${rotulo}: ${r.nome}`}>
      {!depois && <Icone className="size-3" aria-hidden />} {rotulo} {depois && <Icone className="size-3" aria-hidden />}
    </BotaoLink>
  )
}

/** Os números do alerta de relance, antes do texto. */
function FaixaKpis({ alerta, risco }: { alerta: AlertaDetalhado; risco: RiscoUsina }) {
  const itens: [string, string, string?][] = [
    ['Probabilidade', `${formatPct(alerta.probabilidadePct, 1)}%`, RISK_STYLES[risco.severidade].label],
    ['Montante previsto', `${formatMw(alerta.montanteMw)} MW`],
    ['Horário previsto', `${formatDataHoraBrt(alerta.horarioPrevisto)}`, 'BRT'],
    ['Janela', alerta.janelaPrevisao],
    ['Fonte', risco.fonte],
    ['Distribuidora', risco.distribuidora],
  ]
  return (
    <dl className={`grid gap-px border border-line bg-line sm:grid-cols-3 xl:grid-cols-6 border-t-2 ${RISK_STYLES[risco.severidade].topo}`}>
      {itens.map(([k, v, apoio]) => (
        <div key={k} className="bg-surface px-4 py-2.5">
          <dt className="rotulo text-[10px]">{k}</dt>
          <dd className="kpi mt-0.5 truncate text-lg font-semibold text-ink" title={v}>
            {v} {apoio && <span className="text-[11px] font-normal text-ink-faint">{apoio}</span>}
          </dd>
        </div>
      ))}
    </dl>
  )
}

/** Bloco estilo terminal com o texto exatamente como o Backend gerou, com "copiar". */
function TextoAlerta({ texto, barra }: { texto: string; barra: string }) {
  const [copiado, setCopiado] = useState(false)
  const copiar = async () => {
    try {
      await navigator.clipboard.writeText(texto)
      setCopiado(true)
      window.setTimeout(() => setCopiado(false), 1800)
    } catch {
      setCopiado(false) // sem permissão de área de transferência: o texto continua selecionável
    }
  }
  return (
    <section aria-label="Texto do alerta" className={`overflow-hidden border border-line border-l-4 bg-fundo ${barra}`}>
      <header className="flex items-center gap-2 border-b border-line bg-surface px-4 py-1.5">
        <span className="size-2 rounded-full bg-ink-faint" aria-hidden />
        <span className="size-2 rounded-full bg-ink-faint" aria-hidden />
        <span className="size-2 rounded-full bg-ink-faint" aria-hidden />
        <span className="ml-2 font-mono text-[11px] text-ink-faint">explicabilidade.gerar_texto_alerta()</span>
        <Botao variante="fantasma" className="ml-auto" onClick={copiar} title="Copiar o texto para enviar à distribuidora">
          {copiado ? <Check className="size-3" aria-hidden /> : <Copy className="size-3" aria-hidden />} {copiado ? 'copiado' : 'copiar'}
        </Botao>
      </header>
      {/* pre: preserva as quebras de linha do texto gerado; sem reformatação na tela */}
      <pre className="overflow-x-auto whitespace-pre-wrap px-4 py-3 font-mono text-sm leading-relaxed text-ink">{texto}</pre>
    </section>
  )
}

/**
 * A ação que o alerta sugere (pitch, slide 10: "explicar e recomendar"). O texto vem do
 * contrato (RiscoUsina.acaoRecomendada); a ressalva repete o limite declarado no slide 7: o
 * produto apoia a decisão, não automatiza o despacho.
 */
function AcaoRecomendada({ risco }: { risco: RiscoUsina }) {
  return (
    <Card title="Ação recomendada" accent={RISK_STYLES[risco.severidade].topo} actions={<MockTag mock={risco.mock} />}>
      <p className="text-body text-ink">{risco.acaoRecomendada}</p>
      <p className="mt-2 text-xs text-ink-faint">
        Apoio à decisão: não automatiza o despacho nem substitui procedimentos operativos.
      </p>
    </Card>
  )
}

function Motivos({ alerta }: { alerta: AlertaDetalhado }) {
  return (
    <Card title="Motivos por razão">
      <ul className="space-y-3">
        {alerta.motivos.map((m) => (
          <li key={m.razao} className="grid grid-cols-[3.5rem_1fr_3rem] items-center gap-3">
            <RazaoBadge razao={m.razao} />
            <div className="h-2 overflow-hidden rounded-full bg-line" title={RAZAO_INFO[m.razao].nome}>
              <div className={`h-full rounded-full ${RAZAO_INFO[m.razao].dot}`} style={{ width: `${m.pesoPct}%` }} />
            </div>
            <span className="kpi text-right text-sm text-ink">{formatPct(m.pesoPct, 0)}%</span>
          </li>
        ))}
      </ul>
      <p className="kpi mt-4 border-t border-line pt-3 text-xs text-ink-muted">
        {formatPct(alerta.probabilidadePct, 0)}% · {formatMw(alerta.montanteMw)} MW · {formatDataHoraBrt(alerta.horarioPrevisto)} BRT
      </p>
    </Card>
  )
}

/** De onde veio o alerta: dataset → previsão → explicação → texto. */
function Rastreabilidade({ alerta, risco }: { alerta: AlertaDetalhado; risco: RiscoUsina }) {
  const itens: [string, string][] = [
    ['Dataset de origem', alerta.fonteDataset],
    ['Previsão gerada em', `${formatDataHoraBrt(alerta.atualizadoEm)} BRT (há ${alerta.atualizadoHaMin} min)`],
    ['Janela de previsão', alerta.janelaPrevisao],
    ['Explicação', METODOS[alerta.metodoExplicacao] ?? alerta.metodoExplicacao],
    ['Registro', risco.id],
  ]
  return (
    <Card title="Rastreabilidade" actions={<Database className="size-4 text-ink-faint" aria-hidden />}>
      <dl className="space-y-3">
        {itens.map(([k, v]) => (
          <div key={k}>
            <dt className="rotulo text-[10px] text-ink-faint">{k}</dt>
            <dd className="mt-0.5 break-words text-body text-ink">{v}</dd>
          </div>
        ))}
      </dl>
    </Card>
  )
}

function VoltarLista() {
  return (
    <Link to={LISTA.path} className="inline-flex items-center gap-1 text-body text-accent hover:underline">
      <ArrowLeft className="size-4" aria-hidden /> {LISTA.label}
    </Link>
  )
}

/** Sem id na URL: atalho para cada alerta, na mesma ordem da Lista de Riscos. */
function EscolherAlerta({ riscos }: { riscos: RiscoUsina[] }) {
  return (
    <Card title="Escolha um alerta">
      <ul className="divide-y divide-line">
        {ordenarPorSeveridade(riscos).map((r) => (
          <li key={r.id}>
            <Link to={rotaDetalheAlerta(r.id)} className="flex items-center gap-3 px-1 py-2.5 hover:bg-surface-raised">
              <SeverityBadge level={r.severidade} />
              <span className="font-mono text-xs text-ink-muted">{r.uf}</span>
              <span className="flex-1 text-body text-ink">{r.nome}</span>
              <span className="kpi text-sm text-ink-muted">{formatPct(r.probabilidadePct, 0)}%</span>
              <ChevronRight className="size-4 text-ink-faint" aria-hidden />
            </Link>
          </li>
        ))}
      </ul>
    </Card>
  )
}
