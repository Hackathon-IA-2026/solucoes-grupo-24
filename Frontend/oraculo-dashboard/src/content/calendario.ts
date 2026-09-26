/**
 * Patamares da curva de carga e faixas horárias de curtailment, vindos de
 * Backend/config/processamento.yaml (injetados no build por vite.config.ts como __CALENDARIO__).
 *
 * Decisão: o dashboard NÃO escreve esses horários à mão. O gráfico do Despacho Preditivo e a
 * Metodologia leem daqui, e daqui só sai o que o Backend usa no calendário e no backtest —
 * a faixa desenhada na tela nunca discorda da métrica por patamar.
 *
 * O formato é validado com Zod na carga do módulo: um YAML mal editado (ex.: [22, 19]) derruba
 * o build/teste com mensagem clara, em vez de desenhar uma faixa vazia em silêncio.
 */
import { z } from 'zod'

/** Intervalo semiaberto [inicio, fim) em horas locais (mesma convenção do Backend). */
const Intervalo = z
  .tuple([z.number().int().min(0).max(24), z.number().int().min(0).max(24)])
  .refine(([ini, fim]) => ini < fim, { message: 'intervalo de horas precisa ter inicio < fim' })

const CalendarioSchema = z.object({
  patamares: z.object({
    ponta_noturna: Intervalo,
    minima_diurna: Intervalo,
    rampa_vespertina: Intervalo,
  }),
  faixasCurtailment: z.record(z.string(), z.array(Intervalo).min(1)),
})

const calendario = CalendarioSchema.parse(__CALENDARIO__)

export type ChavePatamar = keyof typeof calendario.patamares

export interface Patamar {
  chave: ChavePatamar
  nome: string
  horas: readonly [number, number]
  /**
   * Por que o patamar importa para a operação (planejamento v2, "assimetria do erro"): o ONS
   * declarou que errar para baixo na ponta e para cima na mínima custam muito mais.
   */
  errarPior: string
}

/**
 * Patamares na ordem do dia. Record exaustivo sobre ChavePatamar: se o YAML ganhar um patamar
 * novo, o Zod acima o descarta até alguém descrevê-lo aqui (nunca aparece sem nome na tela).
 */
const DESCRICAO: Record<ChavePatamar, Omit<Patamar, 'chave' | 'horas'>> = {
  minima_diurna: {
    nome: 'Mínima diurna',
    errarPior: 'superestimar: a carga real fica abaixo do previsto e sobra geração (risco de corte por razão energética)',
  },
  rampa_vespertina: {
    nome: 'Rampa vespertina',
    errarPior: 'errar o instante e a inclinação da subida: exige recursos flexíveis em poucas horas',
  },
  ponta_noturna: {
    nome: 'Ponta noturna',
    errarPior: 'subestimar: falta recurso na ponta (acionamento emergencial ou risco de não atendimento)',
  },
}

export const PATAMARES: readonly Patamar[] = (['minima_diurna', 'rampa_vespertina', 'ponta_noturna'] as const).map(
  (chave) => ({ chave, horas: calendario.patamares[chave], ...DESCRICAO[chave] }),
)

/** Faixas horárias de curtailment (rótulo do Backend -> intervalos), na ordem do YAML. */
export const FAIXAS_CURTAILMENT: readonly { rotulo: string; intervalos: readonly (readonly [number, number])[] }[] =
  Object.entries(calendario.faixasCurtailment).map(([rotulo, intervalos]) => ({ rotulo, intervalos }))

/** "9–16h" a partir de [9, 16]. */
export const formatIntervalo = ([ini, fim]: readonly [number, number]) => `${ini}–${fim}h`
