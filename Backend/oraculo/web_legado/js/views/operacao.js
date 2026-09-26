/* Paineis operacionais: despacho preditivo e risco/excedentes. */
(function () {
  "use strict";
  const V = window.App.VIEWS;

  // ==================================================== 1. DESPACHO PREDITIVO
  V.operacao = {
    title: "Despacho preditivo",
    subtitle: "Carga medida − MMGD estimada = carga supervisionada, com banda "
            + "probabilística e múltiplos horizontes",
    loadingText: "Decompondo a carga e treinando o preditor…",
    async render(root, S, U) {
      const [decB, fcB] = await Promise.all([
        Api.decomposition(S.area, 72),
        Api.forecast(S.area, S.horizon, S.asymmetric),
      ]);
      const d = decB.data, f = fcB.data;

      const lastLoad = lastFinite(d.carga_supervisionada);
      const mmgdPeak = Math.max.apply(null, (d.mmgd_estimada || [0]).map(z));
      const m = f.metrics || {};

      root.innerHTML =
        '<div class="grid g4" style="margin-bottom:14px">' +
          U.kpi("Carga supervisionada (último ponto)", U.num(lastLoad), "MWmed",
                "Área " + U.esc(d.area) + " · grade horária", "teal") +
          U.kpi("MMGD estimada — pico na janela", U.num(mmgdPeak), "MWmed",
                "Participação máxima " + U.pct(d.mmgd_share_peak, 1) +
                " da carga global", "amber") +
          U.kpi("Mínima supervisionada", U.num(d.min_supervised_mw), "MWmed",
                "em " + U.esc(String(d.min_supervised_at || "").replace("T", " ")),
                "green") +
          U.kpi("Maior rampa horária", U.num(d.max_ramp_mw_h), "MW/h",
                "amplitude diária " + U.num(d.daily_amplitude_mw) + " MW",
                "crimson") +
        "</div>" +

        '<div class="grid g-2-1" style="margin-bottom:14px">' +
          U.card("Decomposição da carga · últimas 72 h",
                 '<div id="ch-decomp"></div>',
                 { hint: "identidade verificada · resíduo " +
                         U.num(d.identity_residual_max, 6),
                   note: "A MMGD não é medida: é estimada pelo método do envelope " +
                         "(" + U.esc((d.mmgd || {}).method || "—") + "). " +
                         U.esc((d.mmgd || {}).bias_note || "") }) +
          U.card("Fator de nebulosidade e irradiância",
                 '<div id="ch-cloud"></div>',
                 { note: "O fator de nebulosidade é o que separa a geração " +
                         "potencial de céu claro da geração provável." }) +
        "</div>" +

        U.card("Previsão da carga supervisionada",
          '<div class="chips" style="margin-bottom:10px">' +
            horizonChips(S) + assymChip(S) +
          "</div><div id=\"ch-fc\"></div>",
          { hint: "treino " + U.num((f.train || {}).train_rows) + " h · teste " +
                  U.num((f.train || {}).test_rows) + " h · corte " +
                  U.esc(String((f.train || {}).cut_at || "").replace("T", " ")),
            note: "Métricas calculadas sobre todo o conjunto de teste; o gráfico " +
                  "mostra a janela recente. " + lossNote(f) }) +

        '<div class="grid g3" style="margin-top:14px">' +
          U.card("Desempenho no teste", U.statLines([
            ["MAE", U.num(m.mae, 1) + " MW"],
            ["RMSE", U.num(m.rmse, 1) + " MW"],
            ["MAPE", U.num(m.mape, 2) + "%"],
            ["Viés", U.signed(m.bias, 1) + " MW"],
            ["Erro de rampa", U.num(m.ramp_mae_mw_h, 1) + " MW/h"],
            ["Skill vs. persistência", skillHtml((f.skill || {}).vs_persistence)],
            ["Skill vs. sazonal-ingênuo", skillHtml((f.skill || {}).vs_seasonal)],
          ])) +
          U.card("Erro por patamar operativo", patamarTable(f.by_patamar, U)) +
          U.card("Peso por grupo de variável",
                 (f.drivers || []).map((g) =>
                   U.barRow(g.group, g.weight, U.pct(g.weight, 1))).join("") ||
                 '<div class="empty">—</div>',
                 { note: "Contribuição relativa dos coeficientes da mediana, " +
                         "escalada pelo desvio de cada variável." }) +
        "</div>" +
        U.provenanceBlock(decB);

      // graficos
      Charts.lineChart(document.getElementById("ch-decomp"), {
        index: d.index, height: 268, compact: true, yLabel: "MWmed",
        series: [
          { label: "Carga global (estimada)", values: d.carga_global, color: "muted", style: "dash" },
          { label: "MMGD estimada", values: d.mmgd_estimada, color: "amber", area: true },
          { label: "Carga supervisionada", values: d.carga_supervisionada, color: "teal", width: 2.2 },
        ],
      });

      Charts.lineChart(document.getElementById("ch-cloud"), {
        index: d.index, height: 268, digits: 2,
        series: [
          { label: "Irradiância céu claro (norm.)", values: d.ghi_norm, color: "navy", area: true, digits: 2 },
          { label: "Fator de nebulosidade", values: d.cloud_factor, color: "amber", digits: 2 },
        ],
      });

      drawForecast(f);
      wireChips(S);
    },
  };

  function drawForecast(f) {
    Charts.lineChart(document.getElementById("ch-fc"), {
      index: f.index, height: 300, compact: true, yLabel: "MWmed",
      bands: [{ lower: f.p10, upper: f.p90, color: "teal", opacity: 0.2,
                label: "Banda P10–P90" }],
      series: [
        { label: "Observado", values: f.observed, color: "ink", width: 2.2 },
        { label: "P50 previsto", values: f.p50, color: "teal", width: 2 },
        { label: "Persistência", values: f.baseline_persistence, color: "muted", style: "dash" },
        { label: "Sazonal-ingênuo", values: f.baseline_seasonal, color: "purple", style: "dash" },
      ],
    });
  }

  function horizonChips(S) {
    return ["30min", "3h", "d1"].map((hz) =>
      '<span class="chip clickable' + (S.horizon === hz ? " on" : "") +
      '" data-hz="' + hz + '">' + ({ "30min": "30 min", "3h": "3 h", d1: "D+1" }[hz]) +
      "</span>").join("");
  }

  function assymChip(S) {
    return '<span class="chip clickable ' + (S.asymmetric ? "on" : "") +
      '" data-asym="1" title="Liga e desliga a perda assimétrica por patamar">' +
      "perda assimétrica " + (S.asymmetric ? "ativa" : "desligada") + "</span>";
  }

  function wireChips(S) {
    document.querySelectorAll("[data-hz]").forEach((c) =>
      c.addEventListener("click", () => { S.horizon = c.dataset.hz; App.render(); }));
    document.querySelectorAll("[data-asym]").forEach((c) =>
      c.addEventListener("click", () => { S.asymmetric = !S.asymmetric; App.render(); }));
  }

  function lossNote(f) {
    const l = f.loss || {};
    if (!f.asymmetric) return "Perda simétrica: todos os patamares pesam igual.";
    const w = l.weights_by_patamar || {};
    const parts = Object.keys(w).filter((k) => k !== "base").map((k) =>
      k.replace(/_/g, " ") + " " + w[k].subestimacao + "/" + w[k].superestimacao);
    return "Perda assimétrica (subestimação/superestimação): " + parts.join(" · ") + ".";
  }

  function patamarTable(byP, U) {
    const rows = Object.keys(byP || {}).map((k) => {
      const v = byP[k] || {};
      return "<tr><td>" + U.esc(k.replace(/_/g, " ")) + '</td><td class="num">' +
        U.num(v.mae, 1) + '</td><td class="num">' + U.signed(v.bias, 1) +
        '</td><td class="num">' + U.num(v.n) + "</td></tr>";
    }).join("");
    return '<div class="table-wrap"><table><thead><tr><th>Patamar</th>' +
      '<th class="num">MAE</th><th class="num">Viés</th><th class="num">n</th>' +
      "</tr></thead><tbody>" + (rows || '<tr><td colspan="4">—</td></tr>') +
      "</tbody></table></div>";
  }

  function skillHtml(v) {
    if (v === null || v === undefined || !isFinite(v)) return "—";
    const cls = v > 0 ? "pos" : "neg";
    return '<span class="' + cls + '">' + App.signed(v, 3) + "</span>";
  }

  // ======================================================== 2. RISCO
  V.risco = {
    title: "Risco de curtailment e excedentes",
    subtitle: "Localizar · priorizar · explicar e recomendar, com rastreabilidade "
            + "até o dado de origem",
    loadingText: "Treinando o classificador de restrição por área…",
    async render(root, S, U) {
      const body = await Api.risk(S.horizon === "30min" ? "30min" : S.horizon, "estado", 0);
      const r = body.data;
      const areas = r.areas || [];
      const events = r.events || [];
      if (!areas.length) {
        root.innerHTML = '<div class="empty">Sem áreas com histórico suficiente ' +
          'de constrained-off na janela carregada.</div>' + U.provenanceBlock(body);
        return;
      }
      if (!S.selArea || !areas.some((a) => a.area === S.selArea)) {
        S.selArea = areas[0].area;
      }
      const totalMw = areas.reduce((s, a) => s + (a.expected_mw || 0), 0);
      const high = areas.filter((a) => a.probability >= 0.5).length;
      const ene = areas.filter((a) => a.reason === "ENE").length;

      root.innerHTML =
        '<div class="grid g4" style="margin-bottom:14px">' +
          U.kpi("Áreas com risco ≥ 50%", U.num(high), "de " + areas.length,
                "janela de " + U.esc(S.horizon === "d1" ? "D+1" : S.horizon), "amber") +
          U.kpi("Potência esperada de corte", U.num(totalMw), "MW",
                "soma de E[corte] nas áreas modeladas", "crimson") +
          U.kpi("Predominância de razão energética", U.num(ene), "áreas",
                "ENE é a razão que mais cresce desde abr/2025", "green") +
          U.kpi("AUC fora da amostra (mediana)",
                U.num((r.model || {}).auc_oos_median, 3), "",
                "avaliado só na janela solar, onde a pergunta é não trivial", "teal") +
        "</div>" +

        '<div class="grid g-1-2" style="margin-bottom:14px">' +
          U.card("Mapa esquemático · severidade por área",
                 '<div id="map" class="map-grid"></div>' +
                 '<div class="legend"><span class="legend-item">' +
                 '<span class="legend-swatch" style="background:var(--crimson)"></span>' +
                 'severidade alta</span><span class="legend-item">' +
                 '<span class="legend-swatch" style="background:var(--amber)"></span>' +
                 'média</span><span class="legend-item">' +
                 '<span class="legend-swatch" style="background:var(--green)"></span>' +
                 'baixa</span></div>',
                 { note: "Arranjo geográfico aproximado por unidade federativa. " +
                         "A granularidade-alvo em produção é área de concessão e " +
                         "transformação de fronteira, que exige a BDGD." }) +
          U.card("Eventos priorizados por severidade",
                 '<div class="table-wrap scroll-y" id="ev-table"></div>',
                 { hint: "severidade = 0,45·P + 0,35·E[corte] + 0,20·criticidade" }) +
        "</div>" +

        '<div class="grid g-2-1">' +
          '<div id="alert-box"></div>' +
          U.card("Probabilidade horária · área selecionada",
                 '<div id="ch-prob"></div>',
                 { note: "Probabilidade calibrada por binning monotônico no " +
                         "conjunto de validação." }) +
        "</div>" +
        U.provenanceBlock(body);

      drawMap(document.getElementById("map"), areas, S, U);
      drawEvents(document.getElementById("ev-table"), events, S, U);
      drawAlert(events, areas, S, U);
      drawProb(areas, S);
    },
  };

  // Arranjo geografico aproximado das UF (linhas x colunas).
  const UF_GRID = [
    ["", "", "", "", "", "AP", ""],
    ["AC", "AM", "", "PA", "MA", "", "RR"],
    ["", "RO", "MT", "TO", "PI", "CE", "RN"],
    ["", "", "MS", "GO", "BA", "PE", "PB"],
    ["", "", "", "MG", "ES", "AL", "SE"],
    ["", "", "PR", "SP", "RJ", "", ""],
    ["", "", "RS", "SC", "", "", ""],
  ];

  function sevColor(s) {
    return s >= 0.72 ? "crimson" : s >= 0.55 ? "amber" : "green";
  }

  function drawMap(host, areas, S, U) {
    const byUf = {};
    areas.forEach((a) => { byUf[a.area] = a; });
    const cells = [];
    UF_GRID.forEach((row) => row.forEach((uf) => {
      if (!uf) { cells.push('<div class="map-cell empty"></div>'); return; }
      const a = byUf[uf];
      if (!a) {
        cells.push('<div class="map-cell empty"><span class="uf">' + uf + "</span></div>");
        return;
      }
      const c = sevColor(a.severity);
      cells.push('<div class="map-cell' + (S.selArea === uf ? " sel" : "") +
        '" data-uf="' + uf + '" style="background:color-mix(in srgb, var(--' + c +
        ') ' + Math.round(12 + a.severity * 45) + '%, var(--panel-2))">' +
        '<span class="uf">' + uf + "</span>" +
        '<span class="mw">' + U.num(a.expected_mw) + " MW</span></div>");
    }));
    host.innerHTML = cells.join("");
    host.querySelectorAll("[data-uf]").forEach((c) =>
      c.addEventListener("click", () => { S.selArea = c.dataset.uf; App.render(); }));
  }

  function drawEvents(host, events, S, U) {
    const rows = events.map((e) =>
      '<tr data-ev="' + U.esc(e.area) + '" class="' +
      (e.area === S.selArea ? "sel" : "") + '" style="cursor:pointer">' +
      "<td><strong>" + U.esc(e.area) + "</strong><br>" +
      '<span class="small faint">' + U.esc(e.subsystem) + "</span></td>" +
      "<td>" + U.reasonTag(e.reason) + "</td>" +
      '<td class="num">' + U.pct(e.probability, 0) + "</td>" +
      '<td class="num">' + U.num(e.expected_mw) + "</td>" +
      '<td class="num">' + U.num(e.severity, 3) + "</td>" +
      '<td class="small">' + U.esc(String(e.patamar || "").replace(/_/g, " ")) +
      "<br>" + U.esc(String(e.peak_hour).padStart(2, "0")) + "h</td></tr>").join("");
    host.innerHTML = "<table><thead><tr><th>Área</th><th>Razão</th>" +
      '<th class="num">P</th><th class="num">E[corte] MW</th>' +
      '<th class="num">Sev.</th><th>Patamar</th></tr></thead><tbody>' +
      rows + "</tbody></table>";
    host.querySelectorAll("[data-ev]").forEach((tr) =>
      tr.addEventListener("click", () => { S.selArea = tr.dataset.ev; App.render(); }));
  }

  function drawAlert(events, areas, S, U) {
    const e = events.find((x) => x.area === S.selArea) || events[0];
    const box = document.getElementById("alert-box");
    if (!e) { box.innerHTML = '<div class="empty">Selecione uma área.</div>'; return; }
    const a = areas.find((x) => x.area === e.area) || {};
    const rw = e.reason_weights || {};
    const motive = Object.keys(rw).sort((x, y) => rw[y] - rw[x])
      .filter((k) => rw[k] > 0.01)
      .map((k) => U.pct(rw[k], 0) + " " + k).join(" · ");

    box.innerHTML =
      '<div class="alert">' +
        '<div class="alert-title">⚠ Alerta — risco de curtailment · ' +
          U.esc(e.area) + "</div>" +
        '<div class="alert-main">Probabilidade de <strong>' +
          U.pct(e.probability, 0) + "</strong> de restrição com montante esperado de <strong>" +
          U.num(e.expected_mw) + " MW</strong>, na janela " +
          U.esc(String((e.window || [])[0] || "").replace("T", " ")) + " → " +
          U.esc(String((e.window || [])[1] || "").replace("T", " ")) + ".</div>" +
        '<div class="alert-reason">Motivo predominante: ' + U.reasonTag(e.reason) +
          " " + U.esc(e.reason_label || "") + " · decomposição " + U.esc(motive) + "</div>" +
        '<div class="evidence">' + (e.evidence || []).map((ev) =>
          '<div class="evidence-row"><span class="lbl">' + U.esc(ev.label) +
          '</span><span class="val">' + U.esc(ev.value) + "</span>" +
          '<span class="src">fonte: ' + U.esc(ev.source) + "</span></div>").join("") +
        "</div>" +
        "<ul class=\"actions\">" + (e.recommended_actions || []).map((x) =>
          "<li>" + U.esc(x) + "</li>").join("") + "</ul>" +
        '<div class="alert-src">ponto de conexão: ' +
          U.esc(e.point_of_connection || "—") + " · histórico da área: corte total " +
          U.num((a.history || {}).total_cut_gwh, 2) + " GWh · taxa de ocorrência " +
          U.pct((a.history || {}).occurrence_rate, 1) + " · limiar de rótulo " +
          U.num((a.history || {}).threshold_mw, 1) + " MW · AUC " +
          U.num(a.auc_oos, 3) + "</div>" +
        '<div class="alert-src">As ações são apoio à decisão humana. O produto ' +
          "não automatiza despacho nem substitui procedimentos operativos.</div>" +
      "</div>";
  }

  function drawProb(areas, S) {
    const a = areas.find((x) => x.area === S.selArea) || areas[0];
    if (!a) return;
    Charts.lineChart(document.getElementById("ch-prob"), {
      index: a.hourly_index || [], height: 300, digits: 2, yMin: 0,
      series: [{ label: "P(restrição) — " + a.area, values: a.hourly_probability,
                 color: sevColor(a.severity), area: true, digits: 3 }],
    });
  }

  // ------------------------------------------------------------- util
  function z(v) { return (v === null || v === undefined || !isFinite(v)) ? 0 : v; }
  function lastFinite(arr) {
    for (let i = (arr || []).length - 1; i >= 0; i--) {
      const v = arr[i];
      if (v !== null && v !== undefined && isFinite(v)) return v;
    }
    return null;
  }
})();
