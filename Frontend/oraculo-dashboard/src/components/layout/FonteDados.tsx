import { DATA_SOURCE_MODE, getSaude } from '../../data/dataSource'
import { useDados } from '../../data/useDados'
import { formatDataHoraBrt } from '../../utils/format'
import { StatusPill } from '../ui/StatusPill'

/**
 * Pill da topbar que diz DE ONDE vêm os números da tela, sempre visível:
 * - modo mock            -> "DADOS MOCK" (âmbar): nada ali é dado real do Backend;
 * - API respondendo      -> "DADOS DE dd/mm HH:MM" (verde): o "agora" do replay publicado;
 * - API fora / sem banco -> "API INDISPONÍVEL" (vermelho), com a causa no tooltip.
 * Decisão: sem isto, um dashboard em modo mock e um ligado à API são idênticos à vista, e
 * dado ilustrativo poderia ser apresentado como real (regra "nunca inventar dados").
 */
export function FonteDados() {
  const saude = useDados(getSaude)

  if (DATA_SOURCE_MODE === 'mock') return <StatusPill level="medium" label="Dados mock" />
  if (saude.status === 'loading') return <StatusPill level="none" label="Conectando à API" />
  if (saude.status === 'erro' || saude.data === null)
    return (
      <span title={saude.status === 'erro' ? saude.erro.message : undefined}>
        <StatusPill level="critical" label="API indisponível" />
      </span>
    )

  const s = saude.data
  return (
    <span title={`Execução #${s.execucaoId} (${s.origem}), publicada em ${formatDataHoraBrt(s.geradoEm)} BRT`}>
      <StatusPill level="low" label={`Dados de ${formatDataHoraBrt(s.instanteReferencia)}`} />
    </span>
  )
}
