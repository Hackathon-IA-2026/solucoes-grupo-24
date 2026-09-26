/**
 * Botão do console em três variantes, e a mesma aparência para links de navegação (BotaoLink),
 * para "Ver no mapa", "Exportar CSV" e "Detalhe do alerta" terem um visual só em todas as telas.
 *
 * - primario: ação principal da área (accent);
 * - neutro:   ação secundária (borda de linha);
 * - fantasma: ação discreta dentro de listas (só texto/ícone).
 */
import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { Link, type LinkProps } from 'react-router-dom'

type Variante = 'primario' | 'neutro' | 'fantasma'

const BASE =
  'inline-flex items-center gap-1.5 whitespace-nowrap rounded-sm font-mono text-[11px] font-semibold tracking-wider transition-colors disabled:cursor-not-allowed disabled:opacity-40 focus-visible:outline focus-visible:outline-1 focus-visible:outline-accent'
const VARIANTE: Record<Variante, string> = {
  primario: 'border border-accent/50 bg-accent/10 px-2.5 py-1 text-accent hover:bg-accent/20',
  neutro: 'border border-line bg-fundo px-2.5 py-1 text-ink-muted hover:border-ink-faint hover:text-ink',
  fantasma: 'px-1.5 py-1 text-ink-muted hover:bg-surface-raised hover:text-accent',
}

interface BotaoProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variante?: Variante
  children: ReactNode
}

export function Botao({ variante = 'neutro', className = '', type = 'button', ...resto }: BotaoProps) {
  return <button type={type} className={`${BASE} ${VARIANTE[variante]} ${className}`} {...resto} />
}

export function BotaoLink({ variante = 'neutro', className = '', ...resto }: LinkProps & { variante?: Variante }) {
  return <Link className={`${BASE} ${VARIANTE[variante]} ${className}`} {...resto} />
}
