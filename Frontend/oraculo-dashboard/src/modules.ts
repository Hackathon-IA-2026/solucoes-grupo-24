/**
 * Registro ÚNICO dos módulos do dashboard.
 *
 * A barra lateral e as rotas são geradas a partir desta lista, então a ordem, o nome e o
 * caminho de um módulo não podem divergir entre menu e roteamento (a ordem do array É a
 * ordem do menu). Para criar um módulo novo: uma página em src/pages/ + uma entrada aqui.
 */
import { lazy, type ComponentType } from 'react'
import { GRUPO_CONTRATO, MODULOS_ORACULO } from './oraculo/modulos'
import {
  Activity,
  BookOpen,
  CircleCheckBig,
  LayoutDashboard,
  ListOrdered,
  Map as MapIcon,
  SendToBack,
  TriangleAlert,
  type LucideIcon,
} from 'lucide-react'

/*
 * Cada página é carregada sob demanda (React.lazy): o bundle inicial leva só o layout, e
 * bibliotecas pesadas de uma tela (Recharts, mapa...) só descem quando ela é aberta.
 * A casca (oraculo/Casca.tsx) envolve a página em <Suspense>.
 */
/** Caminho do Detalhe do Alerta: usado no registro E em rotaDetalheAlerta() — uma fonte só. */
const DETALHE_ALERTA_PATH = '/detalhe-alerta'
/** Caminho do Mapa Híbrido: usado no registro E em rotaMapa() — uma fonte só. */
const MAPA_PATH = '/mapa-hibrido'

export interface ModuleDef {
  /** caminho base da rota (também usado no link do menu) */
  path: string
  /** padrão de rota do react-router, quando difere de `path` (ex.: parâmetro opcional) */
  routePattern?: string
  label: string
  description: string
  icon: LucideIcon
  Page: ComponentType
  /** título do grupo no menu lateral (ver ./oraculo/modulos.ts) */
  grupo?: string
  /** id da página da documentação embutida (ajuda F1, src/oraculo/documentacao/): toda tela tem uma */
  ajuda?: string
  /** título da tela na topbar, quando difere do rótulo do menu (títulos do protótipo) */
  titulo?: string
  /** ícone do protótipo (chave de ICONES em oraculo/Casca.tsx); sem ele, usa `icon` */
  icone?: string
}

/** Módulos do dashboard do contrato (types.ts ↔ Backend/src/api), no grupo próprio do menu. */
const MODULOS_CONTRATO: readonly ModuleDef[] = ([
  {
    path: '/visao-geral',
    ajuda: 'visao-geral',
    label: 'Visão Geral',
    description: 'Panorama do SIN: KPIs de carga, risco de curtailment e alertas ativos.',
    icon: LayoutDashboard,
    Page: lazy(() => import('./pages/VisaoGeral')),
  },
  {
    path: MAPA_PATH,
    ajuda: 'mapa-hibrido',
    label: 'Mapa Híbrido',
    description: 'Usinas em risco, excedentes TSO-DSO e densidade de MMGD sobre o mapa do Brasil.',
    icon: MapIcon,
    Page: lazy(() => import('./pages/MapaHibrido')),
  },
  {
    path: '/despacho-preditivo',
    ajuda: 'despacho-preditivo',
    label: 'Despacho Preditivo',
    description: 'Previsão de carga supervisionada (P10/P50/P90) nos horizontes 30 min, 3h e D+1.',
    icon: Activity,
    Page: lazy(() => import('./pages/DespachoPreditivo')),
  },
  {
    path: '/lista-riscos',
    ajuda: 'lista-riscos',
    label: 'Lista de Riscos',
    description: 'Usinas e áreas ordenadas por risco e montante previsto de corte.',
    icon: ListOrdered,
    Page: lazy(() => import('./pages/ListaRiscos')),
  },
  {
    path: DETALHE_ALERTA_PATH,
    ajuda: 'detalhe-alerta',
    // :alertId opcional: a rota abre vazia pelo menu ou já focada num alerta vindo da lista.
    routePattern: `${DETALHE_ALERTA_PATH}/:alertId?`,
    label: 'Detalhe do Alerta',
    description: 'Drill-down de um alerta: razão (ENE/CNF), faixa horária e série associada.',
    icon: TriangleAlert,
    Page: lazy(() => import('./pages/DetalheAlerta')),
  },
  {
    path: '/excedentes-tso-dso',
    ajuda: 'excedentes',
    label: 'Excedentes TSO-DSO',
    description: 'Excedentes da geração distribuída vistos pela distribuidora e pelo ONS.',
    icon: SendToBack,
    Page: lazy(() => import('./pages/ExcedentesTsoDso')),
  },
  {
    path: '/validacao',
    ajuda: 'validacao-contrato',
    label: 'Validação',
    description: 'Métricas fora da amostra, com split cronológico, contra os baselines.',
    icon: CircleCheckBig,
    Page: lazy(() => import('./pages/Validacao')),
  },
  {
    path: '/metodologia',
    ajuda: 'metodologia',
    label: 'Metodologia',
    description: 'Fontes de dados, modelos e premissas da solução.',
    icon: BookOpen,
    Page: lazy(() => import('./pages/Metodologia')),
  },
] satisfies ModuleDef[]).map((m) => ({ ...m, grupo: GRUPO_CONTRATO }))

/**
 * Ordem do menu: primeiro as telas do protótipo O.R.A.C.U.L.O. (prioridade da consolidação,
 * grupos Operação → Confiança, com as duas soluções de visão computacional), depois o
 * dashboard do contrato. "/" abre o primeiro módulo (Despacho preditivo do protótipo).
 */
export const MODULES: readonly ModuleDef[] = [...MODULOS_ORACULO, ...MODULOS_CONTRATO]

/** Módulo da rota corrente (inclui subrotas, como /detalhe-alerta/:id). Usado pela casca e pela ajuda F1. */
export function moduloDaRota(pathname: string): ModuleDef | undefined {
  return MODULES.find((m) => pathname === m.path || pathname.startsWith(m.path + '/'))
}

/** URL do Detalhe do Alerta de um risco (Lista de Riscos e demais links usam só isto). */
export function rotaDetalheAlerta(riscoUsinaId: string): string {
  return `${DETALHE_ALERTA_PATH}/${encodeURIComponent(riscoUsinaId)}`
}

/**
 * Seleção do Mapa Híbrido na URL (`/mapa-hibrido?sel=risco:<id>`): o link "ver no mapa" das
 * outras telas abre o mapa já com o item selecionado e o zoom nele, e a seleção fica
 * compartilhável. Formato definido SÓ aqui (quem monta e quem lê usam estas duas funções).
 */
export type SelecaoMapa = { tipo: 'risco' | 'excedente'; id: string }
export const PARAM_SELECAO_MAPA = 'sel'

export function rotaMapa(sel?: SelecaoMapa): string {
  const base = MAPA_PATH
  return sel ? `${base}?${PARAM_SELECAO_MAPA}=${encodeURIComponent(`${sel.tipo}:${sel.id}`)}` : base
}

export function lerSelecaoMapa(valor: string | null): SelecaoMapa | null {
  if (!valor) return null
  const i = valor.indexOf(':')
  const tipo = valor.slice(0, i)
  const id = valor.slice(i + 1)
  return (tipo === 'risco' || tipo === 'excedente') && id ? { tipo, id } : null
}

/** Id estável de um excedente (o contrato não tem id): área + distribuidora. */
export const idExcedente = (e: { areaConcessao: string; distribuidora: string }) => `${e.areaConcessao}|${e.distribuidora}`
