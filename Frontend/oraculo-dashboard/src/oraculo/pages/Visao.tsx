/**
 * Visão computacional sobre imagem de satélite (protótipo, painel "visao"). Porte de
 * 02-PROTOTIPO/web/js/views/mapa.js (V.visao): detector clássico + adaptador YOLOv8-seg,
 * banco de ensaio contra verdade fundamental, cena de referência e curva precisão × revocação.
 */
import { useEffect, useState } from 'react'
import { Polygon, Rectangle, Tooltip } from 'react-leaflet'
import { Link } from 'react-router-dom'
import { Api, type Envelope } from '../api'
import { color, fmt, scatter } from '../charts'
import { usePersistido } from '../estado'
import { num, pct, signed } from '../format'
import { ImagemGeo, MapaOsm, limitesDaCena, pixelParaLatLon } from '../MapaOsm'
import { Chip, Conteudo, Grafico, Kpi, OCard, Pagina, Proveniencia, StatLines, useApi } from '../ui'

/* eslint-disable @typescript-eslint/no-explicit-any */
type Dado = any

/** Metros por grau de latitude, o mesmo de MapaOsm.limitesDaCena (para a geo estimada fechar). */
const M_POR_GRAU = 111_320

function geoValida(g: Dado): boolean {
  return (
    !!g &&
    Number.isFinite(g.center_lat) &&
    Number.isFinite(g.center_lon) &&
    Array.isArray(g.extent_m) &&
    g.extent_m.length === 2 &&
    g.width_px > 0 &&
    g.height_px > 0
  )
}

/**
 * Georreferência da cena a partir das próprias detecções: cada uma traz a caixa em pixels e o
 * lat/lon do centro, calculados pelo backend com a transformação da cena. Ajuste linear por
 * mínimos quadrados (lat × y, lon × x) + tamanho da imagem => centro, extensão e GSD.
 */
function geoPorDeteccoes(dets: Dado[], w: number, h: number): Dado | null {
  const p = dets
    .filter((x) => Array.isArray(x.box) && x.box.length >= 4 && Number.isFinite(x.lat) && Number.isFinite(x.lon))
    .map((x) => ({ cx: (x.box[0] + x.box[2]) / 2, cy: (x.box[1] + x.box[3]) / 2, lat: x.lat as number, lon: x.lon as number }))
  if (p.length < 2 || !(w > 0) || !(h > 0)) return null
  const ajuste = (xs: number[], ys: number[]): [number, number] | null => {
    const mx = xs.reduce((a, b) => a + b, 0) / xs.length
    const my = ys.reduce((a, b) => a + b, 0) / ys.length
    let sxx = 0
    let sxy = 0
    xs.forEach((x, i) => {
      sxx += (x - mx) ** 2
      sxy += (x - mx) * (ys[i] - my)
    })
    if (sxx < 1) return null
    const b = sxy / sxx
    return [my - b * mx, b]
  }
  const la = ajuste(
    p.map((q) => q.cy),
    p.map((q) => q.lat),
  )
  const lo = ajuste(
    p.map((q) => q.cx),
    p.map((q) => q.lon),
  )
  if (!la || !lo || !(la[1] < 0) || !(lo[1] > 0)) return null
  const centerLat = la[0] + (la[1] * h) / 2
  const centerLon = lo[0] + (lo[1] * w) / 2
  const hM = -la[1] * h * M_POR_GRAU
  const wM = lo[1] * w * M_POR_GRAU * Math.cos((centerLat * Math.PI) / 180)
  return { center_lat: centerLat, center_lon: centerLon, gsd_m: hM / h, width_px: w, height_px: h, extent_m: [wM, hM] as [number, number] }
}

/** Tamanho natural da imagem (para a geo estimada). */
function useTamanhoImagem(url: string | undefined): [number, number] | null {
  const [tam, setTam] = useState<{ url: string; wh: [number, number] } | null>(null)
  useEffect(() => {
    if (!url) return
    let vivo = true
    const im = new Image()
    im.onload = () => vivo && setTam({ url, wh: [im.naturalWidth, im.naturalHeight] })
    im.src = url
    return () => {
      vivo = false
    }
  }, [url])
  return tam && tam.url === url ? tam.wh : null
}

/** Detecções como polígonos georreferenciados (cantos da caixa, em pixels da cena). */
function DeteccoesGeo({ geo, dets }: { geo: Dado; dets: Dado[] }) {
  const cor = color('teal')
  return (
    <>
      {dets.map((x, i) => {
        const b = x.box
        if (!Array.isArray(b) || b.length < 4) return null
        const [x0, y0, x1, y1] = b as number[]
        const anel = [pixelParaLatLon(geo, x0, y0), pixelParaLatLon(geo, x1, y0), pixelParaLatLon(geo, x1, y1), pixelParaLatLon(geo, x0, y1)]
        const sc = Math.max(0, Math.min(1, Number(x.score) || 0))
        return (
          <Polygon key={i} positions={anel} pathOptions={{ color: cor, weight: 2, opacity: 0.6 + 0.4 * sc, fillColor: cor, fillOpacity: 0.1 + 0.45 * sc }}>
            <Tooltip direction="top">
              #{i + 1} · {num(x.area_m2, 1)} m² · {num(x.kwp, 2)} kWp · score {num(x.score, 3)}
            </Tooltip>
          </Polygon>
        )
      })}
    </>
  )
}

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
        <CenaReferencia refe={ref} />
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

/** Cena de referência do banco de ensaio: imagem (5 vistas) ou sobre o OpenStreetMap. */
function CenaReferencia({ refe }: { refe: Dado }) {
  const [bench, setBench] = useState('')
  const [osm, setOsm] = usePersistido('oraculo.visaoOsm', true)
  const [opac, setOpac] = usePersistido('oraculo.visaoOsmOpacidade', 0.85)
  const url: string = bench ? '/api/mapa/bench.png' + bench : refe.image_url

  // 1) geo na própria referência; 2) detalhe da subestação de referência; 3) estimada das detecções
  const geoApi = [refe.geo, refe.vision?.geo].find(geoValida) || null
  const subId: string | null = geoApi ? null : refe.sub_id || refe.substation_id || null
  const detalhe = useApi(() => (subId ? Api.get('mapa/substations/' + encodeURIComponent(subId)) : Promise.resolve(null)), [subId])
  const visSub: Dado = detalhe.status === 'ok' && detalhe.dado ? (detalhe.dado.data as Dado)?.vision || {} : {}
  const geoSub = geoValida(visSub.geo) ? visSub.geo : null
  const tam = useTamanhoImagem(geoApi || geoSub ? undefined : refe.image_url)
  const detsRef: Dado[] = refe.detections || []
  const geoEst = geoApi || geoSub || !tam ? null : geoPorDeteccoes(detsRef, tam[0], tam[1])
  const geo: Dado = geoApi || geoSub || geoEst
  const dets: Dado[] = detsRef.length ? detsRef : visSub.detections || []
  const verOsm = osm && !!geo
  const lim = geo ? limitesDaCena(geo) : null

  return (
    <OCard
      title="Cena de referência"
      hint={num(refe.truth) + ' painéis reais · ' + num(refe.pred) + ' detectados'}
      note={
        <>
          Teal: detecção. Âmbar: verdade fundamental. Carmim: painel real não detectado. Os canais de característica mostram <em>por que</em> o detector marcou o que marcou.
          {verOsm && (
            <>
              {' '}
              Cena sintética georreferenciada (GSD {num(geo.gsd_m, 2)} m) sobre o OpenStreetMap
              {geoEst ? ', georreferência reconstruída a partir do lat/lon das detecções' : ''}; tracejado âmbar = extensão da cena; © OpenStreetMap contributors.
            </>
          )}
        </>
      }
    >
      {verOsm && lim ? (
        <MapaOsm limites={lim} altura={420} maxZoom={19}>
          <ImagemGeo key={url} url={url} limites={lim} opacidade={opac} />
          <Rectangle bounds={lim} interactive={false} pathOptions={{ color: color('amber'), weight: 1.5, dashArray: '5 4', fill: false }} />
          <DeteccoesGeo geo={geo} dets={dets} />
        </MapaOsm>
      ) : (
        <img src={url} style={{ width: '100%', borderRadius: 6, border: '1px solid var(--o-line)' }} alt="cena de referência com detecções" />
      )}
      <div className="chips" style={{ marginTop: 8 }}>
        {BENCH_MODOS.map(([q, rot]) => (
          <Chip key={q} on={bench === q} onClick={() => setBench(q)}>
            {rot}
          </Chip>
        ))}
      </div>
      <div className="chips" style={{ marginTop: 6 }}>
        <Chip on={osm} onClick={() => setOsm(true)}>
          Sobre o OpenStreetMap
        </Chip>
        <Chip on={!osm} onClick={() => setOsm(false)}>
          Imagem
        </Chip>
        {verOsm && (
          <label className="chip" style={{ gap: 6 }}>
            opacidade
            <input type="range" min={0} max={1} step={0.05} value={opac} style={{ width: 90 }} onChange={(e) => setOpac(parseFloat(e.target.value))} />
            <span>{pct(opac, 0)}</span>
          </label>
        )}
      </div>
      {osm && !geo && (
        <div className="small faint">
          {(subId && detalhe.status === 'carregando') || (!geoApi && !subId && !tam && refe.image_url)
            ? 'Obtendo a georreferência da cena…'
            : 'A cena de referência não traz georreferência na API: exibindo só a imagem.'}
        </div>
      )}
    </OCard>
  )
}
