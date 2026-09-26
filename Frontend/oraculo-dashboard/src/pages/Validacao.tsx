/**
 * Validação: erro do modelo vs. baseline (MAE e RMSE) no período escolhido (7, 14 ou 30 dias),
 * resumo do período (em quantos dias o modelo venceu o baseline, pior dia), status das fontes
 * de dados (offline primeiro), metadados do modelo, limitações declaradas e CSV do histórico.
 *
 * Os KPIs do topo são os do Backend (janela fixa publicada); o seletor de período muda os
 * gráficos e o resumo, que são recalculados do histórico diário (resumoValidacao).
 */
import { useState } from 'react'
import { GraficoErro, type PontoErro } from '../components/charts/GraficoErro'
import { BotaoExportar } from '../components/ui/BotaoExportar'
import { Card } from '../components/ui/Card'
import { SegmentedControl } from '../components/ui/SegmentedControl'
import { resumoValidacao } from '../data/derivados'
import type { ColunaCsv } from '../utils/csv'
import { Carregando, ErroDados } from '../components/ui/Estado'
import { KpiCard } from '../components/ui/KpiCard'
import { ListaLimitacoes } from '../components/ui/ListaLimitacoes'
import { MockTag } from '../components/ui/MockTag'
import { StatusPill } from '../components/ui/StatusPill'
import { LIMITACOES } from '../content/limitacoes'
import { getValidacao } from '../data/dataSource'
import type { MetricasValidacao, ModeloInfo } from '../data/types'
import { useDados } from '../data/useDados'
import { formatDataHoraBrt, formatHaQuanto, formatMw, formatNum } from '../utils/format'

const PERIODOS = ['7 dias', '14 dias', '30 dias'] as const
type Periodo = (typeof PERIODOS)[number]
const DIAS: Record<Periodo, number> = { '7 dias': 7, '14 dias': 14, '30 dias': 30 }

type LinhaHistorico = MetricasValidacao['historicoErro30d'][number]
const CSV_HISTORICO: ColunaCsv<LinhaHistorico>[] = [
  { rotulo: 'data', valor: (h) => h.data },
  { rotulo: 'mae_modelo_mw', valor: (h) => h.mae },
  { rotulo: 'mae_baseline_mw', valor: (h) => h.maeBaseline },
  { rotulo: 'rmse_modelo_mw', valor: (h) => h.rmse },
  { rotulo: 'rmse_baseline_mw', valor: (h) => h.rmseBaseline },
]

export default function Validacao() {
  const dados = useDados(getValidacao)
  if (dados.status === 'erro') return <ErroDados erro={dados.erro} />
  if (dados.status === 'loading') return <Carregando altura="h-96" />
  return <PainelValidacao v={dados.data} />
}

function PainelValidacao({ v }: { v: MetricasValidacao }) {
  const [periodo, setPeriodo] = useState<Periodo>('30 dias')
  const historico = v.historicoErro30d.slice(-DIAS[periodo])
  const resumo = resumoValidacao(v.historicoErro30d, DIAS[periodo])

  // Série de cada gráfico montada a partir do histórico (uma métrica por gráfico).
  const serie = (m: 'mae' | 'rmse'): PontoErro[] =>
    historico.map((h) => ({ data: h.data, modelo: h[m], baseline: m === 'mae' ? h.maeBaseline : h.rmseBaseline }))

  return (
    <div className="space-y-4">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <KpiCard label="MAE" accent="border-t-chart-1" value={formatMw(v.erroMedioAbsolutoMw)} unit="MW" actions={<MockTag mock={v.mock} />} hint="erro médio absoluto, 30 dias" />
        <KpiCard label="RMSE" value={formatMw(v.rmseMw)} unit="MW" actions={<MockTag mock={v.mock} />} hint="penaliza erros grandes" />
        <KpiCard label="MAPE" value={formatNum(v.mapePct)} unit="%" actions={<MockTag mock={v.mock} />} hint="erro percentual médio" />
        <KpiCard
          label={`Skill vs. ${v.baselineNome}`}
          value={formatNum(v.skillVsClimatologia * 100, 0)}
          unit="%"
          actions={<MockTag mock={v.mock} />}
          hint={`1 − MAE modelo ÷ MAE ${v.baselineNome.toLowerCase()} (> 0 = melhor)`}
        />
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <SegmentedControl label="Período dos gráficos" options={PERIODOS} value={periodo} onChange={setPeriodo} />
        {resumo && (
          <p className="kpi text-xs text-ink-muted">
            no período: MAE médio diário <span className="text-ink">{formatMw(resumo.maeMedio)} MW</span> × {formatMw(resumo.maeBaselineMedio)} MW do {v.baselineNome.toLowerCase()} ·
            modelo melhor em <span className="text-ink">{resumo.diasMelhorQueBaseline} de {resumo.dias}</span> dias · pior dia{' '}
            {resumo.piorDia.data.slice(8, 10)}/{resumo.piorDia.data.slice(5, 7)} ({formatMw(resumo.piorDia.mae)} MW)
          </p>
        )}
        <span className="ml-auto">
          <BotaoExportar nome="validacao_erro_diario" colunas={CSV_HISTORICO} linhas={historico} />
        </span>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <Card title="MAE diário · modelo vs. baseline" actions={<MockTag mock={v.mock} />}>
          <GraficoErro dados={serie('mae')} metrica="MAE" baselineNome={v.baselineNome} />
        </Card>
        <Card title="RMSE diário · modelo vs. baseline" actions={<MockTag mock={v.mock} />}>
          <GraficoErro dados={serie('rmse')} metrica="RMSE" baselineNome={v.baselineNome} />
        </Card>
      </div>

      <StatusFontes fontes={v.statusFontes} mock={v.mock} />

      <div className="grid gap-4 xl:grid-cols-2">
        <MetadadosModelo modelo={v.modelo} mock={v.mock} />
        <Limitacoes />
      </div>
    </div>
  )
}

function StatusFontes({ fontes, mock }: { fontes: MetricasValidacao['statusFontes']; mock: boolean }) {
  return (
    <Card title="Status das fontes de dados" actions={<MockTag mock={mock} />}>
      <ul className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        {/* offline primeiro (é o que pede atenção), depois a sincronização mais antiga */}
        {[...fontes].sort((a, b) => Number(a.online) - Number(b.online) || a.ultimaSincronizacao.localeCompare(b.ultimaSincronizacao)).map((f) => (
          <li key={f.fonte} className="border border-line bg-fundo p-3">
            <p className="min-h-10 text-body text-ink">{f.fonte}</p>
            {/* pill com texto "online"/"offline": estado nunca comunicado só pela cor */}
            <StatusPill level={f.online ? 'low' : 'critical'} label={f.online ? 'online' : 'offline'} pulse={f.online} className="mt-2" />
            <p className="kpi mt-2 text-[11px] text-ink-muted">
              sinc. {formatDataHoraBrt(f.ultimaSincronizacao)} BRT
              <br />
              {formatHaQuanto(f.ultimaSincronizacao)}
            </p>
          </li>
        ))}
      </ul>
    </Card>
  )
}

function MetadadosModelo({ modelo, mock }: { modelo: ModeloInfo; mock: boolean }) {
  const periodo = (p: { inicio: string; fim: string }) => `${p.inicio} → ${p.fim}`
  const itens: [string, string][] = [
    ['Modelo', modelo.nome],
    ['Versão', modelo.versao],
    ['Data de treino', modelo.dataTreino],
    ['Treino (split cronológico)', periodo(modelo.periodoTreino)],
    ['Teste (fora da amostra)', periodo(modelo.periodoTeste)],
  ]
  return (
    <Card title="Metadados do modelo" actions={<MockTag mock={mock} />}>
      {mock && (
        <p className="mb-3 text-xs text-ink-muted">Placeholder: nenhum modelo foi treinado ainda.</p>
      )}
      <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-2 text-body">
        {itens.map(([k, val]) => (
          <div key={k} className="contents">
            <dt className="text-ink-muted">{k}</dt>
            <dd className="kpi text-ink">{val}</dd>
          </div>
        ))}
      </dl>
    </Card>
  )
}

function Limitacoes() {
  return (
    <Card title="Limitações declaradas">
      <ListaLimitacoes itens={LIMITACOES} />
    </Card>
  )
}
