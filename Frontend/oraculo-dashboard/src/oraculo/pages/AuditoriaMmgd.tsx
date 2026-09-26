/**
 * Auditoria da MMGD em 3 camadas: a solução de visão computacional do time
 * (Backend/pipeline/auditoria_camada1.py + auditoria_camadas_2_3.py, config/visao.yaml).
 *
 * Camada 1: painéis detectados em imagem de satélite (YOLOv8-seg) -> GeoJSON com área em m².
 * Camadas 2/3: desempate BDGD × cadastro ANEEL (Cadastrada / Lag de Sistema / Divergência
 * cadastral / Não homologada) e fator de correção por mancha de rede.
 * A rota /api/auditoria/mmgd só LÊ as saídas do pipeline; dado sintético vem com is_mock.
 * A outra solução (detector por subestação do protótipo) está em /visao.
 */
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ApiError } from '../api'
import { num, pct } from '../format'
import { Conteudo, Kpi, OCard, Pagina, StatLines, Vazio, useApi } from '../ui'

/* eslint-disable @typescript-eslint/no-explicit-any */
type Dado = any

const CLASSES = ['Cadastrada', 'Lag de Sistema', 'Divergência cadastral', 'Não homologada'] as const
const COR: Record<string, string> = {
  Cadastrada: 'var(--o-green)',
  'Lag de Sistema': 'var(--o-teal)',
  'Divergência cadastral': 'var(--o-amber)',
  'Não homologada': 'var(--o-crimson)',
}
const EXPLICA: Record<string, [string, string, string]> = {
  Cadastrada: ['ok', 'Na BDGD', 'Painel casou com unidade com GD na BDGD. Entra no fator.'],
  'Lag de Sistema': ['warn', 'Homologado depois da BDGD', 'Fora da BDGD, mas homologado na ANEEL depois da data de referência: o ciclo anual ainda não absorveu. Entra no fator.'],
  'Divergência cadastral': ['neutral', 'Homologado antes da BDGD', 'Homologado antes e mesmo assim fora da BDGD: divergência entre bases, vai para revisão. Entra no fator.'],
  'Não homologada': ['bad', 'Sem registro', 'Nem BDGD nem ANEEL: exceção escalada, NUNCA incorporada em silêncio à previsão.'],
}

async function carregar(): Promise<Dado> {
  let r: Response
  try {
    r = await fetch('/api/auditoria/mmgd', { headers: { Accept: 'application/json' } })
  } catch {
    throw new ApiError('NETWORK', 'Não foi possível falar com o serviço.', 'Suba o Backend: python main.py em Backend/.')
  }
  const corpo = await r.json().catch(() => ({}))
  if (!r.ok) throw new ApiError(String(r.status), corpo.detail || r.statusText, 'python -m pipeline.auditoria_camada1 --mock && python -m pipeline.auditoria_camadas_2_3 --mock')
  return corpo
}

export default function AuditoriaMmgd() {
  const estado = useApi(carregar, [])
  return (
    <Pagina>
      <Conteudo estado={estado} texto="Lendo as saídas da auditoria em 3 camadas…">
        {(d) => <Corpo d={d} />}
      </Conteudo>
    </Pagina>
  )
}

function Corpo({ d }: { d: Dado }) {
  const c1 = d.camada1
  const a = d.camadas23
  const [sel, setSel] = useState<string | null>(null)
  const porId: Record<string, Dado> = Object.fromEntries((a.deteccoes || []).map((x: Dado) => [x.id, x]))
  const total = (a.deteccoes || []).length
  const noFator = (a.deteccoes || []).filter((x: Dado) => x.entra_no_fator)
  const kwAud = noFator.reduce((s: number, x: Dado) => s + (x.capacidade_estimada_kw || 0), 0)
  const kwBdgd = (a.manchas || []).reduce((s: number, m: Dado) => s + (m.capacidade_cadastrada_bdgd_kw || 0), 0)
  const excecoes = (a.excecoes_nao_homologadas || []).length
  const s = sel ? porId[sel] : null

  return (
    <>
      <div className="note-strip">
        Solução de visão computacional do time: painéis em satélite (YOLOv8-seg) × BDGD × cadastro ANEEL. A outra solução, o detector por subestação
        do protótipo, está em <Link to="/visao">Visão computacional › Detector por subestação</Link>.
      </div>
      {d.is_mock && (
        <div className="note-strip warn">
          <strong>DADOS MOCK</strong> — sem imagem da área piloto nem pesos do modelo nesta máquina, a Camada 1 usa painéis sintéticos declarados à mão
          (pipeline/mock/), que passam pela mesma geometria do modo real. Nenhum número desta tela é medição.
        </div>
      )}

      <div className="grid g4" style={{ marginBottom: 14 }}>
        <Kpi label="Painéis detectados (Camada 1)" value={num(c1.properties?.n_paineis ?? total)} foot={'área total ' + num(c1.properties?.area_total_m2, 1) + ' m² · origem ' + (c1.properties?.origem || '—')} accent="teal" />
        <Kpi label="Capacidade auditada" value={num(kwAud, 1)} unit="kWp" foot={'área × ' + num(a.parametros?.kwp_por_m2, 2) + ' kWp/m² · sem as não homologadas'} accent="green" />
        <Kpi label="Capacidade na BDGD" value={num(kwBdgd, 1)} unit="kW" foot={'fator agregado ' + (kwBdgd > 0 ? num(kwAud / kwBdgd, 3) : '—')} accent="amber" />
        <Kpi label="Exceções não homologadas" value={num(excecoes)} foot={pct(total ? excecoes / total : null, 0) + ' das detecções · escaladas'} accent="crimson" />
      </div>

      <div className="grid g-2-1" style={{ marginBottom: 14 }}>
        <OCard
          title="Camada 1 · painéis detectados"
          hint={'EPSG:4326 · raio de casamento ' + num(a.parametros?.raio_casamento_m) + ' m'}
          note="Polígono do painel (máscara do YOLO-seg ou caixa; no mock, retângulo sintético) colorido pela classificação das camadas 2/3. Clique para ver o desempate."
        >
          <MapaPaineis features={c1.features || []} porId={porId} sel={sel} onSel={setSel} />
          <div className="legend">
            {CLASSES.map((k) => (
              <span className="legend-item" key={k}>
                <span className="legend-swatch" style={{ background: COR[k] }} />
                {k}
              </span>
            ))}
          </div>
        </OCard>
        <OCard title="Desempate BDGD × ANEEL (camadas 2 e 3)" hint={'BDGD de ' + (a.parametros?.data_referencia_bdgd || '—') + ' · ANEEL de ' + (a.parametros?.data_extracao_aneel || '—')}>
          <div className="matrix" style={{ gridTemplateColumns: '1fr' }}>
            {CLASSES.map((k) => {
              const [cls, titulo, texto] = EXPLICA[k]
              return (
                <div className={'mcell ' + cls} key={k}>
                  <h4>
                    {k} · <span className="n">{num(a.resumo?.[k] ?? 0)}</span>
                  </h4>
                  <p>
                    <strong>{titulo}.</strong> {texto}
                  </p>
                </div>
              )
            })}
          </div>
        </OCard>
      </div>

      {s && (
        <OCard title={'Detecção ' + sel} hint={s.classificacao}>
          <StatLines
            pares={[
              ['Mancha (' + (a.parametros?.nivel_mancha || 'mancha') + ')', s.mancha + ' · por ' + s.mancha_por],
              ['Área', num(s.area_m2, 1) + ' m²'],
              ['Capacidade estimada', num(s.capacidade_estimada_kw, 2) + ' kWp'],
              ['Unidade BDGD', s.bdgd_id ? s.bdgd_id + ' a ' + num(s.distancia_bdgd_m, 1) + ' m' : '—'],
              ['Registro ANEEL', s.aneel_codigo ? s.aneel_codigo + ' a ' + num(s.distancia_aneel_m, 1) + ' m' : '—'],
              ['Homologação', s.data_homologacao || '—'],
              ['Entra no fator', s.entra_no_fator ? 'sim' : 'não (exceção escalada)'],
            ]}
          />
        </OCard>
      )}

      <div style={{ marginTop: 14 }}>
        <OCard title="Fator de correção por mancha" hint="capacidade auditada ÷ capacidade cadastrada na BDGD" flush>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Mancha</th>
                  <th className="num">BDGD (kW)</th>
                  <th className="num">Auditada (kWp)</th>
                  <th className="num">Fator</th>
                  <th className="num">Não homol. (kWp)</th>
                  {CLASSES.map((k) => (
                    <th className="num" key={k}>
                      {k}
                    </th>
                  ))}
                  <th>BDGD sem detecção</th>
                </tr>
              </thead>
              <tbody>
                {(a.manchas || []).map((m: Dado) => (
                  <tr key={m.mancha}>
                    <td className="mono">{m.mancha}</td>
                    <td className="num">{num(m.capacidade_cadastrada_bdgd_kw, 2)}</td>
                    <td className="num">{num(m.capacidade_auditada_kw, 2)}</td>
                    <td className="num">
                      {m.fator_correcao === null ? <span className="muted">{m.motivo_sem_fator}</span> : <strong className={m.fator_correcao > 1 ? 'pos' : 'neg'}>{num(m.fator_correcao, 3)}</strong>}
                    </td>
                    <td className="num">{num(m.capacidade_nao_homologada_kw, 2)}</td>
                    {CLASSES.map((k) => (
                      <td className="num" key={k}>
                        {num(m['n_' + k] ?? 0)}
                      </td>
                    ))}
                    <td className="small muted">{(m.bdgd_sem_deteccao || []).join(', ') || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </OCard>
      </div>

      <div className="grid g2" style={{ marginTop: 14 }}>
        <OCard title="Detecções" flush>
          <div className="table-wrap scroll-y">
            <table>
              <thead>
                <tr>
                  <th>Id</th>
                  <th>Classificação</th>
                  <th>Mancha</th>
                  <th className="num">m²</th>
                  <th className="num">kWp</th>
                  <th className="num">Confiança</th>
                </tr>
              </thead>
              <tbody>
                {(c1.features || []).map((f: Dado) => {
                  const p = f.properties
                  const r = porId[p.id] || {}
                  return (
                    <tr key={p.id} className={sel === p.id ? 'sel' : ''} style={{ cursor: 'pointer' }} onClick={() => setSel(p.id)}>
                      <td className="mono">{p.id}</td>
                      <td>
                        <span className="chip" style={{ color: COR[r.classificacao], borderColor: COR[r.classificacao] }}>
                          {r.classificacao || '—'}
                        </span>
                      </td>
                      <td className="mono small">{r.mancha || '—'}</td>
                      <td className="num">{num(p.area_m2, 1)}</td>
                      <td className="num">{num(r.capacidade_estimada_kw, 2)}</td>
                      <td className="num">{pct(p.confianca, 0)}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </OCard>
        <OCard title="Modelo, imagem e reprodução" note="O serviço web só lê as saídas: rodar o modelo é trabalho do pipeline (extra [visao]: ultralytics + earthengine-api).">
          <StatLines
            pares={[
              ['Pesos do YOLO', d.modelo.caminho + (d.modelo.presente ? ' · presente' : ' · ausente nesta máquina')],
              ['Confiança mínima', num(d.modelo.confianca_minima, 2)],
              ['GSD máximo aceito', num(d.modelo.gsd_maximo_m, 2) + ' m/pixel'],
              ['Coleção de satélite', d.satelite.colecao + ' · ' + num(d.satelite.escala_m) + ' m'],
              ['Janela', (d.satelite.data_inicio || '—') + ' → ' + (d.satelite.data_fim || '—')],
              ['Área piloto (bbox)', d.satelite.bbox ? d.satelite.bbox.join(', ') : 'a definir (config/visao.yaml)'],
              ['Gerado em', a.gerado_em || '—'],
            ]}
          />
          <pre className="code-block" style={{ marginTop: 10 }}>
            {'cd Backend\n# sintético (sem imagem nem modelo)\npython -m pipeline.auditoria_camada1 --mock\npython -m pipeline.auditoria_camadas_2_3 --mock\n# real\npython -m pipeline.download_satelite --bbox LON_MIN LAT_MIN LON_MAX LAT_MAX\npython -m pipeline.auditoria_camada1 --imagens <pasta> --modelo <best.pt>\npython -m pipeline.auditoria_camadas_2_3 --bdgd <bdgd.json> --aneel <aneel.json>'}
          </pre>
        </OCard>
      </div>
    </>
  )
}

function MapaPaineis({ features, porId, sel, onSel }: { features: Dado[]; porId: Record<string, Dado>; sel: string | null; onSel: (id: string) => void }) {
  if (!features.length) return <Vazio>Nenhum painel detectado.</Vazio>
  const pts = features.flatMap((f) => f.geometry.coordinates[0] as [number, number][])
  const lons = pts.map((p) => p[0])
  const lats = pts.map((p) => p[1])
  const [x0, x1, y0, y1] = [Math.min(...lons), Math.max(...lons), Math.min(...lats), Math.max(...lats)]
  const W = 640
  const H = 300
  const pad = 24
  const escala = Math.min((W - 2 * pad) / Math.max(x1 - x0, 1e-9), (H - 2 * pad) / Math.max(y1 - y0, 1e-9))
  const sx = (lon: number) => pad + (lon - x0) * escala
  const sy = (lat: number) => H - pad - (lat - y0) * escala
  // painéis têm poucos metros: o círculo em volta garante alvo clicável em qualquer escala
  return (
    <svg className="chart" viewBox={`0 0 ${W} ${H}`} width="100%" height={H} role="img" aria-label="Painéis detectados">
      {features.map((f) => {
        const p = f.properties
        const r = porId[p.id] || {}
        const cor = COR[r.classificacao] || 'var(--o-muted)'
        const anel = f.geometry.coordinates[0] as [number, number][]
        return (
          <g key={p.id} style={{ cursor: 'pointer' }} onClick={() => onSel(p.id)}>
            <circle cx={sx(p.lon)} cy={sy(p.lat)} r={sel === p.id ? 10 : 7} fill={cor} opacity={0.25} stroke={sel === p.id ? 'var(--o-ink)' : 'none'} />
            <polygon points={anel.map(([lo, la]) => `${sx(lo)},${sy(la)}`).join(' ')} fill={cor} stroke={cor} strokeWidth={1.5} />
            <text className="tick" x={sx(p.lon) + 10} y={sy(p.lat) + 3}>
              {p.id}
            </text>
          </g>
        )
      })}
    </svg>
  )
}
