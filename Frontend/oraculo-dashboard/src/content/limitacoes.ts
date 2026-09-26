/**
 * Limitações DECLARADAS do projeto (texto fixo, não é dado). Fonte única: a tela Validação
 * exibe LIMITACOES (limites dos dados) e a Metodologia exibe as duas listas, sem duplicar texto.
 */
export interface Limitacao {
  titulo: string
  detalhe: string
}

export const LIMITACOES: readonly Limitacao[] = [
  {
    titulo: 'BDGD anual e heterogênea',
    detalhe:
      'A base da distribuidora é publicada uma vez por ano e o preenchimento varia entre distribuidoras; a capacidade de MMGD por mancha fica defasada entre publicações.',
  },
  {
    titulo: 'Satélite periódico, não tempo real',
    detalhe:
      'As imagens corrigem a capacidade instalada por revisita periódica; não observam a geração instante a instante.',
  },
  {
    titulo: 'ERA5 é reanálise, não previsão',
    detalhe:
      'Serve para treinar e avaliar com o clima observado; em operação, as variáveis climáticas precisam vir de um modelo de previsão meteorológica.',
  },
]

/**
 * Limites do ESCOPO da solução (o que ela não faz), declarados no planejamento v2 (seção 8) e
 * no pitch (slides 6 e 7). Declarar limite é critério de avaliação do Caderno de Desafios.
 */
export const LIMITES_SOLUCAO: readonly Limitacao[] = [
  {
    titulo: 'Sem modelo elétrico da rede',
    detalhe:
      'Não executa fluxo de potência nem estudos de estabilidade: entrega insumos (perfis e previsões) para os modelos oficiais, como o Composite Load Model, e para os especialistas do ONS.',
  },
  {
    titulo: 'Complementar aos modelos do ONS',
    detalhe:
      'Não substitui o PREVCARGA/PMO: o foco é a granularidade espacial da MMGD e a fronteira transmissão–distribuição.',
  },
  {
    titulo: 'O rótulo é a decisão observada',
    detalhe:
      'O curtailment das bases do ONS registra a restrição efetivamente solicitada, não o potencial físico de corte; o modelo aprende a decisão operativa.',
  },
  {
    titulo: 'Prever não elimina o corte',
    detalhe:
      'O valor está em antecipar e alocar recursos de flexibilidade; o produto apoia a decisão e não automatiza o despacho.',
  },
]
