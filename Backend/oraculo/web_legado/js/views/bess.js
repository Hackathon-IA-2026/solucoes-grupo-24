/* Investimento: alocação de BESS pelo corte observado e pela MMGD.
   Dois painéis novos. A interface não calcula nada: os pesos vão ao servidor,
   que refaz a pontuação. */
(function () {
  "use strict";
  const V = window.App.VIEWS;
  const COMP = [
    ["energia", "Energia recuperável", "teal"],
    ["mmgd", "Excedente da MMGD", "amber"],
    ["recorrencia", "Recorrência do corte", "purple"],
    ["local", "Restrição local", "green"],
  ];
  let POLL = null;

  function weightParams(S) {
    const w = S.bsW;
    if (!w) return {};
    const out = {};
    COMP.forEach((c) => { out["w_" + c[0]] = w[c[0]]; });
    return out;
  }

  async function ready(root, S, U, viewId) {
    const body = await Api.get("bess/status", null, { fresh: true });
    const st = body.data;
    if (st.state === "ready") return body;
    root.innerHTML =
      '<div class="note-strip' + (st.state === "error" ? " warn" : "") + '">' +
      (st.state === "error"
        ? "<strong>Falha ao montar a base de constrained-off.</strong> " +
          U.esc(st.error) + ' <button class="ghost small" id="bs-retry">tentar de novo</button>'
        : "<strong>Baixando 12 meses de constrained-off do ONS</strong> " +
          "(fotovoltaica e eólica, ~800 MB). Cada mês é agregado e guardado; " +
          "da próxima vez, só o mês novo é baixado.") + "</div>" +
      U.card("Progresso", U.barRow("meses agregados", st.overall || 0,
        U.num(st.done) + " de " + U.num(st.total), "teal") +
        '<div class="card-note">Agora: ' + U.esc(st.stage || "—") +
        (st.elapsed_s ? " · " + U.num(st.elapsed_s, 0) + " s decorridos" : "") + "</div>");
    const b = root.querySelector("#bs-retry");
    if (b) b.addEventListener("click", async () => {
      try { await Api.post("bess/reconstruir"); } catch (e) { /* status mostra */ }
      App.render();
    });
    clearTimeout(POLL);
    if (st.state !== "error") {
      POLL = setTimeout(() => { if (S.view === viewId) App.render(); }, 3000);
    }
    return null;
  }

  function scoreBar(v) {
    const f = Math.max(0, Math.min(1, v || 0));
    return '<span class="bar-track" style="display:inline-block;width:70px;' +
      'vertical-align:middle"><span class="bar-fill" style="width:' +
      (f * 100).toFixed(0) + '%"></span></span> ' + App.num(v, 2);
  }

  function utilChip(g) {
    if (!g || !g.p_mw) return '<span class="chip">—</span>';
    const c = g.utilization === "adequada" ? "green" : "amber";
    return '<span class="chip ' + c + '">' + App.num(g.p_mw) + " MW · " +
      App.num(g.hours) + " h</span>";
  }

  // ------------------------------------------------------------ mapa
  function drawMap(host, pts, S, onPick) {
    if (!pts.length) { host.innerHTML = '<div class="empty">Sem sítios localizados.</div>'; return; }
    const lats = pts.map((p) => p.lat), lons = pts.map((p) => p.lon);
    let la0 = Math.min.apply(null, lats), la1 = Math.max.apply(null, lats);
    let lo0 = Math.min.apply(null, lons), lo1 = Math.max.apply(null, lons);
    const pl = (la1 - la0) * 0.08 + 0.3, pn = (lo1 - lo0) * 0.08 + 0.3;
    la0 -= pl; la1 += pl; lo0 -= pn; lo1 += pn;
    const k = Math.cos(((la0 + la1) / 2) * Math.PI / 180);
    const W = 640;
    const H = Math.max(280, Math.min(560, W * (la1 - la0) / ((lo1 - lo0) * k)));
    const sx = (lo) => ((lo - lo0) / (lo1 - lo0)) * W;
    const sy = (la) => H - ((la - la0) / (la1 - la0)) * H;
    const maxE = Math.max.apply(null, pts.map((p) => p.cut_gwh || 0).concat([1]));
    const sorted = pts.slice().sort((a, b) => (b.cut_gwh || 0) - (a.cut_gwh || 0));
    let s = '<svg viewBox="0 0 ' + W + " " + H.toFixed(0) + '" width="100%" role="img" ' +
      'aria-label="Mapa de sítios de corte" style="display:block">';
    sorted.forEach((p) => {
      const r = 3 + 16 * Math.sqrt((p.cut_gwh || 0) / maxE);
      const col = p.rank <= 10 ? "crimson" : p.score >= 0.5 ? "amber" : "teal";
      const on = p.code === S.bsSel;
      s += '<circle data-code="' + App.esc(p.code) + '" cx="' + sx(p.lon).toFixed(1) +
        '" cy="' + sy(p.lat).toFixed(1) + '" r="' + r.toFixed(1) + '" fill="' +
        Charts.color(col) + '" fill-opacity="' + (on ? 0.95 : 0.55) + '" stroke="' +
        Charts.color(on ? "teal" : col) + '" stroke-width="' + (on ? 2.6 : 1) +
        '" style="cursor:pointer"><title>#' + p.rank + " " + App.esc(p.name) + " · " +
        App.num(p.cut_gwh, 0) + " GWh/ano cortados · pontuação " + App.num(p.score, 2) +
        "</title></circle>";
      if (p.rank <= 10) {
        s += '<text x="' + sx(p.lon).toFixed(1) + '" y="' + (sy(p.lat) + 3.5).toFixed(1) +
          '" text-anchor="middle" style="font:700 9px var(--mono);fill:#fff;' +
          'pointer-events:none">' + p.rank + "</text>";
      }
    });
    s += "</svg>";
    host.innerHTML = s + '<div class="chips small" style="margin-top:8px;gap:10px">' +
      legend("crimson", "top 10 da pontuação") + legend("amber", "pontuação ≥ 0,5") +
      legend("teal", "demais") + '<span class="small muted">tamanho ∝ √ energia cortada</span></div>';
    host.querySelectorAll("[data-code]").forEach((c) =>
      c.addEventListener("click", () => onPick(c.getAttribute("data-code"))));
  }

  function legend(color, label) {
    return '<span class="small muted" style="display:inline-flex;align-items:center;gap:5px">' +
      '<span style="width:9px;height:9px;border-radius:50%;background:' +
      Charts.color(color) + '"></span>' + App.esc(label) + "</span>";
  }

  // ============================================== ALOCAÇÃO DE BESS
  V.bess = {
    title: "Alocação de BESS pelo corte observado",
    subtitle: "Onde um armazenamento recupera mais energia cortada das usinas "
            + "centralizadas — e quanto desse corte é excedente criado pela MMGD",
    loadingText: "Simulando o BESS em cada sítio de corte…",
    async render(root, S, U) {
      const st = await ready(root, S, U, "bess");
      if (!st) return;
      const params = Object.assign({ uf: S.bsUf || "", fonte: S.bsFonte || "" },
                                   weightParams(S));
      const body = await Api.get("bess/ranking", params);
      const d = body.data;
      const k = d.kpis || {};
      const rows = d.rows || [];
      const w = S.bsW || d.default_weights;
      if (!S.bsSel || !rows.some((r) => r.code === S.bsSel)) {
        S.bsSel = rows.length ? rows[0].code : null;
      }

      root.innerHTML =
        '<div class="note-strip"><strong>Apoio à decisão de investimento.</strong> ' +
        "O corte acontece nas usinas <strong>eólicas e fotovoltaicas centralizadas" +
        "</strong> — 12 meses de <em>constrained-off</em> apurado pelo ONS, por " +
        "subestação de conexão. A MMGD não é cortada: ela reduz a carga líquida ao " +
        "meio-dia, aprofunda a barriga da curva do pato e cria o excedente que vira " +
        "corte por razão energética de origem sistêmica (ENE+SIS). Em cada sítio, um " +
        "BESS é simulado carregando no corte e devolvendo na rampa do fim da tarde.</div>" +

        '<div class="grid g4" style="margin-bottom:14px">' +
          U.kpi("Corte apurado", U.num(k.cut_twh_year, 2), "TWh/ano",
                "FV + eólica · " + U.num(k.sites) + " sítios · " +
                U.pct(k.ene_share, 0) + " por razão energética", "crimson") +
          U.kpi("Concentração", U.pct(k.cut_top10_share, 0), "",
                "do corte está em 10 sítios", "amber") +
          U.kpi("Excedente da MMGD", U.num(k.mmgd_induced_twh, 1), "TWh/ano",
                "até " + U.pct(k.mmgd_induced_share, 0) + " do corte · limite superior " +
                "sobre o corte ENE+SIS (" + U.pct(k.es_share, 0) + ")", "amber") +
          U.kpi("Recuperável no top 10", U.num(k.recoverable_top10_twh, 2), "TWh/ano",
                "BESS dimensionado em cada sítio · " + U.pct(k.located_share, 1) +
                " do corte localizado", "teal") +
        "</div>" +

        '<div class="grid g-1-2" style="margin-bottom:14px">' +
          U.card("Pesos da pontuação", weightPanel(w, U) +
                 '<div style="margin-top:10px;display:flex;gap:8px">' +
                 '<button id="bs-apply">Aplicar</button>' +
                 '<button class="ghost" id="bs-reset">Padrão</button></div>',
                 { note: "Cada componente é um posto percentual (0 a 1) entre os " +
                         "sítios; os pesos são normalizados. A estabilidade do top 10 " +
                         "sob outros pesos está no painel Método." }) +
          '<div class="card">' +
            '<div class="chips" style="margin-bottom:10px">' +
              '<span class="small muted" style="align-self:center">fonte</span>' +
              [["", "todas"], ["fotovoltaica", "fotovoltaica"], ["eólica", "eólica"]].map((f) =>
                '<span class="chip clickable' + ((S.bsFonte || "") === f[0] ? " on" : "") +
                '" data-fonte="' + f[0] + '">' + f[1] + "</span>").join("") +
              '<span class="small muted" style="align-self:center;margin-left:10px">UF</span>' +
              '<span class="chip clickable' + (!S.bsUf ? " on" : "") + '" data-uf="">todas</span>' +
              (d.ufs || []).map((u) =>
                '<span class="chip clickable' + (S.bsUf === u ? " on" : "") +
                '" data-uf="' + u + '">' + u + "</span>").join("") +
            "</div>" +
            '<div id="bs-map"></div>' +
          "</div>" +
        "</div>" +

        '<div class="grid g-2-1" style="margin-bottom:14px">' +
          U.card("Por que há excedente: a curva do pato", duckChips(d.duck, S, U) +
                 '<div id="bs-duck"></div>',
                 { hint: "perfil médio horário na janela do corte",
                   note: "Carga com MMGD − MMGD = carga supervisionada; menos eólica e " +
                         "solar centralizadas = carga líquida. A distância entre a " +
                         "primeira e a segunda curvas ao meio-dia é a MMGD, que aprofunda " +
                         "a barriga do pato; o corte (vermelho) acontece ali." }) +
          U.card("Tese 2 · BESS junto à carga", loadSideTable(d.load_side, U),
                 { hint: "onde a MMGD mais pesa sobre a carga",
                   note: "Outra decisão de investimento: armazenamento perto da MMGD " +
                         "achata a curva do pato na origem e suaviza a rampa. Não recupera " +
                         "o corte de uma usina específica — por isso não entra no ranking " +
                         "ao lado. MW de MMGD ÷ MW médio de carga (seção Fronteira T–D)." }) +
        "</div>" +

        U.card("Tese 1 · BESS junto à geração cortada", rankTable(rows, S, U),
               { hint: "clique num sítio para o detalhe · " + U.num(rows.length) + " no filtro",
                 note: "BESS sugerido: o maior tamanho da grade em que o MWh " +
                       "ADICIONAL ainda cicla ≥ 200 vezes/ano. Chip âmbar: nem o " +
                       "menor tamanho atinge esse uso." }) +

        '<div id="bs-detail" style="margin-top:14px"></div>' +

        '<div class="grid g2" style="margin-top:14px">' +
          U.card("Pipeline replicável", "<ol class=\"actions\" style=\"padding-left:20px\">" +
                 (d.pipeline || []).map((x) => "<li>" + U.esc(x) + "</li>").join("") + "</ol>",
                 { note: "Meses na janela: " + U.esc((d.months || []).join(", ")) }) +
          U.card("Premissas", U.statLines((d.premises || []).map((p) => [p.k, U.esc(p.v)])),
                 { note: "Versionadas em <span class=\"mono\">config.BESS</span>." }) +
        "</div>" +
        U.provenanceBlock(body);

      drawMap(document.getElementById("bs-map"), d.map || [], S, pick);
      drawDuck(d.duck, S);
      root.querySelectorAll("[data-ss]").forEach((c) => c.addEventListener("click", () => {
        S.bsSS = c.dataset.ss;
        root.querySelectorAll("[data-ss]").forEach((x) =>
          x.classList.toggle("on", x.dataset.ss === S.bsSS));
        drawDuck(d.duck, S);
      }));
      bindTable();
      await drawDetail(S, U);

      async function pick(code) {
        S.bsSel = code;
        drawMap(document.getElementById("bs-map"), d.map || [], S, pick);
        document.querySelectorAll("#bs-rank tr[data-code]").forEach((tr) =>
          tr.classList.toggle("sel", tr.dataset.code === code));
        await drawDetail(S, U);
      }
      function bindTable() {
        document.querySelectorAll("#bs-rank tr[data-code]").forEach((tr) =>
          tr.addEventListener("click", () => pick(tr.dataset.code)));
      }

      root.querySelectorAll("[data-uf]").forEach((c) => c.addEventListener("click", () => {
        S.bsUf = c.dataset.uf; S.bsSel = null; App.render();
      }));
      root.querySelectorAll("[data-fonte]").forEach((c) => c.addEventListener("click", () => {
        S.bsFonte = c.dataset.fonte; S.bsSel = null; App.render();
      }));
      root.querySelectorAll("input[data-w]").forEach((inp) => inp.addEventListener("input", () => {
        const o = root.querySelector("#w-" + inp.dataset.w + "-v");
        if (o) o.textContent = App.num(parseFloat(inp.value), 2);
      }));
      root.querySelector("#bs-apply").addEventListener("click", () => {
        const nw = {};
        root.querySelectorAll("input[data-w]").forEach((inp) => {
          nw[inp.dataset.w] = parseFloat(inp.value);
        });
        S.bsW = nw; S.bsSel = null; App.render();
      });
      root.querySelector("#bs-reset").addEventListener("click", () => {
        S.bsW = null; S.bsSel = null; App.render();
      });
    },
  };

  function weightPanel(w, U) {
    return COMP.map((c) =>
      '<div class="bar-row" style="grid-template-columns:150px 1fr 44px">' +
      "<span>" + U.esc(c[1]) + "</span>" +
      '<input type="range" min="0" max="1" step="0.05" data-w="' + c[0] + '" value="' +
      ((w || {})[c[0]] || 0) + '" style="accent-color:var(--' + c[2] + ')">' +
      '<span class="v" id="w-' + c[0] + '-v">' + U.num((w || {})[c[0]] || 0, 2) + "</span>" +
      "</div>").join("");
  }

  function rankTable(rows, S, U) {
    return '<div class="table-wrap scroll-y" style="max-height:460px"><table id="bs-rank">' +
      '<thead><tr><th class="num">#</th><th>Sítio (SE de conexão)</th>' +
      '<th class="num">Corte GWh/ano</th><th class="num">Dias com corte</th>' +
      '<th class="num">Origem local</th><th>BESS sugerido</th>' +
      '<th class="num">Entrega GWh/ano</th><th class="num">Excedente MMGD</th>' +
      "<th>Pontuação</th></tr></thead><tbody>" + rows.map((r) => {
        const g = r.suggested || {};
        return '<tr data-code="' + U.esc(r.code) + '" class="' +
          (r.code === S.bsSel ? "sel" : "") + '" style="cursor:pointer">' +
          '<td class="num"><strong>' + r.rank + "</strong></td>" +
          "<td><strong>" + U.esc(r.name) + '</strong><br><span class="small faint">' +
          U.esc(r.uf) + " · " + U.esc((r.sources || []).join(" + ")) + " · " +
          U.num(r.disp_max_mw) + " MW disponíveis</span></td>" +
          '<td class="num">' + U.num(r.cut_gwh_year, 0) + '<br><span class="small faint">' +
          U.pct(r.cut_rate, 0) + " da geração</span></td>" +
          '<td class="num">' + U.pct(r.recurrence, 0) + "</td>" +
          '<td class="num">' + U.pct(r.local_share, 0) + "</td>" +
          "<td>" + utilChip(g) + "</td>" +
          '<td class="num">' + U.num((g.delivered_mwh || 0) / 1000, 0) + "</td>" +
          '<td class="num">' + U.pct(r.induced_share, 0) + "</td>" +
          "<td>" + scoreBar(r.score) + "</td></tr>";
      }).join("") + "</tbody></table></div>";
  }

  async function drawDetail(S, U) {
    const host = document.getElementById("bs-detail");
    if (!host || !S.bsSel) return;
    host.innerHTML = App.loading("Montando o detalhe do sítio…");
    let body;
    try {
      body = await Api.get("bess/sitio/" + encodeURIComponent(S.bsSel), weightParams(S));
    } catch (err) {
      host.innerHTML = App.errorBlock(err);
      return;
    }
    const r = body.data, g = r.suggested || {}, c = r.components || {};
    host.innerHTML = U.card(
      "#" + r.rank + " · " + U.esc(r.name) + " (" + U.esc(r.uf) + ")",
      '<div class="grid g4" style="gap:12px;margin-bottom:12px">' +
        U.kpi("Corte apurado", U.num(r.cut_gwh_year, 0), "GWh/ano",
              U.pct(r.cut_rate, 0) + " da geração · pico " + U.num(r.peak_cut_mw, 0) + " MW") +
        U.kpi("BESS sugerido", g.p_mw ? U.num(g.p_mw) + " MW / " + U.num(g.hours) + " h" : "—", "",
              U.num(g.cycles, 0) + " ciclos/ano · MWh marginal " + U.num(g.marginal_cycles, 0)) +
        U.kpi("Energia recuperada", U.num((g.delivered_mwh || 0) / 1000, 0), "GWh/ano",
              U.pct(g.capture, 0) + " do corte do sítio") +
        U.kpi("Excedente da MMGD", U.pct(r.induced_share, 0), "",
              "até " + U.num(r.induced_gwh_year, 0) + " GWh/ano · corte ENE+SIS " +
              U.pct(r.es_share, 0)) +
      "</div>" +
      '<div class="grid g2" style="gap:12px">' +
        "<div>" +
          '<div class="kpi-label" style="margin-bottom:6px">Por que este sítio</div>' +
          '<ul class="actions" style="padding-left:18px">' +
          (r.reasoning || []).map((x) => "<li>" + U.esc(x) + "</li>").join("") + "</ul>" +
          '<div class="kpi-label" style="margin:12px 0 6px">Componentes da pontuação</div>' +
          COMP.map((cc) => U.barRow(cc[1], c[cc[0]] || 0, U.num(c[cc[0]], 2), cc[2])).join("") +
        "</div>" +
        "<div>" +
          '<div class="kpi-label" style="margin-bottom:6px">Curva de dimensionamento · ' +
          "energia entregue × energia instalada</div>" +
          '<div id="bs-curve"></div>' +
          '<div class="card-note">Cada ponto é um BESS da grade (potência × duração). ' +
          "A curva achata quando o MWh adicional quase não é usado — é ali que o " +
          "investimento marginal deixa de se pagar.</div>" +
        "</div>" +
      "</div>",
      { hint: U.esc(r.location_method) + " · " + U.num(r.n_usinas) + " usinas · " +
              U.esc((r.sources || []).join(" + ")) }) +

      '<div class="grid g2" style="margin-top:14px">' +
        U.card("Quando o corte acontece", '<div id="bs-heat"></div>',
               { hint: "MW médio de corte · mês × hora do dia",
                 note: "Corte concentrado ao meio-dia é o perfil que a MMGD agrava e " +
                       "que um BESS de 4 a 6 h desloca para a rampa do fim da tarde." }) +
        U.card("Perfil médio diário", '<div id="bs-prof"></div>',
               { hint: "MWh cortados por meia hora, média da janela" }) +
      "</div>" +
      '<div class="grid g3" style="margin-top:14px">' +
        U.card("Razão da restrição", reasonBars(r.e_reason_gwh, U),
               { hint: "GWh/ano" }) +
        U.card("Origem", reasonBars(r.e_origin_gwh, U),
               { hint: "GWh/ano · LOC local, SIS sistêmica",
                 note: "Corte LOCAL só é aliviado por armazenamento no próprio ponto." }) +
        U.card("Usinas no sítio", '<div class="small" style="max-height:170px;overflow:auto">' +
               (r.usinas || []).map(U.esc).join("<br>") + "</div>",
               { hint: U.num(r.n_usinas) + " usinas · " + U.num((r.points || []).length) +
                       " ponto(s) de conexão" }) +
      "</div>";

    Charts.scatter(document.getElementById("bs-curve"), {
      points: (r.grid || []).map((x) => ({
        x: x.e_mwh, y: x.delivered_mwh / 1000,
        label: U.num(x.p_mw) + " MW × " + U.num(x.hours) + " h · " +
               U.num(x.cycles, 0) + " ciclos/ano",
        color: g.p_mw === x.p_mw && g.hours === x.hours ? "crimson"
          : x.hours === 2 ? "teal" : x.hours === 4 ? "amber" : "navy",
      })),
      xLabel: "MWh instalados", yLabel: "GWh/ano entregues", height: 220,
      xDigits: 0, digits: 0, r: 5,
    });
    const maxH = Math.max.apply(null, (r.heat || []).map((h) =>
      Math.max.apply(null, h.values.concat([0]))).concat([1]));
    Charts.heatStrip(document.getElementById("bs-heat"), {
      rows: (r.heat || []).map((h) => ({ label: h.label,
        values: h.values.map((v) => v / maxH) })),
      raw: (r.heat || []).map((h) => h.values), color: "crimson", unit: "MW",
      seriesLabel: "corte médio", digits: 0, padLeft: 50,
      colLabel: (c) => String(Math.floor(c / 2)).padStart(2, "0") + (c % 2 ? ":30" : "h"),
    });
    Charts.barChart(document.getElementById("bs-prof"), {
      labels: (r.profile_mwh || []).map((_, i) =>
        i % 2 ? "" : String(i / 2).padStart(2, "0") + "h"),
      values: r.profile_mwh || [], color: "crimson", height: 200, digits: 1,
      unit: "MWh", seriesLabel: "corte médio",
    });
  }

  function reasonBars(obj, U) {
    const e = Object.entries(obj || {}).sort((a, b) => b[1] - a[1]);
    const tot = e.reduce((s, x) => s + x[1], 0) || 1;
    return e.map(([k, v]) => U.barRow(k, v / tot, U.num(v, 0),
      k === "ENE" ? "amber" : k === "LOC" ? "crimson" : "teal")).join("") ||
      '<div class="empty">—</div>';
  }

  const SS_ORDER = ["NE", "SE", "S", "N"];

  function duckChips(duck, S, U) {
    if (!S.bsSS) S.bsSS = "NE";
    return '<div class="chips" style="margin-bottom:8px">' +
      SS_ORDER.filter((k) => (duck || {})[k]).map((k) =>
        '<span class="chip clickable' + (S.bsSS === k ? " on" : "") + '" data-ss="' +
        k + '">' + k + " — " + U.esc(duck[k].name) + "</span>").join("") + "</div>";
  }

  function drawDuck(duck, S) {
    const host = document.getElementById("bs-duck");
    const d = (duck || {})[S.bsSS || "NE"];
    if (!host) return;
    if (!d) { host.innerHTML = '<div class="empty">Sem série para o subsistema.</div>'; return; }
    const idx = [];
    for (let h = 0; h < 24; h++) idx.push("2026-01-01T" + String(h).padStart(2, "0") + ":00:00");
    Charts.lineChart(host, {
      index: idx, height: 250, compact: true,
      formatTime: (v) => String(v).slice(11, 13) + "h",
      series: [
        { label: "carga com MMGD", values: d.carga_global, color: "muted", style: "dash" },
        { label: "carga supervisionada", values: d.supervisionada, color: "navy" },
        { label: "carga líquida (− eólica e solar centralizadas)", values: d.liquida, color: "teal" },
        { label: "corte apurado", values: d.corte, color: "crimson", width: 2.4 },
      ],
    });
  }

  function loadSideTable(rows, U) {
    if (!rows || !rows.length) {
      return '<div class="empty">Requer a base da seção Fronteira T–D.</div>';
    }
    return '<div class="table-wrap scroll-y" style="max-height:290px"><table><thead><tr>' +
      '<th>SE de fronteira</th><th class="num">MMGD MW</th><th class="num">carga MW</th>' +
      '<th class="num">MMGD ÷ carga</th></tr></thead><tbody>' +
      rows.map((r) => "<tr><td><strong>" + U.esc(r.name) + '</strong> <span class="small faint">' +
        U.esc(r.uf) + " · " + U.esc(r.subsystem) + '</span></td><td class="num">' +
        U.num(r.gd_mw, 0) + '</td><td class="num">' + U.num(r.load_mw, 0) +
        '</td><td class="num">' + U.num(r.penetration, 2) + "</td></tr>").join("") +
      "</tbody></table></div>";
  }

  // ============================================== MÉTODO E SENSIBILIDADE
  V.bessmetodo = {
    title: "BESS: método, cobertura e sensibilidade",
    subtitle: "De onde vem cada número, o que ficou de fora e o quanto o ranking "
            + "depende dos pesos",
    loadingText: "Calculando a estabilidade do ranking…",
    async render(root, S, U) {
      const st = await ready(root, S, U, "bessmetodo");
      if (!st) return;
      const body = await Api.get("bess/metodo");
      const d = body.data;
      root.innerHTML =
        '<div class="grid g3" style="margin-bottom:14px">' +
          U.card("Localização do corte", Object.entries(d.location || {}).map(([k, v]) =>
            U.barRow(k, v, U.pct(v, 1), k === "não localizado" ? "crimson" : "teal")).join(""),
            { note: "Ponto de conexão → SE pelo código de 6 caracteres no cadastro do " +
                    "ONS; recuo pelas usinas (CEG) no SIGA/ANEEL. Sítio não localizado " +
                    "fica no ranking com a MMGD da UF." }) +
          U.card("Razão da restrição", Object.entries(d.reasons || {}).map(([k, v]) =>
            U.barRow(k, v, U.pct(v, 1), k === "ENE" ? "amber" : "teal")).join(""),
            { note: "ENE: excedente energético · CNF: confiabilidade · REL: " +
                    "indisponibilidade externa · PAR: parecer de acesso." }) +
          U.card("Origem", Object.entries(d.origins || {}).map(([k, v]) =>
            U.barRow(k, v, U.pct(v, 1), k === "LOC" ? "crimson" : "teal")).join(""),
            { note: "Origem SIS é aliviada por armazenamento em qualquer ponto do " +
                    "subsistema; LOC, só no ponto." }) +
        "</div>" +
        U.card("Estabilidade do top 10 sob outros pesos", stabTable(d.stability, U),
               { note: "Quantos dos 10 primeiros sítios com os pesos padrão continuam no " +
                       "top 10 em cada cenário. Sítio que resiste a todos é candidato " +
                       "robusto: não depende de uma escolha de peso." }) +
        '<div class="grid g2" style="margin-top:14px">' +
          U.card("Premissas", U.statLines((d.premises || []).map((p) => [p.k, U.esc(p.v)]))) +
          U.card("Limites declarados", '<ul class="actions" style="padding-left:18px">' +
                 (d.limits || []).map((x) => "<li>" + U.esc(x) + "</li>").join("") + "</ul>") +
        "</div>" +
        U.card("Sítios não localizados", unlocTable(d.unlocated, U),
               { hint: U.num((d.unlocated || []).length) + " sítios" }) +
        U.provenanceBlock(body);
    },
  };

  function stabTable(rows, U) {
    return '<div class="table-wrap"><table><thead><tr><th>Cenário de pesos</th>' +
      '<th class="num">Permanecem no top 10</th><th>Top 3 no cenário</th></tr></thead><tbody>' +
      (rows || []).map((x) => "<tr><td>" + U.esc(x.scenario) + '</td><td class="num">' +
        '<span class="chip ' + (x.overlap >= 7 ? "green" : x.overlap >= 5 ? "amber" : "crimson") +
        '">' + x.overlap + " de " + x.top + "</span></td><td class=\"small\">" +
        U.esc((x.top3_names || x.top3 || []).join(" · ")) + "</td></tr>").join("") + "</tbody></table></div>";
  }

  function unlocTable(rows, U) {
    if (!rows || !rows.length) return '<div class="empty">Todos localizados.</div>';
    return '<div class="table-wrap"><table><thead><tr><th>Código</th><th>Sítio</th>' +
      '<th>UF</th><th class="num">Corte na janela (GWh)</th></tr></thead><tbody>' +
      rows.map((r) => '<tr><td class="mono">' + U.esc(r.code) + "</td><td>" +
        U.esc(r.name) + "</td><td>" + U.esc(r.uf) + '</td><td class="num">' +
        U.num(r.cut_gwh, 1) + "</td></tr>").join("") + "</tbody></table></div>";
  }
})();
