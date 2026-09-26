/**
 * Despacho Preditivo: a decomposição carga global − MMGD = carga supervisionada (retrato
 * atual), a curva prevista (P10/P50/P90) por horizonte com a rampa e os patamares destacados,
 * e o painel lateral com fatores climáticos e o porquê dos patamares.
 *
 * Estrutura tirada do protótipo Figma e do pitch (slide 9: "1 · DECOMPOR, 2 · PROJETAR,
 * 3 · QUANTIFICAR INCERTEZA"). Do Figma NÃO veio o "Cenário 2029" com valores fixos: a curva
 * é sempre a do contrato (getPrevisao), e a equação é o snapshot real (getCarga).
 */
import { useState } from 'react'
import { Cloud, Sun, Thermometer, Wind } from 'lucide-react'
import { GraficoPrevisao, LegendaPrevisao } from '../components/charts/GraficoPrevisao'
import { Card } from '../components/ui/Card'
import { Carregando, ErroDados } from '../components/ui/Estado'
import { MiniStat } from '../components/ui/MiniStat'
import { MockTag } from '../components/ui/MockTag'
import { SegmentedControl } from '../components/ui/SegmentedControl'
import { formatIntervalo, PATAMARES } from '../content/calendario'
import { getCarga, getPrevisao } from '../data/dataSource'
import { HorizonteSchema, type CargaSnapshot, type FatoresClimaticos, type Horizonte, type PrevisaoCurva } from '../data/types'
import { useDados } from '../data/useDados'
import { formatDataHoraBrt, formatGw, formatHoraBrt, formatMw, formatNum, formatPct } from '../utils/format'

// Opções do seletor vêm do próprio schema: horizonte novo no contrato aparece aqui sozinho.
const HORIZONTES = HorizonteSchema.options

export default function DespachoPreditivo() {
  const [horizonte, setHorizonte] = useState<Horizonte>('D+1')
  // Busca as três curvas uma vez e troca só a exibida: mudar de horizonte é instantâneo.
  const previsao = useDados(getPrevisao)
  const carga = useDados(getCarga)

  return (
    <div className="space-y-4">
      {carga.status === 'ok' && <EquacaoCarga c={carga.data} />}
      {carga.status === 'erro' && <ErroDados erro={carga.erro} />}
      {carga.status === 'loading' && <Carregando altura="h-28" />}

      {previsao.status === 'erro' && <ErroDados erro={previsao.erro} />}
      {previsao.status === 'loading' && <Carregando altura="h-96" />}
      {previsao.status === 'ok' && <Previsao curvas={previsao.data} horizonte={horizonte} onHorizonte={setHorizonte} />}
    </div>
  )
}

/**
 * Faixa-equação (peça principal do Figma nesta tela): o operador lê a decomposição de uma vez.
 * O resultado (carga supervisionada) tem a borda de identidade da série chart-1.
 */
function EquacaoCarga({ c }: { c: CargaSnapshot }) {
  const termos = [
    { rotulo: 'Carga global', mw: c.cargaGlobalMw, apoio: `snapshot · ${formatHoraBrt(c.timestampUtc)} BRT`, cor: 'text-ink' },
    { rotulo: 'MMGD estimada', mw: c.mmgdEstimadaMw, apoio: `${formatPct(c.percentualMmgdNaGeracao)}% da geração`, cor: 'text-ink' },
  ]
  return (
    <section aria-label="Decomposição da carga" className="border border-line bg-surface">
      <header className="flex items-center justify-between border-b border-line px-4 py-1.5">
        <h2 className="rotulo">Decomposição · carga global − MMGD estimada = carga supervisionada</h2>
        <MockTag mock={c.mock} />
      </header>
      <div className="grid md:grid-cols-[1fr_auto_1fr_auto_1.2fr_0.8fr]">
        {termos.map((t, i) => (
          <div key={t.rotulo} className="contents">
            <Termo {...t} />
            <Operador s={i === 0 ? '−' : '='} />
          </div>
        ))}
        <div className="border-t-2 border-t-chart-1 bg-chart-1/5 px-5 py-4 md:border-t-0 md:border-l-2 md:border-l-chart-1">
          <p className="rotulo text-accent">Carga supervisionada</p>
          <p className="kpi mt-2 flex items-baseline gap-1.5 text-accent">
            <span className="text-kpi-xl font-bold">{formatMw(c.cargaSupervisionadaMw)}</span>
            <span className="text-body opacity-70">MW</span>
          </p>
          <p className="mt-1.5 text-xs text-ink-muted">a carga que o ONS de fato opera</p>
        </div>
        <div className="border-t border-line px-5 py-4 md:border-t-0 md:border-l">
          <p className="rotulo">MMGD ÷ cap. instalada</p>
          <p className="kpi mt-2 text-kpi font-semibold text-chart-2">
            {formatPct(c.mmgdSobreCapacidadeInstalada * 100)}
            <span className="text-body">%</span>
          </p>
          <p className="mt-1.5 text-xs text-ink-muted">fator de geração da MMGD agora</p>
        </div>
      </div>
    </section>
  )
}

/** Sinal da equação (− / =) entre os termos; decorativo, some em tela estreita. */
function Operador({ s }: { s: string }) {
  return (
    <div className="hidden items-center px-3 font-mono text-4xl font-light text-ink-faint md:flex" aria-hidden>
      {s}
    </div>
  )
}

function Termo({ rotulo, mw, apoio, cor }: { rotulo: string; mw: number; apoio: string; cor: string }) {
  return (
    <div className="px-5 py-4">
      <p className="rotulo">{rotulo}</p>
      <p className={`kpi mt-2 flex items-baseline gap-1.5 ${cor}`}>
        <span className="text-kpi-xl font-semibold">{formatMw(mw)}</span>
        <span className="text-body text-ink-muted">MW</span>
      </p>
      <p className="mt-1.5 text-xs text-ink-muted">{apoio}</p>
    </div>
  )
}

function Previsao({ curvas, horizonte, onHorizonte }: { curvas: PrevisaoCurva[]; horizonte: Horizonte; onHorizonte: (h: Horizonte) => void }) {
  const curva = curvas.find((c) => c.horizonte === horizonte)
  return (
    <>
      {/* filtros numa linha acima do gráfico */}
      <div className="flex flex-wrap items-center gap-3">
        <SegmentedControl label="Horizonte de previsão" options={HORIZONTES} value={horizonte} onChange={onHorizonte} />
        {curva && (
          <span className="kpi text-xs text-ink-muted">
            {formatDataHoraBrt(curva.pontos[0].timestamp)} → {formatDataHoraBrt(curva.pontos.at(-1)!.timestamp)} BRT ·{' '}
            {curva.pontos.length} pontos de 30 min
          </span>
        )}
      </div>

      {curva ? (
        <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_18rem]">
          <PainelCurva curva={curva} />
          <div className="space-y-4">
            <PainelClima fatores={curva.fatoresClimaticos} mock={curva.mock} />
            <PainelPatamares />
          </div>
        </div>
      ) : (
        <Card>
          <p className="text-body text-ink-muted">Sem curva disponível para o horizonte {horizonte}.</p>
        </Card>
      )}
    </>
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
      <GraficoPrevisao curva={curva} altura="h-[22rem]" />
      <div className="mt-3">
        <LegendaPrevisao janelaRampaHoras={curva.janelaRampaHoras} />
      </div>
    </Card>
  )
}

function PainelClima({ fatores, mock }: { fatores: FatoresClimaticos; mock: boolean }) {
  return (
    <Card flush title="Fatores climáticos" actions={<MockTag mock={mock} />}>
      <div className="divide-y divide-line/60">
        <MiniStat icon={Sun} label="Radiação solar" value={formatNum(fatores.radiacaoSolar, 0)} unit="W/m²" />
        <MiniStat icon={Wind} label="Vento" value={formatNum(fatores.ventoMs)} unit="m/s" />
        <MiniStat icon={Thermometer} label="Temperatura" value={formatNum(fatores.temperaturaC)} unit="°C" />
        <MiniStat icon={Cloud} label="Cobertura de nuvens" value={formatPct(fatores.coberturaNuvensPct, 0)} unit="%" />
      </div>
    </Card>
  )
}

/**
 * Por que os patamares estão marcados na curva: o erro de previsão de carga é ASSIMÉTRICO
 * (lacuna declarada pelo ONS, planejamento v2). Texto e horas vêm de content/calendario.ts.
 */
function PainelPatamares() {
  return (
    <Card title="Patamares · o erro que custa mais">
      <ul className="space-y-3">
        {PATAMARES.map((p) => (
          <li key={p.chave}>
            <p className="flex items-baseline justify-between gap-2 text-body text-ink">
              {p.nome}
              <span className="kpi text-xs text-ink-faint">{formatIntervalo(p.horas)}</span>
            </p>
            <p className="mt-0.5 text-xs text-ink-muted">Pior erro: {p.errarPior}.</p>
          </li>
        ))}
      </ul>
    </Card>
  )
}
