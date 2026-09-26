/**
 * Contrato de dados do dashboard: schemas Zod + tipos TypeScript inferidos deles.
 *
 * Decisão: o schema é a fonte ÚNICA; o tipo sai de `z.infer`. Assim tipo e validação não
 * têm como divergir. Todo dado que entra na aplicação (JSON mockado hoje, API amanhã) passa
 * por `schema.parse` em dataSource.ts — um campo faltando, um enum errado ou um número
 * vindo como texto quebra na fronteira, com mensagem clara, e não no meio de um gráfico.
 *
 * Convenções:
 * - `mock`: obrigatório em todo registro de nível superior. true = dado ilustrativo
 *   (registrado em docs/real_vs_mock.md). Telas podem exibir um selo "MOCK" a partir dele.
 * - Timestamps: ISO-8601 em UTC (sufixo Z). A conversão para horário de Brasília é só
 *   na exibição.
 * - Potências em MW; percentuais em 0–100 (sufixo Pct); razões/frações em 0–1.
 */
import { z } from 'zod'

// ---------------------------------------------------------------------------
// Blocos compartilhados
// ---------------------------------------------------------------------------

/** Marca de procedência exigida em todo registro de nível superior. */
const registro = { mock: z.boolean() }

const timestampUtc = z.iso.datetime({ offset: false })
const mw = z.number().finite()
const pct = z.number().min(0).max(100)

/**
 * Posição geográfica (WGS84). Limitada a uma caixa em torno do Brasil: coordenada trocada
 * (lat↔lon) ou com sinal errado cai fora e é recusada — não vira um ponto no oceano.
 */
const posicao = {
  lat: z.number().min(-34).max(6),
  lon: z.number().min(-74).max(-28),
}

/** Horizontes de previsão do projeto (CLAUDE.md: 30 min, 3h e D+1). */
export const HorizonteSchema = z.enum(['30min', '3h', 'D+1'])
export type Horizonte = z.infer<typeof HorizonteSchema>

/**
 * Severidade dos dados. Mesmos identificadores de RiskLevel em src/theme/severity.ts,
 * então qualquer valor daqui vai direto para <SeverityBadge level={...} />.
 */
export const SeveridadeSchema = z.enum(['low', 'medium', 'high', 'critical'])
export type Severidade = z.infer<typeof SeveridadeSchema>

/**
 * Razões de constrained-off do dicionário do ONS: REL (indisponibilidade externa),
 * CNF (confiabilidade elétrica), ENE (razão energética).
 */
export const RazaoSchema = z.enum(['REL', 'CNF', 'ENE'])
export type Razao = z.infer<typeof RazaoSchema>

export const FonteGeracaoSchema = z.enum(['Eólica', 'Solar FV'])
export type FonteGeracao = z.infer<typeof FonteGeracaoSchema>

// ---------------------------------------------------------------------------
// 1. CargaSnapshot — retrato instantâneo da carga do SIN
// ---------------------------------------------------------------------------

export const CargaSnapshotSchema = z
  .object({
    ...registro,
    timestampUtc,
    cargaGlobalMw: mw,
    mmgdEstimadaMw: mw,
    cargaSupervisionadaMw: mw,
    percentualMmgdNaGeracao: pct,
    /** geração MMGD atual ÷ capacidade instalada de MMGD (fração 0–1) */
    mmgdSobreCapacidadeInstalada: z.number().min(0).max(1),
  })
  // Regra do projeto: carga supervisionada = carga global − MMGD estimada.
  // Validado aqui para que um snapshot incoerente nunca chegue à tela.
  .refine((c) => Math.abs(c.cargaGlobalMw - c.mmgdEstimadaMw - c.cargaSupervisionadaMw) <= 1, {
    message: 'cargaSupervisionadaMw deve ser cargaGlobalMw − mmgdEstimadaMw (tolerância 1 MW)',
  })
export type CargaSnapshot = z.infer<typeof CargaSnapshotSchema>

// ---------------------------------------------------------------------------
// 2. PrevisaoCurva — curva probabilística de carga supervisionada por horizonte
// ---------------------------------------------------------------------------

export const PontoPrevisaoSchema = z
  .object({ timestamp: timestampUtc, p10: mw, p50: mw, p90: mw })
  // Quantis cruzados (p10 > p50) são um bug clássico de modelos quantílicos: barrado aqui.
  .refine((p) => p.p10 <= p.p50 && p.p50 <= p.p90, { message: 'quantis fora de ordem (p10 ≤ p50 ≤ p90)' })
export type PontoPrevisao = z.infer<typeof PontoPrevisaoSchema>

export const FatoresClimaticosSchema = z.object({
  /** W/m² */
  radiacaoSolar: z.number().min(0),
  ventoMs: z.number().min(0),
  temperaturaC: z.number(),
  coberturaNuvensPct: pct,
})
export type FatoresClimaticos = z.infer<typeof FatoresClimaticosSchema>

export const PrevisaoCurvaSchema = z.object({
  ...registro,
  horizonte: HorizonteSchema,
  pontos: z.array(PontoPrevisaoSchema).min(1),
  /** maior variação de carga projetada dentro da janela (MW) */
  rampaProjetadaMw: mw,
  janelaRampaHoras: z.number().positive(),
  fatoresClimaticos: FatoresClimaticosSchema,
})
export type PrevisaoCurva = z.infer<typeof PrevisaoCurvaSchema>

// ---------------------------------------------------------------------------
// 3. RiscoUsina — risco de curtailment por usina/conjunto
// ---------------------------------------------------------------------------

export const RiscoUsinaSchema = z.object({
  ...registro,
  id: z.string().min(1),
  nome: z.string().min(1),
  /** UF da usina (acréscimo ao contrato pedido: o protótipo exibe "CE", "PI"... ao lado do nome) */
  uf: z.string().length(2),
  /** posição da usina/subestação no Mapa Híbrido */
  ...posicao,
  distribuidora: z.string().min(1),
  fonte: FonteGeracaoSchema,
  razao: RazaoSchema,
  probabilidadePct: pct,
  montanteMw: mw,
  horizonte: HorizonteSchema,
  severidade: SeveridadeSchema,
  acaoRecomendada: z.string().min(1),
})
export type RiscoUsina = z.infer<typeof RiscoUsinaSchema>

// ---------------------------------------------------------------------------
// 4. AlertaDetalhado — drill-down de um RiscoUsina
// ---------------------------------------------------------------------------

export const ShapValueSchema = z.object({
  variavel: z.string().min(1),
  /** contribuição absoluta normalizada (0–1) */
  peso: z.number().min(0).max(1),
  direcao: z.enum(['aumenta', 'reduz']),
})
export type ShapValue = z.infer<typeof ShapValueSchema>

export const AlertaDetalhadoSchema = z.object({
  ...registro,
  riscoUsinaId: z.string().min(1),
  probabilidadePct: pct,
  montanteMw: mw,
  horarioPrevisto: timestampUtc,
  motivos: z
    .array(z.object({ razao: RazaoSchema, pesoPct: pct }))
    .min(1)
    // Os pesos repartem o alerta entre as razões: precisam fechar 100%.
    .refine((ms) => Math.abs(ms.reduce((s, m) => s + m.pesoPct, 0) - 100) <= 0.5, {
      message: 'a soma de motivos[].pesoPct deve ser 100',
    }),
  fonteDataset: z.string().min(1),
  janelaPrevisao: HorizonteSchema,
  atualizadoHaMin: z.number().int().min(0),
  /** instante em que a previsão foi gerada (rastreabilidade) */
  atualizadoEm: timestampUtc,
  /** como as variáveis foram explicadas (ex.: ExplicadorPrecomputado = stub, ExplicadorShap) */
  metodoExplicacao: z.string().min(1),
  shapValues: z.array(ShapValueSchema),
  /**
   * Texto do alerta pronto, gerado no Backend por gerar_texto_alerta()
   * (Backend/pipeline/explicabilidade.py). O dashboard só exibe: o template tem UMA
   * implementação, então tela e Backend nunca escrevem o alerta de jeitos diferentes.
   */
  textoAlerta: z.string().min(1),
})
export type AlertaDetalhado = z.infer<typeof AlertaDetalhadoSchema>

// ---------------------------------------------------------------------------
// 5. ExcedenteTsoDso — excedente de geração por área de concessão
// ---------------------------------------------------------------------------

/**
 * Horizonte do excedente: inclui "1h", que aparece no protótipo mas não é um horizonte
 * dos modelos (30min/3h/D+1). Mantido separado de HorizonteSchema para não contaminá-lo.
 */
export const HorizonteExcedenteSchema = z.enum(['1h', '3h', 'D+1'])
export type HorizonteExcedente = z.infer<typeof HorizonteExcedenteSchema>

export const ExcedenteTsoDsoSchema = z.object({
  ...registro,
  areaConcessao: z.string().min(1),
  distribuidora: z.string().min(1),
  /** ponto representativo da área (fronteira TSO-DSO) no Mapa Híbrido */
  ...posicao,
  fonte: z.string().min(1), // texto livre: pode ser misto ("Eólica/Solar")
  excedenteMw: mw,
  /**
   * Decisão: prioridade usa a MESMA escala de SeveridadeSchema (minúsculas) em vez de
   * "High/Medium/Low" do protótipo, para reaproveitar SeverityBadge sem tradução.
   */
  prioridade: SeveridadeSchema,
  horizonte: HorizonteExcedenteSchema,
  acaoRecomendada: z.string().min(1),
})
export type ExcedenteTsoDso = z.infer<typeof ExcedenteTsoDsoSchema>

// ---------------------------------------------------------------------------
// 6. MetricasValidacao — desempenho fora da amostra e saúde das fontes
// ---------------------------------------------------------------------------

/** Metadados do modelo avaliado (placeholder enquanto não há modelo treinado). */
export const ModeloInfoSchema = z.object({
  nome: z.string().min(1),
  versao: z.string().min(1),
  dataTreino: z.iso.date(),
  /** períodos do split CRONOLÓGICO (regra do projeto: nunca aleatório) */
  periodoTreino: z.object({ inicio: z.iso.date(), fim: z.iso.date() }),
  periodoTeste: z.object({ inicio: z.iso.date(), fim: z.iso.date() }),
})
export type ModeloInfo = z.infer<typeof ModeloInfoSchema>

export const MetricasValidacaoSchema = z.object({
  ...registro,
  erroMedioAbsolutoMw: mw,
  rmseMw: mw,
  mapePct: z.number().min(0),
  /** 1 − erro_modelo/erro_climatologia: > 0 = melhor que a climatologia */
  skillVsClimatologia: z.number().max(1),
  /** nome do baseline comparado no histórico (ex.: "Climatologia") */
  baselineNome: z.string().min(1),
  historicoErro30d: z.array(
    z.object({ data: z.iso.date(), mae: mw, rmse: mw, maeBaseline: mw, rmseBaseline: mw }),
  ),
  modelo: ModeloInfoSchema
    // teste depois do treino: split cronológico sem sobreposição (vazamento temporal)
    .refine((m) => m.periodoTreino.fim < m.periodoTeste.inicio, {
      message: 'periodoTeste deve começar depois do fim do periodoTreino (split cronológico)',
    }),
  statusFontes: z.array(
    z.object({ fonte: z.string().min(1), online: z.boolean(), ultimaSincronizacao: timestampUtc }),
  ),
})
export type MetricasValidacao = z.infer<typeof MetricasValidacaoSchema>

// ---------------------------------------------------------------------------
// 7. DensidadeMmgd — camada de calor do Mapa Híbrido
// ---------------------------------------------------------------------------

export const DensidadeMmgdSchema = z.object({
  ...registro,
  descricao: z.string().min(1),
  /** [lat, lon, intensidade 0–1] — formato direto do leaflet.heat */
  pontos: z.array(z.tuple([posicao.lat, posicao.lon, z.number().min(0).max(1)])).min(1),
})
export type DensidadeMmgd = z.infer<typeof DensidadeMmgdSchema>

// ---------------------------------------------------------------------------
// 8. AreasInfluencia — polígonos das áreas de influência das subestações (Mapa Híbrido)
// ---------------------------------------------------------------------------
// GeoJSON (RFC 7946) comum, que o Leaflet desenha direto; `mock` é membro extra do objeto.
// Espelha AreasInfluencia em Backend/src/contrato/modelos.py.

/** Par [lon, lat] do GeoJSON (ordem INVERSA de lat/lon do resto do contrato), dentro do Brasil. */
const lonLat = z.tuple([posicao.lon, posicao.lat])
const anel = z.array(lonLat).min(4) // anel fechado: pelo menos 4 pontos

export const GeometriaAreaSchema = z.discriminatedUnion('type', [
  z.object({ type: z.literal('Polygon'), coordinates: z.array(anel).min(1) }),
  z.object({ type: z.literal('MultiPolygon'), coordinates: z.array(z.array(anel).min(1)).min(1) }),
])

export const PropriedadesAreaSchema = z.object({
  /** "<distribuidora>:<código da subestação>" */
  areaId: z.string().min(1),
  nome: z.string().min(1),
  distribuidora: z.string().min(1),
  /** plena, satélite, transformadora pura, transporte/manobra */
  classificacao: z.string().min(1),
  /** subestação que alimenta esta (satélites) */
  areaMae: z.string().nullable(),
  latSub: posicao.lat,
  lonSub: posicao.lon,
  areaKm2: z.number().min(0),
  /** MMGD cadastrada na ANEEL e localizada pela BDGD (já com o fator do satélite, se houver) */
  capacidadeMmgdMw: mw.min(0),
  /** parte da capacidade que ainda não está na BDGD (lag de sistema) */
  capacidadeLagMw: mw.min(0),
  /** fator de correção por imagem de satélite; null = sem correção */
  fatorCorrecao: z.number().positive().nullable(),
  /** pico de excedente previsto em 24 h; null = não é subestação de fronteira */
  excedenteMw: mw.min(0).nullable(),
  horizonteExcedente: HorizonteExcedenteSchema.nullable(),
})
export type PropriedadesArea = z.infer<typeof PropriedadesAreaSchema>

export const AreasInfluenciaSchema = z.object({
  ...registro,
  type: z.literal('FeatureCollection'),
  descricao: z.string().min(1),
  features: z
    .array(z.object({ type: z.literal('Feature'), geometry: GeometriaAreaSchema, properties: PropriedadesAreaSchema }))
    .min(1)
    .refine((fs) => new Set(fs.map((f) => f.properties.areaId)).size === fs.length, {
      message: 'areaId repetido nas áreas de influência',
    }),
})
export type AreasInfluencia = z.infer<typeof AreasInfluenciaSchema>

// ---------------------------------------------------------------------------
// Fora do contrato: estado da API (rota /saude)
// ---------------------------------------------------------------------------
// Não é um dos 6 recursos publicados (não entra em docs/schema_contrato.json): descreve QUAL
// execução do run_heavywork.py a API está servindo. Espelha `Saude` em Backend/src/api/app.py.

export const SaudeApiSchema = z.object({
  status: z.literal('ok'),
  execucaoId: z.number().int(),
  /** quando o run_heavywork.py publicou */
  geradoEm: timestampUtc,
  /** o "agora" do replay: instante a que os dados se referem */
  instanteReferencia: timestampUtc,
  origem: z.string().min(1),
})
export type SaudeApi = z.infer<typeof SaudeApiSchema>
