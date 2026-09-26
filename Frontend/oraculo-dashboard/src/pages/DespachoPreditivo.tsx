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
import { BotaoExportar } from '../components/ui/BotaoExportar'
import { CELULA, LINHA, Tabela } from '../components/ui/Tabela'
import { formatIntervalo, PATAMARES } from '../content/calendario'
import { resumoCurva, resumoPatamar } from '../data/derivados'
import { getCarga, getPrevisao } from '../data/dataSource'
import { HorizonteSchema, type CargaSnapshot, type FatoresClimaticos, type Horizonte, type PontoPrevisao, type PrevisaoCurva } from '../data/types'
import { useDados } from '../data/useDados'
import type { ColunaCsv } from '../utils/csv'
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

const VISOES = ['Gráfico', 'Tabela'] as const
type Visao = (typeof VISOES)[number]

function Previsao({ curvas, horizonte, onHorizonte }: { curvas: PrevisaoCurva[]; horizonte: Horizonte; onHorizonte: (h: Horizonte) => void }) {
  const curva = curvas.find((c) => c.horizonte === horizonte)
  const [visao, setVisao] = useState<Visao>('Gráfico')
  return (
    <>
      {/* filtros numa linha acima do gráfico */}
      <div className="flex flex-wrap items-center gap-3">
        <SegmentedControl label="Horizonte de previsão" options={HORIZONTES} value={horizonte} onChange={onHorizonte} />
        <SegmentedControl label="Visualização" options={VISOES} value={visao} onChange={setVisao} />
        {curva && (
          <span className="kpi text-xs text-ink-muted">
            {formatDataHoraBrt(curva.pontos[0].timestamp)} → {formatDataHoraBrt(curva.pontos.at(-1)!.timestamp)} BRT ·{' '}
            {curva.pontos.length} pontos de 30 min
          </span>
        )}
      </div>

      {curva ? (
        <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_18rem]">
          <div className="min-w-0 space-y-4">
            {visao === 'Gráfico' ? <PainelCurva curva={curva} /> : <TabelaCurva curva={curva} />}
            <ResumoDaCurva curva={curva} />
          </div>
          <div className="space-y-4">
            <PainelClima fatores={curva.fatoresClimaticos} mock={curva.mock} />
            <PainelPatamares curva={curva} />
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
function PainelPatamares({ curva }: { curva: PrevisaoCurva }) {
  return (
    <Card title="Patamares · o erro que custa mais">
      <ul className="space-y-3">
        {PATAMARES.map((p) => {
          // o que ESTA curva prevê dentro do patamar (P50 e incerteza médios)
          const r = resumoPatamar(curva.pontos, p.horas)
          return (
            <li key={p.chave}>
              <p className="flex items-baseline justify-between gap-2 text-body text-ink">
                {p.nome}
                <span className="kpi text-xs text-ink-faint">{formatIntervalo(p.horas)}</span>
              </p>
              {r ? (
                <p className="kpi mt-0.5 text-xs text-ink">
                  P50 médio {formatGw(r.p50MedioMw)} GW · banda {formatGw(r.bandaMediaMw)} GW
                </p>
              ) : (
                <p className="mt-0.5 text-xs text-ink-faint">fora da janela desta curva</p>
              )}
              <p className="mt-0.5 text-xs text-ink-muted">Pior erro: {p.errarPior}.</p>
            </li>
          )
        })}
      </ul>
    </Card>
  )
}

/**
 * Resumo da curva (pitch, slide 5: "amplitude diária" e rampa): mínima e máxima do P50 com o
 * horário, amplitude, incerteza média e o instante de maior incerteza. Tudo de resumoCurva().
 */
function ResumoDaCurva({ curva }: { curva: PrevisaoCurva }) {
  const r = resumoCurva(curva.pontos)
  if (!r) return null
  const itens: [string, string, string][] = [
    ['Mínima (P50)', `${formatGw(r.minimo.mw)} GW`, `${formatHoraBrt(r.minimo.timestamp)} BRT`],
    ['Máxima (P50)', `${formatGw(r.maximo.mw)} GW`, `${formatHoraBrt(r.maximo.timestamp)} BRT`],
    ['Amplitude', `${formatGw(r.amplitudeMw)} GW`, 'máx − mín'],
    [`Maior rampa (${curva.janelaRampaHoras}h)`, `${formatGw(curva.rampaProjetadaMw)} GW`, 'subida do P50'],
    ['Incerteza média', `${formatGw(r.bandaMediaMw)} GW`, 'largura P10–P90'],
    ['Maior incerteza', `${formatGw(r.bandaMaxima.mw)} GW`, `${formatHoraBrt(r.bandaMaxima.timestamp)} BRT`],
  ]
  return (
    <dl className="grid gap-px border border-line bg-line sm:grid-cols-3 2xl:grid-cols-6">
      {itens.map(([k, v, apoio]) => (
        <div key={k} className="bg-surface px-4 py-2.5">
          <dt className="rotulo text-[10px]">{k}</dt>
          <dd className="kpi mt-0.5 text-lg font-semibold text-ink">{v}</dd>
          <dd className="text-[11px] text-ink-faint">{apoio}</dd>
        </div>
      ))}
    </dl>
  )
}

const CSV_CURVA: ColunaCsv<PontoPrevisao>[] = [
  { rotulo: 'timestamp_utc', valor: (p) => p.timestamp },
  { rotulo: 'horario_brt', valor: (p) => formatDataHoraBrt(p.timestamp) },
  { rotulo: 'p10_mw', valor: (p) => p.p10 },
  { rotulo: 'p50_mw', valor: (p) => p.p50 },
  { rotulo: 'p90_mw', valor: (p) => p.p90 },
  { rotulo: 'banda_mw', valor: (p) => p.p90 - p.p10 },
]

/** Os 48 pontos em tabela (leitura exata e acessibilidade) + CSV. */
function TabelaCurva({ curva }: { curva: PrevisaoCurva }) {
  return (
    <Card
      flush
      title={`Pontos da curva · horizonte ${curva.horizonte}`}
      actions={
        <>
          <MockTag mock={curva.mock} />
          <BotaoExportar nome={`previsao_carga_${curva.horizonte}`} colunas={CSV_CURVA} linhas={curva.pontos} />
        </>
      }
    >
      <div className="max-h-[26rem] overflow-y-auto">
        <Tabela colunas={[{ rotulo: 'Horário (BRT)' }, { rotulo: 'P10', num: true }, { rotulo: 'P50', num: true }, { rotulo: 'P90', num: true }, { rotulo: 'Banda P10–P90', num: true }]}>
          {curva.pontos.map((p) => (
            <tr key={p.timestamp} className={LINHA}>
              <td className={`${CELULA} kpi text-ink-muted`}>{formatDataHoraBrt(p.timestamp)}</td>
              <td className={`${CELULA} kpi text-right text-ink-muted`}>{formatMw(p.p10)}</td>
              <td className={`${CELULA} kpi text-right text-ink`}>{formatMw(p.p50)}</td>
              <td className={`${CELULA} kpi text-right text-ink-muted`}>{formatMw(p.p90)}</td>
              <td className={`${CELULA} kpi text-right text-ink-faint`}>{formatMw(p.p90 - p.p10)}</td>
            </tr>
          ))}
        </Tabela>
      </div>
    </Card>
  )
}
