/**
 * Gera os mocks de SÉRIES (src/data/mock/previsao.json e validacao.json).
 *
 * Uso: npm run mocks:series
 *
 * Por que um script: curvas de 48 pontos e 30 dias de histórico escritos à mão ficam
 * inconsistentes (quantis cruzados, datas puladas). Aqui elas saem de fórmulas
 * determinísticas (sem Math.random), então rodar de novo produz exatamente o mesmo arquivo.
 * Os seeds pontuais (carga, riscos, alertas, excedentes) ficam direto nos JSONs.
 *
 * TODOS os valores são ILUSTRATIVOS (mock: true) — ver docs/real_vs_mock.md.
 */
import { writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const DESTINO = join(dirname(fileURLToPath(import.meta.url)), '..', 'src', 'data', 'mock')
const MEIA_HORA_MS = 30 * 60 * 1000
const BRT_OFFSET_H = -3 // só para desenhar o perfil diário pelo horário local

/**
 * Perfil diário ilustrativo da carga SUPERVISIONADA (MW) em função da hora local:
 * "curva do pato" — vale ao meio-dia (MMGD solar abate a carga vista pelo ONS) e
 * rampa forte até a ponta noturna (19–22h).
 */
/**
 * Gaussiana na hora do dia com distância CIRCULAR (23h e 1h estão a 2h, não a 22h).
 * Sem isso a curva dava um degrau à meia-noite (cauda da ponta das 20h cortada).
 */
function sino(hora, centro, largura) {
  const d = Math.min(Math.abs(hora - centro), 24 - Math.abs(hora - centro))
  return Math.exp(-(d ** 2) / (2 * largura ** 2))
}

function perfilSupervisionada(horaLocal) {
  const noturno = 38000
  const vale = -9500 * sino(horaLocal, 12.5, 2.2)
  const ponta = 17000 * sino(horaLocal, 20.5, 1.6)
  const manha = 4000 * sino(horaLocal, 8, 1.5)
  const madrugada = -3000 * sino(horaLocal, 4, 1.5)
  return noturno + vale + ponta + manha + madrugada
}

/** Meia-largura relativa da banda P10–P90: cresce com o horizonte. */
const INCERTEZA = { '30min': 0.012, '3h': 0.03, 'D+1': 0.065 }

function curva(horizonte, inicioUtc, fatoresClimaticos) {
  const pontos = []
  for (let i = 0; i < 48; i++) {
    const t = new Date(Date.parse(inicioUtc) + i * MEIA_HORA_MS)
    const horaLocal = (t.getUTCHours() + t.getUTCMinutes() / 60 + BRT_OFFSET_H + 24) % 24
    const p50 = perfilSupervisionada(horaLocal)
    // incerteza também cresce ao longo da própria curva (passos mais distantes)
    const meia = p50 * INCERTEZA[horizonte] * (1 + i / 96)
    pontos.push({
      timestamp: t.toISOString().replace('.000Z', 'Z'),
      p10: Math.round(p50 - meia * 1.1), // leve assimetria: risco de subestimar a ponta
      p50: Math.round(p50),
      p90: Math.round(p50 + meia * 1.3),
    })
  }
  // rampa = maior subida do P50 em qualquer janela de 3h (6 passos) da curva
  let rampa = 0
  for (let i = 0; i + 6 < pontos.length; i++) rampa = Math.max(rampa, pontos[i + 6].p50 - pontos[i].p50)
  return { mock: true, horizonte, pontos, rampaProjetadaMw: rampa, janelaRampaHoras: 3, fatoresClimaticos }
}

const previsao = [
  curva('30min', '2026-09-25T18:00:00Z', { radiacaoSolar: 612, ventoMs: 8.4, temperaturaC: 29.1, coberturaNuvensPct: 18 }),
  curva('3h', '2026-09-25T18:00:00Z', { radiacaoSolar: 540, ventoMs: 9.1, temperaturaC: 28.4, coberturaNuvensPct: 22 }),
  curva('D+1', '2026-09-26T03:00:00Z', { radiacaoSolar: 705, ventoMs: 10.2, temperaturaC: 31.0, coberturaNuvensPct: 12 }),
]

// Histórico de erro: 30 dias terminando em 2026-09-24, com ondulação semanal suave.
// Baseline (climatologia) ~60% pior, com fase semanal própria para as curvas não serem cópias.
const historicoErro30d = Array.from({ length: 30 }, (_, i) => {
  const d = new Date(Date.UTC(2026, 7, 26) + i * 86400000)
  const mae = 690 + 120 * Math.sin((2 * Math.PI * i) / 7) + 4 * (i % 5)
  const maeBase = 1110 + 160 * Math.sin((2 * Math.PI * (i + 2)) / 7) + 6 * (i % 4)
  return {
    data: d.toISOString().slice(0, 10),
    mae: Math.round(mae),
    rmse: Math.round(mae * 1.32),
    maeBaseline: Math.round(maeBase),
    rmseBaseline: Math.round(maeBase * 1.36),
  }
})
const media = (k) => Math.round(historicoErro30d.reduce((s, h) => s + h[k], 0) / historicoErro30d.length)
// skill DERIVADO do histórico (não chutado): 1 − MAE_modelo / MAE_baseline no período
const skill = Math.round((1 - media('mae') / media('maeBaseline')) * 100) / 100

const validacao = {
  mock: true,
  erroMedioAbsolutoMw: media('mae'),
  rmseMw: media('rmse'),
  mapePct: 1.9,
  skillVsClimatologia: skill,
  baselineNome: 'Climatologia',
  historicoErro30d,
  // Placeholder: nenhum modelo foi treinado ainda (mock). Datas coerentes com split cronológico.
  modelo: {
    nome: 'TFT — carga supervisionada',
    versao: '0.0.0-placeholder',
    dataTreino: '2026-09-20',
    periodoTreino: { inicio: '2021-10-01', fim: '2025-12-31' },
    periodoTeste: { inicio: '2026-01-01', fim: '2026-09-24' },
  },
  statusFontes: [
    { fonte: 'ONS — Dados Abertos (constrained-off)', online: true, ultimaSincronizacao: '2026-09-25T17:00:00Z' },
    { fonte: 'ONS — API de Carga Verificada', online: true, ultimaSincronizacao: '2026-09-25T17:30:00Z' },
    { fonte: 'ERA5 (Copernicus CDS)', online: true, ultimaSincronizacao: '2026-09-25T12:00:00Z' },
    { fonte: 'BDGD (ANEEL)', online: true, ultimaSincronizacao: '2026-09-20T09:00:00Z' },
    { fonte: 'Imagens de satélite', online: false, ultimaSincronizacao: '2026-09-24T21:00:00Z' },
  ],
}

// Densidade de MMGD SINTÉTICA para o heatmap do Mapa Híbrido: nuvens de pontos em torno de
// capitais/polos com muita geração distribuída. Pesos ilustrativos (não medidos).
const POLOS = [
  ['São Paulo', -23.55, -46.63, 1.0], ['Belo Horizonte', -19.92, -43.94, 0.75], ['Porto Alegre', -30.03, -51.23, 0.6],
  ['Curitiba', -25.43, -49.27, 0.6], ['Rio de Janeiro', -22.91, -43.2, 0.6], ['Goiânia', -16.69, -49.26, 0.55],
  ['Florianópolis', -27.6, -48.55, 0.5], ['Cuiabá', -15.6, -56.1, 0.45], ['Brasília', -15.79, -47.88, 0.45],
  ['Fortaleza', -3.73, -38.52, 0.4], ['Salvador', -12.97, -38.5, 0.4], ['Campo Grande', -20.47, -54.62, 0.35],
  ['Recife', -8.05, -34.9, 0.35], ['Uberlândia', -18.92, -48.28, 0.4], ['Ribeirão Preto', -21.18, -47.81, 0.45],
]
const pontosMmgd = []
for (const [, lat, lon, peso] of POLOS) {
  // espiral determinística (ângulo áureo): pontos espalhados sem Math.random
  for (let k = 0; k < 36; k++) {
    const raio = 1.6 * Math.sqrt(k / 36)
    const ang = k * 2.39996
    const intensidade = peso * Math.exp(-(raio ** 2) / 1.2)
    pontosMmgd.push([
      Math.round((lat + raio * Math.sin(ang)) * 1e3) / 1e3,
      Math.round((lon + raio * Math.cos(ang)) * 1e3) / 1e3,
      Math.round(intensidade * 1e3) / 1e3,
    ])
  }
}
const mmgdDensidade = {
  mock: true,
  descricao: 'Densidade SINTÉTICA de MMGD (ilustrativa) — substituir pela capacidade por mancha (BDGD + satélite)',
  pontos: pontosMmgd,
}

for (const [nome, dado] of [
  ['previsao.json', previsao],
  ['validacao.json', validacao],
  ['mmgd_densidade.json', mmgdDensidade],
]) {
  writeFileSync(join(DESTINO, nome), JSON.stringify(dado, null, 2) + '\n')
  console.log(`gerado ${nome}`)
}
