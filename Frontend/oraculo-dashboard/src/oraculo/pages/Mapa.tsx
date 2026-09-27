/**
 * Mapa Inteligente de perfis de carga e GD (protótipo, painel "mapa"). Porte de
 * 02-PROTOTIPO/web/js/views/mapa.js (V.mapa). Para cada subestação de fronteira: classe de
 * consumo predominante e nível de penetração de MMGD, com a amostra de ortoimagem e detecções.
 * Abre no mapa do Brasil; escolher a UF aproxima o mapa e mostra a rede de distribuição da BDGD
 * no desenho do mapa do RDX (áreas de influência, classificação, hierarquia, fundo satélite)
 * e as subestações de fronteira do ONS; o banco de ensaio do detector fecha a tela.
 */
import L from 'leaflet'
import { useMemo, useState, type ReactNode } from 'react'
import { Circle, CircleMarker, GeoJSON, Pane, Tooltip } from 'react-leaflet'
import { Link } from 'react-router-dom'
import ufsGeo from '../../data/geo/ufs.geo.json'
import { Api, type Envelope } from '../api'
import { color } from '../charts'
import { useOraculo, usePersistido } from '../estado'
import { CamadaAreas } from '../../components/mapa/CamadaAreas'
import { getAreasInfluencia } from '../../data/dataSource'
import type { AreasInfluencia } from '../../data/types'
import { TabelaDeteccoes } from '../CenaSatelite'
import { MapaOsm, type Fundo, type Limites } from '../MapaOsm'
import { ChipsClasses, PainelSubestacaoBdgd, RedeBdgd } from '../RedeBdgd'
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
  const [uf, setUf] = useState('')
  const [sel, setSel] = usePersistido<string | null>('oraculo.mapaSel', null)
  // a análise da UF leva alguns segundos: com uma UF só liberada, já pede os dados dela na
  // abertura, e o tempo em que a pessoa olha o mapa (e o voo) cobre parte da espera
  const ufDados = uf || UFS_ATIVAS[0]
  const estado = useApi(() => Api.get('mapa/substations', { uf: ufDados, limit: 50, frontier_only: 1 }), [ufDados])
  const rows: Dado[] = uf && estado.status === 'ok' ? ((estado.dado as Envelope).data as Dado).rows || [] : []
  const selId: string | null = sel && rows.some((r) => r.sub_id === sel) ? sel : (rows[0]?.sub_id ?? null)
  const detalhe = useApi(() => (selId ? Api.get('mapa/substations/' + encodeURIComponent(selId)) : Promise.resolve(null)), [selId])
  const dSub: Dado | null = detalhe.status === 'ok' && detalhe.dado ? (detalhe.dado as Envelope).data : null

  // Rede da BDGD (dado real: áreas de influência, classificação, mãe, MMGD, excedente). Pedida
  // na abertura, como os dados da UF; o contrato cobre só a área piloto (RJ).
  const areas = useApi(() => getAreasInfluencia(), [])
  const rede: AreasInfluencia | null = areas.status === 'ok' ? areas.dado : null
  const [selBdgd, setSelBdgd] = useState<string | null>(null)
  const pBdgd = rede?.features.find((f) => f.properties.areaId === selBdgd)?.properties ?? null

  return (
    <Pagina>
      <div id="mapa-perfis" style={{ marginBottom: 14 }}>
        <MapaBrasil
          uf={uf}
          setUf={(u) => {
            setUf(u)
            setSelBdgd(null)
          }}
          rows={rows}
          selId={selId}
          setSel={setSel}
          carregando={!!uf && estado.status === 'carregando'}
          rede={uf === UF_BDGD ? rede : null}
          redeCarregando={uf === UF_BDGD && areas.status === 'carregando'}
          selBdgd={selBdgd}
          setSelBdgd={setSelBdgd}
        />
      </div>
      {uf === UF_BDGD && (
        <div style={{ marginBottom: 14 }}>
          <OCard
            title={pBdgd ? 'Subestação da BDGD · ' + pBdgd.nome : 'Rede de distribuição da BDGD · ' + (NOME_UF[uf] || uf)}
            hint={pBdgd ? pBdgd.areaId : 'clique numa área ou num ícone no mapa'}
            note={
              'Dado real: BDGD 2025 (LIGHT e Enel RJ) × cadastro de MMGD da ANEEL, pela pipeline do RDX migrada para Backend/src/spatial (docs/metodo_espacial.md). ' +
              (rede?.descricao ?? '')
            }
          >
            <Conteudo estado={areas} texto="Carregando as áreas de influência da BDGD…">
              {(a) => (pBdgd ? <PainelSubestacaoBdgd p={pBdgd} areas={a} onSel={setSelBdgd} /> : <ResumoBdgd areas={a} />)}
            </Conteudo>
          </OCard>
        </div>
      )}
      {uf ? (
        <Conteudo estado={estado} texto={'Carregando subestações do ONS em ' + (NOME_UF[uf] || uf) + ' e analisando as amostras…'}>
          {(body) => (
            <Corpo
              body={body}
              selId={selId}
              setSel={setSel}
              detalhe={
                <Conteudo estado={detalhe} texto="Analisando a amostra…">
                  {() => (dSub ? <DetalheCorpo d={dSub} /> : null)}
                </Conteudo>
              }
            />
          )}
        </Conteudo>
      ) : (
        <div className="note-strip">
          Selecione um estado no mapa para ver a rede de distribuição da BDGD (áreas de influência, classificação das subestações e hierarquia de alimentação) e as
          subestações de fronteira com o ONS. Nesta versão, só o <strong>Rio de Janeiro</strong> está disponível; os demais estados entram em seguida.
        </div>
      )}
    </Pagina>
  )
}

/** UF coberta pelo recurso areas_influencia (área piloto da espacialização). */
const UF_BDGD = 'RJ'

/** Totais da rede da BDGD na UF (quando nenhuma subestação está selecionada). */
function ResumoBdgd({ areas }: { areas: AreasInfluencia }) {
  const ps = areas.features.map((f) => f.properties)
  const soma = (k: 'capacidadeMmgdMw' | 'capacidadeLagMw') => ps.reduce((a, p) => a + p[k], 0)
  const porDist = new Map<string, number>()
  ps.forEach((p) => porDist.set(p.distribuidora, (porDist.get(p.distribuidora) ?? 0) + 1))
  const comExcedente = ps.filter((p) => (p.excedenteMw ?? 0) > 0)
  return (
    <div className="grid g4">
      <Kpi label="Áreas de influência" value={num(ps.length)} foot={[...porDist].map(([d, n]) => d + ' ' + num(n)).join(' · ')} accent="teal" />
      <Kpi label="MMGD na rede" value={num(soma('capacidadeMmgdMw'), 1)} unit="MW" foot="cadastro ANEEL localizado pela BDGD" accent="amber" />
      <Kpi label="Lag de cadastro" value={num(soma('capacidadeLagMw'), 1)} unit="MW" foot="na ANEEL e ainda fora da BDGD" accent="navy" />
      <Kpi
        label="Com excedente previsto"
        value={num(comExcedente.length)}
        foot={'subestações de fronteira · ' + num(comExcedente.reduce((a, p) => a + (p.excedenteMw ?? 0), 0), 1) + ' MW nas próximas 24 h'}
        accent="crimson"
      />
    </div>
  )
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
        {num(rr.frontier_substations)} com transformação de fronteira com a distribuição. Saída, por subestação: composição por classe de consumo e nível de penetração de MMGD.{' '}
        {sm.real ? (
          <>
            <strong>Dado real:</strong> composição pela energia faturada (BDGD MT/AT + SAMP BT) das subestações de distribuição associadas a cada SE; MMGD pelo cadastro
            da ANEEL nessas SEDs.
          </>
        ) : (
          <>
            <strong>Sem a base real da fronteira T–D:</strong> os perfis abaixo vêm da amostra sintética de ortoimagem (demonstração).
          </>
        )}
      </div>

      <div className="grid g4" style={{ marginBottom: 14 }}>
        <Kpi label="Subestações de fronteira" value={num(d.total)} foot={'no estado · ' + num(d.returned) + ' analisadas'} accent="teal" />
        <Kpi label="Classe dominante no estado" value={topLabel(sm.by_class)} foot={spread(sm.by_class)} accent="navy" />
        <Kpi label="Penetração de MMGD" value={topLabel(sm.by_mmgd_level)} foot={spread(sm.by_mmgd_level)} accent="amber" />
        {sm.real ? (
          <Kpi
            label="MMGD cadastrada nas SEs"
            value={num((sm.total_kwp || 0) / 1000, 1)}
            unit="MW"
            foot={'cadastro ANEEL · no SIN a MMGD é ' + num(d.sin_mmgd_ratio, 2) + '× a carga média'}
            accent="green"
          />
        ) : (
          <Kpi
            label="Qualidade da detecção"
            value={num(sm.detector_f1_mean, 3)}
            unit="F1"
            foot={'IoU de máscara ' + num(sm.detector_mask_iou_mean, 3) + ' · banco de ensaio sintético'}
            accent="green"
          />
        )}
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
                      <span className="faint">
                        {r.real ? 'medido ' : 'conf. '}
                        {pct(r.class_confidence, 0)}
                      </span>
                    </td>
                    <td>
                      <LevelChip lv={r.mmgd_level} />
                      <br />
                      <span className="small faint mono">{mmgdTexto(r)}</span>
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
        {sm.real ? (
          <OCard
            title="Faixas do indicador de MMGD"
            note={
              'Razão MMGD cadastrada ÷ carga média da SE, em múltiplos da mesma razão no SIN (' +
              num(d.sin_mmgd_ratio, 3) +
              ': 43,5 GWp de MMGD ÷ carga média supervisionada do SIN). Comparável entre SEs de porte diferente; nenhuma base pública traz a área servida.'
            }
          >
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Nível</th>
                    <th className="num">de (× SIN)</th>
                    <th className="num">até</th>
                  </tr>
                </thead>
                <tbody>
                  {(d.penetration_rel_bins || []).map((b: Dado, i: number) => (
                    <tr key={i}>
                      <td>
                        <LevelChip lv={b.level} />
                      </td>
                      <td className="num">{num(b.from_rel, 1)}</td>
                      <td className="num">{b.to_rel === null ? '—' : num(b.to_rel, 1)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </OCard>
        ) : (
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
        )}
      </div>
      <SecaoVisao />
      <Proveniencia body={body} />
    </>
  )
}

/**
 * Mapa em dois níveis, sempre o mesmo Leaflet (a transição é um voo, não uma troca de tela):
 * 1. Brasil, com as UFs do IBGE: clicar numa UF liberada voa até ela;
 * 2. UF: a rede de distribuição da BDGD no desenho do mapa do RDX (Backend/RDX/main.py) —
 *    áreas de influência, subestações com ícone por classificação, linhas de alimentação
 *    mãe → satélite, fundo OpenStreetMap ou satélite — e as subestações de fronteira do ONS
 *    (cor pelo nível de MMGD do protótipo). Cada grupo liga e desliga, como o LayerControl do RDX.
 */
function MapaBrasil({
  uf,
  setUf,
  rows,
  selId,
  setSel,
  carregando,
  rede,
  redeCarregando,
  selBdgd,
  setSelBdgd,
}: {
  uf: string
  setUf: (u: string) => void
  rows: Dado[]
  selId: string | null
  setSel: (s: string) => void
  carregando: boolean
  rede: AreasInfluencia | null
  redeCarregando: boolean
  selBdgd: string | null
  setSelBdgd: (id: string | null) => void
}) {
  const [raios, setRaios] = usePersistido('oraculo.mapaOsmRaios', false)
  const [fundo, setFundo] = usePersistido<Fundo>('oraculo.mapaFundo', 'mapa')
  const [verAreas, setVerAreas] = usePersistido('oraculo.mapaAreas', true)
  const [verOns, setVerOns] = usePersistido('oraculo.mapaOns', true)
  const [hierarquia, setHierarquia] = usePersistido('oraculo.mapaHierarquia', false)
  const [classesLista, setClassesLista] = usePersistido<string[]>('oraculo.mapaClasses', ['Distribuição plena', 'Distribuição satélite', 'Transformadora pura'])
  const classes = useMemo(() => new Set(classesLista), [classesLista])
  const alternarClasse = (c: string) => setClassesLista(classes.has(c) ? classesLista.filter((x) => x !== c) : [...classesLista, c])
  const contagem = useMemo(() => {
    const m = new Map<string, number>()
    rede?.features.forEach((f) => m.set(f.properties.classificacao, (m.get(f.properties.classificacao) ?? 0) + 1))
    return m
  }, [rede])

  const limites = useMemo(() => (uf ? limitesDaUf(uf) : null) || BRASIL, [uf])
  const pts = verOns ? rows.filter((r) => Number.isFinite(r.lat) && Number.isFinite(r.lon)) : []
  // a selecionada por último, para ficar por cima das demais
  const ordem = [...pts].sort((a, b) => (a.sub_id === selId ? 1 : 0) - (b.sub_id === selId ? 1 : 0))
  const nome = NOME_UF[uf] || uf

  const hint = uf
    ? carregando || redeCarregando
      ? 'carregando a rede e as subestações…'
      : (rede ? num(rede.features.length) + ' subestações da BDGD · ' : '') + num(rows.length) + ' de fronteira do ONS'
    : 'estados em destaque já têm a análise'
  const nota = uf
    ? 'Áreas de influência: violeta mais forte = mais MMGD; contorno laranja = subestação com excedente previsto (tracejado nas satélites dela). ' +
      'Linhas âmbar = alimentação mãe → satélite. Círculos = subestações de fronteira do ONS, cor pelo nível de MMGD do protótipo. Divisas: IBGE.'
    : 'Divisas: IBGE. © OpenStreetMap contributors.'

  return (
    <OCard title={uf ? nome + ' · rede de distribuição e fronteira com o ONS' : 'Brasil · selecione um estado'} hint={hint} note={nota}>
      <MapaOsm limites={limites} altura={560} maxZoom={uf ? 9 : 5} zoomMin={3} animar rolagem fundo={fundo}>
        <Pane name="ufs" style={{ zIndex: 350 }}>
          <CamadaUfs uf={uf} onUf={setUf} />
        </Pane>
        {rede && verAreas && (
          <Pane name="areas" style={{ zIndex: 360 }}>
            <CamadaAreas areas={rede} selecionada={selBdgd} onClicar={(p) => setSelBdgd(p.areaId)} />
          </Pane>
        )}
        {rede && <RedeBdgd areas={rede} classes={classes} hierarquia={hierarquia} sel={selBdgd} onSel={setSelBdgd} />}
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
                Fronteira ONS: <strong>{r.name}</strong> ({r.uf}) · {r.sub_id}
                <br />
                classe: {r.class_label || r.class_dominant || '—'}
                <br />
                MMGD: {r.mmgd_level || '—'} · {mmgdTexto(r)}
              </Tooltip>
            </CircleMarker>
          )
        })}
      </MapaOsm>
      {uf ? (
        <>
          <div className="chips" style={{ marginTop: 8 }}>
            <Chip onClick={() => setUf('')}>← voltar ao Brasil</Chip>
            <Chip on={fundo === 'mapa'} onClick={() => setFundo('mapa')}>
              Mapa
            </Chip>
            <Chip on={fundo === 'satelite'} onClick={() => setFundo('satelite')}>
              Satélite
            </Chip>
            {selBdgd && <Chip onClick={() => setSelBdgd(null)}>✕ limpar seleção</Chip>}
          </div>
          {rede && (
            <div className="chips" style={{ marginTop: 6 }}>
              <Chip on={verAreas} onClick={() => setVerAreas(!verAreas)}>
                Áreas de influência (MMGD)
              </Chip>
              <Chip on={hierarquia} onClick={() => setHierarquia(!hierarquia)}>
                🔗 Hierarquia de alimentação
              </Chip>
              <ChipsClasses classes={classes} alternar={alternarClasse} contagem={contagem} />
            </div>
          )}
          <div className="chips" style={{ marginTop: 6 }}>
            <Chip on={verOns} onClick={() => setVerOns(!verOns)}>
              Fronteira ONS ({num(rows.length)})
            </Chip>
            {verOns &&
              Object.keys(LEVEL_COLORS).map((lv) => (
                <LevelChip key={lv} lv={lv} />
              ))}
            {verOns && (
              <Chip on={raios} onClick={() => setRaios(!raios)}>
                raio de análise
              </Chip>
            )}
          </div>
        </>
      ) : (
        <div className="chips" style={{ marginTop: 8 }}>
          {UFS_ATIVAS.map((u) => (
            <Chip key={u} cor="teal" onClick={() => setUf(u)}>
              {NOME_UF[u] || u}
            </Chip>
          ))}
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

/** MMGD de uma linha: real = MW cadastrados e razão relativa ao SIN; sintético = kWp/km² da amostra. */
function mmgdTexto(r: Dado): string {
  if (!r.real) return num(r.mmgd_kwp_per_km2) + ' kWp/km² (amostra sintética)'
  if (r.mmgd_kwp === null || r.mmgd_kwp === undefined) return 'sem SED associada'
  return num(r.mmgd_kwp / 1000, 1) + ' MW · ' + num(r.mmgd_relative_to_sin, 2) + '× SIN'
}

function nivelCor(lv: string | null | undefined): string {
  return color((lv && LEVEL_COLORS[lv]) || 'muted')
}

function DetalheCorpo({ d }: { d: Dado }) {
  const [iDet, setIDet] = useState<number | null>(null)
  const s = d.substation || {}
  const lc = d.load_class || {}
  const m = d.mmgd || {}
  const an = d.clm || {}
  const ev = d.evaluation || {}
  const mt = ev.match || {}
  const vis = d.vision || {}

  return (
    <>
      <OCard
        title={'Detalhe · ' + (s.name || '') + ' (' + (s.uf || '') + ')'}
        hint={num(s.frontier_mva) + ' MVA de fronteira · raio ' + num(s.radius_km, 2) + ' km' + (lc.real ? '' : ' · morfologia ' + (d.urban_hint ?? ''))}
        note={(d.notes || []).join(' ') || undefined}
      >
        <div className="grid g2" style={{ gap: 12 }}>
          <div>
            <div className="okpi-label">1 · Perfil predominante de consumo</div>
            <div style={{ fontSize: 17, fontWeight: 650, margin: '4px 0 8px' }}>
              {lc.label}{' '}
              <span className="small muted">
                {lc.real ? 'energia medida por UC ' + pct(lc.confidence, 0) : 'confiança ' + pct(lc.confidence, 0) + ' · amostra sintética'}
              </span>
            </div>
            <WeightBars weights={lc.weights} />
            <div className="okpi-label" style={{ marginTop: 14 }}>
              2 · Presença de geração distribuída
            </div>
            {m.real ? (
              <>
                <div style={{ fontSize: 17, fontWeight: 650, margin: '4px 0 8px' }}>
                  <LevelChip lv={m.level} /> {m.kwp_total === null || m.kwp_total === undefined ? 'sem dado' : num(m.kwp_total / 1000, 1) + ' MW'}{' '}
                  <span className="small muted">cadastro ANEEL</span>
                </div>
                <StatLines
                  pares={[
                    ['Empreendimentos', num(m.gd_n)],
                    ['Carga média da SE', num(m.mw_avg, 1) + ' MW'],
                    ['MMGD ÷ carga média', num(m.ratio_to_load, 3)],
                    ['Mesma razão no SIN', num(m.ratio_to_load_sin, 3)],
                    ['Relativo ao SIN', num(m.relative_to_sin, 2) + '×'],
                    ['Localizada direto pela BDGD', pct(m.direct_share, 1)],
                    ['Tipo III na UF', num(m.tipo3_mw_uf, 1) + ' MW (' + num(m.tipo3_count_uf) + ' usinas)'],
                  ]}
                />
                <div className="small faint" style={{ marginTop: 6 }}>
                  {m.source}. {m.confidence_note ? 'Confiança = ' + m.confidence_note + '.' : ''}
                </div>
              </>
            ) : (
              <>
            <div style={{ fontSize: 17, fontWeight: 650, margin: '4px 0 8px' }}>
              <LevelChip lv={m.level} /> {num(m.kwp_per_km2)} <span className="small muted">kWp/km² · confiança {pct(m.confidence, 0)} · amostra sintética</span>
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
              </>
            )}
          </div>
          <div>
            <div className="okpi-label">3 · Visão computacional · amostra sintética (demonstração)</div>
            <div style={{ fontSize: 17, fontWeight: 650, margin: '4px 0 8px' }}>
              {num(vis.kept_count)} painéis <span className="small muted">· {num(vis.total_kwp, 1)} kWp</span>
            </div>
            <StatLines
              pares={[
                // vision.detector é o descritor do backend ({name, kind, runtime, …}), não um texto
                ['Detector', (vis.detector && (vis.detector.name || vis.detector.kind)) || '—'],
                // tile_grid é a lista dos ladrilhos (um objeto por ladrilho), não as dimensões da grade
                ['Ladrilhos analisados', num(vis.tiles)],
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
            <div className="small faint" style={{ marginTop: 8 }}>
              A ortoimagem do protótipo é sintética: os números medem o detector, não painéis reais nesta subestação. A MMGD real da rede está nas áreas de
              influência da BDGD, no mapa acima.
            </div>
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
          {lc.real ? (
            <StatLines
              pares={[
                ['Desvio da média regional', num(lc.deviation_from_regional, 3)],
                ['Classe do subsistema (curva ONS)', (lc.regional_prior || {}).label || '—'],
                ['R² do ajuste do subsistema', num((lc.regional_prior || {}).r2, 3)],
                ['Classe desta SE (energia faturada)', lc.label || '—'],
                ['Fonte', lc.source || '—'],
              ]}
            />
          ) : (
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
          )}
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
          ' ladrilhos · cena sintética'
        }
      >
        <TabelaDeteccoes dets={vis.detections || []} sel={iDet} onSel={setIDet} />
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
