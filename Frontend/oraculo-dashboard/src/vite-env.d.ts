/// <reference types="vite/client" />

/** Variáveis de ambiente do dashboard (arquivo .env.local, nunca versionado). */
interface ImportMetaEnv {
  /** "api" (padrão) busca no Backend; "mock" lê src/data/mock/*.json (npm run dev:mock) */
  readonly VITE_DATA_SOURCE?: 'mock' | 'api'
  /** URL base da API no modo api (padrão: /api, repassado ao Backend pelo proxy do Vite) */
  readonly VITE_API_BASE_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
