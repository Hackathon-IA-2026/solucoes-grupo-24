/**
 * Rede de distribuição da BDGD no mapa, no desenho do mapa do RDX (Backend/RDX/main.py, o
 * hackathon anterior): um ícone por classificação da subestação e as linhas de alimentação
 * "mãe → satélite". Os dados são os REAIS do recurso areas_influencia (a pipeline do RDX
 * migrada e corrigida em Backend/src/spatial; docs/metodo_espacial.md) — nada é recalculado aqui.
 *
 * Diferenças em relação ao RDX, com o motivo:
 * - tamanho do ícone fixo: o RDX escalava pela potência calculada, que não está no contrato;
 * - AntPath (plugin do folium) virou linha tracejada com animação em CSS (.fluxo-alimentacao):
 *   o mesmo efeito de "formigas andando" sem dependência nova.
 */
import L from 'leaflet'
import { useMemo } from 'react'
import { Marker, Polyline, Tooltip } from 'react-leaflet'
import type { AreasInfluencia, PropriedadesArea } from '../data/types'
import iconeRaio from './icones/raio.png'
import iconeSatelite from './icones/satelite.png'
import iconeTorre from './icones/torre.png'
import iconeTransformador from './icones/transformador.png'
import { num } from './format'
import { Chip, StatLines } from './ui'

/** Classificações da BDGD (texto da API) → ícone, cor do selo e rótulo, na ordem das camadas do RDX. */
export const CLASSES_SE: { chave: string; rotulo: string; icone: string; cor: string }[] = [
  { chave: 'Distribuição plena', rotulo: 'Distribuição plena', icone: iconeRaio, cor: 'var(--o-teal)' },
  { chave: 'Distribuição satélite', rotulo: 'Distribuição satélite', icone: iconeSatelite, cor: 'var(--o-purple)' },
  { chave: 'Transformadora pura', rotulo: 'Transformadora pura', icone: iconeTransformador, cor: 'var(--o-amber)' },
  { chave: 'Transporte/manobra', rotulo: 'Transporte/manobra', icone: iconeTorre, cor: 'var(--o-muted)' },
]
const POR_CHAVE = new Map(CLASSES_SE.map((c) => [c.chave, c]))

/**
 * Ícone da subestação: o PNG do RDX dentro de um selo branco redondo com a borda na cor da
 * classe. Só o PNG (11×20 px) sumia sobre o violeta das áreas de influência; o RDX usava de 25 a
 * 70 px. A selecionada fica maior. Criados uma vez só (cache).
 */
const cacheIcones = new Map<string, L.DivIcon>()
function icone(classificacao: string, grande: boolean): L.DivIcon {
  const k = classificacao + (grande ? '+' : '')
  let i = cacheIcones.get(k)
  if (!i) {
    const c = POR_CHAVE.get(classificacao) ?? CLASSES_SE[3]
    const lado = grande ? 38 : 26
    i = L.divIcon({
      html: `<span class="se-selo${grande ? ' sel' : ''}" style="border-color:${c.cor}"><img src="${c.icone}" alt="" /></span>`,
      className: 'icone-se',
      iconSize: [lado, lado],
      iconAnchor: [lado / 2, lado / 2],
    })
    cacheIcones.set(k, i)
  }
  return i
}

/** Marcadores das subestações da BDGD (filtrados pelas classes ligadas) + linhas de alimentação. */
export function RedeBdgd({
  areas,
  classes,
  hierarquia,
  sel,
  onSel,
}: {
  areas: AreasInfluencia
  /** classificações visíveis */
  classes: ReadonlySet<string>
  /** desenhar todas as linhas mãe → satélite (as da selecionada aparecem sempre) */
  hierarquia: boolean
  sel: string | null
  onSel: (id: string) => void
}) {
  const props = useMemo(() => areas.features.map((f) => f.properties), [areas])
  const porId = useMemo(() => new Map(props.map((p) => [p.areaId, p])), [props])
  // pares mãe → filha com as duas pontas conhecidas
  const ligacoes = useMemo(
    () =>
      props
        .filter((p) => p.areaMae && p.areaMae !== p.areaId && porId.has(p.areaMae))
        .map((p) => ({ mae: porId.get(p.areaMae!)!, filha: p })),
    [props, porId],
  )
  const linhas = hierarquia ? ligacoes : ligacoes.filter((l) => l.mae.areaId === sel || l.filha.areaId === sel)

  return (
    <>
      {linhas.map(({ mae, filha }) => {
        const daSel = mae.areaId === sel || filha.areaId === sel
        return (
          <Polyline
            key={mae.areaId + '>' + filha.areaId + (daSel ? '+' : '')}
            positions={[
              [mae.latSub, mae.lonSub],
              [filha.latSub, filha.lonSub],
            ]}
            pathOptions={{ className: 'fluxo-alimentacao' + (daSel ? ' sel' : ''), weight: daSel ? 3.5 : 2.5, dashArray: '10 14' }}
          >
            <Tooltip sticky direction="top">
              Alimentação: <strong>{mae.nome}</strong> → {filha.nome}
            </Tooltip>
          </Polyline>
        )
      })}
      {props
        .filter((p) => classes.has(p.classificacao) || p.areaId === sel)
        .map((p) => (
          <Marker
            key={p.areaId + (p.areaId === sel ? '+' : '')}
            position={[p.latSub, p.lonSub]}
            icon={icone(p.classificacao, p.areaId === sel)}
            zIndexOffset={p.areaId === sel ? 1000 : 0}
            eventHandlers={{ click: () => onSel(p.areaId) }}
          >
            <Tooltip direction="top">
              SE: <strong>{p.nome}</strong> · {p.distribuidora}
              <br />
              {p.classificacao} · MMGD {num(p.capacidadeMmgdMw, 2)} MW
            </Tooltip>
          </Marker>
        ))}
    </>
  )
}

/** Legenda/filtro das classificações com o ícone de cada uma (as camadas do RDX). */
export function ChipsClasses({ classes, alternar, contagem }: { classes: ReadonlySet<string>; alternar: (c: string) => void; contagem: Map<string, number> }) {
  return (
    <>
      {CLASSES_SE.map((c) => (
        <Chip key={c.chave} on={classes.has(c.chave)} onClick={() => alternar(c.chave)} title={'mostrar/ocultar: ' + c.rotulo}>
          <img src={c.icone} alt="" style={{ height: 13, width: 'auto', verticalAlign: '-2px', marginRight: 5 }} />
          {c.rotulo} ({num(contagem.get(c.chave) ?? 0)})
        </Chip>
      ))}
    </>
  )
}

/**
 * Painel da subestação da BDGD selecionada: o conteúdo do popup do RDX com os campos que o
 * contrato traz (areas_influencia). Mãe e satélites são clicáveis para navegar na hierarquia.
 */
export function PainelSubestacaoBdgd({ p, areas, onSel }: { p: PropriedadesArea; areas: AreasInfluencia; onSel: (id: string) => void }) {
  const todos = areas.features.map((f) => f.properties)
  const mae = p.areaMae ? todos.find((x) => x.areaId === p.areaMae) : undefined
  const filhas = todos.filter((x) => x.areaMae === p.areaId && x.areaId !== p.areaId)
  const c = POR_CHAVE.get(p.classificacao)
  return (
    <div className="grid g2" style={{ gap: 12 }}>
      <div>
        <div style={{ fontSize: 17, fontWeight: 650, margin: '2px 0 8px', display: 'flex', alignItems: 'center', gap: 8 }}>
          {c && <img src={c.icone} alt="" style={{ height: 20, width: 'auto' }} />}
          {p.nome}
        </div>
        <StatLines
          pares={[
            ['Distribuidora', p.distribuidora],
            ['Classificação', p.classificacao],
            ['Alimentada por', mae ? <a key="mae" onClick={() => onSel(mae.areaId)} style={{ cursor: 'pointer' }}>{mae.nome}</a> : p.areaMae || '— (não é satélite)'],
            ['Área de influência', num(p.areaKm2, 1) + ' km²'],
            ['Código (BDGD)', <span key="c" className="mono">{p.areaId}</span>],
          ]}
        />
      </div>
      <div>
        <div className="okpi-label">☀️ Geração distribuída (MMGD)</div>
        <StatLines
          pares={[
            ['Capacidade de MMGD', num(p.capacidadeMmgdMw, 3) + ' MW'],
            ['… ainda fora da BDGD (lag de cadastro)', num(p.capacidadeLagMw, 3) + ' MW'],
            ['Fator de correção (satélite)', p.fatorCorrecao === null ? 'sem correção' : num(p.fatorCorrecao, 2)],
            [
              'Excedente previsto (24 h)',
              p.excedenteMw === null ? 'não é subestação de fronteira' : num(p.excedenteMw, 2) + ' MW' + (p.excedenteMw > 0 && p.horizonteExcedente ? ' · ' + p.horizonteExcedente : ''),
            ],
          ]}
        />
        {filhas.length > 0 && (
          <>
            <div className="okpi-label" style={{ marginTop: 12 }}>
              Alimenta {filhas.length} subestaç{filhas.length === 1 ? 'ão' : 'ões'}
            </div>
            <div className="chips" style={{ marginTop: 6 }}>
              {filhas.map((f) => (
                <Chip key={f.areaId} onClick={() => onSel(f.areaId)}>
                  {f.nome}
                </Chip>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  )
}
