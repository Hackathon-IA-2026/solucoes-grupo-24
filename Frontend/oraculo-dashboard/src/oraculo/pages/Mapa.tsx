/**
 * Mapa Inteligente de perfis de carga e GD (protótipo, painel "mapa"). Porte de
 * 02-PROTOTIPO/web/js/views/mapa.js (V.mapa). Para cada subestação de fronteira: classe de
 * consumo predominante e nível de penetração de MMGD, com a amostra de ortoimagem e detecções.
 * Abre no mapa do Brasil; escolher a UF aproxima o mapa e carrega as subestações dela; a
 * subestação abre, no mesmo mapa, a amostra de satélite com os painéis detectados (visão
 * computacional), e o banco de ensaio do detector fecha a tela.
 */
import L from 'leaflet'
import { useMemo, useState, type ReactNode } from 'react'
import { Circle, CircleMarker, GeoJSON, Pane, Tooltip } from 'react-leaflet'
import { Link } from 'react-router-dom'
import ufsGeo from '../../data/geo/ufs.geo.json'
import { Api, type Envelope } from '../api'
import { color } from '../charts'
import { useOraculo, usePersistido } from '../estado'
import { CamadaCena, ControlesCena, DetalheDeteccao, LegendaCena, TabelaDeteccoes, geoValida, limitesDoEntorno } from '../CenaSatelite'
import { MapaOsm, limitesDaCena, type Limites } from '../MapaOsm'
import { num, pct, signed } from '../format'
import { BarRow, Chip, Conteudo, Kpi, OCard, Pagina, Proveniencia, StatLines, Vazio, useApi } from '../ui'
import { PainelVisao } from './Visao'

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
  const [uf, setUfBruto] = useState('')
  const [sel, setSel] = usePersistido<string | null>('oraculo.mapaSel', null)
  // a análise da UF leva alguns segundos: com uma UF só liberada, já pede os dados dela na
  // abertura, e o tempo em que a pessoa olha o mapa (e o voo) cobre parte da espera
  const ufDados = uf || UFS_ATIVAS[0]
  const estado = useApi(() => Api.get('mapa/substations', { uf: ufDados, limit: 50, frontier_only: 1 }), [ufDados])
  const rows: Dado[] = uf && estado.status === 'ok' ? ((estado.dado as Envelope).data as Dado).rows || [] : []
  const selId: string | null = sel && rows.some((r) => r.sub_id === sel) ? sel : (rows[0]?.sub_id ?? null)

  // Detalhe da subestação selecionada: buscado aqui (e não no painel) porque o mapa usa a
  // mesma resposta para desenhar a cena de satélite e as detecções no terceiro nível de zoom.
  const detalhe = useApi(() => (selId ? Api.get('mapa/substations/' + encodeURIComponent(selId)) : Promise.resolve(null)), [selId])
  const dSub: Dado | null = detalhe.status === 'ok' && detalhe.dado ? (detalhe.dado as Envelope).data : null
  const vis: Dado = dSub?.vision || {}
  const geo = geoValida(vis.geo) ? vis.geo : null
  const dets: Dado[] = vis.detections || []

  // Estado da cena (Brasil → UF → subestação): ligada, vista da imagem, opacidade, detecção escolhida
  const [verCena, setVerCena] = useState(false)
  const [entorno, setEntorno] = useState(false)
  const [modoImg, setModoImg] = useState('')
  const [opac, setOpac] = usePersistido('oraculo.mapaOsmOpacidade', 0.85)
  const [mostrarDets, setMostrarDets] = usePersistido('oraculo.mapaDets', true)
  const [selDet, setSelDet] = useState<{ sub: string; i: number } | null>(null)
  const iDet = selDet && selDet.sub === selId ? selDet.i : null
  const cenaAtiva = !!uf && verCena && !!geo && !!dSub

  const setUf = (u: string) => {
    setUfBruto(u)
    setVerCena(false)
  }
  const abrirCena = () => {
    setEntorno(false)
    setVerCena(true)
    document.getElementById('mapa-perfis')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
  // escolher uma detecção (no mapa ou na tabela) também leva o mapa para a cena
  const escolherDet = (i: number) => {
    if (!selId) return
    setSelDet({ sub: selId, i })
    setVerCena(true)
  }

  const cena: CenaNoMapa | null =
    cenaAtiva && geo
      ? {
          nome: dSub.substation?.name || selId || '',
          limites: entorno ? limitesDoEntorno(geo) : limitesDaCena(geo),
          hint: num(vis.kept_count) + ' painéis detectados · ' + num(vis.total_kwp, 1) + ' kWp na amostra',
          camada: (
            <CamadaCena url={dSub.image_url + modoImg} geo={geo} dets={dets} opacidade={opac} sel={iDet} onSel={escolherDet} mostrarDets={mostrarDets} />
          ),
          rodape: (
            <>
              {iDet !== null && dets[iDet] && <DetalheDeteccao det={dets[iDet]} i={iDet} />}
              <ControlesCena
                modo={modoImg}
                setModo={setModoImg}
                opacidade={opac}
                setOpacidade={setOpac}
                mostrarDets={mostrarDets}
                setMostrarDets={setMostrarDets}
                entorno={entorno}
                setEntorno={setEntorno}
                extra={<Chip onClick={() => setVerCena(false)}>← voltar a {NOME_UF[uf] || uf}</Chip>}
              />
            </>
          ),
        }
      : null

  return (
    <Pagina>
      <div id="mapa-perfis" style={{ marginBottom: 14, scrollMarginTop: 130 }}>
        <MapaBrasil
          uf={uf}
          setUf={setUf}
          rows={rows}
          selId={selId}
          setSel={setSel}
          carregando={!!uf && estado.status === 'carregando'}
          cena={cena}
          podeAbrirCena={!!geo && !!dSub}
          abrirCena={abrirCena}
        />
      </div>
      {uf ? (
        <Conteudo estado={estado} texto={'Carregando subestações do ONS em ' + (NOME_UF[uf] || uf) + ' e analisando as amostras…'}>
          {(body) => (
            <Corpo
              body={body}
              selId={selId}
              setSel={setSel}
              detalhe={
                <Conteudo estado={detalhe} texto="Analisando a amostra…">
                  {() => (dSub ? <DetalheCorpo d={dSub} iDet={iDet} onDet={escolherDet} verCena={cenaAtiva} abrirCena={abrirCena} /> : null)}
                </Conteudo>
              }
            />
          )}
        </Conteudo>
      ) : (
        <div className="note-strip">
          Selecione um estado no mapa para ver as subestações de fronteira com a distribuição: composição por classe de consumo, nível de penetração de MMGD e a
          amostra de satélite com os painéis detectados. Nesta versão, só o <strong>Rio de Janeiro</strong> está disponível; os demais estados entram em seguida.
        </div>
      )}
    </Pagina>
  )
}

/** Terceiro nível do mapa: a cena de satélite da subestação selecionada, com as detecções. */
interface CenaNoMapa {
  nome: string
  limites: Limites
  hint: string
  camada: ReactNode
  rodape: ReactNode
}

function Corpo({ body, selId, setSel, detalhe }: { body: Envelope; selId: string | null; setSel: (s: string) => void; detalhe: ReactNode }) {
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
        <div>{detalhe}</div>
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
      <SecaoVisao />
      <Proveniencia body={body} />
    </>
  )
}

/**
 * Mapa com três níveis de zoom, sempre o mesmo Leaflet (a transição é um voo, não uma troca de tela):
 * 1. Brasil, com as UFs do IBGE: clicar numa UF liberada voa até ela;
 * 2. UF: subestações de fronteira (cor pelo nível de MMGD, círculo do raio de análise);
 *    clicar numa subestação seleciona; clicar de novo na selecionada abre a cena;
 * 3. Cena da subestação: amostra de satélite com os painéis detectados (visão computacional).
 */
function MapaBrasil({
  uf,
  setUf,
  rows,
  selId,
  setSel,
  carregando,
  cena,
  podeAbrirCena,
  abrirCena,
}: {
  uf: string
  setUf: (u: string) => void
  rows: Dado[]
  selId: string | null
  setSel: (s: string) => void
  carregando: boolean
  cena: CenaNoMapa | null
  podeAbrirCena: boolean
  abrirCena: () => void
}) {
  const [raios, setRaios] = usePersistido('oraculo.mapaOsmRaios', true)
  const limUf = useMemo(() => (uf ? limitesDaUf(uf) : null) || BRASIL, [uf])
  const limites = cena ? cena.limites : limUf
  // na cena os marcadores somem: o da selecionada ficaria em cima dos painéis detectados
  const pts = cena ? [] : rows.filter((r) => Number.isFinite(r.lat) && Number.isFinite(r.lon))
  // a selecionada por último, para ficar por cima das demais
  const ordem = [...pts].sort((a, b) => (a.sub_id === selId ? 1 : 0) - (b.sub_id === selId ? 1 : 0))
  const nome = NOME_UF[uf] || uf
  const selNome = rows.find((r) => r.sub_id === selId)?.name

  const titulo = cena ? cena.nome + ' · amostra de satélite' : uf ? nome + ' · subestações de fronteira' : 'Brasil · selecione um estado'
  const hint = cena
    ? cena.hint
    : uf
      ? carregando
        ? 'analisando as subestações…'
        : num(pts.length) + ' subestações · clique para selecionar, de novo para ver a amostra de satélite'
      : 'estados em destaque já têm a análise'
  const nota = cena
    ? 'Visão computacional: cena sintética georreferenciada sobre o OpenStreetMap, com os painéis que o detector encontrou. Roda do mouse dá zoom. © OpenStreetMap contributors.'
    : uf
      ? 'Cor pelo nível de penetração de MMGD' + (raios ? '; círculo claro = raio de análise da subestação' : '') + '. Divisas: IBGE. © OpenStreetMap contributors.'
      : 'Divisas: IBGE. © OpenStreetMap contributors.'

  return (
    <OCard title={titulo} hint={hint} note={nota}>
      <MapaOsm limites={limites} altura={540} maxZoom={cena ? 19 : uf ? 9 : 5} zoomMin={3} animar rolagem={!!cena} sobreposicao={cena ? <LegendaCena /> : undefined}>
        <Pane name="ufs" style={{ zIndex: 350 }}>
          <CamadaUfs uf={uf} onUf={setUf} />
        </Pane>
        {cena?.camada}
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
              eventHandlers={{ click: () => (on && podeAbrirCena ? abrirCena() : setSel(r.sub_id)) }}
            >
              <Tooltip direction="top">
                <strong>{r.name}</strong> ({r.uf}) · {r.sub_id}
                <br />
                classe: {r.class_label || r.class_dominant || '—'}
                <br />
                MMGD: {r.mmgd_level || '—'} · {num(r.mmgd_kwp_per_km2)} kWp/km²
                <br />
                <span className="faint">{on ? 'clique para ver a amostra de satélite' : 'clique para selecionar'}</span>
              </Tooltip>
            </CircleMarker>
          )
        })}
      </MapaOsm>
      {cena ? (
        cena.rodape
      ) : (
        <div className="chips" style={{ marginTop: 8 }}>
          {uf ? (
            <>
              <Chip onClick={() => setUf('')}>← voltar ao Brasil</Chip>
              {selNome && podeAbrirCena && (
                <Chip cor="teal" onClick={abrirCena}>
                  ver amostra de satélite · {selNome}
                </Chip>
              )}
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
      )}
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

function DetalheCorpo({ d, iDet, onDet, verCena, abrirCena }: { d: Dado; iDet: number | null; onDet: (i: number) => void; verCena: boolean; abrirCena: () => void }) {
  const s = d.substation || {}
  const lc = d.load_class || {}
  const m = d.mmgd || {}
  const an = d.clm || {}
  const ev = d.evaluation || {}
  const mt = ev.match || {}
  const vis = d.vision || {}
  const temGeo = geoValida(vis.geo)

  return (
    <>
      <OCard
        title={'Detalhe · ' + (s.name || '') + ' (' + (s.uf || '') + ')'}
        hint={num(s.frontier_mva) + ' MVA de fronteira · raio ' + num(s.radius_km, 2) + ' km · morfologia ' + (d.urban_hint ?? '')}
        note={(d.notes || []).join(' ') || undefined}
      >
        <div className="grid g2" style={{ gap: 12 }}>
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
          <div>
            <div className="okpi-label">3 · Visão computacional na amostra de satélite</div>
            <div style={{ fontSize: 17, fontWeight: 650, margin: '4px 0 8px' }}>
              {num(vis.kept_count)} painéis <span className="small muted">· {num(vis.total_kwp, 1)} kWp</span>
            </div>
            <StatLines
              pares={[
                // vision.detector é o descritor do backend ({name, kind, runtime, …}), não um texto
                ['Detector', (vis.detector && (vis.detector.name || vis.detector.kind)) || '—'],
                ['Ladrilhos analisados', num(vis.tiles) + (Array.isArray(vis.tile_grid) ? ' (' + vis.tile_grid.join(' × ') + ')' : '')],
                ['Detecções brutas → mantidas', num(vis.raw_count) + ' → ' + num(vis.kept_count)],
                ['Duplicatas removidas na costura', num(vis.duplicates_removed)],
                ['Área de painel (calibrada)', num(vis.total_area_m2, 1) + ' m²'],
                ['Área de painel (bruta)', num(vis.total_area_raw_m2, 1) + ' m²'],
                ['Calibração de área', num(vis.area_calibration, 3) + '×'],
                ['Potência por área', num(vis.watt_per_m2) + ' W/m²'],
                ['Precisão · revocação', pct(mt.precision, 1) + ' · ' + pct(mt.recall, 1)],
                ['F1 · IoU de máscara', num(mt.f1, 3) + ' · ' + num(ev.mask_iou, 3)],
              ]}
            />
            {temGeo && (
              <div className="chips" style={{ marginTop: 10 }}>
                <Chip cor="teal" on={verCena} onClick={abrirCena}>
                  {verCena ? 'amostra aberta no mapa ↑' : 'ver a amostra de satélite no mapa ↑'}
                </Chip>
              </div>
            )}
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
          ' ladrilhos · clique para localizar no mapa'
        }
      >
        <TabelaDeteccoes dets={vis.detections || []} sel={iDet} onSel={onDet} />
      </OCard>
    </>
  )
}

/**
 * Banco de ensaio do detector (o mesmo painel da tela Visão computacional, sem a cena de
 * referência): a qualidade medida que dá lastro às detecções mostradas no mapa.
 */
function SecaoVisao() {
  const estado = useApi(() => Api.get('mapa/vision'), [])
  return (
    <div style={{ marginTop: 18 }}>
      <div className="note-strip">
        <strong>Visão computacional · banco de ensaio do detector.</strong> As detecções de cada subestação vêm deste detector; abaixo, o desempenho dele medido
        contra verdade fundamental. A cena de referência e as vistas de característica estão em <Link to="/visao">Visão computacional</Link>.
      </div>
      <Conteudo estado={estado} texto="Executando o banco de ensaio do detector…">
        {(body) => <PainelVisao body={body} comCena={false} />}
      </Conteudo>
    </div>
  )
}
