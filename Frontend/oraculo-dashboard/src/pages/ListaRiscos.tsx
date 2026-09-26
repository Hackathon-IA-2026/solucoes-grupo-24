/**
 * Lista de Riscos: usinas/conjuntos com risco de curtailment, com triagem completa:
 * - busca por nome, UF, ponto de conexão e ação (sem acento, vários termos);
 * - filtros de razão, fonte e horizonte (mais os de severidade da topbar);
 * - ordenação por coluna (padrão: severidade → probabilidade → montante);
 * - resumo do que está na tela (por severidade e MW) e exportação CSV do mesmo recorte;
 * - por linha: abrir o Detalhe do Alerta (clique/Enter) ou ver a usina no mapa.
 */
import { useMemo, useState } from 'react'
import { ChevronRight, MapPin } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { AvisoFiltro } from '../components/ui/AvisoFiltro'
import { BotaoExportar } from '../components/ui/BotaoExportar'
import { BotaoLink } from '../components/ui/Botao'
import { CampoBusca } from '../components/ui/CampoBusca'
import { Card } from '../components/ui/Card'
import { Carregando, ErroDados } from '../components/ui/Estado'
import { FiltroChips } from '../components/ui/FiltroChips'
import { MockTag } from '../components/ui/MockTag'
import { RazaoBadge } from '../components/ui/RazaoBadge'
import { SeverityBadge } from '../components/ui/SeverityBadge'
import { CELULA, LINHA, LinhaVazia, Tabela, type ColunaTabela } from '../components/ui/Tabela'
import { getRiscos } from '../data/dataSource'
import { compararSeveridade, contarPor, montanteEmRiscoMw } from '../data/derivados'
import { FonteGeracaoSchema, HorizonteSchema, RazaoSchema, SeveridadeSchema, type FonteGeracao, type Horizonte, type Razao, type RiscoUsina } from '../data/types'
import { useDados } from '../data/useDados'
import { rotaDetalheAlerta, rotaMapa } from '../modules'
import { useOrdenacao } from '../state/useOrdenacao'
import { useFiltradosPorSeveridade } from '../state/useSeverityFilter'
import { RAZAO_INFO } from '../theme/razao'
import { RISK_STYLES } from '../theme/severity'
import type { ColunaCsv } from '../utils/csv'
import { formatMw, formatPct } from '../utils/format'
import { casaBusca, porHorizonte, porNumero, porTexto } from '../utils/ordenacao'

type ChaveOrdem = 'severidade' | 'nome' | 'distribuidora' | 'fonte' | 'razao' | 'probabilidade' | 'montante' | 'horizonte'

/** Desempate comum: mais provável, maior MW, id — a ordem nunca depende da chegada dos dados. */
const desempate = (a: RiscoUsina, b: RiscoUsina) =>
  b.probabilidadePct - a.probabilidadePct || b.montanteMw - a.montanteMw || porTexto(a.id, b.id)

/** Comparadores em ordem CRESCENTE; a direção vem do useOrdenacao. */
const COMPARADORES: Record<ChaveOrdem, (a: RiscoUsina, b: RiscoUsina) => number> = {
  severidade: (a, b) => -compararSeveridade(a.severidade, b.severidade) || -desempate(a, b),
  nome: (a, b) => porTexto(a.nome, b.nome),
  distribuidora: (a, b) => porTexto(a.distribuidora, b.distribuidora) || desempate(a, b),
  fonte: (a, b) => porTexto(a.fonte, b.fonte) || desempate(a, b),
  razao: (a, b) => porTexto(a.razao, b.razao) || desempate(a, b),
  probabilidade: (a, b) => porNumero(a.probabilidadePct, b.probabilidadePct) || porNumero(a.montanteMw, b.montanteMw),
  montante: (a, b) => porNumero(a.montanteMw, b.montanteMw) || porNumero(a.probabilidadePct, b.probabilidadePct),
  horizonte: (a, b) => porHorizonte(a.horizonte, b.horizonte) || desempate(a, b),
}
// texto sobe A→Z ao primeiro clique; o resto começa do maior
const DIRECAO_PADRAO = { nome: 'asc', distribuidora: 'asc', fonte: 'asc', razao: 'asc', horizonte: 'asc' } as const

const COLUNAS: ColunaTabela[] = [
  { rotulo: 'Severidade', ordem: 'severidade' },
  { rotulo: 'Usina / UF', ordem: 'nome' },
  { rotulo: 'Distribuidora', ordem: 'distribuidora' },
  { rotulo: 'Fonte', ordem: 'fonte' },
  { rotulo: 'Razão', ordem: 'razao' },
  { rotulo: 'Probabilidade', num: true, ordem: 'probabilidade' },
  { rotulo: 'Montante previsto', num: true, ordem: 'montante' },
  { rotulo: 'Horizonte', ordem: 'horizonte' },
  { rotulo: 'Ação recomendada' },
  { rotulo: 'Ações', semRotulo: true },
]

const CSV: ColunaCsv<RiscoUsina>[] = [
  { rotulo: 'id', valor: (r) => r.id },
  { rotulo: 'usina', valor: (r) => r.nome },
  { rotulo: 'uf', valor: (r) => r.uf },
  { rotulo: 'distribuidora', valor: (r) => r.distribuidora },
  { rotulo: 'fonte', valor: (r) => r.fonte },
  { rotulo: 'razao', valor: (r) => r.razao },
  { rotulo: 'severidade', valor: (r) => r.severidade },
  { rotulo: 'probabilidade_pct', valor: (r) => r.probabilidadePct },
  { rotulo: 'montante_mw', valor: (r) => r.montanteMw },
  { rotulo: 'horizonte', valor: (r) => r.horizonte },
  { rotulo: 'acao_recomendada', valor: (r) => r.acaoRecomendada },
  { rotulo: 'mock', valor: (r) => r.mock },
]

export default function ListaRiscos() {
  const riscos = useDados(getRiscos)
  if (riscos.status === 'erro') return <ErroDados erro={riscos.erro} />
  if (riscos.status === 'loading') return <Carregando altura="h-96" />
  return <TabelaRiscos riscos={riscos.data} />
}

function TabelaRiscos({ riscos }: { riscos: RiscoUsina[] }) {
  const navigate = useNavigate()
  const abrir = (r: RiscoUsina) => navigate(rotaDetalheAlerta(r.id))

  // filtros: severidade (topbar) + os desta tela
  const { visiveis, ocultos } = useFiltradosPorSeveridade(riscos, (r) => r.severidade)
  const [busca, setBusca] = useState('')
  const [razoes, setRazoes] = useState<Set<Razao>>(() => new Set(RazaoSchema.options))
  const [fontes, setFontes] = useState<Set<FonteGeracao>>(() => new Set(FonteGeracaoSchema.options))
  const [horizontes, setHorizontes] = useState<Set<Horizonte>>(() => new Set(HorizonteSchema.options))
  const filtrados = useMemo(
    () =>
      visiveis.filter(
        (r) =>
          razoes.has(r.razao) &&
          fontes.has(r.fonte) &&
          horizontes.has(r.horizonte) &&
          casaBusca(busca, [r.nome, r.uf, r.distribuidora, r.acaoRecomendada, r.razao]),
      ),
    [visiveis, razoes, fontes, horizontes, busca],
  )
  const { ordenados, ordenacao, alternar } = useOrdenacao(filtrados, COMPARADORES, { chave: 'severidade', direcao: 'desc' }, DIRECAO_PADRAO)
  const porSeveridade = contarPor(ordenados, (r) => r.severidade, [...SeveridadeSchema.options].reverse())

  return (
    <div className="space-y-4">
      {/* resumo do recorte na tela */}
      <div className="grid gap-px border border-line bg-line sm:grid-cols-3 xl:grid-cols-6">
        <Resumo rotulo="Usinas na tela" valor={String(ordenados.length)} extra={`de ${riscos.length}`} />
        <Resumo rotulo="Montante previsto" valor={`${formatMw(montanteEmRiscoMw(ordenados))} MW`} />
        {(Object.entries(porSeveridade) as [keyof typeof RISK_STYLES, number][]).map(([s, n]) => (
          <Resumo key={s} rotulo={RISK_STYLES[s].label} valor={String(n)} ponto={RISK_STYLES[s].dot} />
        ))}
      </div>

      <Card
        flush
        title="Usinas com risco de curtailment"
        actions={
          <>
            <MockTag mock={riscos.some((r) => r.mock)} />
            <BotaoExportar nome="riscos_curtailment" colunas={CSV} linhas={ordenados} />
          </>
        }
      >
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-line px-4 py-2.5">
          <CampoBusca valor={busca} onChange={setBusca} placeholder="Buscar usina, UF, conexão, ação…" />
          <FiltroChips rotulo="Razão" opcoes={RazaoSchema.options} ativos={razoes} onChange={setRazoes} pontoOpcao={(r) => RAZAO_INFO[r].dot} />
          <FiltroChips rotulo="Fonte" opcoes={FonteGeracaoSchema.options} ativos={fontes} onChange={setFontes} />
          <FiltroChips rotulo="Horizonte" opcoes={HorizonteSchema.options} ativos={horizontes} onChange={setHorizontes} />
        </div>

        <Tabela colunas={COLUNAS} ordenacao={ordenacao} onOrdenar={(k) => alternar(k as ChaveOrdem)}>
          {ordenados.map((r) => (
            <tr
              key={r.id}
              // Linha inteira clicável; tabIndex + Enter/Espaço para quem navega por teclado.
              tabIndex={0}
              role="link"
              aria-label={`Abrir alerta de ${r.nome} (${r.uf})`}
              onClick={() => abrir(r)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault()
                  abrir(r)
                }
              }}
              className={`group cursor-pointer ${LINHA} hover:bg-surface-raised focus-visible:bg-surface-raised focus-visible:outline focus-visible:outline-1 focus-visible:outline-accent`}
            >
              {/* faixa de severidade na borda esquerda (leitura de relance, padrão do Figma) */}
              <td className={`${CELULA} border-l-2 ${RISK_STYLES[r.severidade].barra}`}>
                <SeverityBadge level={r.severidade} />
              </td>
              <td className={CELULA}>
                <span className="mr-2 font-mono text-xs text-ink-muted">{r.uf}</span>
                <span className="font-medium text-ink">{r.nome}</span>
              </td>
              <td className={`${CELULA} text-ink-muted`}>{r.distribuidora}</td>
              <td className={`${CELULA} text-ink-muted`}>{r.fonte}</td>
              <td className={CELULA}>
                <RazaoBadge razao={r.razao} />
              </td>
              <td className={CELULA}>
                <Probabilidade pct={r.probabilidadePct} />
              </td>
              <td className={`${CELULA} kpi text-right text-ink`}>
                {formatMw(r.montanteMw)} <span className="text-xs text-ink-muted">MW</span>
              </td>
              <td className={`${CELULA} kpi text-ink-muted`}>{r.horizonte}</td>
              <td className={`${CELULA} quebra min-w-48 text-ink-muted`}>{r.acaoRecomendada}</td>
              <td className="pr-3 text-right" onClick={(e) => e.stopPropagation()}>
                <span className="inline-flex items-center gap-1">
                  <BotaoLink variante="fantasma" to={rotaMapa({ tipo: 'risco', id: r.id })} title="Ver no mapa" aria-label={`Ver ${r.nome} no mapa`}>
                    <MapPin className="size-3.5" aria-hidden />
                  </BotaoLink>
                  <ChevronRight className="size-4 text-ink-faint group-hover:text-accent" aria-hidden />
                </span>
              </td>
            </tr>
          ))}
          {!ordenados.length && <LinhaVazia colunas={COLUNAS.length} texto="Nenhuma usina com os filtros atuais." />}
        </Tabela>

        <AvisoFiltro ocultos={ocultos} className="border-t border-line px-4 py-2" />
        <LegendaRazoes />
      </Card>
    </div>
  )
}

function Resumo({ rotulo, valor, extra, ponto }: { rotulo: string; valor: string; extra?: string; ponto?: string }) {
  return (
    <div className="bg-surface px-4 py-2.5">
      <p className="rotulo flex items-center gap-1.5 text-[10px]">
        {ponto && <span className={`size-1.5 rounded-full ${ponto}`} aria-hidden />}
        {rotulo}
      </p>
      <p className="kpi mt-0.5 text-lg font-semibold text-ink">
        {valor} {extra && <span className="text-xs font-normal text-ink-faint">{extra}</span>}
      </p>
    </div>
  )
}

/** Número + barra fina 0–100% (magnitude em cor única; a severidade já tem coluna própria). */
function Probabilidade({ pct }: { pct: number }) {
  return (
    <div className="flex items-center justify-end gap-2">
      <div className="h-1 w-12 overflow-hidden rounded-full bg-line" aria-hidden>
        <div className="h-full rounded-full bg-accent" style={{ width: `${pct}%` }} />
      </div>
      <span className="kpi w-12 text-right text-ink">{formatPct(pct, 0)}%</span>
    </div>
  )
}

/** Significado das siglas, abaixo da tabela. */
function LegendaRazoes() {
  return (
    <ul className="flex flex-wrap gap-x-6 gap-y-2 border-t border-line px-4 py-2.5 text-xs text-ink-muted">
      {Object.entries(RAZAO_INFO).map(([sigla, info]) => (
        <li key={sigla} className="flex items-center gap-2">
          <span className={`size-2 rounded-full ${info.dot}`} aria-hidden />
          <span className="font-mono text-ink">{sigla}</span> {info.nome}
        </li>
      ))}
    </ul>
  )
}
