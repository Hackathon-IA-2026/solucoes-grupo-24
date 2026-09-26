/* Paineis de confianca: validacao do metodo e navegacao pelos dados abertos. */
(function () {
  "use strict";
  const V = window.App.VIEWS;

  // ==================================================== 6. VALIDACAO
  V.validacao = {
    title: "Validação do método",
    subtitle: "Backtest cronológico, baselines obrigatórios, métricas por patamar "
            + "e calibração probabilística",
    loadingText: "Executando backtest cronológico em todos os horizontes…",
    async render(root, S, U) {
      const body = await Api.validation(S.area, S.asymmetric);
      const v = body.data;
      const split = v.split || {};
      const hz = v.horizons || [];
      const eff = v.asymmetry_effect || {};
      const best = hz.reduce((b, x) =>
        (x.mae && (!b.mae || x.mae < b.mae)) ? x : b, {});

      root.innerHTML =
        '<div class="note-strip">Princípio: <strong>nenhuma promessa de desempenho ' +
        "sem teste; nenhum alerta sem evidência rastreável</strong>. A divisão é " +
        "estritamente cronológica — divisão aleatória vazaria informação do futuro " +
        "pelas variáveis de defasagem.</div>" +

        '<div class="grid g4" style="margin-bottom:14px">' +
          U.kpi("Corte cronológico", split.leakage_free
                  ? '<span class="pos">sem vazamento</span>'
                  : '<span class="neg">verificar</span>', "",
                U.num(split.train_rows) + " h de treino · " +
                U.num(split.test_rows) + " h de teste", "green") +
          U.kpi("Instante do corte",
                '<span style="font-size:16px">' +
                U.esc(String(split.cut_at || "—").replace("T", " ")) + "</span>", "",
                "nenhum ponto de teste antecede o treino", "teal") +
          U.kpi("Melhor MAE", U.num(best.mae, 1), "MW",
                "horizonte " + U.esc(best.horizon || "—"), "amber") +
          U.kpi("Função de perda", v.asymmetric ? "assimétrica" : "simétrica", "",
                v.asymmetric ? "pesos por patamar ativos"
                             : "todos os patamares pesam igual", "crimson") +
        "</div>" +

        U.card("Desempenho por horizonte", horizonTable(hz, U),
               { hint: "skill = 1 − MAE_modelo / MAE_baseline · positivo significa ganho",
                 note: "Um skill negativo aparece em vermelho e não é escondido: " +
                       "o modelo só é útil onde supera os baselines." }) +

        '<div class="grid g2" style="margin:14px 0">' +
          U.card("Métricas por patamar operativo", patamarTable(hz, U),
                 { note: "Uma melhoria de MAE global que piora a ponta noturna é " +
                         "uma piora operacional. Por isso o recorte é obrigatório." }) +
          U.card("Calibração probabilística", '<div id="ch-cal"></div>',
                 { note: "Um P90 que cobre 60% dos casos não é um P90. Desvio " +
                         "sistemático engana a decisão mais que um MAE alto." }) +
        "</div>" +

        '<div class="grid g2" style="margin-bottom:14px">' +
          U.card("Efeito da perda assimétrica (3 h)", asymTable(eff, v, U),
                 { note: "É isto que transforma o argumento em evidência: o mesmo " +
                         "conjunto de teste, com e sem os pesos por patamar. " +
                         "Observe o sinal do viés na ponta noturna." }) +
          U.card("Série de teste · horizonte 3 h", '<div id="ch-test"></div>',
                 { note: "Observado contra P50 e banda P10–P90, nas duas primeiras " +
                         "semanas do conjunto de teste." }) +
        "</div>" +

        U.card("Baselines avaliados no mesmo conjunto de teste", baselineTable(hz, U)) +
        U.provenanceBlock(body);

      // calibracao: cobertura empirica x nominal
      const h3 = hz.find((x) => x.horizon === "3h") || hz[0] || {};
      const cal = h3.calibration || [];
      Charts.scatter(document.getElementById("ch-cal"), {
        points: cal.filter((c) => c.empirical !== null).map((c) => ({
          x: c.nominal, y: c.empirical, label: "quantil P" + Math.round(c.nominal * 100),
          color: Math.abs((c.empirical || 0) - c.nominal) > 0.07 ? "crimson" : "teal",
        })),
        xDomain: [0, 1], yDomain: [0, 1], diagonal: true, height: 240,
        xLabel: "nominal", yLabel: "empírico", digits: 2, xDigits: 2,
        xAxisLabel: "quantil nominal → cobertura observada",
      });

      const series = (v.series || {})["3h"] || {};
      if (series.index && series.index.length) {
        Charts.lineChart(document.getElementById("ch-test"), {
          index: series.index, height: 240, compact: true,
          bands: [{ lower: series.p10, upper: series.p90, color: "teal",
                    opacity: 0.18, label: "P10–P90" }],
          series: [
            { label: "Observado", values: series.observed, color: "ink", width: 2 },
            { label: "P50", values: series.p50, color: "teal" },
            { label: "Persistência", values: series.persistencia, color: "muted", style: "dash" },
          ],
        });
      } else {
        document.getElementById("ch-test").innerHTML =
          '<div class="empty">Série de teste indisponível.</div>';
      }
    },
  };

  function horizonTable(hz, U) {
    const rows = hz.map((x) =>
      "<tr><td><strong>" + U.esc(label(x.horizon)) + "</strong> " +
      '<span class="small faint">' + U.num(x.steps) + "h à frente</span></td>" +
      '<td class="num">' + U.num(x.mae, 1) + "</td>" +
      '<td class="num">' + U.num(x.rmse, 1) + "</td>" +
      '<td class="num">' + U.num(x.mape, 2) + "</td>" +
      '<td class="num">' + U.signed(x.bias, 1) + "</td>" +
      '<td class="num">' + U.num(x.pinball, 2) + "</td>" +
      '<td class="num">' + U.num(x.interval_width_mw, 0) + "</td>" +
      '<td class="num">' + U.num(x.ramp_mae_mw_h, 1) + "</td>" +
      '<td class="num">' + skill((x.skill || {}).persistencia) + "</td>" +
      '<td class="num">' + skill((x.skill || {}).sazonal_diario) + "</td>" +
      '<td class="num">' + skill((x.skill || {}).sazonal_semanal) + "</td></tr>").join("");
    return '<div class="table-wrap"><table><thead><tr><th>Horizonte</th>' +
      '<th class="num">MAE</th><th class="num">RMSE</th><th class="num">MAPE %</th>' +
      '<th class="num">Viés</th><th class="num">Pinball</th>' +
      '<th class="num">Banda MW</th><th class="num">Rampa MAE</th>' +
      '<th class="num">skill persist.</th><th class="num">skill diário</th>' +
      '<th class="num">skill semanal</th></tr></thead><tbody>' + rows +
      "</tbody></table></div>";
  }

  function patamarTable(hz, U) {
    const pats = ["minima_diurna", "rampa", "ponta_noturna"];
    const rows = pats.map((p) => {
      const cells = hz.map((x) => {
        const m = (x.by_patamar || {})[p] || {};
        return '<td class="num">' + U.num(m.mae, 0) + "</td>" +
               '<td class="num">' + U.signed(m.bias, 0) + "</td>";
      }).join("");
      return "<tr><td>" + U.esc(p.replace(/_/g, " ")) + "</td>" + cells + "</tr>";
    }).join("");
    const head = hz.map((x) =>
      '<th class="num" colspan="2">' + U.esc(label(x.horizon)) + "</th>").join("");
    const sub = hz.map(() =>
      '<th class="num">MAE</th><th class="num">viés</th>').join("");
    return '<div class="table-wrap"><table><thead><tr><th rowspan="2">Patamar</th>' +
      head + "</tr><tr>" + sub + "</tr></thead><tbody>" + rows + "</tbody></table></div>";
  }

  function asymTable(eff, v, U) {
    const keys = ["assimetrica", "simetrica"];
    const pats = ["minima_diurna", "rampa", "ponta_noturna"];
    const rows = keys.map((k) => {
      const e = eff[k] || {};
      const cells = pats.map((p) => {
        const m = (e.by_patamar || {})[p] || {};
        return '<td class="num">' + U.num(m.mae, 0) + "</td>" +
               '<td class="num">' + U.signed(m.bias, 0) + "</td>";
      }).join("");
      return "<tr><td><strong>" + U.esc(k) + "</strong></td>" +
        '<td class="num">' + U.num(e.mae, 1) + "</td>" +
        '<td class="num">' + U.num(e.pinball, 2) + "</td>" + cells + "</tr>";
    }).join("");
    const w = v.weights || {};
    const wrows = Object.keys(w).filter((k) => k !== "base").map((k) =>
      '<span class="chip amber">' + U.esc(k.replace(/_/g, " ")) + " · sub " +
      w[k].subestimacao + " / super " + w[k].superestimacao + "</span>").join(" ");
    return '<div class="table-wrap"><table><thead><tr>' +
      '<th rowspan="2">Perda</th><th class="num" rowspan="2">MAE</th>' +
      '<th class="num" rowspan="2">Pinball</th>' +
      pats.map((p) => '<th class="num" colspan="2">' +
        U.esc(p.replace(/_/g, " ")) + "</th>").join("") + "</tr><tr>" +
      pats.map(() => '<th class="num">MAE</th><th class="num">viés</th>').join("") +
      "</tr></thead><tbody>" + rows + "</tbody></table></div>" +
      '<div class="chips" style="margin-top:10px">' + wrows + "</div>";
  }

  function baselineTable(hz, U) {
    const names = ["persistencia", "sazonal_diario", "sazonal_semanal"];
    const rows = names.map((n) => {
      const cells = hz.map((x) => {
        const b = (x.baselines || {})[n] || {};
        return '<td class="num">' + U.num(b.mae, 1) + "</td>" +
               '<td class="num">' + U.num(b.rmse, 1) + "</td>";
      }).join("");
      const lbl = ((hz[0] || {}).baselines || {})[n];
      return "<tr><td>" + U.esc((lbl && lbl.label) || n) + "</td>" + cells + "</tr>";
    }).join("");
    const head = hz.map((x) =>
      '<th class="num" colspan="2">' + U.esc(label(x.horizon)) + "</th>").join("");
    const sub = hz.map(() => '<th class="num">MAE</th><th class="num">RMSE</th>').join("");
    return '<div class="table-wrap"><table><thead><tr><th rowspan="2">Baseline</th>' +
      head + "</tr><tr>" + sub + "</tr></thead><tbody>" + rows + "</tbody></table></div>";
  }

  function label(h) {
    return { "30min": "30 min", "3h": "3 h", d1: "D+1" }[h] || h;
  }

  function skill(v) {
    if (v === null || v === undefined || !isFinite(v)) return "—";
    return '<span class="' + (v > 0 ? "pos" : "neg") + '">' + App.signed(v, 3) + "</span>";
  }

  // ==================================================== 7. DADOS ABERTOS
  V.dados = {
    title: "Dados abertos e proveniência",
    subtitle: "Navegação pelo catálogo do Portal de Dados Abertos do ONS, estado "
            + "do cache e rastro de cada número exibido",
    loadingText: "Consultando o catálogo CKAN do ONS…",
    async render(root, S, U) {
      const [catB, provB] = await Promise.all([Api.catalog(), Api.provenance()]);
      const c = catB.data, pv = provB.data;
      const cache = pv.cache || {};
      const curated = c.curated || [];
      const pkgs = c.packages || [];

      root.innerHTML =
        '<div class="grid g4" style="margin-bottom:14px">' +
          U.kpi("Conjuntos no Portal", U.num(c.count), "",
                U.num(curated.length) + " curados nesta solução", "teal") +
          U.kpi("Recursos em cache", U.num(cache.entries), "",
                U.bytes(cache.bytes) + " em disco", "green") +
          U.kpi("Modo corrente", U.esc(pv.mode || "—"), "",
                "live = rede · cache = disco · demo = sintético",
                pv.mode === "demo" ? "amber" : "teal") +
          U.kpi("Fontes externas mapeadas", U.num((c.external || []).length), "",
                "BDGD, cadastro ANEEL, satélite, meteorologia", "crimson") +
        "</div>" +

        '<div style="margin-bottom:14px"><button class="primary" id="btn-ingest">' +
        "Reexecutar ingestão</button> " +
        '<button class="ghost" id="btn-refresh-cat">Atualizar catálogo do ONS</button>' +
        ' <span class="small muted" id="ingest-status"></span></div>' +

        U.card("Conjuntos usados na solução", curatedTable(curated, U),
               { note: "Esquemas verificados por inspeção direta dos recursos CSV." }) +

        '<div class="grid g-2-1" style="margin:14px 0">' +
          U.card("Catálogo completo do Portal",
                 '<input id="flt" placeholder="filtrar conjuntos…" ' +
                 'style="width:100%;margin-bottom:9px">' +
                 '<div class="table-wrap scroll-y" id="pkg-table"></div>',
                 { hint: U.num(pkgs.length) + " conjuntos" }) +
          U.card("Detalhe do conjunto", '<div id="pkg-detail">' +
                 '<div class="empty">Selecione um conjunto à esquerda.</div></div>') +
        "</div>" +

        U.card("Relatório de ingestão", ingestTable(pv.reports, U),
               { note: "Campo numérico vazio vira NaN, nunca zero: zerar inventa " +
                       "informação. Descartes e colisões são contabilizados." }) +

        '<div class="grid g2" style="margin:14px 0">' +
          U.card("Previsto para a fase presencial", plannedTable(c.planned, U)) +
          U.card("Fontes externas e seu estado", externalTable(c.external, U)) +
        "</div>" +

        U.card("Manifesto de cache · auditoria", manifestTable(pv.entries, U),
               { hint: "cada recurso com hash, tamanho e instante de extração" }) +
        U.provenanceBlock(catB);

      // filtro do catalogo
      const drawPkgs = (term) => {
        const t = (term || "").toLowerCase();
        const rows = pkgs.filter((p) =>
          !t || p.id.toLowerCase().includes(t) ||
          String(p.title || "").toLowerCase().includes(t)
        ).map((p) =>
          '<tr data-pkg="' + U.esc(p.id) + '" style="cursor:pointer">' +
          "<td>" + (p.curated ? '<span class="chip green">curado</span> ' : "") +
          '<span class="mono small">' + U.esc(p.id) + "</span>" +
          (p.title && p.title !== p.id ? "<br>" + U.esc(p.title) : "") + "</td>" +
          '<td class="small muted">' + U.esc(p.granularity || p.role || "") +
          "</td></tr>").join("");
        const host = document.getElementById("pkg-table");
        host.innerHTML = "<table><thead><tr><th>Conjunto</th><th>Papel</th>" +
          "</tr></thead><tbody>" + (rows || '<tr><td colspan="2">nada encontrado</td></tr>') +
          "</tbody></table>";
        host.querySelectorAll("[data-pkg]").forEach((tr) =>
          tr.addEventListener("click", () => loadPackage(tr.dataset.pkg, U)));
      };
      drawPkgs("");
      document.getElementById("flt").addEventListener("input",
        (ev) => drawPkgs(ev.target.value));

      document.getElementById("btn-ingest").addEventListener("click", async () => {
        const st = document.getElementById("ingest-status");
        st.textContent = "executando…";
        try {
          const res = await Api.ingest({ force: false });
          st.textContent = "concluído · modo " + res.data.mode;
          Api.clearCache();
          setTimeout(() => App.render(), 600);
        } catch (err) {
          st.textContent = "falhou: " + err.message;
        }
      });
      document.getElementById("btn-refresh-cat").addEventListener("click", async () => {
        const st = document.getElementById("ingest-status");
        st.textContent = "consultando CKAN…";
        try { await Api.catalog(true); st.textContent = "catálogo atualizado";
              setTimeout(() => App.render(), 400); }
        catch (err) { st.textContent = "falhou: " + err.message; }
      });
    },
  };

  async function loadPackage(pkg, U) {
    const host = document.getElementById("pkg-detail");
    host.innerHTML = App.loading("Consultando " + pkg + "…");
    try {
      const body = await Api.packageDetail(pkg);
      const d = body.data;
      const rows = (d.resources || []).slice(0, 26).map((r) =>
        "<tr><td>" + U.esc(r.name || "—") + "</td>" +
        '<td><span class="chip">' + U.esc(r.format || "?") + "</span></td>" +
        '<td class="num">' + U.esc(r.year || "") +
        (r.month ? "/" + String(r.month).padStart(2, "0") : "") + "</td>" +
        '<td><a href="' + U.esc(r.url) + '" target="_blank" rel="noreferrer">abrir</a>' +
        "</td></tr>").join("");
      host.innerHTML = "<h4 style=\"margin:0 0 6px;font-size:13px\">" +
        U.esc(d.title) + "</h4>" +
        '<div class="small muted" style="margin-bottom:9px">' +
        U.esc((d.notes || "").slice(0, 420)) + "</div>" +
        '<div class="small faint" style="margin-bottom:9px">' +
        U.num(d.resource_count) + " recursos · modo " + U.esc(d.mode) + "</div>" +
        '<div class="table-wrap scroll-y"><table><thead><tr><th>Recurso</th>' +
        "<th>Formato</th><th class=\"num\">Período</th><th></th></tr></thead>" +
        "<tbody>" + rows + "</tbody></table></div>";
    } catch (err) {
      host.innerHTML = App.errorBlock(err);
    }
  }

  function curatedTable(curated, U) {
    const rows = curated.map((c) =>
      "<tr><td><strong>" + U.esc(c.title) + "</strong><br>" +
      '<span class="mono small faint">' + U.esc(c.package) + "</span></td>" +
      '<td class="small">' + U.esc(c.role) + "</td>" +
      '<td><span class="chip teal">' + U.esc(c.granularity) + "</span></td>" +
      '<td class="num small">' + U.bytes(c.approx_bytes) + "</td>" +
      '<td class="small muted">' + U.esc(c.lag_note) + "</td>" +
      '<td class="small faint">' + (c.fields || []).length + " campos</td></tr>").join("");
    return '<div class="table-wrap"><table><thead><tr><th>Conjunto</th>' +
      "<th>Papel na solução</th><th>Granularidade</th>" +
      '<th class="num">Tamanho</th><th>Defasagem declarada</th><th>Esquema</th>' +
      "</tr></thead><tbody>" + rows + "</tbody></table></div>";
  }

  function ingestTable(reports, U) {
    const rows = (reports || []).map((r) =>
      "<tr><td>" + U.esc(r.dataset) + "</td>" +
      '<td class="mono small">' + U.esc(r.resource) + "</td>" +
      '<td><span class="chip ' + U.modeClass(r.mode) + '">' + U.esc(r.mode) +
      "</span></td>" +
      '<td class="num">' + U.num(r.rows) + "</td>" +
      '<td class="num">' + U.bytes(r.bytes_read) + "</td>" +
      '<td class="num">' + U.num(r.discarded_bad_time) + "</td>" +
      '<td class="num">' + U.num(r.discarded_short_line) + "</td>" +
      '<td class="num">' + U.num(r.duplicates) + "</td>" +
      '<td class="small neg">' + U.esc(r.error || "") + "</td></tr>").join("");
    return '<div class="table-wrap"><table><thead><tr><th>Conjunto</th>' +
      '<th>Recurso</th><th>Modo</th><th class="num">Linhas</th>' +
      '<th class="num">Bytes</th><th class="num">Instante inválido</th>' +
      '<th class="num">Linha curta</th><th class="num">Duplicatas</th>' +
      "<th>Erro</th></tr></thead><tbody>" + rows + "</tbody></table></div>";
  }

  function plannedTable(planned, U) {
    const rows = (planned || []).map((p) =>
      '<tr><td class="mono small">' + U.esc(p.package) + "</td>" +
      '<td class="small">' + U.esc(p.role) + "</td></tr>").join("");
    return '<div class="table-wrap"><table><tbody>' + rows + "</tbody></table></div>";
  }

  function externalTable(ext, U) {
    const rows = (ext || []).map((e) =>
      "<tr><td><strong>" + U.esc(e.name) + "</strong><br>" +
      '<span class="small muted">' + U.esc(e.role) + "</span></td>" +
      '<td><span class="chip teal">' + U.esc(e.cadence) + "</span></td>" +
      '<td class="small faint">' + U.esc(e.status) + "</td></tr>").join("");
    return '<div class="table-wrap"><table><thead><tr><th>Fonte</th>' +
      "<th>Cadência</th><th>Estado</th></tr></thead><tbody>" + rows +
      "</tbody></table></div>";
  }

  function manifestTable(entries, U) {
    const rows = (entries || []).slice(0, 40).map((e) =>
      "<tr><td>" + U.esc(e.dataset || "—") + "</td>" +
      '<td class="mono small">' + U.esc(e.resource || e.file) + "</td>" +
      '<td class="num">' + U.bytes(e.bytes) + "</td>" +
      '<td class="mono small faint">' + U.esc(String(e.sha256 || "").slice(0, 14)) +
      "…</td><td>" + U.when(e.fetched_at) + "</td>" +
      '<td class="small muted">' + U.esc(e.note || "") + "</td></tr>").join("");
    return '<div class="table-wrap scroll-y"><table><thead><tr><th>Conjunto</th>' +
      '<th>Recurso</th><th class="num">Bytes</th><th>SHA-256</th>' +
      "<th>Extraído</th><th>Nota</th></tr></thead><tbody>" +
      (rows || '<tr><td colspan="6">cache vazio</td></tr>') + "</tbody></table></div>";
  }
})();
