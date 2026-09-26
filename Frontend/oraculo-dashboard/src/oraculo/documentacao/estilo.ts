/**
 * Estilo do corpo da documentação, escrito UMA vez e usado em dois lugares:
 * - na ajuda F1 (injetado por Ajuda.tsx), com as variáveis do tema da aplicação (--o-*), então
 *   segue o tema claro/escuro;
 * - no HTML exportado e na impressão (exportar.ts), onde PALETA_IMPRESSAO define as mesmas
 *   variáveis com uma paleta clara de documento (o arquivo exportado não tem o CSS da aplicação).
 *
 * Tudo escopado em `.doc` para não vazar para as telas.
 */
export const CSS_DOC = `
.doc { color: var(--o-ink-2); font-size: 13.5px; line-height: 1.6; max-width: 860px; }
.doc h1 { font-size: 21px; line-height: 1.25; color: var(--o-ink); margin: 4px 0 6px; }
.doc h2 { font-size: 15.5px; color: var(--o-ink); margin: 26px 0 8px; padding-bottom: 5px; border-bottom: 1px solid var(--o-line); }
.doc h3 { font-size: 13.5px; color: var(--o-ink); margin: 16px 0 6px; }
.doc p { margin: 7px 0; }
.doc ul, .doc ol { margin: 6px 0 8px; padding-left: 22px; }
.doc li { margin: 3px 0; }
.doc strong { color: var(--o-ink); }
.doc code { font-family: var(--o-mono); font-size: 12px; background: var(--o-panel-2); border: 1px solid var(--o-line); border-radius: 4px; padding: 0 4px; }
.doc pre { font-family: var(--o-mono); font-size: 11.5px; line-height: 1.45; background: var(--o-panel-2); border: 1px solid var(--o-line); border-radius: 6px; padding: 10px 12px; overflow-x: auto; white-space: pre; margin: 10px 0; color: var(--o-ink-2); }
.doc pre.formula { border-left: 3px solid var(--o-teal); color: var(--o-ink); }
.doc a, .doc .doc-link { color: var(--o-teal); text-decoration: underline; text-underline-offset: 2px; cursor: pointer; background: none; border: 0; padding: 0; font: inherit; }
.doc .doc-meta { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin-bottom: 4px; font-size: 11px; color: var(--o-muted); text-transform: uppercase; letter-spacing: .04em; }
.doc .doc-resumo { font-size: 14px; color: var(--o-ink-2); margin: 0 0 12px; }
.doc .doc-pergunta { border: 1px solid var(--o-line); border-left: 3px solid var(--o-navy-2); background: var(--o-panel-2); border-radius: 6px; padding: 8px 12px; margin: 10px 0; }
.doc .doc-pergunta b { display: block; font-size: 10.5px; text-transform: uppercase; letter-spacing: .05em; color: var(--o-muted); margin-bottom: 2px; }
.doc .doc-telas { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin: 10px 0; font-size: 12px; }
.doc .doc-rotas { font-size: 12px; margin: 8px 0 0; }
.doc .doc-rotas code { margin: 0 4px 4px 0; display: inline-block; }
.doc .doc-tabela { overflow-x: auto; margin: 10px 0; }
.doc table { border-collapse: collapse; width: 100%; font-size: 12.5px; }
.doc th, .doc td { text-align: left; vertical-align: top; padding: 6px 8px; border-bottom: 1px solid var(--o-line); }
.doc th { color: var(--o-ink); font-weight: 600; background: var(--o-panel-2); white-space: nowrap; }
.doc .aviso { border: 1px solid var(--o-line); border-left: 3px solid var(--o-navy-2); border-radius: 6px; padding: 8px 12px; margin: 12px 0; background: var(--o-panel-2); }
.doc .aviso > .aviso-tit { font-size: 12px; font-weight: 650; color: var(--o-ink); margin-bottom: 2px; }
.doc .aviso > .aviso-tit span { font-size: 10px; text-transform: uppercase; letter-spacing: .05em; margin-right: 6px; }
.doc .aviso.nota { border-left-color: var(--o-navy-2); }
.doc .aviso.nota > .aviso-tit span { color: var(--o-navy-2); }
.doc .aviso.premissa { border-left-color: var(--o-amber); }
.doc .aviso.premissa > .aviso-tit span { color: var(--o-amber); }
.doc .aviso.medido { border-left-color: var(--o-green); }
.doc .aviso.medido > .aviso-tit span { color: var(--o-green); }
.doc .aviso.limite { border-left-color: var(--o-crimson); }
.doc .aviso.limite > .aviso-tit span { color: var(--o-crimson); }
.doc .aviso > :last-child { margin-bottom: 2px; }
`

/** Paleta clara de documento para o HTML exportado e a impressão (mesmos nomes de variável). */
export const PALETA_IMPRESSAO = `
:root {
  --o-ink: #16203c; --o-ink-2: #2f3b5c; --o-muted: #67748f; --o-line: #dde3ef;
  --o-panel-2: #f4f6fb; --o-navy-2: #2b4393; --o-teal: #0e7c74; --o-green: #2e9b57;
  --o-amber: #c06410; --o-crimson: #b3262a;
  --o-mono: ui-monospace, "Cascadia Mono", "SF Mono", Menlo, Consolas, monospace;
}
body { margin: 0; background: #fff; font-family: "Segoe UI", system-ui, -apple-system, "Helvetica Neue", Arial, sans-serif; }
.doc-export { max-width: 900px; margin: 0 auto; padding: 32px 24px 64px; }
.doc-export .doc { max-width: none; }
.doc-capa h1 { font-size: 26px; margin-bottom: 4px; }
.doc-sumario { columns: 2; font-size: 13px; margin: 12px 0 28px; }
.doc-sumario h3 { break-after: avoid; margin: 10px 0 2px; font-size: 12px; text-transform: uppercase; letter-spacing: .05em; color: var(--o-muted); }
.doc-sumario a { display: block; }
.doc-export article { border-top: 2px solid var(--o-line); padding-top: 18px; margin-top: 28px; }
@media (max-width: 640px) { .doc-sumario { columns: 1; } }
@media print {
  .doc-export { padding: 0; }
  .doc-export article { break-before: page; border-top: 0; margin-top: 0; }
  .doc-export article:first-of-type { break-before: auto; }
  .doc pre, .doc table, .doc .aviso { break-inside: avoid; }
  .doc a { color: inherit; }
}
`
