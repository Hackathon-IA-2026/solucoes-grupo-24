import { Link } from 'react-router-dom'
import { Card } from '../components/ui/Card'
import { SeverityBadge } from '../components/ui/SeverityBadge'

/** Rota desconhecida: mantém o layout e oferece volta à Visão Geral. */
export default function NotFound() {
  return (
    <Card title="Rota não encontrada" actions={<SeverityBadge level="high" label="404" />}>
      <Link to="/" className="text-sm text-accent hover:underline">
        Voltar para a Visão Geral
      </Link>
    </Card>
  )
}
