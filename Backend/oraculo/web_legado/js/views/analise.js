/* Paineis de analise: curtailment, perfis/CLM e triangulacao de evidencias. */
(function () {
  "use strict";
  const V = window.App.VIEWS;

  // ==================================================== 3. CURTAILMENT
  V.curtailment = {
    title: "Curtailment observado",
    subtitle: "Montante, razão e origem da restrição, a partir dos registros de "
            + "constrained-off do ONS",
    loadingText: "Agregando os registros de constrained-off…",
    async render(root, S, U) {
      const body = await Api.risk("d1", "estado", 0);
      const r = body.data;
      const areas = (r.areas || []).slice();
      if (!areas.length) {
        root.innerHTML = '<div class="empty">Sem registros de constrained-off na ' +
          "janela carregada.</div>" + U.provenanceBlock(body);
        return;
      }
      areas.sort((a, b) => (b.history.total_cut_gwh || 0) - (a.history.total_cut_gwh || 0));

      const totalGwh = areas.reduce((s, a) => s + (a.history.total_cut_gwh || 0), 0);
      const peak = Math.max.apply(null, areas.map((a) => a.history.peak_cut_mw || 0));
      const meanOcc = areas.reduce((s, a) => s + (a.history.occurrence_rate || 0), 0) / areas.length;
      const shares = aggregateReasons(areas);

      root.innerHTML =
        '<div class="note-strip">A razão energética (ENE) é a única não ressarcida ' +
        "e é a que mais cresce desde abril de 2025. O O.R.A.C.U.L.O. foca o risco " +
        "por razão energética; o corte é medida técnica para preservar segurança, " +
        "confiabilidade e limites elétricos do SIN.</div>" +

        '<div class="grid g4" style="margin-bottom:14px">' +
          U.kpi("Energia restringida na janela", U.num(totalGwh, 1), "GWh",
                U.num(areas.length) + " áreas com registro", "crimson") +
          U.kpi("Maior corte horário", U.num(peak), "MWmed",
                "pico entre todas as áreas", "amber") +
          U.kpi("Taxa média de ocorrência", U.pct(meanOcc, 1), "",
                "horas com corte acima do limiar, na janela solar", "teal") +
          U.kpi("Participação da razão ENE", U.pct(shares.ENE || 0, 1), "",
                "do montante restringido nas áreas modeladas", "green") +
        "</div>" +

        '<div class="grid g2" style="margin-bottom:14px">' +
          U.card("Montante restringido por área e razão",
                 '<div id="ch-reason"></div>',
                 { note: "Códigos do ONS: REL indisponibilidade externa · CNF " +
                         "confiabilidade · ENE razão energética · PAR parecer de acesso." }) +
          U.card("Probabilidade horária por área",
                 '<div id="ch-heat"></div>',
                 { note: "Cada linha é uma área; cada coluna, uma hora da janela " +
                         "prospectiva. Intensidade proporcional à probabilidade." }) +
        "</div>" +

        U.card("Histórico por área", areaTable(areas, U),
               { hint: "limiar de rótulo = 10% da disponibilidade agregada (p95)" }) +

        '<div class="grid g2" style="margin-top:14px">' +
          U.card("Códigos de razão", dictTable(r.reasons, U)) +
          U.card("Códigos de origem", dictTable(r.origins, U)) +
        "</div>" +
        U.provenanceBlock(body);

      const reasons = ["ENE", "CNF", "REL", "PAR"];
      const colors = { ENE: "green", CNF: "purple", REL: "crimson", PAR: "muted" };
      Charts.stackedBars(document.getElementById("ch-reason"), {
        labels: areas.map((a) => a.area),
        unit: "GWh",
        height: 260,
        stacks: reasons.map((rz) => ({
          label: rz, color: colors[rz],
          values: areas.map((a) =>
            ((a.history.reason_shares || {})[rz] || 0) * (a.history.total_cut_gwh || 0)),
        })),
      });

      Charts.heatStrip(document.getElementById("ch-heat"), {
        rows: areas.map((a) => ({
          label: a.area,
          values: (a.hourly_probability || []).map((v) => v === null ? null : v),
        })),
        raw: areas.map((a) => a.hourly_probability || []),
        colLabel: (c) => {
          const idx = (areas[0].hourly_index || [])[c];
          return idx ? String(idx).slice(11, 13) + "h" : c + "h";
        },
        color: "crimson", seriesLabel: "P(restrição)", digits: 3, height: 260,
      });
    },
  };

  function aggregateReasons(areas) {
    const tot = {};
    let all = 0;
    areas.forEach((a) => {
      const g = a.history.total_cut_gwh || 0;
      all += g;
      const sh = a.history.reason_shares || {};
      Object.keys(sh).forEach((k) => { tot[k] = (tot[k] || 0) + sh[k] * g; });
    });
    const out = {};
    Object.keys(tot).forEach((k) => { out[k] = all ? tot[k] / all : 0; });
    return out;
  }

  function areaTable(areas, U) {
    const rows = areas.map((a) => {
      const h = a.history || {};
      const sh = h.reason_shares || {};
      return "<tr><td><strong>" + U.esc(a.area) + "</strong> " +
        '<span class="small faint">' + U.esc(a.subsystem) + "</span></td>" +
        '<td class="num">' + U.num(h.hours) + "</td>" +
        '<td class="num">' + U.num(h.total_cut_gwh, 2) + "</td>" +
        '<td class="num">' + U.num(h.peak_cut_mw) + "</td>" +
        '<td class="num">' + U.pct(h.occurrence_rate, 1) + "</td>" +
        "<td>" + ["ENE", "CNF", "REL"].map((k) =>
          '<span class="chip ' + (k === "ENE" ? "green" : k === "CNF" ? "" : "crimson") +
          '">' + k + " " + U.pct(sh[k] || 0, 0) + "</span>").join(" ") + "</td>" +
        '<td class="num">' + U.num(a.criticality, 2) + "</td></tr>";
    }).join("");
    return '<div class="table-wrap"><table><thead><tr><th>Área</th>' +
      '<th class="num">Horas</th><th class="num">Corte (GWh)</th>' +
      '<th class="num">Pico (MW)</th><th class="num">Ocorrência</th>' +
      "<th>Composição por razão</th><th class=\"num\">Criticidade</th>" +
      "</tr></thead><tbody>" + rows + "</tbody></table></div>";
  }

  function dictTable(dict, U) {
    const rows = Object.keys(dict || {}).map((k) =>
      "<tr><td>" + U.reasonTag(k) + "</td><td>" + U.esc(dict[k]) + "</td></tr>").join("");
    return '<div class="table-wrap"><table><tbody>' + rows + "</tbody></table></div>";
  }

  // ==================================================== 4. PERFIS / CLM
  V.perfis = {
    title: "Perfis representativos e insumos ao CLM",
    subtitle: "Eixo 1: caracterizar perfis de consumo e a presença da geração "
            + "distribuída para parametrizar modelos equivalentes",
    loadingText: "Construindo perfis por dia-tipo…",
    async render(root, S, U) {
      const body = await Api.profiles(S.area);
      const p = body.data;
      const c = p.clm_inputs || {};

      root.innerHTML =
        '<div class="note-strip">A solução <strong>não executa</strong> fluxo de ' +
        "potência nem estudos de estabilidade. Entrega insumos consistentes para " +
        "os modelos oficiais e para os especialistas do ONS. Referência técnica: " +
        "WECC — Composite Load Model Specification.</div>" +

        '<div class="grid g4" style="margin-bottom:14px">' +
          U.kpi("Fator de carga", U.num(c.load_factor, 3), "",
                "média / máxima no período", "teal") +
          U.kpi("Penetração solar no pico", U.pct(c.solar_penetration_peak, 1), "",
                "participação máxima da MMGD na carga global", "amber") +
          U.kpi("Âncora noturna", U.num(c.night_anchor_mw), "MWmed",
                "carga média nas horas sem geração solar", "green") +
          U.kpi("Rampa máxima", U.num(c.ramp_max_mw_h), "MW/h",
                "amplitude " + U.num(c.amplitude_mw) + " MW · " +
                U.num(c.samples) + " amostras", "crimson") +
        "</div>" +

        '<div class="grid g3" style="margin-bottom:14px">' +
          (p.typedays || []).map((td, i) =>
            U.card(td.label, '<div id="ch-td' + i + '"></div>',
                   { hint: U.num(Math.max.apply(null, td.samples || [0])) + " amostras/hora" })
          ).join("") +
        "</div>" +

        '<div class="grid g-2-1">' +
          U.card("Perfil de MMGD estimada por dia-tipo",
                 '<div id="ch-mmgd"></div>',
                 { note: "A MMGD é estimada, não medida. O perfil é o insumo que " +
                         "qualifica a representação equivalente da geração " +
                         "distribuída nos estudos." }) +
          U.card("Insumos agregados propostos", U.statLines([
            ["Fator de carga", U.num(c.load_factor, 4)],
            ["Penetração solar (pico)", U.pct(c.solar_penetration_peak, 2)],
            ["Âncora noturna", U.num(c.night_anchor_mw, 1) + " MW"],
            ["Mínima supervisionada", U.num(c.min_supervised_mw, 1) + " MW"],
            ["Máxima supervisionada", U.num(c.max_supervised_mw, 1) + " MW"],
            ["Amplitude diária", U.num(c.amplitude_mw, 1) + " MW"],
            ["Rampa máxima", U.num(c.ramp_max_mw_h, 1) + " MW/h"],
            ["Amostras", U.num(c.samples)],
          ]), { note: U.esc(p.note || "") }) +
        "</div>" +
        U.provenanceBlock(body);

      (p.typedays || []).forEach((td, i) => {
        Charts.lineChart(document.getElementById("ch-td" + i), {
          index: td.hours.map((x) => String(x).padStart(2, "0") + "h"),
          height: 210, compact: true, xTicks: 6,
          formatTime: (v) => v,
          bands: [{ lower: td.carga_p10, upper: td.carga_p90, color: "teal",
                    opacity: 0.18, label: "P10–P90" }],
          series: [{ label: "Carga P50", values: td.carga_p50, color: "teal", width: 2 }],
        });
      });

      const colors = ["amber", "green", "purple"];
      Charts.lineChart(document.getElementById("ch-mmgd"), {
        index: (p.typedays[0] || { hours: [] }).hours.map((x) => String(x).padStart(2, "0") + "h"),
        height: 280, compact: true, xTicks: 8, formatTime: (v) => v, zeroBase: true,
        series: (p.typedays || []).map((td, i) => ({
          label: td.label, values: td.mmgd_p50, color: colors[i % 3],
          area: i === 0, areaOpacity: 0.12,
        })),
      });
    },
  };

  // ==================================================== 5. TRIANGULACAO
  V.triangulacao = {
    title: "Triangulação de evidências",
    subtitle: "Três camadas independentes e a lógica de desempate que separa "
            + "defasagem administrativa de instalação não homologada",
    loadingText: "Cruzando realidade física, topologia e cadastro…",
    async render(root, S, U) {
      const body = await Api.triangulation();
      const t = body.data;
      const areas = t.areas || [];
      const tot = {};
      areas.forEach((a) => Object.keys(a.matrix).forEach((k) => {
        tot[k] = (tot[k] || 0) + a.matrix[k];
      }));
      const units = areas.reduce((s, a) => s + a.units_total, 0);
      const lag = tot.lag_de_sistema || 0;
      const nh = tot.nao_homologada || 0;

      root.innerHTML =
        '<div class="note-strip warn">' + U.esc(t.note || "") + "</div>" +

        '<div class="grid g4" style="margin-bottom:14px">' +
          U.kpi("Unidades avaliadas", U.num(units), "",
                U.num(areas.length) + " áreas", "teal") +
          U.kpi("Defasagem de sistema", U.pct(units ? lag / units : 0, 1), "",
                U.num(lag) + " unidades homologadas e ausentes na BDGD", "amber") +
          U.kpi("Não homologadas", U.pct(units ? nh / units : 0, 1), "",
                U.num(nh) + " unidades escaladas como exceção", "crimson") +
          U.kpi("Confirmadas", U.pct(units ? (tot.confirmada || 0) / units : 0, 1), "",
                "três camadas concordam", "green") +
        "</div>" +

        U.card("Lógica de desempate", matrixHtml(t, tot, U),
               { note: "Somente <strong>confirmada</strong> e <strong>defasagem de " +
                       "sistema</strong> entram no fator de correção de capacidade. " +
                       "Instalação não homologada é reportada em separado, nunca " +
                       "somada silenciosamente." }) +

        '<div class="grid g2" style="margin-top:14px;margin-bottom:14px">' +
          U.card("Três camadas de evidência", layersTable(t.layers, U)) +
          U.card("Fator de correção por área", correctionTable(areas, U),
                 { note: "A capacidade implicada vem do déficit diurno observado " +
                         "na carga; uma razão muito acima de 1 sugere cadastro " +
                         "defasado." }) +
        "</div>" +

        U.card("Amostra de unidades classificadas", sampleTable(t.sample, U),
               { hint: "40 primeiras de " + U.num(units) }) +
        U.provenanceBlock(body);
    },
  };

  function matrixHtml(t, tot, U) {
    const cls = t.classes || {};
    const cell = (key, kind) => {
      const c = cls[key] || {};
      return '<div class="mcell ' + kind + '"><h4>' + U.esc(c.label || key) +
        '</h4><div class="n">' + U.num(tot[key] || 0) + "</div><p>" +
        U.esc(c.note || "") + "</p></div>";
    };
    return '<div class="matrix">' +
      '<div class="mh"></div><div class="mh">Consta na ANEEL</div><div class="mh">Não consta</div>' +
      '<div class="rh">Detectado no satélite</div>' +
      '<div class="mcell ok"><h4>' + U.esc((cls.confirmada || {}).label || "") +
        ' · ' + U.esc((cls.lag_de_sistema || {}).label || "") + "</h4>" +
        '<div class="n">' + U.num((tot.confirmada || 0) + (tot.lag_de_sistema || 0)) +
        "</div><p>" + U.esc((cls.lag_de_sistema || {}).note || "") + "</p></div>" +
      cell("nao_homologada", "bad") +
      '<div class="rh">Não detectado</div>' +
      cell("cadastro_sem_evidencia", "warn") +
      cell("sem_evidencia", "neutral") +
      "</div>";
  }

  function layersTable(layers, U) {
    const rows = (layers || []).map((l) =>
      "<tr><td><strong>" + U.num(l.layer) + " · " + U.esc(l.name) + "</strong><br>" +
      '<span class="small faint">' + U.esc(l.source) + "</span></td>" +
      "<td>" + U.esc(l.question) + "</td>" +
      '<td><span class="chip teal">' + U.esc(l.cadence) + "</span></td>" +
      '<td class="small muted">' + U.esc(l.limitation) + "</td></tr>").join("");
    return '<div class="table-wrap"><table><thead><tr><th>Camada</th>' +
      "<th>Pergunta</th><th>Cadência</th><th>Limitação declarada</th>" +
      "</tr></thead><tbody>" + rows + "</tbody></table></div>";
  }

  function correctionTable(areas, U) {
    const rows = (areas || []).map((a) =>
      "<tr><td><strong>" + U.esc(a.area) + "</strong></td>" +
      '<td class="num">' + U.num(a.units_total) + "</td>" +
      '<td class="num">' + U.num(a.capacity_declared_mw, 1) + "</td>" +
      '<td class="num">' + U.num(a.capacity_corrected_mw, 1) + "</td>" +
      '<td class="num"><strong>' + U.num(a.correction_factor, 3) + "</strong></td>" +
      '<td class="num">' + U.num(a.capacity_unhomologated_mw, 1) + "</td>" +
      '<td class="num">' + U.num(a.implied_capacity_mwp) + "</td>" +
      '<td class="num">' + U.pct(a.coverage, 0) + "</td></tr>").join("");
    return '<div class="table-wrap"><table><thead><tr><th>Área</th>' +
      '<th class="num">Unid.</th><th class="num">Declarada MW</th>' +
      '<th class="num">Corrigida MW</th><th class="num">Fator</th>' +
      '<th class="num">Não homol. MW</th><th class="num">Implicada MWp</th>' +
      '<th class="num">Cobertura</th></tr></thead><tbody>' + rows +
      "</tbody></table></div>";
  }

  function sampleTable(sample, U) {
    const badge = { confirmada: "green", lag_de_sistema: "amber",
                    nao_homologada: "crimson", cadastro_sem_evidencia: "",
                    sem_evidencia: "" };
    const rows = (sample || []).map((u) =>
      "<tr><td class=\"mono small\">" + U.esc(u.unit_id) + "</td>" +
      "<td>" + U.esc(u.area) + "</td>" +
      '<td class="num">' + U.num(u.capacity_kwp, 1) + "</td>" +
      "<td>" + yesno(u.detected) + "</td>" +
      "<td>" + yesno(u.in_bdgd) + "</td>" +
      "<td>" + yesno(u.in_aneel) + "</td>" +
      '<td><span class="chip ' + (badge[u.classification] || "") + '">' +
        U.esc(u.label) + "</span></td>" +
      '<td class="small">' + (u.counts_in_correction
        ? '<span class="pos">entra</span>' : '<span class="neg">não entra</span>') +
      "</td></tr>").join("");
    return '<div class="table-wrap scroll-y"><table><thead><tr><th>Unidade</th>' +
      '<th>Área</th><th class="num">kWp</th><th>Satélite</th><th>BDGD</th>' +
      "<th>ANEEL</th><th>Classificação</th><th>Correção</th>" +
      "</tr></thead><tbody>" + rows + "</tbody></table></div>";
  }

  function yesno(v) {
    return v ? '<span class="pos">sim</span>' : '<span class="faint">não</span>';
  }
})();
