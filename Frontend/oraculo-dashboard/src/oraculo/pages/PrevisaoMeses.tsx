/**
 * Previsão de meses (Operação): demanda, MMGD e curva do pato prevista para 1–6 meses.
 * Especificação: docs/oraculo/especificacao/17-previsao-meses-carga-mmgd-pato.md (Fases 1–3).
 * Dado: GET /api/previsao-meses (Backend/src/api/previsao_meses.py, fora do contrato), gravado por
 * Backend/src/models/pato_meses.py. A tela só lê; nenhum cálculo aqui além de escolher o que mostrar.
 */
import { useState } from 'react'
import { Api, type Envelope } from '../api'
import { lineChart } from '../charts'
import { num } from '../format'
import { Chip, Conteudo, Grafico, Kpi, OCard, Pagina, Proveniencia, StatLines, Vazio, useApi } from '../ui'

/* eslint-disable @typescript-eslint/no-explicit-any */
type Dado = any

const SERIES = ['SIN', 'SE', 'S', 'NE', 'N']
const CENARIO: Record<string, string> = { baixo: 'baixo (PAR/PEL)', referencia: 'referência (PLAN)', alto: 'alto (cadastro)' }
const HORAS = Array.from({ length: 24 }, (_, h) => h)
const pctFmt = (v: number | null | undefined, d = 0) => (v === null || v === undefined || !Number.isFinite(v) ? '—' : (100 * v).toFixed(d) + '%')
const sinal = (v: number | null | undefined) => (v === null || v === undefined || !Number.isFinite(v) ? '—' : (v > 0 ? '+' : '') + v.toFixed(3))

export default function PrevisaoMeses() {
  const estado = useApi(() => Api.get('previsao-meses'), [])
  return (
    <Pagina>
      <Conteudo estado={estado} texto="Lendo a previsão de meses…">
        {(b) => <Corpo body={b as Envelope} />}
      </Conteudo>
    </Pagina>
  )
}

function Corpo({ body }: { body: Envelope }) {
  const d = body.data as Dado
  const [serie, setSerie] = useState('SIN')
  const [cenario, setCenario] = useState('referencia')
  const [iMes, setIMes] = useState(0)
  const bloco = d.series?.[serie]?.[cenario]
  if (!bloco) return <Vazio>Sem previsão para {serie} no cenário {cenario}.</Vazio>
  const meses: Dado[] = bloco.meses
  const m = meses[Math.min(iMes, meses.length - 1)]
  const pf = m.perfil
  const [b0, b1] = d.patamares.barriga
  const [p0, p1] = d.patamares.ponta
  const val = d.validacao
  const linhaPato = (val.pato as Dado[]).find((r) => r.serie === serie) || {}

  return (
    <>
      <div className="chips" style={{ marginBottom: 10 }}>
        {SERIES.map((s) => (
          <Chip key={s} on={serie === s} onClick={() => setSerie(s)}>
            {s}
          </Chip>
        ))}
        <span style={{ width: 16 }} />
        {d.cenarios.map((c: string) => (
          <Chip key={c} on={cenario === c} onClick={() => setCenario(c)} title="Cenário de capacidade instalada de MMGD">
            MMGD {CENARIO[c] || c}
          </Chip>
        ))}
      </div>
      <div className="chips" style={{ marginBottom: 14 }}>
        {meses.map((x, i) => (
          <Chip key={x.mes} on={i === iMes} onClick={() => setIMes(i)} title={x.dias + ' dias previstos'}>
            {x.mes}
          </Chip>
        ))}
      </div>

      <div className="grid g4" style={{ marginBottom: 14 }}>
        <Kpi label={'Barriga da curva do pato · ' + m.mes} value={num(m.barriga.p50)} unit="MW" foot={'P10–P90: ' + num(m.barriga.p10) + ' – ' + num(m.barriga.p90) + ' · ~' + m.hora_barriga + 'h'} accent="teal" />
        <Kpi label="Rampa até a ponta noturna" value={num(m.rampa.p50)} unit="MW" foot={'P10–P90: ' + num(m.rampa.p10) + ' – ' + num(m.rampa.p90)} accent="crimson" />
        <Kpi label="MMGD na hora da barriga" value={num(m.participacao_mmgd_barriga, 1)} unit="% da demanda" foot={'MMGD média do mês ' + num(m.media.g_p50) + ' MW'} accent="amber" />
        <Kpi label="Risco de carga líquida mínima" value={num(m.risco_carga_minima, 0)} unit="% dos dias" foot={'barriga abaixo de ' + num(m.limiar_mw) + ' MW (P5 dos 12 meses anteriores)'} accent="green" />
      </div>

      <div className="grid g-2-1" style={{ marginBottom: 14 }}>
        <OCard
          title={'Curva do pato prevista · dia médio de ' + m.mes + ' · ' + serie}
          hint={bloco.membros + ' anos-análogos do ERA5 · emissão ' + String(d.emissao).replace('T', ' ')}
          note="Carga líquida = demanda − MMGD, com o MESMO ano-análogo nos dois lados (sol forte aquece e sobe a carga). Banda P10–P90 calibrada no backtest. Meses à frente: distribuição climática, não previsão do tempo de um dia."
        >
          <Grafico
            deps={[m, serie, cenario]}
            desenhar={(el) =>
              lineChart(el, {
                index: HORAS,
                height: 300,
                yLabel: 'MW',
                formatTime: (v) => String(v).padStart(2, '0') + 'h',
                xTicks: 12,
                spans: [
                  { from: b0, to: b1 - 1, color: 'amber', opacity: 0.08, label: 'mínima diurna' },
                  { from: p0, to: p1 - 1, color: 'crimson', opacity: 0.08, label: 'ponta noturna' },
                ],
                bands: [{ lower: pf.l_p10, upper: pf.l_p90, color: 'teal', opacity: 0.18, label: 'Carga líquida P10–P90' }],
                series: [
                  { label: 'Demanda (P50)', values: pf.d_p50, color: 'muted', style: 'dash' },
                  { label: 'MMGD (P50)', values: pf.g_p50, color: 'amber', area: true },
                  { label: 'Carga líquida (P50)', values: pf.l_p50, color: 'teal', width: 2.4 },
                ],
              })
            }
          />
        </OCard>
        <OCard title={'Barriga e rampa mês a mês · ' + serie} note="Média diária de cada mês; barriga = mínimo da carga líquida na mínima diurna, rampa = ponta noturna − barriga.">
          <Grafico
            deps={[meses]}
            desenhar={(el) =>
              lineChart(el, {
                index: meses.map((x) => x.mes),
                height: 300,
                yLabel: 'MW',
                formatTime: (v) => String(v),
                bands: [{ lower: meses.map((x) => x.barriga.p10), upper: meses.map((x) => x.barriga.p90), color: 'teal', opacity: 0.18, label: 'Barriga P10–P90' }],
                series: [
                  { label: 'Barriga (P50)', values: meses.map((x) => x.barriga.p50), color: 'teal', width: 2.2 },
                  { label: 'Rampa (P50)', values: meses.map((x) => x.rampa.p50), color: 'crimson' },
                ],
              })
            }
          />
        </OCard>
      </div>

      <OCard title={'Resumo mensal · ' + serie + ' · MMGD ' + (CENARIO[cenario] || cenario)} note="O cenário de capacidade é um eixo, não ruído: compare os três para ver quanto a expansão da MMGD aprofunda a barriga.">
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Mês</th>
                <th className="num">Demanda P50</th>
                <th className="num">MMGD P50</th>
                <th className="num">Carga líquida P50</th>
                <th className="num">Barriga P10 – P50 – P90</th>
                <th className="num">Hora</th>
                <th className="num">Rampa P50</th>
                <th className="num">Risco carga mínima</th>
              </tr>
            </thead>
            <tbody>
              {meses.map((x) => (
                <tr key={x.mes}>
                  <td>{x.mes}</td>
                  <td className="num">{num(x.media.d_p50)}</td>
                  <td className="num">{num(x.media.g_p50)}</td>
                  <td className="num">{num(x.media.l_p50)}</td>
                  <td className="num">{num(x.barriga.p10) + ' – ' + num(x.barriga.p50) + ' – ' + num(x.barriga.p90)}</td>
                  <td className="num">{x.hora_barriga}h</td>
                  <td className="num">{num(x.rampa.p50)}</td>
                  <td className="num">{num(x.risco_carga_minima, 0)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </OCard>

      <div className="grid g3" style={{ marginTop: 14 }}>
        <OCard title={'Validação · curva do pato · ' + serie} note={'Backtest com origem móvel mensal desde ' + val.primeira_emissao + ', horizontes 1–6 meses, contra o sazonal ingênuo (364 dias antes).'}>
          <StatLines
            pares={[
              ['Skill na barriga', sinal(linhaPato.skill_barriga)],
              ['Skill na rampa', sinal(linhaPato.skill_rampa)],
              ['Skill na carga líquida (hora a hora)', sinal(linhaPato.skill_l)],
              ['MAE da barriga', num(linhaPato.barriga_mae_mw) + ' MW'],
              ['Cobertura P10–P90 · carga líquida', pctFmt(linhaPato.l_cobertura)],
              ['Cobertura P10–P90 · barriga', pctFmt(linhaPato.barriga_cobertura)],
              ['Dias avaliados', num(linhaPato.dias)],
            ]}
          />
        </OCard>
        <OCard title={'Validação · MMGD · ' + serie} note="Erro contra a MMGD estimada pelo ONS. 'Tempo perfeito' usa o ERA5 observado: separa o erro do tempo do erro do modelo físico.">
          <StatLines
            pares={[
              ['MAE (anos-análogos)', num(linhaPato.mmgd_mae_mw) + ' MW'],
              ['MAE com tempo perfeito', num(linhaPato.mmgd_mae_tempo_perfeito_mw) + ' MW'],
              ['MAE do sazonal ingênuo', num(linhaPato.mmgd_mae_sazonal_mw) + ' MW'],
              ['Skill MMGD', sinal(linhaPato.skill_mmgd)],
              ['MAE só 09–16h', num(linhaPato.mmgd_mae_diurno_mw) + ' MW'],
            ]}
          />
        </OCard>
        <OCard title="Critérios de aceite da especificação">
          <StatLines
            pares={[
              ['Fase 1 · demanda: skill > 0 sobre o sazonal ingênuo', (val.demanda as Dado[]).filter((r) => r.modelo === 'clim' && r.skill_vs_sazonal_ingenuo > 0).length + ' de 5 séries'],
              ['Fase 2 · erro da MMGD por hora do dia medido', val.aceite.fase2_mmgd_medida ? 'sim' : 'não'],
              ['Fase 3 · skill na barriga > 0 (≥ 3 de 4 subsistemas)', val.aceite.fase3_skill_barriga_subsistemas_positivos + ' de 4 · ' + (val.aceite.fase3_skill_barriga_ok ? 'ok' : 'não')],
              ['Fase 3 · cobertura da carga líquida entre 75% e 85%', val.aceite.fase3_cobertura_l_ok ? 'ok nas 5 séries' : 'não'],
              ['Fase 4 · FourCastNet 3', 'pendente (sem GPU)'],
              ['Fase 5 · fator da visão computacional', 'pendente (sem imagem real)'],
            ]}
          />
        </OCard>
      </div>

      <div className="grid g-2-1" style={{ marginTop: 14 }}>
        <OCard title="Erro da MMGD por hora do dia · SIN" note="MAE (MW) do backtest por hora: anos-análogos × tempo perfeito (ERA5 observado).">
          <Grafico
            deps={[val]}
            desenhar={(el) => {
              const ph = val.mmgd_por_hora_sin as Dado[]
              lineChart(el, {
                index: ph.map((r) => r.hora),
                height: 240,
                yLabel: 'MW',
                formatTime: (v) => String(v).padStart(2, '0') + 'h',
                xTicks: 12,
                series: [
                  { label: 'MMGD média do ONS', values: ph.map((r) => r.mmgd_media_mw), color: 'muted', style: 'dash' },
                  { label: 'MAE · anos-análogos', values: ph.map((r) => r.mae_mw), color: 'amber', width: 2 },
                  { label: 'MAE · tempo perfeito', values: ph.map((r) => r.mae_tempo_perfeito_mw), color: 'teal' },
                ],
              })
            }}
          />
        </OCard>
        <OCard title="Validação · demanda (Fase 1)" note="Média dos horizontes 1–6 meses. 'clim' = sem previsão de tempo (a usada para meses); 'era5' = temperatura observada (teto).">
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Série</th>
                  <th>Modelo</th>
                  <th className="num">MAPE</th>
                  <th className="num">Skill</th>
                  <th className="num">Cobertura</th>
                </tr>
              </thead>
              <tbody>
                {(val.demanda as Dado[])
                  .filter((r) => r.modelo !== 'sazonal_ingenuo')
                  .map((r) => (
                    <tr key={r.serie + r.modelo}>
                      <td>{r.serie}</td>
                      <td>{r.modelo}</td>
                      <td className="num">{num(r.mape_pct, 2)}%</td>
                      <td className="num">{sinal(r.skill_vs_sazonal_ingenuo)}</td>
                      <td className="num">{pctFmt(r.cobertura_p10_p90)}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </OCard>
      </div>
      <Proveniencia body={body} />
    </>
  )
}
