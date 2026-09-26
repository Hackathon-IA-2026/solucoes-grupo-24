/* Operação: curva do pato prevista pelo tempo (radiação × onde está a MMGD).
   A interface não calcula nada: apresenta a previsão e o backtest do servidor. */
(function () {
  "use strict";
  const V = window.App.VIEWS;
  const SSL = ["SIN", "SE", "S", "NE", "N"];
  const MCOL = { "ECMWF AIFS": "purple", "ECMWF IFS": "teal", "NOAA GFS": "amber",
                 "média dos modelos": "crimson", "persistência": "muted",
                 "ERA5 (tempo perfeito)": "green", observado: "navy" };
  let POLL = null;

  async function ready(root, S, U) {
    const body = await Api.get("tempo/status", null, { fresh: true });
    const st = body.data;
    if (st.state === "ready") return body;
    root.innerHTML = '<div class="note-strip' + (st.state === "error" ? " warn" : "") + '">' +
      (st.state === "error"
        ? "<strong>Falha ao montar a previsão.</strong> " + U.esc(st.error)
        : "<strong>Buscando o tempo</strong> — ERA5 de 12 meses para calibrar, as " +
          "previsões arquivadas do AIFS, IFS e GFS para o backtest e a previsão dos " +
          "próximos 7 dias. Leva menos de um minuto.") + "</div>" +
      U.card("Progresso", '<div class="small">Etapa: ' + U.esc(st.stage || "—") +
        (st.elapsed_s ? " · " + U.num(st.elapsed_s, 0) + " s" : "") + "</div>");
    clearTimeout(POLL);
    if (st.state !== "error") {
      POLL = setTimeout(() => { if (S.view === "pato") App.render(); }, 2500);
    }
    return null;
  }

  function hoursIdx() {
    const idx = [];
    for (let h = 0; h < 24; h++) idx.push("2026-01-01T" + String(h).padStart(2, "0") + ":00:00");
    return idx;
  }

  function dayLabel(d) {
    const dt = new Date(d + "T12:00:00");
    return ["dom", "seg", "ter", "qua", "qui", "sex", "sáb"][dt.getDay()] + " " +
      d.slice(8, 10) + "/" + d.slice(5, 7);
  }

  V.pato = {
    title: "Curva do pato prevista pelo tempo",
    subtitle: "Radiação solar prevista por modelos de IA e físicos × onde está a MMGD "
            + "→ carga supervisionada dos próximos dias",
    loadingText: "Cruzando a previsão de radiação com a MMGD…",
    async render(root, S, U) {
      const st = await ready(root, S, U);
      if (!st) return;
      const body = await Api.get("tempo/pato");
      const d = body.data;
      S.ptSS = S.ptSS || "SIN";
      const days = (d.operational[S.ptSS] || []);
      if (!S.ptDay || !days.some((x) => x.day === S.ptDay)) {
        S.ptDay = days.length > 1 ? days[1].day : (days[0] || {}).day;
      }
      const sel = days.find((x) => x.day === S.ptDay) || {};
      const met = (d.metrics[S.ptSS] || {});
      const pers = met["persistência"] || {};
      const ens = met["média dos modelos"] || {};
      const gain = pers.mae_mid_mw ? 1 - ens.mae_mid_mw / pers.mae_mid_mw : null;
      const gainR = pers.mae_ramp_mw ? 1 - ens.mae_ramp_mw / pers.mae_ramp_mw : null;

      root.innerHTML =
        '<div class="note-strip"><strong>Como funciona.</strong> A MMGD é a parte da curva ' +
        "mais sensível ao tempo: um dia nublado no Sudeste devolve gigawatts de carga à " +
        "rede ao meio-dia. A capacidade de MMGD por município (cadastro ANEEL) vira " +
        U.num((d.points || []).length) + " células; em cada uma, a radiação e a temperatura " +
        "previstas viram geração. A carga supervisionada prevista é o dia-tipo corrigido " +
        "pela MMGD e pela temperatura — as duas mexem na carga, em sentidos opostos.</div>" +

        '<div class="grid g4" style="margin-bottom:14px">' +
          U.kpi("Barriga do pato · " + dayLabel(sel.day || ""), U.num(sel.min_mw / 1000, 1), "GW",
                S.ptSS + " · mínimo das 10h–15h às " + U.num(sel.min_hour) + "h · incerteza " +
                "entre modelos " + U.num(sel.spread_min_mw / 1000, 1) + " GW", "teal") +
          U.kpi("Rampa do fim da tarde", U.num(sel.ramp_mw / 1000, 1), "GW",
                "do mínimo ao pico das 17h–21h", "crimson") +
          U.kpi("MMGD no pico", U.num(sel.mmgd_peak_mw / 1000, 1), "GW",
                "média dos modelos · " + U.esc(Object.entries(sel.mmgd_models || {})
                  .map(([k, v]) => k.replace("ECMWF ", "").replace("NOAA ", "") + " " +
                       U.num(v / 1000, 1)).join(" · ")), "amber") +
          U.kpi("Ganho sobre a persistência", gain === null ? "—" : U.pct(gain, 0), "",
                "backtest " + S.ptSS + " · erro 9–16h · rampa " +
                (gainR === null ? "—" : U.pct(gainR, 0)), "green") +
        "</div>" +

        '<div class="chips" style="margin-bottom:10px">' +
          SSL.map((k) => '<span class="chip clickable' + (S.ptSS === k ? " on" : "") +
            '" data-ss="' + k + '">' + k + "</span>").join("") +
          '<span style="width:14px"></span>' +
          days.map((x) => '<span class="chip clickable' + (S.ptDay === x.day ? " on" : "") +
            '" data-day="' + x.day + '">' + dayLabel(x.day) + "</span>").join("") +
        "</div>" +

        '<div class="grid g-2-1" style="margin-bottom:14px">' +
          U.card("Carga supervisionada prevista · " + S.ptSS + " · " + dayLabel(sel.day || ""),
                 '<div id="pt-day"></div>',
                 { hint: "média dos modelos, faixa entre modelos e cada modelo",
                   note: "A faixa é a divergência entre AIFS, IFS e GFS: quando os modelos " +
                         "discordam sobre as nuvens, a barriga do pato fica incerta." }) +
          U.card("Semana", '<div id="pt-week"></div>',
                 { hint: "barriga + rampa = pico da noite · GW",
                   note: "Fim de semana: carga menor com a mesma MMGD — a barriga afunda." }) +
        "</div>" +

        '<div class="grid g2" style="margin-bottom:14px">' +
          U.card("MMGD prevista na semana · " + S.ptSS, '<div id="pt-mmgd"></div>',
                 { hint: "geração da MMGD por hora, média dos modelos · MW" }) +
          U.card("Backtest · últimos 14 dias do teste · SIN", '<div id="pt-bt"></div>',
                 { hint: "observado × persistência × média dos modelos",
                   note: "Com as previsões ARQUIVADAS: o que cada modelo de fato previu." }) +
        "</div>" +

        U.card("Validação fora da amostra · " + S.ptSS, metricsTable(met, U),
               { hint: "janela " + U.esc((d.backtest_window || []).join(" a ")) +
                       " · dias úteis e fins de semana, sem feriados",
                 note: "Persistência: o mesmo dia da semana das duas últimas semanas, sem " +
                       "tempo nenhum. ERA5 (tempo perfeito) é o teto — o erro que sobra ali " +
                       "não é do tempo, é do dia-tipo. Nenhum modelo é o melhor em tudo: o " +
                       "AIFS acerta bem a barriga, mas erra mais a rampa da tarde." }) +

        '<div class="grid g3" style="margin-top:14px">' +
          U.card("O tempo mexe nos dois lados", sensTable(d.sensitivity, U),
                 { note: "Sem controlar a temperatura, a sensibilidade da carga à MMGD " +
                         "sai perto de zero: dia de sol aumenta a MMGD, mas também aquece e " +
                         "aumenta a refrigeração. Com a temperatura, β volta a ~0,8 no " +
                         "Sudeste. β e γ são estimados antes da janela de teste." }) +
          U.card("Modelos de tempo", providersTable(d.providers, U),
                 { note: "Todos pelo Open-Meteo. O NVIDIA Earth-2 segue como provedor " +
                         "plugável: o contrato é o mesmo, falta o runtime." }) +
          U.card("Calibração e premissas", U.statLines(
              Object.entries(d.pr || {}).map(([k, v]) => ["PR efetivo · " + k, U.num(v, 2)])
                .concat((d.premises || []).map((p) => [p.k, U.esc(p.v)]))),
                 { note: "PR calibrado para que a MMGD reconstruída com ERA5 reproduza a " +
                         "MMGD média oficial de 2026 (2ª RQ do PLAN 2026-2030). Os valores, " +
                         "0,64 a 0,83, são os de sistemas fotovoltaicos reais." }) +
        "</div>" +
        U.provenanceBlock(body);

      drawDay(sel);
      drawWeek(days, S);
      drawMmgd(days);
      drawBt(d.backtest_sample);
      root.querySelectorAll("[data-ss]").forEach((c) => c.addEventListener("click", () => {
        S.ptSS = c.dataset.ss; App.render();
      }));
      root.querySelectorAll("[data-day]").forEach((c) => c.addEventListener("click", () => {
        S.ptDay = c.dataset.day; App.render();
      }));
    },
  };

  function metricsTable(met, U) {
    const rows = Object.entries(met || {});
    if (!rows.length) return '<div class="empty">Sem backtest.</div>';
    const best = (k) => Math.min.apply(null, rows.filter(([m]) => !m.startsWith("ERA5"))
      .map(([, v]) => v[k]));
    const cell = (v, k) => '<td class="num' + (v[k] === best(k) ? " pos" : "") + '">' +
      App.num(v[k], 0) + "</td>";
    return '<div class="table-wrap"><table><thead><tr><th>Método</th><th class="num">Dias</th>' +
      '<th class="num">Erro 9–16h (MW)</th><th class="num">% da carga</th>' +
      '<th class="num">Erro na barriga</th><th class="num">Viés na barriga</th>' +
      '<th class="num">Erro na rampa</th></tr></thead><tbody>' +
      rows.map(([m, v]) => "<tr><td>" + '<span class="chip ' + (MCOL[m] || "") + '">' +
        U.esc(m) + "</span></td>" + '<td class="num">' + v.days + "</td>" +
        cell(v, "mae_mid_mw") + '<td class="num">' + U.pct(v.mape_mid, 1) + "</td>" +
        cell(v, "mae_min_mw") + '<td class="num">' + U.signed(v.bias_min_mw, 0) + "</td>" +
        cell(v, "mae_ramp_mw") + "</tr>").join("") + "</tbody></table></div>";
  }

  function sensTable(sens, U) {
    return '<div class="table-wrap"><table><thead><tr><th></th><th class="num">β MMGD</th>' +
      '<th class="num">γ MW/°C</th><th class="num">R² só MMGD</th><th class="num">R² com T</th>' +
      "</tr></thead><tbody>" + Object.entries(sens || {}).map(([k, v]) =>
        "<tr><td>" + k + '</td><td class="num">' + U.num(v.beta, 2) + '</td><td class="num">' +
        U.num(v.gamma, 0) + '</td><td class="num faint">' + U.num(v.r2_mmgd_only, 2) +
        '</td><td class="num">' + U.num(v.r2, 2) + "</td></tr>").join("") +
      "</tbody></table></div>";
  }

  function providersTable(ps, U) {
    return '<div class="table-wrap"><table><tbody>' + (ps || []).map((p) =>
      "<tr><td><strong>" + U.esc(p.label) + '</strong><br><span class="small faint">' +
      U.esc(p.note) + "</span></td><td>" + '<span class="chip ' +
      (p.kind === "IA" ? "purple" : "teal") + '">' + U.esc(p.kind) + "</span></td><td>" +
      (p.available ? '<span class="chip green">em uso</span>'
                   : '<span class="chip crimson">indisponível</span>') + "</td></tr>").join("") +
      "</tbody></table></div>";
  }

  function drawDay(sel) {
    const host = document.getElementById("pt-day");
    if (!host || !sel.ensemble) return;
    const series = [{ label: "média dos modelos", color: "crimson", values: sel.ensemble,
                      width: 2.6 }];
    Object.entries(sel.models || {}).forEach(([k, v]) =>
      series.push({ label: k, color: MCOL[k] || "teal", values: v, style: "dash" }));
    Charts.lineChart(host, {
      index: hoursIdx(), height: 280, compact: true, series: series,
      formatTime: (v) => String(v).slice(11, 13) + "h",
      bands: [{ lower: sel.low, upper: sel.high, color: "crimson", opacity: 0.12,
                label: "faixa entre modelos" }],
      spans: [{ from: 10, to: 15, color: "teal",
                label: "barriga", opacity: 0.06 }],
    });
  }

  function drawWeek(days, S) {
    const host = document.getElementById("pt-week");
    if (!host) return;
    Charts.stackedBars(host, {
      labels: days.map((x) => dayLabel(x.day)),
      stacks: [
        { label: "barriga (GW)", color: "teal", values: days.map((x) => x.min_mw / 1000) },
        { label: "rampa (GW)", color: "crimson", values: days.map((x) => x.ramp_mw / 1000) },
      ], height: 280, unit: "GW",
    });
  }

  function drawMmgd(days) {
    const host = document.getElementById("pt-mmgd");
    if (!host) return;
    const series = days.map((x, i) => ({ label: dayLabel(x.day), values: x.mmgd,
      color: ["amber", "crimson", "teal", "purple", "green", "navy", "muted"][i % 7] }));
    Charts.lineChart(host, { index: hoursIdx(), height: 240, compact: true, series: series,
                             formatTime: (v) => String(v).slice(11, 13) + "h" });
  }

  function drawBt(bs) {
    const host = document.getElementById("pt-bt");
    if (!host || !bs || !bs.days || !bs.days.length) return;
    const idx = [], lab = [];
    bs.days.forEach((d) => { for (let h = 0; h < 24; h++) { idx.push(idx.length);
      lab.push(dayLabel(d) + " " + h + "h"); } });
    const flat = (k) => [].concat.apply([], bs.days.map((_, i) =>
      (bs.series[k] || [])[i] || new Array(24).fill(null)));
    Charts.lineChart(host, {
      index: idx, height: 240, compact: true, formatTime: (i) => lab[i] || "",
      series: [
        { label: "observado", color: "navy", values: flat("observado") },
        { label: "persistência", color: "muted", style: "dash", values: flat("persistência") },
        { label: "média dos modelos", color: "crimson", values: flat("média dos modelos") },
      ],
    });
  }
})();
