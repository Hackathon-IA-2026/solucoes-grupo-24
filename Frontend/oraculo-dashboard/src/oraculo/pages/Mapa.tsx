/**
 * Mapa Inteligente de perfis de carga e GD (protótipo, painel "mapa"). Porte de
 * 02-PROTOTIPO/web/js/views/mapa.js (V.mapa). Para cada subestação de fronteira: classe de
 * consumo predominante e nível de penetração de MMGD, com a amostra de ortoimagem e detecções.
 * Abre no mapa do Brasil; escolher a UF aproxima o mapa e carrega as subestações dela.
 */
import L from 'leaflet'
import { useMemo, useState } from 'react'
import { Circle, CircleMarker, GeoJSON, Pane, Polygon, Rectangle, Tooltip } from 'react-leaflet'
import ufsGeo from '../../data/geo/ufs.geo.json'
import { Api, type Envelope } from '../api'
import { color } from '../charts'
import { useOraculo, usePersistido } from '../estado'
import { ImagemGeo, MapaOsm, limitesDaCena, pixelParaLatLon, type Limites } from '../MapaOsm'
import { num, pct, signed } from '../format'
import { BarRow, Chip, Conteudo, Kpi, OCard, Pagina, Proveniencia, StatLines, Vazio, useApi } from '../ui'

/* eslint-disable @typescript-eslint/no-explicit-any */
type Dado = any

const CLASS_COLORS: Record<string, string> = { residencial: 'teal', comercial: 'navy', industrial: 'amber', rural: 'green' }
const LEVEL_COLORS: Record<string, string> = { baixa: 'green', média: 'amber', alta: 'crimson' }

function LevelChip({ lv }: { lv: string | null | undefined }) {
  const c = (lv && LEVEL_COLORS[lv]) || ''
  return <span className={'chip ' + c}>{lv || '—'}</span>
}

function WeightBars({ weights }: { weights: Dado }) {
  const w = weights || {}
  return (
    <>
      {['residencial', 'comercial', 'industrial', 'rural'].map((k) => (
        <BarRow key={k} label={k} frac={w[k] || 0} value={pct(w[k] || 0, 1)} color={CLASS_COLORS[k]} />
      ))}
    </>
  )
}

function topLabel(obj: Dado): string {
  const e = Object.entries(obj || {}) as [string, number][]
  if (!e.length) return '—'
  e.sort((a, b) => b[1] - a[1])
  return e[0][0]
}

function spread(obj: Dado): string {
  return (
    (Object.entries(obj || {}) as [string, number][]).map(([k, v]) => k + ' ' + num(v)).join(' · ') || '—'
  )
}

/** UFs com a análise por subestação liberada. As demais aparecem no mapa como "em breve". */
const UFS_ATIVAS = ['RJ']

const NOME_UF: Record<string, string> = {
  AC: 'Acre', AL: 'Alagoas', AM: 'Amazonas', AP: 'Amapá', BA: 'Bahia', CE: 'Ceará', DF: 'Distrito Federal',
  ES: 'Espírito Santo', GO: 'Goiás', MA: 'Maranhão', MG: 'Minas Gerais', MS: 'Mato Grosso do Sul', MT: 'Mato Grosso',
  PA: 'Pará', PB: 'Paraíba', PE: 'Pernambuco', PI: 'Piauí', PR: 'Paraná', RJ: 'Rio de Janeiro', RN: 'Rio Grande do Norte',
  RO: 'Rondônia', RR: 'Roraima', RS: 'Rio Grande do Sul', SC: 'Santa Catarina', SE: 'Sergipe', SP: 'São Paulo', TO: 'Tocantins',
}

const COLECAO_UFS = ufsGeo as GeoJSON.FeatureCollection
const BRASIL: Limites = [
  [-33.8, -74.0],
  [5.3, -34.8],
]

/** Enquadramento de uma UF a partir do contorno do IBGE. */
function limitesDaUf(uf: string): Limites | null {
  const f = COLECAO_UFS.features.find((x) => x.properties?.uf === uf)
  if (!f) return null
  const b = L.geoJSON(f).getBounds()
  return [
    [b.getSouth(), b.getWest()],
    [b.getNorth(), b.getEast()],
  ]
}

export default function Mapa() {
  // a tela sempre abre no Brasil; escolher a UF aproxima o mapa e abre os dados dela
  const [uf, setUf] = useState('')
  const [sel, setSel] = usePersistido<string | null>('oraculo.mapaSel', null)
  // a análise da UF leva alguns segundos: com uma UF só liberada, já pede os dados dela na
  // abertura, e o tempo em que a pessoa olha o mapa (e o voo) cobre parte da espera
  const ufDados = uf || UFS_ATIVAS[0]
  const estado = useApi(() => Api.get('mapa/substations', { uf: ufDados, limit: 50, frontier_only: 1 }), [ufDados])
  const rows: Dado[] = uf && estado.status === 'ok' ? ((estado.dado as Envelope).data as Dado).rows || [] : []
  const selId: string | null = sel && rows.some((r) => r.sub_id === sel) ? sel : (rows[0]?.sub_id ?? null)

  return (
    <Pagina>
      <div style={{ marginBottom: 14 }}>
        <MapaBrasil uf={uf} setUf={setUf} rows={rows} selId={selId} setSel={setSel} carregando={!!uf && estado.status === 'carregando'} />
      </div>
      {uf ? (
        <Conteudo estado={estado} texto={'Carregando subestações do ONS em ' + (NOME_UF[uf] || uf) + ' e analisando as amostras…'}>
          {(body) => <Corpo body={body} selId={selId} setSel={setSel} />}
        </Conteudo>
      ) : (
        <div className="note-strip">
          Selecione um estado no mapa para ver as subestações de fronteira com a distribuição: composição por classe de consumo e nível de penetração de MMGD.
          Nesta versão, só o <strong>Rio de Janeiro</strong> está disponível; os demais estados entram em seguida.
        </div>
      )}
    </Pagina>
  )
}

function Corpo({ body, selId, setSel }: { body: Envelope; selId: string | null; setSel: (s: string) => void }) {
  const d = body.data as Dado
  const rows: Dado[] = d.rows || []
  if (!rows.length || !selId) {
    return (
      <>
        <Vazio>Nenhuma subestação de fronteira neste estado.</Vazio>
        <Proveniencia body={body} />
      </>
    )
  }
  const sm = d.summary || {}
  const rr = d.registry_report || {}

  return (
    <>
      <div className="note-strip">
        Entrada: <strong>lista de subestações georreferenciadas</strong> do conjunto <span className="mono">subestacao</span> do ONS — {num(rr.unique_substations)} subestações,{' '}
        {num(rr.frontier_substations)} com transformação de fronteira com a distribuição. Saída, por subestação: composição por classe de consumo e nível de penetração de MMGD.
      </div>

      <div className="grid g4" style={{ marginBottom: 14 }}>
        <Kpi label="Subestações de fronteira" value={num(d.total)} foot={'no estado · ' + num(d.returned) + ' analisadas'} accent="teal" />
        <Kpi label="Classe dominante no estado" value={topLabel(sm.by_class)} foot={spread(sm.by_class)} accent="navy" />
        <Kpi label="Penetração de MMGD" value={topLabel(sm.by_mmgd_level)} foot={spread(sm.by_mmgd_level)} accent="amber" />
        <Kpi
          label="Qualidade da detecção"
          value={num(sm.detector_f1_mean, 3)}
          unit="F1"
          foot={'IoU de máscara ' + num(sm.detector_mask_iou_mean, 3) + ' · medido contra verdade fundamental'}
          accent="green"
        />
      </div>

      <div className="grid g-1-2" style={{ marginBottom: 14 }}>
        <OCard title="Subestações analisadas" hint="clique para abrir o detalhe">
          <div className="table-wrap scroll-y">
            <table>
              <thead>
                <tr>
                  <th>Subestação</th>
                  <th>Classe predominante</th>
                  <th>MMGD</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.sub_id} className={r.sub_id === selId ? 'sel' : ''} style={{ cursor: 'pointer' }} onClick={() => setSel(r.sub_id)}>
                    <td>
                      <strong>{r.name}</strong>
                      <br />
                      <span className="small faint">
                        {r.uf} · {r.sub_id} · {num(r.voltage_kv)}/{num(r.secondary_kv)} kV
                      </span>
                    </td>
                    <td className="small">
                      {r.class_label || '—'}
                      <br />
                      <span className="faint">conf. {pct(r.class_confidence, 0)}</span>
                    </td>
                    <td>
                      <LevelChip lv={r.mmgd_level} />
                      <br />
                      <span className="small faint mono">{num(r.mmgd_kwp_per_km2)} kWp/km²</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </OCard>
        <Detalhe key={selId} subId={selId} />
      </div>

      <div className="grid g2">
        <OCard
          title="Pipeline replicável"
          note={
            'A cada atualização das bases, o mesmo pipeline reproduz o mapa. Amostragem de ' +
            num(d.analysis_gsd_m, 2) +
            ' m/pixel, ' +
            num(d.samples_per_substation) +
            ' janelas por subestação.'
          }
        >
          <ol className="actions" style={{ paddingLeft: 20 }}>
            {(d.pipeline || []).map((s: string, i: number) => (
              <li key={i}>{s}</li>
            ))}
          </ol>
        </OCard>
        <OCard
          title="Faixas do indicador de MMGD"
          note="Ancoragem: unidade com MMGD tem tipicamente 5 kWp; densidade construída urbana de 800 a 2.000 telhados por km²; penetração média brasileira da ordem de 3% das unidades consumidoras."
        >
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Nível</th>
                  <th className="num">de (kWp/km²)</th>
                  <th className="num">até</th>
                </tr>
              </thead>
              <tbody>
                {(d.penetration_bins || []).map((b: Dado, i: number) => (
                  <tr key={i}>
                    <td>
                      <LevelChip lv={b.level} />
                    </td>
                    <td className="num">{num(b.from_kwp_km2)}</td>
                    <td className="num">{b.to_kwp_km2 === null ? '—' : num(b.to_kwp_km2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="card-note">
            Fração construída assumida na extrapolação:{' '}
            {(Object.entries(d.built_up_fraction || {}) as [string, number][]).map(([k, v]) => (
              <span key={k}>
                <span className="chip">
                  {k} {pct(v, 0)}
                </span>{' '}
              </span>
            ))}
          </div>
        </OCard>
      </div>
      <Proveniencia body={body} />
    </>
  )
}

/**
 * Mapa do Brasil com as UFs do IBGE. Abre no país inteiro; clicar numa UF liberada voa até ela e
 * passa a mostrar as subestações de fronteira (cor pelo nível de MMGD, círculo do raio de análise).
 */
function MapaBrasil({
  uf,
  setUf,
  rows,
  selId,
  setSel,
  carregando,
}: {
  uf: string
  setUf: (u: string) => void
  rows: Dado[]
  selId: string | null
  setSel: (s: string) => void
  carregando: boolean
}) {
  const [raios, setRaios] = usePersistido('oraculo.mapaOsmRaios', true)
  const limites = useMemo(() => (uf ? limitesDaUf(uf) : null) || BRASIL, [uf])
  const pts = rows.filter((r) => Number.isFinite(r.lat) && Number.isFinite(r.lon))
  // a selecionada por último, para ficar por cima das demais
  const ordem = [...pts].sort((a, b) => (a.sub_id === selId ? 1 : 0) - (b.sub_id === selId ? 1 : 0))
  const nome = NOME_UF[uf] || uf

  return (
    <OCard
      title={uf ? nome + ' · subestações de fronteira' : 'Brasil · selecione um estado'}
      hint={uf ? (carregando ? 'analisando as subestações…' : num(pts.length) + ' subestações · clique para abrir o detalhe') : 'estados em destaque já têm a análise'}
      note={
        uf
          ? 'Cor pelo nível de penetração de MMGD' + (raios ? '; círculo claro = raio de análise da subestação' : '') + '. Divisas: IBGE. © OpenStreetMap contributors.'
          : 'Divisas: IBGE. © OpenStreetMap contributors.'
      }
    >
      <MapaOsm limites={limites} altura={540} maxZoom={uf ? 9 : 5} zoomMin={3} animar>
        <Pane name="ufs" style={{ zIndex: 350 }}>
          <CamadaUfs uf={uf} onUf={setUf} />
        </Pane>
        {raios &&
          ordem.map((r) =>
            Number.isFinite(r.radius_km) && r.radius_km > 0 ? (
              <Circle
                key={'raio-' + r.sub_id}
                center={[r.lat, r.lon]}
                radius={r.radius_km * 1000}
                interactive={false}
                pathOptions={{ color: nivelCor(r.mmgd_level), weight: 1, opacity: 0.5, fillOpacity: r.sub_id === selId ? 0.14 : 0.06 }}
              />
            ) : null,
          )}
        {ordem.map((r) => {
          const cor = nivelCor(r.mmgd_level)
          const on = r.sub_id === selId
          return (
            <CircleMarker
              key={r.sub_id}
              center={[r.lat, r.lon]}
              radius={on ? 10 : 7}
              pathOptions={{ color: on ? color('ink') : cor, weight: on ? 3 : 1.5, fillColor: cor, fillOpacity: 0.85 }}
              eventHandlers={{ click: () => setSel(r.sub_id) }}
            >
              <Tooltip direction="top">
                <strong>{r.name}</strong> ({r.uf}) · {r.sub_id}
                <br />
                classe: {r.class_label || r.class_dominant || '—'}
                <br />
                MMGD: {r.mmgd_level || '—'} · {num(r.mmgd_kwp_per_km2)} kWp/km²
              </Tooltip>
            </CircleMarker>
          )
        })}
      </MapaOsm>
      <div className="chips" style={{ marginTop: 8 }}>
        {uf ? (
          <>
            <Chip onClick={() => setUf('')}>← voltar ao Brasil</Chip>
            {Object.keys(LEVEL_COLORS).map((lv) => (
              <LevelChip key={lv} lv={lv} />
            ))}
            <Chip on={raios} onClick={() => setRaios(!raios)}>
              raio de análise
            </Chip>
          </>
        ) : (
          UFS_ATIVAS.map((u) => (
            <Chip key={u} cor="teal" onClick={() => setUf(u)}>
              {NOME_UF[u] || u}
            </Chip>
          ))
        )}
      </div>
    </OCard>
  )
}

/** Divisas das UFs: as liberadas em destaque e clicáveis; as demais esmaecidas ("em breve"). */
function CamadaUfs({ uf, onUf }: { uf: string; onUf: (u: string) => void }) {
  const { tema } = useOraculo()
  const estilo = (u: string): L.PathOptions => {
    const teal = color('teal')
    if (u === uf) return { color: teal, weight: 2.5, fillColor: teal, fillOpacity: 0.05 }
    if (UFS_ATIVAS.includes(u)) return { color: teal, weight: 1.5, fillColor: teal, fillOpacity: uf ? 0.12 : 0.5 }
    return { color: color('line'), weight: 0.8, fillColor: color('muted'), fillOpacity: uf ? 0.05 : 0.18 }
  }
  return (
    <GeoJSON
      // remonta ao trocar UF ou tema: o GeoJSON do react-leaflet não reestiliza pelas props
      key={uf + '|' + tema}
      data={COLECAO_UFS}
      style={(f) => estilo(f?.properties?.uf)}
      onEachFeature={(f, layer) => {
        const u: string = f.properties?.uf
        const caminho = layer as L.Path
        const ativa = UFS_ATIVAS.includes(u)
        if (u === uf) return
        layer.bindTooltip('<strong>' + (NOME_UF[u] || u) + '</strong> · ' + (ativa ? 'clique para ver as subestações' : 'em breve'), {
          sticky: true,
          direction: 'top',
        })
        layer.on({
          mouseover: () => caminho.setStyle(ativa ? { weight: 2.5, fillOpacity: 0.7 } : { weight: 1.2, fillOpacity: uf ? 0.1 : 0.28 }),
          mouseout: () => caminho.setStyle(estilo(u)),
          click: () => ativa && onUf(u),
        })
      }}
    />
  )
}

function nivelCor(lv: string | null | undefined): string {
  return color((lv && LEVEL_COLORS[lv]) || 'muted')
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

/** Cena georreferenciada sobre o OSM: imagem com opacidade, contorno da cena e detecções. */
function CenaOsm({ url, geo, dets, opacidade }: { url: string; geo: Dado; dets: Dado[]; opacidade: number }) {
  const lim = limitesDaCena(geo)
  return (
    <MapaOsm limites={lim} altura={400} maxZoom={19}>
      <ImagemGeo key={url} url={url} limites={lim} opacidade={opacidade} />
      <Rectangle bounds={lim} interactive={false} pathOptions={{ color: color('amber'), weight: 1.5, dashArray: '5 4', fill: false }} />
      <DeteccoesGeo geo={geo} dets={dets} />
    </MapaOsm>
  )
}

/** Chip com o controle deslizante da opacidade da imagem sobre o OSM. */
function ChipOpacidade({ v, setV }: { v: number; setV: (v: number) => void }) {
  return (
    <label className="chip" style={{ gap: 6 }}>
      opacidade
      <input type="range" min={0} max={1} step={0.05} value={v} style={{ width: 90 }} onChange={(e) => setV(parseFloat(e.target.value))} />
      <span>{pct(v, 0)}</span>
    </label>
  )
}

const IMG_MODOS: [string, string][] = [
  ['', 'detecções'],
  ['?truth=1&tiles=1', 'verdade + ladrilhos'],
  ['?channel=azul', 'índice de azul'],
  ['?channel=borda', 'densidade de borda'],
]

function Detalhe({ subId }: { subId: string }) {
  const estado = useApi(() => Api.get('mapa/substations/' + encodeURIComponent(subId)), [subId])
  return (
    <div>
      <Conteudo estado={estado} texto="Analisando a amostra…">
        {(body) => <DetalheCorpo d={body.data as Dado} />}
      </Conteudo>
    </div>
  )
}

function DetalheCorpo({ d }: { d: Dado }) {
  const [img, setImg] = useState('')
  const s = d.substation || {}
  const lc = d.load_class || {}
  const m = d.mmgd || {}
  const an = d.clm || {}
  const ev = d.evaluation || {}
  const mt = ev.match || {}
  const vis = d.vision || {}
  const dets: Dado[] = (vis.detections || []).slice(0, 24)
  const [osm, setOsm] = usePersistido('oraculo.mapaOsm', true)
  const [opac, setOpac] = usePersistido('oraculo.mapaOsmOpacidade', 0.85)
  const geo = geoValida(vis.geo) ? vis.geo : null
  const verOsm = osm && !!geo
  const nota = [
    (d.notes || []).join(' '),
    verOsm ? 'Cena sintética georreferenciada (GSD ' + num(geo.gsd_m, 2) + ' m) sobre o OpenStreetMap; © OpenStreetMap contributors.' : '',
  ]
    .filter(Boolean)
    .join(' ')

  return (
    <>
      <OCard
        title={'Detalhe · ' + (s.name || '') + ' (' + (s.uf || '') + ')'}
        hint={num(s.frontier_mva) + ' MVA de fronteira · raio ' + num(s.radius_km, 2) + ' km · morfologia ' + (d.urban_hint ?? '')}
        note={nota || undefined}
      >
        <div className="grid g2" style={{ gap: 12 }}>
          <div>
            <div className="okpi-label" style={{ marginBottom: 6 }}>
              Amostra de ortoimagem com as detecções
            </div>
            {verOsm ? (
              <CenaOsm url={d.image_url + img} geo={geo} dets={vis.detections || []} opacidade={opac} />
            ) : (
              <img
                src={d.image_url + img}
                style={{ width: '100%', borderRadius: 6, border: '1px solid var(--o-line)' }}
                alt="amostra de ortoimagem com painéis detectados"
              />
            )}
            <div className="chips" style={{ marginTop: 8 }}>
              {IMG_MODOS.map(([q, rot]) => (
                <Chip key={q} on={img === q} onClick={() => setImg(q)}>
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
              {verOsm && <ChipOpacidade v={opac} setV={setOpac} />}
            </div>
            {osm && !geo && <div className="small faint">Esta cena não traz georreferência (vision.geo): exibindo só a imagem.</div>}
          </div>
          <div>
            <div className="okpi-label">1 · Perfil predominante de consumo</div>
            <div style={{ fontSize: 17, fontWeight: 650, margin: '4px 0 8px' }}>
              {lc.label} <span className="small muted">confiança {pct(lc.confidence, 0)}</span>
            </div>
            <WeightBars weights={lc.weights} />
            <div className="okpi-label" style={{ marginTop: 14 }}>
              2 · Presença de geração distribuída
            </div>
            <div style={{ fontSize: 17, fontWeight: 650, margin: '4px 0 8px' }}>
              <LevelChip lv={m.level} /> {num(m.kwp_per_km2)} <span className="small muted">kWp/km² · confiança {pct(m.confidence, 0)}</span>
            </div>
            <StatLines
              pares={[
                ['Painéis detectados na amostra', num(m.panels)],
                ['Área de painel', num(m.panel_area_m2, 1) + ' m²'],
                ['Telhados na amostra', num(m.roofs_detected)],
                ['Penetração em telhados', pct(m.roof_penetration, 1)],
                ['Amostra', num(m.sample_km2, 3) + ' km² de ' + num(m.area_km2, 1) + ' km²'],
                ['Total extrapolado', num(m.kwp_total, 0) + ' kWp'],
                ['Adequação da amostra', m.sample_adequacy || '—'],
                ['Tipo III na UF', num(m.tipo3_mw_uf, 1) + ' MW (' + num(m.tipo3_count_uf) + ' usinas)'],
              ]}
            />
          </div>
        </div>
      </OCard>

      <div className="grid g3" style={{ marginTop: 14 }}>
        <OCard title="Desempenho do detector nesta amostra" note="Verdade fundamental da ortoimagem sintética: estas são medições reais do detector.">
          <StatLines
            pares={[
              ['Precisão', pct(mt.precision, 1)],
              ['Revocação', pct(mt.recall, 1)],
              ['F1', num(mt.f1, 3)],
              ['IoU médio das caixas', num(mt.iou_mean, 3)],
              ['IoU de máscara', num(ev.mask_iou, 3)],
              ['Verdadeiros / falsos+ / falsos−', num(mt.tp) + ' / ' + num(mt.fp) + ' / ' + num(mt.fn)],
              ['Erro de área (calibrado)', signed((ev.area || {}).rel_error, 3)],
              ['Erro de área (bruto)', signed((ev.area_raw || {}).rel_error, 3)],
            ]}
          />
        </OCard>
        <OCard title="Desvio em relação ao subsistema" note={lc.prior_role || undefined}>
          <StatLines
            pares={[
              ['Desvio da média regional', num(lc.deviation_from_regional, 3)],
              ['Peso do prior regional', pct(lc.weight_load, 0)],
              ['Peso da evidência local', pct(lc.weight_morphology, 0)],
              ['Classe pelo prior', (lc.regional_prior || {}).label || '—'],
              ['R² do ajuste do prior', num((lc.regional_prior || {}).r2, 3)],
              ['Classe pela morfologia', (lc.local_evidence || {}).label || '—'],
              ['Área média de telhado', num((lc.local_evidence || {}).mean_footprint_m2, 1) + ' m²'],
              ['Telhados por km²', num((lc.local_evidence || {}).density_per_km2, 0)],
            ]}
          />
        </OCard>
        <OCard title="Insumo proposto ao Modelo de Carga Composta" note={an.aviso || undefined}>
          <StatLines
            pares={[
              ['Fração de motor estimada', num(an.fracao_motor_estimada, 3)],
              ['MMGD na área', num(an.mmgd_kwp_na_area, 0) + ' kWp'],
              ['Penetração', an.mmgd_penetracao ?? ''],
              ['Sinalizar GD no modelo', an.distributed_generation_flag ? <span key="s" className="pos">sim</span> : <span key="n" className="faint">não</span>],
              ['Confiança', pct(an.confianca, 0)],
            ]}
          />
        </OCard>
      </div>

      <OCard
        title="Detecções georreferenciadas"
        hint={
          num(vis.kept_count) +
          ' mantidas de ' +
          num(vis.raw_count) +
          ' brutas · ' +
          num(vis.duplicates_removed) +
          ' duplicatas removidas na costura entre ' +
          num(vis.tiles) +
          ' ladrilhos'
        }
      >
        <div className="table-wrap scroll-y">
          <table>
            <thead>
              <tr>
                <th className="num">#</th>
                <th className="num">conf.</th>
                <th>lat, lon</th>
                <th className="num">área m²</th>
                <th className="num">kWp</th>
                <th className="num">retang.</th>
                <th className="num">azul</th>
                <th className="num">borda</th>
              </tr>
            </thead>
            <tbody>
              {dets.length ? (
                dets.map((x, i) => (
                  <tr key={i}>
                    <td className="num">{i + 1}</td>
                    <td className="num">{num(x.score, 3)}</td>
                    <td className="mono small">
                      {num(x.lat, 5)}, {num(x.lon, 5)}
                    </td>
                    <td className="num">{num(x.area_m2, 1)}</td>
                    <td className="num">{num(x.kwp, 2)}</td>
                    <td className="num">{num(x.rectangularity, 3)}</td>
                    <td className="num">{num(x.blue_index, 3)}</td>
                    <td className="num">{num(x.edge_density, 3)}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={8}>nenhuma detecção nesta amostra</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </OCard>
    </>
  )
}
