/**
 * Lê o valor de uma token de cor (`--color-*` definida em index.css) em tempo de execução.
 *
 * Para quem não aceita classe Tailwind nem `var()`: canvas (leaflet.heat), opções de camada
 * do Leaflet etc. Assim até o mapa usa a paleta de index.css — nenhum hex duplicado.
 */
export function corToken(nome: string): string {
  const v = getComputedStyle(document.documentElement).getPropertyValue(nome).trim()
  if (!v) throw new Error(`token de cor inexistente: ${nome}`) // token com nome errado falha alto
  return v
}
