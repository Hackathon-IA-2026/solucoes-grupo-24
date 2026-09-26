/**
 * Dados abertos e proveniência (protótipo, painel "dados"). Porte de V.dados em
 * 02-PROTOTIPO/web/js/views/confianca.js: catálogo CKAN do ONS, detalhe de conjunto, ingestão,
 * estado do cache e manifesto de auditoria.
 */
import { useEffect, useState } from 'react'
import { Api, ApiError, type Envelope } from '../api'
import { useOraculo } from '../estado'
import { bytes, num, when } from '../format'
import { Carregando, Chip, Conteudo, ErroBloco, Kpi, OCard, Pagina, Proveniencia, Vazio, modeClass, useApi } from '../ui'

/* eslint-disable @typescript-eslint/no-explicit-any */
type Dado = any

export default function DadosAbertos() {
  const { recarregar } = useOraculo()
  // fica fora do <Conteudo> para sobreviver ao recarregamento depois da ingestão
  const [status, setStatus] = useState('')
  const estado = useApi(() => Promise.all([Api.catalog(), Api.provenance()]), [])

  const ingerir = async () => {
    setStatus('executando…')
    try {
      const res = await Api.ingest({ force: false })
      setStatus('concluído · modo ' + (res.data as Dado).mode)
      Api.clearCache()
      setTimeout(() => void recarregar(), 600)
    } catch (err) {
      setStatus('falhou: ' + (err instanceof Error ? err.message : String(err)))
    }
  }
  const atualizarCatalogo = async () => {
    setStatus('consultando CKAN…')
    try {
      await Api.catalog(true)
      setStatus('catálogo atualizado')
      setTimeout(() => void recarregar(), 400)
    } catch (err) {
      setStatus('falhou: ' + (err instanceof Error ? err.message : String(err)))
    }
  }

  return (
    <Pagina>
      <Conteudo estado={estado} texto="Consultando o catálogo CKAN do ONS…">
        {([catB, provB]) => <Corpo catB={catB} provB={provB} status={status} onIngerir={ingerir} onAtualizar={atualizarCatalogo} />}
      </Conteudo>
    </Pagina>
  )
}

function Corpo({
  catB,
  provB,
  status,
  onIngerir,
  onAtualizar,
}: {
  catB: Envelope
  provB: Envelope
  status: string
  onIngerir: () => void
  onAtualizar: () => void
}) {
  const c = catB.data as Dado
  const pv = provB.data as Dado
  const cache = pv.cache || {}
  const curated: Dado[] = c.curated || []
  const pkgs: Dado[] = c.packages || []
  const [filtro, setFiltro] = useState('')
  const [pkg, setPkg] = useState<string | null>(null)

  const t = filtro.toLowerCase()
  const visiveis = pkgs.filter((p) => !t || String(p.id).toLowerCase().includes(t) || String(p.title || '').toLowerCase().includes(t))

  return (
    <>
      <div className="grid g4" style={{ marginBottom: 14 }}>
        <Kpi label="Conjuntos no Portal" value={num(c.count)} foot={num(curated.length) + ' curados nesta solução'} accent="teal" />
        <Kpi label="Recursos em cache" value={num(cache.entries)} foot={bytes(cache.bytes) + ' em disco'} accent="green" />
        <Kpi label="Modo corrente" value={pv.mode || '—'} foot="live = rede · cache = disco · demo = sintético" accent={pv.mode === 'demo' ? 'amber' : 'teal'} />
        <Kpi label="Fontes externas mapeadas" value={num((c.external || []).length)} foot="BDGD, cadastro ANEEL, satélite, meteorologia" accent="crimson" />
      </div>

      <div style={{ marginBottom: 14 }}>
        <button className="primary" onClick={onIngerir}>
          Reexecutar ingestão
        </button>{' '}
        <button className="ghost" onClick={onAtualizar}>
          Atualizar catálogo do ONS
        </button>{' '}
        <span className="small muted">{status}</span>
      </div>

      <OCard title="Conjuntos usados na solução" note="Esquemas verificados por inspeção direta dos recursos CSV.">
        <TabelaCurados curated={curated} />
      </OCard>

      <div className="grid g-2-1" style={{ margin: '14px 0' }}>
        <OCard title="Catálogo completo do Portal" hint={num(pkgs.length) + ' conjuntos'}>
          <input placeholder="filtrar conjuntos…" style={{ width: '100%', marginBottom: 9 }} value={filtro} onChange={(e) => setFiltro(e.target.value)} />
          <div className="table-wrap scroll-y">
            <table>
              <thead>
                <tr>
                  <th>Conjunto</th>
                  <th>Papel</th>
                </tr>
              </thead>
              <tbody>
                {visiveis.length ? (
                  visiveis.map((p) => (
                    <tr key={p.id} style={{ cursor: 'pointer' }} onClick={() => setPkg(p.id)}>
                      <td>
                        {p.curated ? (
                          <>
                            <Chip cor="green">curado</Chip>{' '}
                          </>
                        ) : null}
                        <span className="mono small">{p.id}</span>
                        {p.title && p.title !== p.id ? (
                          <>
                            <br />
                            {p.title}
                          </>
                        ) : null}
                      </td>
                      <td className="small muted">{p.granularity || p.role || ''}</td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={2}>nada encontrado</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </OCard>
        <OCard title="Detalhe do conjunto">{pkg ? <DetalheConjunto key={pkg} pkg={pkg} /> : <Vazio>Selecione um conjunto à esquerda.</Vazio>}</OCard>
      </div>

      <OCard
        title="Relatório de ingestão"
        note="Campo numérico vazio vira NaN, nunca zero: zerar inventa informação. Descartes e colisões são contabilizados."
      >
        <TabelaIngestao reports={pv.reports} />
      </OCard>

      <div className="grid g2" style={{ margin: '14px 0' }}>
        <OCard title="Previsto para a fase presencial">
          <div className="table-wrap">
            <table>
              <tbody>
                {(c.planned || []).map((p: Dado, i: number) => (
                  <tr key={p.package + '-' + i}>
                    <td className="mono small">{p.package}</td>
                    <td className="small">{p.role}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </OCard>
        <OCard title="Fontes externas e seu estado">
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Fonte</th>
                  <th>Cadência</th>
                  <th>Estado</th>
                </tr>
              </thead>
              <tbody>
                {(c.external || []).map((e: Dado, i: number) => (
                  <tr key={e.name + '-' + i}>
                    <td>
                      <strong>{e.name}</strong>
                      <br />
                      <span className="small muted">{e.role}</span>
                    </td>
                    <td>
                      <Chip cor="teal">{e.cadence}</Chip>
                    </td>
                    <td className="small faint">{e.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </OCard>
      </div>

      <OCard title="Manifesto de cache · auditoria" hint="cada recurso com hash, tamanho e instante de extração">
        <TabelaManifesto entries={pv.entries} />
      </OCard>
      <Proveniencia body={catB} />
    </>
  )
}

function DetalheConjunto({ pkg }: { pkg: string }) {
  const [d, setD] = useState<Dado>(null)
  const [erro, setErro] = useState<ApiError | null>(null)
  useEffect(() => {
    let vivo = true
    Api.packageDetail(pkg)
      .then((b) => vivo && setD(b.data))
      .catch((e: unknown) => vivo && setErro(e instanceof ApiError ? e : new ApiError('INTERNAL', String(e))))
    return () => {
      vivo = false
    }
  }, [pkg])
  if (erro) return <ErroBloco erro={erro} />
  if (!d) return <Carregando texto={'Consultando ' + pkg + '…'} />
  return (
    <>
      <h4 style={{ margin: '0 0 6px', fontSize: 13 }}>{d.title}</h4>
      <div className="small muted" style={{ marginBottom: 9 }}>
        {String(d.notes || '').slice(0, 420)}
      </div>
      <div className="small faint" style={{ marginBottom: 9 }}>
        {num(d.resource_count)} recursos · modo {d.mode}
      </div>
      <div className="table-wrap scroll-y">
        <table>
          <thead>
            <tr>
              <th>Recurso</th>
              <th>Formato</th>
              <th className="num">Período</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {(d.resources || []).slice(0, 26).map((r: Dado, i: number) => (
              <tr key={(r.url || r.name) + '-' + i}>
                <td>{r.name || '—'}</td>
                <td>
                  <Chip>{r.format || '?'}</Chip>
                </td>
                <td className="num">
                  {r.year || ''}
                  {r.month ? '/' + String(r.month).padStart(2, '0') : ''}
                </td>
                <td>
                  <a href={r.url} target="_blank" rel="noreferrer">
                    abrir
                  </a>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}

function TabelaCurados({ curated }: { curated: Dado[] }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Conjunto</th>
            <th>Papel na solução</th>
            <th>Granularidade</th>
            <th className="num">Tamanho</th>
            <th>Defasagem declarada</th>
            <th>Esquema</th>
          </tr>
        </thead>
        <tbody>
          {curated.map((c, i) => (
            <tr key={(c.key || c.package) + '-' + i}>
              <td>
                <strong>{c.title}</strong>
                <br />
                <span className="mono small faint">{c.package}</span>
              </td>
              <td className="small">{c.role}</td>
              <td>
                <Chip cor="teal">{c.granularity}</Chip>
              </td>
              <td className="num small">{bytes(c.approx_bytes)}</td>
              <td className="small muted">{c.lag_note}</td>
              <td className="small faint">{(c.fields || []).length} campos</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function TabelaIngestao({ reports }: { reports: Dado[] | undefined }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Conjunto</th>
            <th>Recurso</th>
            <th>Modo</th>
            <th className="num">Linhas</th>
            <th className="num">Bytes</th>
            <th className="num">Instante inválido</th>
            <th className="num">Linha curta</th>
            <th className="num">Duplicatas</th>
            <th>Erro</th>
          </tr>
        </thead>
        <tbody>
          {(reports || []).map((r, i) => (
            <tr key={r.dataset + '-' + r.resource + '-' + i}>
              <td>{r.dataset}</td>
              <td className="mono small">{r.resource}</td>
              <td>
                <Chip cor={modeClass(r.mode)}>{r.mode}</Chip>
              </td>
              <td className="num">{num(r.rows)}</td>
              <td className="num">{bytes(r.bytes_read)}</td>
              <td className="num">{num(r.discarded_bad_time)}</td>
              <td className="num">{num(r.discarded_short_line)}</td>
              <td className="num">{num(r.duplicates)}</td>
              <td className="small neg">{r.error || ''}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function TabelaManifesto({ entries }: { entries: Dado[] | undefined }) {
  const rows = (entries || []).slice(0, 40)
  return (
    <div className="table-wrap scroll-y">
      <table>
        <thead>
          <tr>
            <th>Conjunto</th>
            <th>Recurso</th>
            <th className="num">Bytes</th>
            <th>SHA-256</th>
            <th>Extraído</th>
            <th>Nota</th>
          </tr>
        </thead>
        <tbody>
          {rows.length ? (
            rows.map((e, i) => (
              <tr key={(e.file || e.resource) + '-' + i}>
                <td>{e.dataset || '—'}</td>
                <td className="mono small">{e.resource || e.file}</td>
                <td className="num">{bytes(e.bytes)}</td>
                <td className="mono small faint">{String(e.sha256 || '').slice(0, 14)}…</td>
                <td>{when(e.fetched_at)}</td>
                <td className="small muted">{e.note || ''}</td>
              </tr>
            ))
          ) : (
            <tr>
              <td colSpan={6}>cache vazio</td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  )
}
