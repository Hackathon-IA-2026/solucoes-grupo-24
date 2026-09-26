/**
 * Registro ÚNICO dos módulos do dashboard.
 *
 * A barra lateral e as rotas são geradas a partir desta lista, então a ordem, o nome e o
 * caminho de um módulo não podem divergir entre menu e roteamento (a ordem do array É a
 * ordem do menu). Para criar um módulo novo: uma página em src/pages/ + uma entrada aqui.
 */
import { lazy, type ComponentType } from 'react'
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
 * <ModuleFrame> envolve a página em <Suspense>.
 */
/** Caminho do Detalhe do Alerta: usado no registro E em rotaDetalheAlerta() — uma fonte só. */
const DETALHE_ALERTA_PATH = '/detalhe-alerta'

export interface ModuleDef {
  /** caminho base da rota (também usado no link do menu) */
  path: string
  /** padrão de rota do react-router, quando difere de `path` (ex.: parâmetro opcional) */
  routePattern?: string
  label: string
  description: string
  icon: LucideIcon
  Page: ComponentType
}

export const MODULES: readonly ModuleDef[] = [
  {
    path: '/visao-geral',
    label: 'Visão Geral',
    description: 'Panorama do SIN: KPIs de carga, risco de curtailment e alertas ativos.',
    icon: LayoutDashboard,
    Page: lazy(() => import('./pages/VisaoGeral')),
  },
  {
    path: '/mapa-hibrido',
    label: 'Mapa Híbrido',
    description: 'Usinas em risco, excedentes TSO-DSO e densidade de MMGD sobre o mapa do Brasil.',
    icon: MapIcon,
    Page: lazy(() => import('./pages/MapaHibrido')),
  },
  {
    path: '/despacho-preditivo',
    label: 'Despacho Preditivo',
    description: 'Previsão de carga supervisionada (P10/P50/P90) nos horizontes 30 min, 3h e D+1.',
    icon: Activity,
    Page: lazy(() => import('./pages/DespachoPreditivo')),
  },
  {
    path: '/lista-riscos',
    label: 'Lista de Riscos',
    description: 'Usinas e áreas ordenadas por risco e montante previsto de corte.',
    icon: ListOrdered,
    Page: lazy(() => import('./pages/ListaRiscos')),
  },
  {
    path: DETALHE_ALERTA_PATH,
    // :alertId opcional: a rota abre vazia pelo menu ou já focada num alerta vindo da lista.
    routePattern: `${DETALHE_ALERTA_PATH}/:alertId?`,
    label: 'Detalhe do Alerta',
    description: 'Drill-down de um alerta: razão (ENE/CNF), faixa horária e série associada.',
    icon: TriangleAlert,
    Page: lazy(() => import('./pages/DetalheAlerta')),
  },
  {
    path: '/excedentes-tso-dso',
    label: 'Excedentes TSO-DSO',
    description: 'Excedentes da geração distribuída vistos pela distribuidora e pelo ONS.',
    icon: SendToBack,
    Page: lazy(() => import('./pages/ExcedentesTsoDso')),
  },
  {
    path: '/validacao',
    label: 'Validação',
    description: 'Métricas fora da amostra, com split cronológico, contra os baselines.',
    icon: CircleCheckBig,
    Page: lazy(() => import('./pages/Validacao')),
  },
  {
    path: '/metodologia',
    label: 'Metodologia',
    description: 'Fontes de dados, modelos e premissas da solução.',
    icon: BookOpen,
    Page: lazy(() => import('./pages/Metodologia')),
  },
]

/** URL do Detalhe do Alerta de um risco (Lista de Riscos e demais links usam só isto). */
export function rotaDetalheAlerta(riscoUsinaId: string): string {
  return `${DETALHE_ALERTA_PATH}/${encodeURIComponent(riscoUsinaId)}`
}
