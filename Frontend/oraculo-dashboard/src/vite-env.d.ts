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

/**
 * Patamares e faixas de curtailment injetados no build por vite.config.ts a partir de
 * Backend/config/processamento.yaml. `unknown` de propósito: quem consome valida o formato
 * em src/content/calendario.ts (um YAML mal editado falha lá, com mensagem, e não no gráfico).
 */
declare const __CALENDARIO__: { patamares: unknown; faixasCurtailment: unknown }
