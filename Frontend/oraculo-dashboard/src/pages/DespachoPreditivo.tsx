/**
 * Despacho Preditivo: curva de carga supervisionada (P10/P50/P90) por horizonte, com
 * destaque da rampa, e painel lateral com os fatores climáticos da previsão.
 */
import { useState } from 'react'
import { Cloud, Sun, Thermometer, Wind } from 'lucide-react'
import { GraficoPrevisao } from '../components/charts/GraficoPrevisao'
import { Card } from '../components/ui/Card'
import { Carregando, ErroDados } from '../components/ui/Estado'
import { MiniStat } from '../components/ui/MiniStat'
import { MockTag } from '../components/ui/MockTag'
import { SegmentedControl } from '../components/ui/SegmentedControl'
import { getPrevisao } from '../data/dataSource'
import { HorizonteSchema, type FatoresClimaticos, type Horizonte, type PrevisaoCurva } from '../data/types'
import { useDados } from '../data/useDados'
import { formatDataHoraBrt, formatGw, formatNum, formatPct } from '../utils/format'

// Opções do seletor vêm do próprio schema: horizonte novo no contrato aparece aqui sozinho.
const HORIZONTES = HorizonteSchema.options

export default function DespachoPreditivo() {
  const [horizonte, setHorizonte] = useState<Horizonte>('D+1')
  // Busca as três curvas uma vez e troca só a exibida: mudar de horizonte é instantâneo.
  const previsao = useDados(getPrevisao)

  const seletor = (
    <SegmentedControl label="Horizonte de previsão" options={HORIZONTES} value={horizonte} onChange={setHorizonte} />
  )

  if (previsao.status === 'erro') return <ErroDados erro={previsao.erro} />
  if (previsao.status === 'loading') return <Carregando altura="h-96" />

  const curva = previsao.data.find((c) => c.horizonte === horizonte)

  return (
    <div className="space-y-4">
      {/* filtros numa linha acima do gráfico */}
      <div className="flex flex-wrap items-center gap-3">
        {seletor}
        {curva && (
          <span className="kpi text-xs text-ink-muted">
            {formatDataHoraBrt(curva.pontos[0].timestamp)} → {formatDataHoraBrt(curva.pontos.at(-1)!.timestamp)} BRT ·{' '}
            {curva.pontos.length} pontos de 30 min
          </span>
        )}
      </div>

      {curva ? (
        <div className="grid gap-4 xl:grid-cols-[1fr_16rem]">
          <PainelCurva curva={curva} />
          <PainelClima fatores={curva.fatoresClimaticos} mock={curva.mock} />
        </div>
      ) : (
        <Card>
          <p className="text-sm text-ink-muted">Sem curva disponível para o horizonte {horizonte}.</p>
        </Card>
      )}
    </div>
  )
}

function PainelCurva({ curva }: { curva: PrevisaoCurva }) {
  return (
    <Card
      title={`Carga supervisionada · horizonte ${curva.horizonte}`}
      actions={
        <>
          <MockTag mock={curva.mock} />
          <span className="kpi text-xs text-ink-muted">
            rampa {formatGw(curva.rampaProjetadaMw)} GW / {curva.janelaRampaHoras}h
          </span>
        </>
      }
    >
      <GraficoPrevisao curva={curva} />
      {/* legenda: uma série com banda + a anotação de rampa */}
      <ul className="mt-3 flex flex-wrap gap-x-6 gap-y-2 text-xs text-ink-muted">
        <li className="flex items-center gap-2">
          <span className="h-0.5 w-5 rounded bg-accent" aria-hidden /> P50 (mediana)
        </li>
        <li className="flex items-center gap-2">
          <span className="h-3 w-5 rounded-sm border border-accent/40 bg-accent/15" aria-hidden /> Banda P10–P90
        </li>
        <li className="flex items-center gap-2">
          <span className="h-1 w-5 rounded bg-ink" aria-hidden /> Maior rampa em {curva.janelaRampaHoras}h
        </li>
      </ul>
    </Card>
  )
}

function PainelClima({ fatores, mock }: { fatores: FatoresClimaticos; mock: boolean }) {
  return (
    <aside className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-semibold uppercase tracking-widest text-ink-muted">Fatores climáticos</h3>
        <MockTag mock={mock} />
      </div>
      <div className="grid grid-cols-2 gap-3 xl:grid-cols-1">
        <MiniStat icon={Sun} label="Radiação solar" value={formatNum(fatores.radiacaoSolar, 0)} unit="W/m²" />
        <MiniStat icon={Wind} label="Vento" value={formatNum(fatores.ventoMs)} unit="m/s" />
        <MiniStat icon={Thermometer} label="Temperatura" value={formatNum(fatores.temperaturaC)} unit="°C" />
        <MiniStat icon={Cloud} label="Cobertura de nuvens" value={formatPct(fatores.coberturaNuvensPct, 0)} unit="%" />
      </div>
    </aside>
  )
}
