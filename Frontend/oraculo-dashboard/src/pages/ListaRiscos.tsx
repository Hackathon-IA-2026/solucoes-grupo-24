/**
 * Lista de Riscos: usinas ordenadas por severidade (critical no topo). Clique (ou Enter)
 * numa linha abre o Detalhe do Alerta daquele risco.
 */
import { ChevronRight } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { AvisoFiltro } from '../components/ui/AvisoFiltro'
import { Card } from '../components/ui/Card'
import { Carregando, ErroDados } from '../components/ui/Estado'
import { MockTag } from '../components/ui/MockTag'
import { RazaoBadge } from '../components/ui/RazaoBadge'
import { SeverityBadge } from '../components/ui/SeverityBadge'
import { CELULA, LINHA, Tabela, type ColunaTabela } from '../components/ui/Tabela'
import { getRiscos } from '../data/dataSource'
import { montanteEmRiscoMw, ordenarPorSeveridade } from '../data/derivados'
import type { RiscoUsina } from '../data/types'
import { useDados } from '../data/useDados'
import { rotaDetalheAlerta } from '../modules'
import { useFiltradosPorSeveridade } from '../state/useSeverityFilter'
import { RAZAO_INFO } from '../theme/razao'
import { RISK_STYLES } from '../theme/severity'
import { formatMw, formatPct } from '../utils/format'

// Colunas da tabela (moldura em components/ui/Tabela.tsx).
const COLUNAS: ColunaTabela[] = [
  { rotulo: 'Severidade' },
  { rotulo: 'Usina / UF' },
  { rotulo: 'Distribuidora' },
  { rotulo: 'Fonte' },
  { rotulo: 'Razão' },
  { rotulo: 'Probabilidade', num: true },
  { rotulo: 'Montante previsto', num: true },
  { rotulo: 'Horizonte' },
  { rotulo: 'Ação recomendada' },
  { rotulo: 'Abrir', semRotulo: true },
]

export default function ListaRiscos() {
  const riscos = useDados(getRiscos)
  if (riscos.status === 'erro') return <ErroDados erro={riscos.erro} />
  if (riscos.status === 'loading') return <Carregando altura="h-96" />
  return <TabelaRiscos riscos={ordenarPorSeveridade(riscos.data)} />
}

function TabelaRiscos({ riscos }: { riscos: RiscoUsina[] }) {
  const navigate = useNavigate()
  const abrir = (r: RiscoUsina) => navigate(rotaDetalheAlerta(r.id))
  // Filtros de severidade da topbar; o total no cabeçalho é o do que está visível.
  const { visiveis, ocultos } = useFiltradosPorSeveridade(riscos, (r) => r.severidade)

  return (
    <Card
      flush
      title="Usinas com risco de curtailment"
      actions={
        <>
          <MockTag mock={riscos.some((r) => r.mock)} />
          <span className="kpi text-xs text-ink-muted">
            {visiveis.length} usinas · {formatMw(montanteEmRiscoMw(visiveis))} MW
          </span>
        </>
      }
    >
      <Tabela colunas={COLUNAS}>
        {visiveis.map((r) => (
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
            <td className="pr-3 text-ink-faint group-hover:text-accent">
              <ChevronRight className="size-4" aria-hidden />
            </td>
          </tr>
        ))}
      </Tabela>

      <AvisoFiltro ocultos={ocultos} className="border-t border-line px-4 py-2" />
      <LegendaRazoes />
    </Card>
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
