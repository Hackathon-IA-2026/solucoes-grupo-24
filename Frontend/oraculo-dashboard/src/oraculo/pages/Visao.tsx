/**
 * Visão computacional sobre imagem de satélite (protótipo, painel "visao"). Porte de
 * 02-PROTOTIPO/web/js/views/mapa.js (V.visao): detector clássico + adaptador YOLOv8-seg,
 * banco de ensaio contra verdade fundamental, cena de referência e curva precisão × revocação.
 */
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Api, type Envelope } from '../api'
import { fmt, scatter } from '../charts'
import { num, pct, signed } from '../format'
import { Chip, Conteudo, Grafico, Kpi, OCard, Pagina, Proveniencia, StatLines, useApi } from '../ui'

/* eslint-disable @typescript-eslint/no-explicit-any */
type Dado = any

const BENCH_MODOS: [string, string][] = [
  ['', 'detecções'],
  ['?truth=1&tiles=1', 'verdade + ladrilhos + falsos negativos'],
  ['?channel=azul', 'índice de azul'],
  ['?channel=borda', 'densidade de borda'],
  ['?channel=luminancia', 'luminância'],
]

export default function Visao() {
  const estado = useApi(() => Api.get('mapa/vision'), [])
  return (
    <Pagina>
      <div className="note-strip" style={{ marginBottom: 12 }}>
        Esta é a solução de visão do protótipo (detector por subestação). A auditoria em 3 camadas do time (YOLOv8-seg + BDGD + ANEEL) está em{' '}
        <Link to="/auditoria-mmgd">Visão computacional › Auditoria MMGD · 3 camadas</Link>.
      </div>
      <Conteudo estado={estado} texto="Executando o banco de ensaio do detector…">
        {(body) => <Corpo body={body} />}
      </Conteudo>
    </Pagina>
  )
}

function Corpo({ body }: { body: Envelope }) {
  const d = body.data as Dado
  const ag = d.aggregate || {}
  const ref = d.reference || {}
  const cal = d.area_calibration || {}
  const backends: Dado[] = d.backends || []
  const yolo = backends.find((b) => b.kind === 'yolo') || {}
  const clas = backends.find((b) => b.kind === 'classico') || {}
  const [bench, setBench] = useState('')
  const pr: Dado[] = (d.pr_curve || []).filter((p: Dado) => p.precision !== null && p.recall !== null)

  return (
    <>
      <div className="note-strip warn">
        <strong>Sobre o YOLO:</strong> {d.yolo_note}
      </div>

      <div className="grid g4" style={{ marginBottom: 14 }}>
        <Kpi label="Precisão" value={pct(ag.precision, 1)} foot={num(ag.scenes) + ' cenas · 4 classes urbanas × 3 sementes'} accent="teal" />
        <Kpi label="Revocação" value={pct(ag.recall, 1)} foot={'F1 ' + num(ag.f1, 3)} accent="green" />
        <Kpi label="IoU de máscara" value={num(ag.mask_iou, 3)} foot={'AP ' + num(ag.average_precision, 3)} accent="navy" />
        <Kpi
          label="Erro de área"
          value={signed(ag.area_rel_error, 3)}
          foot={'bruto ' + signed(ag.area_rel_error_raw, 3) + ' · calibração ' + num(cal.factor, 2) + '×'}
          accent="amber"
        />
      </div>

      <div className="grid g2" style={{ marginBottom: 14 }}>
        <OCard
          title="Backends de detecção"
          note="Os dois implementam a mesma interface. O ladrilhamento, a NMS, a deduplicação na costura e a georreferência são compartilhados e testados: trocar o backend não muda mais nada no pipeline."
        >
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Backend</th>
                  <th>Estado</th>
                  <th>Observação</th>
                </tr>
              </thead>
              <tbody>
                {backends.map((b, i) => (
                  <tr key={i}>
                    <td>
                      <strong>{b.name}</strong>
                      <br />
                      <span className="small faint">{b.runtime}</span>
                    </td>
                    <td>{b.available ? <span className="chip green">ativo</span> : <span className="chip amber">indisponível</span>}</td>
                    <td className="small muted">{b.reason || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </OCard>
        <OCard title="Etapas do detector ativo" hint={clas.runtime || undefined}>
          <ol className="actions" style={{ paddingLeft: 20 }}>
            {(d.pipeline || []).map((s: string, i: number) => (
              <li key={i}>{s}</li>
            ))}
          </ol>
        </OCard>
      </div>

      <div className="grid g-2-1" style={{ marginBottom: 14 }}>
        <OCard
          title="Cena de referência"
          hint={num(ref.truth) + ' painéis reais · ' + num(ref.pred) + ' detectados'}
          note={
            <>
              Teal: detecção. Âmbar: verdade fundamental. Carmim: painel real não detectado. Os canais de característica mostram <em>por que</em> o detector marcou o que marcou.
            </>
          }
        >
          <img
            src={bench ? '/api/mapa/bench.png' + bench : ref.image_url}
            style={{ width: '100%', borderRadius: 6, border: '1px solid var(--o-line)' }}
            alt="cena de referência com detecções"
          />
          <div className="chips" style={{ marginTop: 8 }}>
            {BENCH_MODOS.map(([q, rot]) => (
              <Chip key={q} on={bench === q} onClick={() => setBench(q)}>
                {rot}
              </Chip>
            ))}
          </div>
        </OCard>
        <OCard title="Curva precisão × revocação" note="Varredura do limiar de confiança na cena de referência.">
          <Grafico
            deps={[d]}
            desenhar={(el) =>
              scatter(el, {
                points: pr.map((p) => ({ x: p.recall, y: p.precision, label: 'limiar ' + fmt(p.threshold, 2) + ' · n=' + p.n_pred })),
                xDomain: [0, 1.02],
                yDomain: [0, 1.02],
                height: 250,
                xLabel: 'revocação',
                yLabel: 'precisão',
                digits: 3,
                xDigits: 2,
                xAxisLabel: 'revocação →',
                color: 'teal',
                r: 5,
              })
            }
          />
        </OCard>
      </div>

      <OCard title="Desempenho por classe urbana e semente" note={d.synthetic_note || undefined}>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Classe urbana</th>
                <th className="num">semente</th>
                <th className="num">verdade</th>
                <th className="num">pred.</th>
                <th className="num">precisão</th>
                <th className="num">revocação</th>
                <th className="num">F1</th>
                <th className="num">IoU másc.</th>
                <th className="num">erro área</th>
                <th className="num">ladrilhos</th>
                <th className="num">dupl. rem.</th>
                <th className="num">kWp</th>
              </tr>
            </thead>
            <tbody>
              {(d.rows || []).map((r: Dado, i: number) => (
                <tr key={i}>
                  <td>{r.urban_class}</td>
                  <td className="num">{num(r.seed)}</td>
                  <td className="num">{num(r.truth)}</td>
                  <td className="num">{num(r.pred)}</td>
                  <td className="num">{pct(r.precision, 1)}</td>
                  <td className="num">{pct(r.recall, 1)}</td>
                  <td className="num">{num(r.f1, 3)}</td>
                  <td className="num">{num(r.mask_iou, 3)}</td>
                  <td className="num">{signed(r.area_rel_error, 3)}</td>
                  <td className="num">{num(r.tiles)}</td>
                  <td className="num">{num(r.duplicates_removed)}</td>
                  <td className="num">{num(r.total_kwp, 1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </OCard>

      <div className="grid g2" style={{ marginTop: 14 }}>
        <OCard
          title="Calibração de área"
          note={
            'Origem: ' +
            (cal.source ?? '') +
            '. A área propaga para o kWp e daí para o indicador de MMGD, então o viés precisa ser medido e corrigido, não ignorado.'
          }
        >
          <StatLines
            pares={[
              ['Fator aplicado', num(cal.factor, 3) + '×'],
              ['Watt por m² de módulo', num(cal.watt_per_m2) + ' W/m²'],
              ['Erro bruto médio', signed(ag.area_rel_error_raw, 4)],
              ['Erro calibrado médio', signed(ag.area_rel_error, 4)],
            ]}
          />
        </OCard>
        <OCard
          title="Parâmetros do YOLOv8-seg"
          note={yolo.available ? 'Runtime disponível: ' + (yolo.runtime ?? '') : 'Motivo da indisponibilidade: ' + (yolo.reason ?? '')}
        >
          <div className="table-wrap">
            <table>
              <tbody>
                {Object.keys(yolo.params || {}).length ? (
                  Object.entries(yolo.params || {}).map(([k, v]) => (
                    <tr key={k}>
                      <td className="mono small">{k}</td>
                      <td className="num">{String(v)}</td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td>—</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </OCard>
      </div>
      <Proveniencia body={body} />
    </>
  )
}
