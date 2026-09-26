/* Investimento: projeção do corte por razão energética e do BESS que ele
   justifica. A interface não calcula nada: as taxas do cenário vão ao servidor. */
(function () {
  "use strict";
  const V = window.App.VIEWS;
  const REF = "PLAN 2026-2030 (2ª RQ)";
  const SC_COLOR = { "PLAN 2026-2030 (2ª RQ)": "amber", "PAR/PEL 2025": "green",
                     "tendência observada": "crimson", personalizado: "purple" };
  const SLIDERS = [
    ["g_vre", "Eólica + solar centralizadas", 0, 0.40, 0.01, "%/ano"],
    ["g_mmgd", "MMGD", 0, 0.60, 0.01, "%/ano"],
    ["g_load", "Carga", 0, 0.08, 0.005, "%/ano"],
    ["flex_gw", "Nova transmissão / flexibilidade", 0, 10, 0.5, "GW/ano"],
  ];
  let POLL = null;

  async function ready(root, S, U) {
    const body = await Api.get("ene/status", null, { fresh: true });
    const st = body.data;
    if (st.state === "ready") return body;
    root.innerHTML =
      '<div class="note-strip' + (st.state === "error" ? " warn" : "") + '">' +
      (st.state === "error"
        ? "<strong>Falha ao montar o histórico.</strong> " + U.esc(st.error)
        : "<strong>Montando o histórico completo de constrained-off</strong> " +
          "(eólica desde 10/2021, fotovoltaica desde 04/2024), o balanço horário " +
          "do ONS e a série de conexões de MMGD da ANEEL. Meses já agregados vêm " +
          "do cache.") + "</div>" +
      U.card("Progresso", U.barRow("etapas", st.overall || 0,
        U.num(st.done) + " de " + U.num(st.total), "teal") +
        '<div class="card-note">Agora: ' + U.esc(st.stage || "—") +
        (st.elapsed_s ? " · " + U.num(st.elapsed_s, 0) + " s" : "") + "</div>");
    clearTimeout(POLL);
    if (st.state !== "error") {
      POLL = setTimeout(() => { if (S.view === "projecao") App.render(); }, 3000);
    }
    return null;
  }

  function pctv(v) { return v === null || v === undefined ? "—" : App.pct(v, 1); }

  V.projecao = {
    title: "Projeção do corte por razão energética",
    subtitle: "Quanto corte ENE vem pela frente, quanto dele a MMGD explica, e "
            + "quanto BESS ele justifica no SIN",
    loadingText: "Calibrando o modelo da carga líquida e projetando os cenários…",
    async render(root, S, U) {
      const st = await ready(root, S, U);
      if (!st) return;
      const body = await Api.get("ene/projecao", S.eneCustom || null);
      const d = body.data;
      const bt = d.backtest || {};
      const ref = d.reference || {};
      const rs = d.rates || {};
      const scen = d.scenarios || [];
      const refS = scen.find((s) => s.name === REF) || scen[0] || { years: [] };
      const lastY = refS.years[refS.years.length - 1] || {};
      const lb = lastY.bess || {};
      const cust = S.eneCustom || (scen.find((s) => s.name === REF) || {}).params || {};

      root.innerHTML =
        '<div class="note-strip"><strong>Por que um modelo físico.</strong> O corte ' +
        "ENE cresceu em saltos; uma tendência ajustada a isso projeta o salto para " +
        "sempre. O que o gera é mensurável hora a hora: a <strong>carga líquida</strong> " +
        "(carga supervisionada − eólica − solar centralizadas potenciais). Quando ela " +
        "cai abaixo do piso que o sistema absorve, a sobra vira corte. A MMGD reduz " +
        "a carga supervisionada e aprofunda a curva do pato: cresce a MMGD, cresce o " +
        "corte — nas usinas centralizadas.</div>" +

        '<div class="grid g4" style="margin-bottom:14px">' +
          U.kpi("Corte ENE+SIS · referência", U.num(ref.ene_twh, 1), "TWh/ano",
                U.esc((ref.from || "").slice(0, 7)) + " a " + U.esc((ref.to || "").slice(0, 7)) +
                " · " + (d.observed_growth === null ? "—" : U.signed(d.observed_growth * 100, 0) +
                "% sobre os 12 meses anteriores"), "crimson") +
          U.kpi("Erro fora da amostra", U.pct(bt.mape_model, 0), "MAPE mensal",
                "ingênuo (mesmo mês do ano anterior): " + pctv(bt.mape_naive) +
                " · viés " + U.signed((bt.test_bias || 0) * 100, 0) + "%", "teal") +
          U.kpi("Corte ENE+SIS em " + (d.years || []).slice(-1)[0],
                U.num(lastY.ene_twh, 1), "TWh/ano",
                "PLAN 2026-2030 · dos quais " +
                U.num(lastY.ene_twh - lastY.ene_sem_mmgd_twh, 1) +
                " TWh pelo crescimento da MMGD", "amber") +
          U.kpi("Potencial técnico de BESS em " + (d.years || []).slice(-1)[0],
                U.num(lb.e_gwh, 0), "GWh",
                U.num(lb.p_gw, 0) + " GW × " + U.num(lb.hours, 0) + " h · recupera " +
                U.num(lb.delivered_twh, 1) + " TWh/ano" +
                (lb.at_grid_limit ? " · no limite da grade" : ""), "navy") +
        "</div>" +

        leituraBlock(scen, d.years, U) +
        '<div style="margin-bottom:14px">' +
          U.card("Histórico e projeção · corte ENE+SIS", '<div id="pj-hist"></div>',
                 { hint: "TWh por mês · projeção = ano de referência escalado",
                   note: "A série fotovoltaica só é publicada a partir de " +
                         U.esc(d.fv_start) + ": antes disso o total do SIN está " +
                         "incompleto, e o modelo não é calibrado ali." }) +
        "</div>" +
        '<div style="margin-bottom:14px">' +
          U.card("Cenários", scenTable(scen, d.years, U),
                 { hint: "corte ENE+SIS e potencial técnico de BESS por ano",
                   note: "Referência: carga global e MMGD da 2ª Revisão Quadrimestral " +
                         "do PLAN 2026-2030 (ONS/EPE/CCEE, 07/08/2026), ano a ano; eólica + " +
                         "solar centralizadas do PAR/PEL 2025 (+2,3% a.a.). " +
                         "“Tendência observada” extrapola as séries e serve só de " +
                         "contraste. " +
                         "Potencial técnico: maior BESS em que o GWh adicional ainda cicla " +
                         "≥ 200 vezes/ano, dimensionado no SIN (o corte ENE+SIS é " +
                         "sistêmico). Não inclui receita nem soluções concorrentes " +
                         "(transmissão, flexibilidade) — é o teto de uso, não uma " +
                         "recomendação de investimento." }) +
        "</div>" +

        '<div class="grid g3" style="margin-bottom:14px">' +
          U.card("Validação fora da amostra", '<div id="pj-bt"></div>',
                 { hint: "ajuste até " + U.esc(bt.split) + " · teste depois",
                   note: "Correlação horária no teste: " + U.num(bt.hourly_corr, 2) +
                         ". Total do teste: " + U.num(bt.test_total_obs_twh, 1) +
                         " TWh observados × " + U.num(bt.test_total_model_twh, 1) +
                         " modelados." }) +
          U.card("A curva do pato que se aprofunda", '<div id="pj-duck"></div>',
                 { hint: "SIN · perfil médio horário · MW",
                   note: "Carga líquida no ano de referência e o corte ENE+SIS. A MMGD " +
                         "desloca a curva para baixo ao meio-dia; a eólica e a solar " +
                         "centralizadas, idem." }) +
          U.card("MMGD conectada (ANEEL)", '<div id="pj-mmgd"></div>',
                 { hint: "GW acumulados por data de conexão",
                   note: "Crescimento em 12 meses até " + U.esc(rs.mmgd_until || "—") + ": " +
                         pctv(rs.mmgd_12m) + " (desacelerando). Os últimos meses são " +
                         "sub-registrados pela defasagem de cadastro." }) +
        "</div>" +

        '<div class="grid g2" style="margin-bottom:14px">' +
          U.card("Cenário personalizado", sliderPanel(cust, U) +
                 '<div style="margin-top:10px;display:flex;gap:8px">' +
                 '<button id="pj-apply">Aplicar</button>' +
                 '<button class="ghost" id="pj-reset">Só os padrões</button></div>',
                 { note: "Parte das taxas médias do PLAN 2026-2030. Nova transmissão ou " +
                         "flexibilidade reduz o piso de carga líquida θ a cada ano." }) +
          U.card("Onde o BESS do último ano entraria", allocTable(d.allocation, U),
                 { hint: "rateio indicativo pelo corte ENE+SIS dos sítios",
                   note: "O corte ENE+SIS é sistêmico: o armazenamento pode estar em " +
                         "qualquer ponto do SIN. O rateio pelos sítios de maior corte " +
                         "é a leitura de onde ele recupera mais sem depender de rede." }) +
        "</div>" +

        '<div class="grid g2">' +
          U.card("Taxas observadas", U.statLines([
              ["Eólica + solar, último ano", pctv(rs.vre_last)],
              ["Eólica + solar, 2 anos (a.a.)", pctv(rs.vre_2y)],
              ["Carga, último ano", pctv(rs.load_last)],
              ["Carga, série completa (a.a.)", pctv(rs.load_6y)],
              ["MMGD, 12 meses", pctv(rs.mmgd_12m)],
              ["MMGD, 24 meses (a.a.)", pctv(rs.mmgd_24m)],
              ["MMGD conectada", U.num(rs.mmgd_gw, 1) + " GW"],
              ["Parâmetros do modelo", "α = " + U.num((d.params || {}).alpha, 2)],
              ["MMGD média oficial " + ((d.plan || {}).ano_base || ""),
               U.num((d.reference || {}).mmgd_plan_mwmed, 0) + " MWmed (estimativa: " +
               U.num((d.reference || {}).mmgd_est_mwmed, 0) + ")"],
            ]), { note: "Eólica e solar do balanço são geração verificada (já descontado " +
                        "o corte): subestimam o crescimento da capacidade." }) +
          U.card("Premissas", U.statLines((d.premises || []).map((p) => [p.k, U.esc(p.v)])),
                 { note: "Limites: um único ano de referência (clima e hidrologia " +
                         "daquele ano); θ constante sem expansão; o corte é a decisão " +
                         "operativa observada; o perfil horário da MMGD é o do envelope, " +
                         "com o nível oficial do PLAN." }) +
        "</div>" +
        U.provenanceBlock(body);

      drawHist(d, scen);
      drawBacktest(bt);
      drawDuck(d.duck_ref);
      drawMmgd(d.mmgd_series);

      root.querySelectorAll("input[data-g]").forEach((inp) => inp.addEventListener("input", () => {
        const o = root.querySelector("#g-" + inp.dataset.g + "-v");
        if (o) o.textContent = fmtSlider(inp.dataset.g, parseFloat(inp.value));
      }));
      root.querySelector("#pj-apply").addEventListener("click", () => {
        const c = {};
        root.querySelectorAll("input[data-g]").forEach((inp) => {
          c[inp.dataset.g] = parseFloat(inp.value);
        });
        S.eneCustom = c; App.render();
      });
      root.querySelector("#pj-reset").addEventListener("click", () => {
        S.eneCustom = null; App.render();
      });
    },
  };

  /* A leitura que decide o investimento, tirada dos próprios cenários. */
  function leituraBlock(scen, years, U) {
    const ref = scen.find((s) => s.name === REF);
    const tend = scen.find((s) => s.name === "tendência observada");
    if (!ref || !tend) return "";
    const r = ref.years[ref.years.length - 1] || {};
    const t = tend.years[tend.years.length - 1] || {};
    const y = (years || []).slice(-1)[0];
    const mm = r.ene_twh ? (r.ene_twh - r.ene_sem_mmgd_twh) / r.ene_twh : null;
    return '<div class="note-strip warn" style="margin-bottom:14px"><strong>Leitura.</strong> ' +
      "Na trajetória oficial, a carga global (+" + U.pct(ref.params.g_load, 1) +
      " a.a., com datacenters) cresce mais que a eólica e solar centralizadas (+" +
      U.pct(ref.params.g_vre, 1) + " a.a., a expansão considerada no PAR/PEL): o corte " +
      "ENE+SIS cai para " + U.num(r.ene_twh, 1) + " TWh em " + y + ", mas " +
      U.pct(mm, 0) + " dele passa a ser devido ao crescimento da MMGD. Se a expansão " +
      "centralizada seguir o ritmo observado, o corte vai a " + U.num(t.ene_twh, 0) +
      " TWh. <strong>O caso de investimento em BESS depende sobretudo do ritmo da expansão " +
      "centralizada frente à carga</strong> — use o cenário personalizado para testar.</div>";
  }

  function fmtSlider(k, v) {
    return k === "flex_gw" ? App.num(v, 1) + " GW/ano" : App.num(v * 100, 1) + "%/ano";
  }

  function sliderPanel(c, U) {
    return SLIDERS.map((s) =>
      '<div class="bar-row" style="grid-template-columns:190px 1fr 80px">' +
      "<span>" + U.esc(s[1]) + "</span>" +
      '<input type="range" data-g="' + s[0] + '" min="' + s[2] + '" max="' + s[3] +
      '" step="' + s[4] + '" value="' + ((c || {})[s[0]] || 0) + '">' +
      '<span class="v" id="g-' + s[0] + '-v">' + fmtSlider(s[0], (c || {})[s[0]] || 0) +
      "</span></div>").join("");
  }

  function scenTable(scen, years, U) {
    return '<div class="table-wrap"><table><thead><tr><th>Cenário</th><th>Ano</th>' +
      '<th class="num">Corte TWh</th><th class="num" title="diferença para a MMGD ' +
      'mantida no nível de referência: atribuição, não cenário">da MMGD TWh</th>' +
      '<th class="num">% da VRE</th><th class="num">BESS GWh</th>' +
      '<th class="num">Recupera TWh</th></tr></thead><tbody>' +
      scen.map((s) => s.years.map((y, i) =>
        "<tr>" + (i === 0 ? '<td rowspan="' + s.years.length + '"><span class="chip ' +
          (SC_COLOR[s.name] || "") + '">' + U.esc(s.name) + '</span><div class="small faint" ' +
          'style="margin-top:4px">VRE ' + U.pct(s.params.g_vre, 0) + " · MMGD " +
          U.pct(s.params.g_mmgd, 0) + " · carga " + U.pct(s.params.g_load, 1) +
          (s.params.flex_gw ? " · flex " + U.num(s.params.flex_gw, 1) + " GW" : "") +
          (s.source ? '<br><span class="faint">' + U.esc(s.source) + "</span>" : "") +
          "</div></td>" : "") +
        "<td>" + (years[i] || "") + '</td><td class="num">' + U.num(y.ene_twh, 1) +
        '</td><td class="num">' + U.num(y.ene_twh - y.ene_sem_mmgd_twh, 1) + "</td>" +
        '<td class="num ' + (y.implausible ? "neg" : "") + '" title="' +
        (y.implausible ? "acima do plausível: sem realimentação econômica" : "") + '">' +
        U.pct(y.cut_share, 0) + (y.implausible ? " ⚠" : "") + "</td>" +
        '<td class="num" title="' + (y.bess && y.bess.p_gw ? U.num(y.bess.p_gw, 0) +
          " GW × " + U.num(y.bess.hours, 0) + " h" : "") + '">' +
        (y.bess && y.bess.e_gwh ? U.num(y.bess.e_gwh, 0) + (y.bess.at_grid_limit ? " ▲" : "") : "—") +
        '</td><td class="num">' + U.num((y.bess || {}).delivered_twh, 1) + "</td></tr>"
      ).join("")).join("") + "</tbody></table></div>" +
      '<div class="card-note">“da MMGD”: quanto do corte do ano se deve ao crescimento ' +
      "da MMGD — a diferença para a mesma projeção com a MMGD no nível de referência. " +
      "É atribuição, não cenário: a MMGD continua crescendo. " +
      "% da VRE: corte ÷ eólica + solar potenciais. ⚠ acima de 25%: " +
      "cenário economicamente inconsistente — o modelo não tem realimentação (ninguém " +
      "segue construindo nesse ritmo com esse corte). ▲ no limite da grade (60 GW × 6 h)." +
      " Passe o mouse no GWh para ver potência × duração.</div>";
  }

  function allocTable(rows, U) {
    if (!rows || !rows.length) return '<div class="empty">Requer a base da seção BESS.</div>';
    return '<div class="table-wrap"><table><thead><tr><th>Sítio</th>' +
      '<th class="num">Parcela do ENE+SIS</th><th class="num">GW</th></tr></thead><tbody>' +
      rows.map((r) => "<tr><td>" + U.esc(r.name) + ' <span class="small faint">' +
        U.esc(r.uf) + '</span></td><td class="num">' + U.pct(r.share, 1) +
        '</td><td class="num">' + U.num(r.gw, 2) + "</td></tr>").join("") +
      "</tbody></table></div>";
  }

  function drawHist(d, scen) {
    const host = document.getElementById("pj-hist");
    if (!host) return;
    const hist = d.history || [];
    const labels = hist.map((h) => h.label);
    const years = d.years || [];
    const nh = hist.length;
    // projecao mensal: perfil do ano de referencia escalado pelo total anual
    const refMonths = hist.slice(-12);
    const refTot = refMonths.reduce((a, h) => a + h.es_eol_twh + h.es_fv_twh, 0) || 1;
    years.forEach((y) => refMonths.forEach((h) =>
      labels.push(h.label.slice(0, 3) + "/" + String(y).slice(2))));
    const series = [
      { label: "ENE+SIS eólica (obs.)", color: "navy",
        values: hist.map((h) => h.es_eol_twh).concat(new Array(years.length * 12).fill(null)) },
      { label: "ENE+SIS fotovoltaica (obs.)", color: "amber",
        values: hist.map((h) => h.es_fv_twh).concat(new Array(years.length * 12).fill(null)) },
    ];
    scen.forEach((s) => {
      const vals = new Array(nh).fill(null);
      s.years.forEach((y) => refMonths.forEach((h) => {
        vals.push(y.ene_twh * (h.es_eol_twh + h.es_fv_twh) / refTot);
      }));
      series.push({ label: "projeção · " + s.name, color: SC_COLOR[s.name] || "teal",
                    values: vals, style: s.name === REF ? "" : "dash" });
    });
    const idx = labels.map((_, i) => i);
    Charts.lineChart(host, {
      index: idx, series: series, height: 290, compact: true,
      formatTime: (i) => labels[i] || "",
    });
  }

  function drawBacktest(bt) {
    const host = document.getElementById("pj-bt");
    if (!host || !bt.monthly) return;
    const m = bt.monthly;
    const idx = m.map((_, i) => i);
    Charts.lineChart(host, {
      index: idx, height: 220, compact: true,
      formatTime: (i) => (m[i] || {}).month || "",
      series: [
        { label: "observado", color: "navy", values: m.map((x) => x.observed_twh) },
        { label: "modelo", color: "crimson", style: "dash", values: m.map((x) => x.model_twh) },
      ],
      spans: [{ from: m.findIndex((x) => x.test), to: m.length - 1, color: "teal",
                label: "teste" }],
    });
  }

  function drawDuck(dr) {
    const host = document.getElementById("pj-duck");
    if (!host || !dr) return;
    const idx = [];
    for (let h = 0; h < 24; h++) idx.push("2026-01-01T" + String(h).padStart(2, "0") + ":00:00");
    Charts.lineChart(host, {
      index: idx, height: 220, compact: true,
      formatTime: (v) => String(v).slice(11, 13) + "h",
      series: [
        { label: "carga líquida", color: "teal", values: dr.nl_mw },
        { label: "piso médio θ", color: "muted", style: "dash",
          values: new Array(24).fill(dr.theta_mean_mw) },
        { label: "corte ENE+SIS", color: "crimson", values: dr.es_mw },
      ],
    });
  }

  function drawMmgd(ms) {
    const host = document.getElementById("pj-mmgd");
    if (!host || !ms) return;
    const idx = ms.months.map((_, i) => i);
    Charts.lineChart(host, {
      index: idx, height: 220, compact: true,
      formatTime: (i) => ms.months[i] || "",
      series: [{ label: "MMGD conectada (GW)", color: "amber", values: ms.cumulative_gw }],
    });
  }
})();
