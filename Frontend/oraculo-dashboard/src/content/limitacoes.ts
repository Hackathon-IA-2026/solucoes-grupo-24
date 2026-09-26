/**
 * Limitações DECLARADAS do projeto (texto fixo, não é dado). Fonte única: a tela Validação
 * exibe esta lista e a Metodologia pode reaproveitá-la sem duplicar o texto.
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
