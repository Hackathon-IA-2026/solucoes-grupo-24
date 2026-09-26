import { readFileSync } from 'node:fs'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'
import { parse } from 'yaml'

/**
 * Onde o Backend (FastAPI, Backend/main.py) escuta. Decisão: LIDO de Backend/config/api.yaml,
 * a mesma config que o `python main.py` usa — host, porta e prefixo existem num lugar só.
 * Se alguém mudar a porta da API, o proxy do dashboard acompanha sem editar nada aqui
 * (a classe de bug "proxy apontando para a porta antiga" deixa de existir).
 */
interface ApiConfig {
  host: string
  porta: number
  prefixo: string
}
const api = parse(readFileSync(new URL('../../Backend/config/api.yaml', import.meta.url), 'utf-8')) as ApiConfig
const alvoApi = `http://${api.host}:${api.porta}`

// Proxy do prefixo da API: o navegador chama /api/... na MESMA origem do dashboard e o Vite
// repassa para o FastAPI. Sem CORS no desenvolvimento e com a mesma URL relativa que o
// Backend usa quando ele mesmo serve o build (dist/) em produção.
const proxy = { [api.prefixo]: { target: alvoApi, changeOrigin: true } }

// https://vite.dev/config/
// Tailwind v4 entra como plugin do Vite; as tokens ficam em src/index.css (@theme).
export default defineConfig(({ mode }) => ({
  plugins: [react(), tailwindcss()],
  // `vite --mode mock` (npm run dev:mock / build:mock) força o modo mock. Decisão: aqui, e não
  // num .env.mock — arquivos .env.* são ignorados pelo git (podem ter segredos) e o script
  // funciona igual no Windows e no Linux, sem sintaxe de variável de ambiente no shell.
  define: mode === 'mock' ? { 'import.meta.env.VITE_DATA_SOURCE': JSON.stringify('mock') } : {},
  server: { proxy },
  preview: { proxy },
  test: {
    // Os testes do contrato leem os JSONs mockados: o modo mock é explícito aqui, e não
    // herdado de um .env da máquina. Fora dos testes o padrão é a API (dataSource.ts).
    env: { VITE_DATA_SOURCE: 'mock' },
  },
}))
