/**
 * Triangulação de evidências (protótipo, painel "triangulacao"). Porte de V.triangulacao em
 * 02-PROTOTIPO/web/js/views/analise.js: três camadas independentes (satélite, BDGD, ANEEL) e a
 * lógica de desempate entre defasagem administrativa e instalação não homologada.
 */
import { Api, type Envelope } from '../api'
import { num, pct } from '../format'
import { Conteudo, Kpi, OCard, Pagina, Proveniencia, useApi } from '../ui'

/* eslint-disable @typescript-eslint/no-explicit-any */
type Dado = any

export default function Triangulacao() {
  const estado = useApi(() => Api.triangulation(), [])
  return (
    <Pagina>
      <Conteudo estado={estado} texto="Cruzando realidade física, topologia e cadastro…">
        {(body) => <Corpo body={body} />}
      </Conteudo>
    </Pagina>
  )
}

function Corpo({ body }: { body: Envelope }) {
  const t = body.data as Dado
  const areas: Dado[] = t.areas || []
  const tot: Record<string, number> = {}
  areas.forEach((a) =>
    Object.keys(a.matrix || {}).forEach((k) => {
      tot[k] = (tot[k] || 0) + a.matrix[k]
    }),
  )
  const units = areas.reduce((s, a) => s + (a.units_total || 0), 0)
  const lag = tot.lag_de_sistema || 0
  const nh = tot.nao_homologada || 0

  return (
    <>
      <div className="note-strip warn">{t.note || ''}</div>

      <div className="grid g4" style={{ marginBottom: 14 }}>
        <Kpi label="Unidades avaliadas" value={num(units)} foot={num(areas.length) + ' áreas'} accent="teal" />
        <Kpi label="Defasagem de sistema" value={pct(units ? lag / units : 0, 1)} foot={num(lag) + ' unidades homologadas e ausentes na BDGD'} accent="amber" />
        <Kpi label="Não homologadas" value={pct(units ? nh / units : 0, 1)} foot={num(nh) + ' unidades escaladas como exceção'} accent="crimson" />
        <Kpi label="Confirmadas" value={pct(units ? (tot.confirmada || 0) / units : 0, 1)} foot="três camadas concordam" accent="green" />
      </div>

      <OCard
        title="Lógica de desempate"
        note={
          <>
            Somente <strong>confirmada</strong> e <strong>defasagem de sistema</strong> entram no fator de correção de capacidade. Instalação não homologada é reportada em separado,
            nunca somada silenciosamente.
          </>
        }
      >
        <Matriz t={t} tot={tot} />
      </OCard>

      <div className="grid g2" style={{ marginTop: 14, marginBottom: 14 }}>
        <OCard title="Três camadas de evidência">
          <TabelaCamadas layers={t.layers} />
        </OCard>
        <OCard
          title="Fator de correção por área"
          note="A capacidade implicada vem do déficit diurno observado na carga; uma razão muito acima de 1 sugere cadastro defasado."
        >
          <TabelaCorrecao areas={areas} />
        </OCard>
      </div>

      <OCard title="Amostra de unidades classificadas" hint={'40 primeiras de ' + num(units)}>
        <TabelaAmostra sample={t.sample} />
      </OCard>
      <Proveniencia body={body} />
    </>
  )
}

function Matriz({ t, tot }: { t: Dado; tot: Record<string, number> }) {
  const cls = t.classes || {}
  const cell = (key: string, kind: string) => {
    const c = cls[key] || {}
    return (
      <div className={'mcell ' + kind}>
        <h4>{c.label || key}</h4>
        <div className="n">{num(tot[key] || 0)}</div>
        <p>{c.note || ''}</p>
      </div>
    )
  }
  return (
    <div className="matrix">
      <div className="mh" />
      <div className="mh">Consta na ANEEL</div>
      <div className="mh">Não consta</div>
      <div className="rh">Detectado no satélite</div>
      <div className="mcell ok">
        <h4>
          {(cls.confirmada || {}).label || ''} · {(cls.lag_de_sistema || {}).label || ''}
        </h4>
        <div className="n">{num((tot.confirmada || 0) + (tot.lag_de_sistema || 0))}</div>
        <p>{(cls.lag_de_sistema || {}).note || ''}</p>
      </div>
      {cell('nao_homologada', 'bad')}
      <div className="rh">Não detectado</div>
      {cell('cadastro_sem_evidencia', 'warn')}
      {cell('sem_evidencia', 'neutral')}
    </div>
  )
}

function TabelaCamadas({ layers }: { layers: Dado[] | undefined }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Camada</th>
            <th>Pergunta</th>
            <th>Cadência</th>
            <th>Limitação declarada</th>
          </tr>
        </thead>
        <tbody>
          {(layers || []).map((l, i) => (
            <tr key={l.layer ?? i}>
              <td>
                <strong>
                  {num(l.layer)} · {l.name}
                </strong>
                <br />
                <span className="small faint">{l.source}</span>
              </td>
              <td>{l.question}</td>
              <td>
                <span className="chip teal">{l.cadence}</span>
              </td>
              <td className="small muted">{l.limitation}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function TabelaCorrecao({ areas }: { areas: Dado[] }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Área</th>
            <th className="num">Unid.</th>
            <th className="num">Declarada MW</th>
            <th className="num">Corrigida MW</th>
            <th className="num">Fator</th>
            <th className="num">Não homol. MW</th>
            <th className="num">Implicada MWp</th>
            <th className="num">Cobertura</th>
          </tr>
        </thead>
        <tbody>
          {areas.map((a) => (
            <tr key={a.area}>
              <td>
                <strong>{a.area}</strong>
              </td>
              <td className="num">{num(a.units_total)}</td>
              <td className="num">{num(a.capacity_declared_mw, 1)}</td>
              <td className="num">{num(a.capacity_corrected_mw, 1)}</td>
              <td className="num">
                <strong>{num(a.correction_factor, 3)}</strong>
              </td>
              <td className="num">{num(a.capacity_unhomologated_mw, 1)}</td>
              <td className="num">{num(a.implied_capacity_mwp)}</td>
              <td className="num">{pct(a.coverage, 0)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

const BADGE: Record<string, string> = { confirmada: 'green', lag_de_sistema: 'amber', nao_homologada: 'crimson', cadastro_sem_evidencia: '', sem_evidencia: '' }

function SimNao({ v }: { v: unknown }) {
  return v ? <span className="pos">sim</span> : <span className="faint">não</span>
}

function TabelaAmostra({ sample }: { sample: Dado[] | undefined }) {
  return (
    <div className="table-wrap scroll-y">
      <table>
        <thead>
          <tr>
            <th>Unidade</th>
            <th>Área</th>
            <th className="num">kWp</th>
            <th>Satélite</th>
            <th>BDGD</th>
            <th>ANEEL</th>
            <th>Classificação</th>
            <th>Correção</th>
          </tr>
        </thead>
        <tbody>
          {(sample || []).map((u, i) => (
            <tr key={u.unit_id ?? i}>
              <td className="mono small">{u.unit_id}</td>
              <td>{u.area}</td>
              <td className="num">{num(u.capacity_kwp, 1)}</td>
              <td>
                <SimNao v={u.detected} />
              </td>
              <td>
                <SimNao v={u.in_bdgd} />
              </td>
              <td>
                <SimNao v={u.in_aneel} />
              </td>
              <td>
                <span className={'chip ' + (BADGE[u.classification] || '')}>{u.label}</span>
              </td>
              <td className="small">{u.counts_in_correction ? <span className="pos">entra</span> : <span className="neg">não entra</span>}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
