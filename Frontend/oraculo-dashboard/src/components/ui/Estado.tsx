import { Card } from './Card'

/**
 * Placeholders de carregamento e erro compartilhados por todas as telas que usam
 * useDados. Erro mostra a mensagem do dataSource (que já diz qual recurso e por quê).
 */
export function Carregando({ altura = 'h-32' }: { altura?: string }) {
  return <div className={`${altura} animate-pulse border border-line bg-surface`} aria-busy="true" />
}

export function ErroDados({ erro }: { erro: Error }) {
  return (
    <Card title="Falha ao carregar dados">
      <pre className="whitespace-pre-wrap font-mono text-xs text-risk-critical">{erro.message}</pre>
    </Card>
  )
}
