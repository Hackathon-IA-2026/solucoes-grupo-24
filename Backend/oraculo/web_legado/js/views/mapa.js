/* Mapa Inteligente de Perfis de Carga e Geração Distribuída.
   Desafio Radix + AXIA + Cepel. Três painéis novos: mapa, visão e classes.
   Nenhuma view anterior é alterada. */
(function () {
  "use strict";
  const V = window.App.VIEWS;

  const CLASS_COLORS = {
    residencial: "teal", comercial: "navy",
    industrial: "amber", rural: "green",
  };
  const LEVEL_COLORS = { baixa: "green", "média": "amber", alta: "crimson" };

  function levelChip(lv) {
    const c = LEVEL_COLORS[lv] || "";
    return '<span class="chip ' + c + '">' + App.esc(lv || "—") + "</span>";
  }

  function weightBars(weights, U) {
    const keys = ["residencial", "comercial", "industrial", "rural"];
    return keys.map((k) => U.barRow(k, (weights || {})[k] || 0,
      U.pct((weights || {})[k] || 0, 1), CLASS_COLORS[k])).join("");
  }

  // ============================================== 8. MAPA INTELIGENTE
  V.mapa = {
    title: "Mapa Inteligente de perfis de carga e GD",
    subtitle: "Para cada subestação georreferenciada: perfil predominante de "
            + "consumo e indicador de presença de geração distribuída",
    loadingText: "Carregando subestações do ONS e analisando as amostras…",
    async render(root, S, U) {
      const limit = S.mapaLimit || 12;
      const body = await Api.get("mapa/substations", {
        uf: S.mapaUf || "", limit: limit, frontier_only: 1,
      });
      const d = body.data;
      const rows = d.rows || [];
      if (!rows.length) {
        root.innerHTML = '<div class="empty">Nenhuma subestação de fronteira ' +
          "no filtro atual.</div>" + U.provenanceBlock(body);
        return;
      }
      if (!S.mapaSel || !rows.some((r) => r.sub_id === S.mapaSel)) {
        S.mapaSel = rows[0].sub_id;
      }
      const sm = d.summary || {};
      const rr = d.registry_report || {};

      root.innerHTML =
        '<div class="note-strip">Entrada: <strong>lista de subestações ' +
        "georreferenciadas</strong> do conjunto <span class=\"mono\">subestacao" +
        "</span> do ONS — " + U.num(rr.unique_substations) + " subestações, " +
        U.num(rr.frontier_substations) + " com transformação de fronteira com a " +
        "distribuição. Saída, por subestação: composição por classe de consumo " +
        "e nível de penetração de MMGD.</div>" +

        '<div class="grid g4" style="margin-bottom:14px">' +
          U.kpi("Subestações de fronteira", U.num(d.total), "",
                "filtro atual · " + U.num(d.returned) + " analisadas nesta página",
                "teal") +
          U.kpi("Classe dominante no lote",
                topLabel(sm.by_class), "",
                classSpread(sm.by_class, U), "navy") +
          U.kpi("Penetração de MMGD",
                topLabel(sm.by_mmgd_level), "",
                levelSpread(sm.by_mmgd_level, U), "amber") +
          U.kpi("Qualidade da detecção", U.num(sm.detector_f1_mean, 3), "F1",
                "IoU de máscara " + U.num(sm.detector_mask_iou_mean, 3) +
                " · medido contra verdade fundamental", "green") +
        "</div>" +

        '<div class="chips" style="margin-bottom:12px">' +
          '<span class="chip clickable' + (!S.mapaUf ? " on" : "") +
          '" data-uf="">todas as UF</span>' +
          (d.ufs || []).map((u) =>
            '<span class="chip clickable' + (S.mapaUf === u ? " on" : "") +
            '" data-uf="' + u + '">' + u + "</span>").join("") +
        "</div>" +

        '<div class="grid g-1-2" style="margin-bottom:14px">' +
          U.card("Subestações analisadas",
                 '<div class="table-wrap scroll-y" id="sub-table"></div>',
                 { hint: "clique para abrir o detalhe" }) +
          '<div id="sub-detail"></div>' +
        "</div>" +

        '<div class="grid g2">' +
          U.card("Pipeline replicável", pipelineList(d.pipeline, U),
                 { note: "A cada atualização das bases, o mesmo pipeline " +
                         "reproduz o mapa. Amostragem de " +
                         U.num(d.analysis_gsd_m, 2) + " m/pixel, " +
                         U.num(d.samples_per_substation) + " janelas por " +
                         "subestação." }) +
          U.card("Faixas do indicador de MMGD", binsTable(d, U),
                 { note: "Ancoragem: unidade com MMGD tem tipicamente 5 kWp; " +
                         "densidade construída urbana de 800 a 2.000 telhados " +
                         "por km²; penetração média brasileira da ordem de 3% " +
                         "das unidades consumidoras." }) +
        "</div>" +
        U.provenanceBlock(body);

      drawSubTable(rows, S, U);
      await drawDetail(S, U);

      root.querySelectorAll("[data-uf]").forEach((c) =>
        c.addEventListener("click", () => {
          S.mapaUf = c.dataset.uf; S.mapaSel = null; App.render();
        }));
    },
  };

  function topLabel(obj) {
    const e = Object.entries(obj || {});
    if (!e.length) return "—";
    e.sort((a, b) => b[1] - a[1]);
    return App.esc(e[0][0]);
  }

  function classSpread(obj, U) {
    return Object.entries(obj || {}).map(([k, v]) =>
      App.esc(k) + " " + U.num(v)).join(" · ") || "—";
  }

  function levelSpread(obj, U) {
    return Object.entries(obj || {}).map(([k, v]) =>
      App.esc(k) + " " + U.num(v)).join(" · ") || "—";
  }

  function pipelineList(steps, U) {
    return "<ol class=\"actions\" style=\"padding-left:20px\">" +
      (steps || []).map((s) => "<li>" + U.esc(s) + "</li>").join("") + "</ol>";
  }

  function binsTable(d, U) {
    const rows = (d.penetration_bins || []).map((b) =>
      "<tr><td>" + levelChip(b.level) + '</td><td class="num">' +
      U.num(b.from_kwp_km2) + '</td><td class="num">' +
      (b.to_kwp_km2 === null ? "—" : U.num(b.to_kwp_km2)) + "</td></tr>").join("");
    const bu = Object.entries(d.built_up_fraction || {}).map(([k, v]) =>
      '<span class="chip">' + App.esc(k) + " " + U.pct(v, 0) + "</span>").join(" ");
    return '<div class="table-wrap"><table><thead><tr><th>Nível</th>' +
      '<th class="num">de (kWp/km²)</th><th class="num">até</th></tr></thead>' +
      "<tbody>" + rows + "</tbody></table></div>" +
      '<div class="card-note">Fração construída assumida na extrapolação: ' +
      bu + "</div>";
  }

  function drawSubTable(rows, S, U) {
    const host = document.getElementById("sub-table");
    const body = rows.map((r) =>
      '<tr data-sub="' + U.esc(r.sub_id) + '" class="' +
      (r.sub_id === S.mapaSel ? "sel" : "") + '" style="cursor:pointer">' +
      "<td><strong>" + U.esc(r.name) + "</strong><br>" +
      '<span class="small faint">' + U.esc(r.uf) + " · " + U.esc(r.sub_id) +
      " · " + U.num(r.voltage_kv) + "/" + U.num(r.secondary_kv) + " kV</span></td>" +
      '<td class="small">' + U.esc(r.class_label || "—") + "<br>" +
      '<span class="faint">conf. ' + U.pct(r.class_confidence, 0) + "</span></td>" +
      "<td>" + levelChip(r.mmgd_level) + "<br>" +
      '<span class="small faint mono">' + U.num(r.mmgd_kwp_per_km2) +
      " kWp/km²</span></td></tr>").join("");
    host.innerHTML = "<table><thead><tr><th>Subestação</th>" +
      "<th>Classe predominante</th><th>MMGD</th></tr></thead><tbody>" +
      body + "</tbody></table>";
    host.querySelectorAll("[data-sub]").forEach((tr) =>
      tr.addEventListener("click", async () => {
        S.mapaSel = tr.dataset.sub;
        host.querySelectorAll("tr").forEach((x) => x.classList.remove("sel"));
        tr.classList.add("sel");
        await drawDetail(S, U);
      }));
  }

  async function drawDetail(S, U) {
    const host = document.getElementById("sub-detail");
    if (!host) return;
    host.innerHTML = App.loading("Analisando a amostra…");
    let body;
    try {
      body = await Api.get("mapa/substations/" + encodeURIComponent(S.mapaSel));
    } catch (err) {
      host.innerHTML = App.errorBlock(err);
      return;
    }
    const d = body.data;
    const s = d.substation, lc = d.load_class, m = d.mmgd, an = d.clm;
    const ev = d.evaluation || {};
    const mt = ev.match || {};
    const vis = d.vision || {};

    host.innerHTML = U.card(
      "Detalhe · " + U.esc(s.name) + " (" + U.esc(s.uf) + ")",
      '<div class="grid g2" style="gap:12px">' +
        "<div>" +
          '<div class="kpi-label" style="margin-bottom:6px">Amostra de ' +
          'ortoimagem com as detecções</div>' +
          '<img id="scene-img" src="' + U.esc(d.image_url) +
          '" style="width:100%;border-radius:6px;border:1px solid var(--line)" ' +
          'alt="amostra de ortoimagem com painéis detectados">' +
          '<div class="chips" style="margin-top:8px">' +
            '<span class="chip clickable on" data-img="">detecções</span>' +
            '<span class="chip clickable" data-img="?truth=1&tiles=1">' +
            "verdade + ladrilhos</span>" +
            '<span class="chip clickable" data-img="?channel=azul">' +
            "índice de azul</span>" +
            '<span class="chip clickable" data-img="?channel=borda">' +
            "densidade de borda</span>" +
          "</div>" +
        "</div>" +
        "<div>" +
          '<div class="kpi-label">1 · Perfil predominante de consumo</div>' +
          '<div style="font-size:17px;font-weight:650;margin:4px 0 8px">' +
          U.esc(lc.label) + ' <span class="small muted">confiança ' +
          U.pct(lc.confidence, 0) + "</span></div>" +
          weightBars(lc.weights, U) +
          '<div class="kpi-label" style="margin-top:14px">' +
          "2 · Presença de geração distribuída</div>" +
          '<div style="font-size:17px;font-weight:650;margin:4px 0 8px">' +
          levelChip(m.level) + " " + U.num(m.kwp_per_km2) +
          ' <span class="small muted">kWp/km² · confiança ' +
          U.pct(m.confidence, 0) + "</span></div>" +
          U.statLines([
            ["Painéis detectados na amostra", U.num(m.panels)],
            ["Área de painel", U.num(m.panel_area_m2, 1) + " m²"],
            ["Telhados na amostra", U.num(m.roofs_detected)],
            ["Penetração em telhados", U.pct(m.roof_penetration, 1)],
            ["Amostra", U.num(m.sample_km2, 3) + " km² de " +
                        U.num(m.area_km2, 1) + " km²"],
            ["Total extrapolado", U.num(m.kwp_total, 0) + " kWp"],
            ["Adequação da amostra", U.esc(m.sample_adequacy || "—")],
            ["Tipo III na UF", U.num(m.tipo3_mw_uf, 1) + " MW (" +
                               U.num(m.tipo3_count_uf) + " usinas)"],
          ]) +
        "</div>" +
      "</div>",
      { hint: U.num(s.frontier_mva) + " MVA de fronteira · raio " +
              U.num(s.radius_km, 2) + " km · morfologia " + U.esc(d.urban_hint),
        note: (d.notes || []).map(U.esc).join(" ") }) +

      '<div class="grid g3" style="margin-top:14px">' +
        U.card("Desempenho do detector nesta amostra", U.statLines([
          ["Precisão", U.pct(mt.precision, 1)],
          ["Revocação", U.pct(mt.recall, 1)],
          ["F1", U.num(mt.f1, 3)],
          ["IoU médio das caixas", U.num(mt.iou_mean, 3)],
          ["IoU de máscara", U.num(ev.mask_iou, 3)],
          ["Verdadeiros / falsos+ / falsos−",
            U.num(mt.tp) + " / " + U.num(mt.fp) + " / " + U.num(mt.fn)],
          ["Erro de área (calibrado)", U.signed((ev.area || {}).rel_error, 3)],
          ["Erro de área (bruto)", U.signed((ev.area_raw || {}).rel_error, 3)],
        ]), { note: "Verdade fundamental da ortoimagem sintética: estas são " +
                    "medições reais do detector." }) +
        U.card("Desvio em relação ao subsistema", U.statLines([
          ["Desvio da média regional", U.num(lc.deviation_from_regional, 3)],
          ["Peso do prior regional", U.pct(lc.weight_load, 0)],
          ["Peso da evidência local", U.pct(lc.weight_morphology, 0)],
          ["Classe pelo prior", U.esc((lc.regional_prior || {}).label || "—")],
          ["R² do ajuste do prior", U.num((lc.regional_prior || {}).r2, 3)],
          ["Classe pela morfologia",
            U.esc((lc.local_evidence || {}).label || "—")],
          ["Área média de telhado",
            U.num((lc.local_evidence || {}).mean_footprint_m2, 1) + " m²"],
          ["Telhados por km²",
            U.num((lc.local_evidence || {}).density_per_km2, 0)],
        ]), { note: U.esc(lc.prior_role || "") }) +
        U.card("Insumo proposto ao Modelo de Carga Composta", U.statLines([
          ["Fração de motor estimada", U.num(an.fracao_motor_estimada, 3)],
          ["MMGD na área", U.num(an.mmgd_kwp_na_area, 0) + " kWp"],
          ["Penetração", U.esc(an.mmgd_penetracao)],
          ["Sinalizar GD no modelo",
            an.distributed_generation_flag ? '<span class="pos">sim</span>'
                                           : '<span class="faint">não</span>'],
          ["Confiança", U.pct(an.confianca, 0)],
        ]), { note: U.esc(an.aviso) }) +
      "</div>" +

      U.card("Detecções georreferenciadas", detTable(vis, U),
             { hint: U.num(vis.kept_count) + " mantidas de " +
                     U.num(vis.raw_count) + " brutas · " +
                     U.num(vis.duplicates_removed) + " duplicatas removidas na " +
                     "costura entre " + U.num(vis.tiles) + " ladrilhos" });

    host.querySelectorAll("[data-img]").forEach((c) =>
      c.addEventListener("click", () => {
        host.querySelectorAll("[data-img]").forEach((x) => x.classList.remove("on"));
        c.classList.add("on");
        document.getElementById("scene-img").src = d.image_url + c.dataset.img;
      }));
  }

  function detTable(vis, U) {
    const rows = (vis.detections || []).slice(0, 24).map((x, i) =>
      '<tr><td class="num">' + (i + 1) + "</td>" +
      '<td class="num">' + U.num(x.score, 3) + "</td>" +
      '<td class="mono small">' + U.num(x.lat, 5) + ", " + U.num(x.lon, 5) + "</td>" +
      '<td class="num">' + U.num(x.area_m2, 1) + "</td>" +
      '<td class="num">' + U.num(x.kwp, 2) + "</td>" +
      '<td class="num">' + U.num(x.rectangularity, 3) + "</td>" +
      '<td class="num">' + U.num(x.blue_index, 3) + "</td>" +
      '<td class="num">' + U.num(x.edge_density, 3) + "</td></tr>").join("");
    return '<div class="table-wrap scroll-y"><table><thead><tr>' +
      '<th class="num">#</th><th class="num">conf.</th><th>lat, lon</th>' +
      '<th class="num">área m²</th><th class="num">kWp</th>' +
      '<th class="num">retang.</th><th class="num">azul</th>' +
      '<th class="num">borda</th></tr></thead><tbody>' +
      (rows || '<tr><td colspan="8">nenhuma detecção nesta amostra</td></tr>') +
      "</tbody></table></div>";
  }

  // ============================================== 9. VISÃO COMPUTACIONAL
  V.visao = {
    title: "Visão computacional sobre imagem de satélite",
    subtitle: "Detecção de painéis fotovoltaicos: pipeline, backends e "
            + "desempenho medido contra verdade fundamental",
    loadingText: "Executando o banco de ensaio do detector…",
    async render(root, S, U) {
      const body = await Api.get("mapa/vision");
      const d = body.data;
      const ag = d.aggregate || {};
      const ref = d.reference || {};
      const cal = d.area_calibration || {};
      const yolo = (d.backends || []).find((b) => b.kind === "yolo") || {};
      const clas = (d.backends || []).find((b) => b.kind === "classico") || {};

      root.innerHTML =
        '<div class="note-strip warn"><strong>Sobre o YOLO:</strong> ' +
        U.esc(d.yolo_note) + "</div>" +

        '<div class="grid g4" style="margin-bottom:14px">' +
          U.kpi("Precisão", U.pct(ag.precision, 1), "",
                U.num(ag.scenes) + " cenas · 4 classes urbanas × 3 sementes",
                "teal") +
          U.kpi("Revocação", U.pct(ag.recall, 1), "",
                "F1 " + U.num(ag.f1, 3), "green") +
          U.kpi("IoU de máscara", U.num(ag.mask_iou, 3), "",
                "AP " + U.num(ag.average_precision, 3), "navy") +
          U.kpi("Erro de área", U.signed(ag.area_rel_error, 3), "",
                "bruto " + U.signed(ag.area_rel_error_raw, 3) +
                " · calibração " + U.num(cal.factor, 2) + "×", "amber") +
        "</div>" +

        '<div class="grid g2" style="margin-bottom:14px">' +
          U.card("Backends de detecção", backendsTable(d.backends, U),
                 { note: "Os dois implementam a mesma interface. O " +
                         "ladrilhamento, a NMS, a deduplicação na costura e a " +
                         "georreferência são compartilhados e testados: trocar " +
                         "o backend não muda mais nada no pipeline." }) +
          U.card("Etapas do detector ativo", pipelineList(d.pipeline, U),
                 { hint: U.esc(clas.runtime || "") }) +
        "</div>" +

        '<div class="grid g-2-1" style="margin-bottom:14px">' +
          U.card("Cena de referência",
                 '<img id="bench-img" src="' + U.esc(ref.image_url) +
                 '" style="width:100%;border-radius:6px;border:1px solid var(--line)" ' +
                 'alt="cena de referência com detecções">' +
                 '<div class="chips" style="margin-top:8px">' +
                   '<span class="chip clickable on" data-b="">detecções</span>' +
                   '<span class="chip clickable" data-b="?truth=1&tiles=1">' +
                   "verdade + ladrilhos + falsos negativos</span>" +
                   '<span class="chip clickable" data-b="?channel=azul">' +
                   "índice de azul</span>" +
                   '<span class="chip clickable" data-b="?channel=borda">' +
                   "densidade de borda</span>" +
                   '<span class="chip clickable" data-b="?channel=luminancia">' +
                   "luminância</span>" +
                 "</div>",
                 { hint: U.num(ref.truth) + " painéis reais · " +
                         U.num(ref.pred) + " detectados",
                   note: "Teal: detecção. Âmbar: verdade fundamental. " +
                         "Carmim: painel real não detectado. Os canais de " +
                         "característica mostram <em>por que</em> o detector " +
                         "marcou o que marcou." }) +
          U.card("Curva precisão × revocação", '<div id="ch-pr"></div>',
                 { note: "Varredura do limiar de confiança na cena de " +
                         "referência." }) +
        "</div>" +

        U.card("Desempenho por classe urbana e semente", benchTable(d.rows, U),
               { note: U.esc(d.synthetic_note) }) +

        '<div class="grid g2" style="margin-top:14px">' +
          U.card("Calibração de área", U.statLines([
            ["Fator aplicado", U.num(cal.factor, 3) + "×"],
            ["Watt por m² de módulo", U.num(cal.watt_per_m2) + " W/m²"],
            ["Erro bruto médio", U.signed(ag.area_rel_error_raw, 4)],
            ["Erro calibrado médio", U.signed(ag.area_rel_error, 4)],
          ]), { note: "Origem: " + U.esc(cal.source) + ". A área propaga para " +
                      "o kWp e daí para o indicador de MMGD, então o viés " +
                      "precisa ser medido e corrigido, não ignorado." }) +
          U.card("Parâmetros do YOLOv8-seg", paramsTable(yolo.params, U),
                 { note: yolo.available
                     ? "Runtime disponível: " + U.esc(yolo.runtime)
                     : "Motivo da indisponibilidade: " + U.esc(yolo.reason) }) +
        "</div>" +
        U.provenanceBlock(body);

      const pr = (d.pr_curve || []).filter((p) =>
        p.precision !== null && p.recall !== null);
      Charts.scatter(document.getElementById("ch-pr"), {
        points: pr.map((p) => ({
          x: p.recall, y: p.precision,
          label: "limiar " + Charts.fmt(p.threshold, 2) + " · n=" + p.n_pred,
        })),
        xDomain: [0, 1.02], yDomain: [0, 1.02], height: 250,
        xLabel: "revocação", yLabel: "precisão", digits: 3, xDigits: 2,
        xAxisLabel: "revocação →", color: "teal", r: 5,
      });

      root.querySelectorAll("[data-b]").forEach((c) =>
        c.addEventListener("click", () => {
          root.querySelectorAll("[data-b]").forEach((x) => x.classList.remove("on"));
          c.classList.add("on");
          document.getElementById("bench-img").src =
            "/api/mapa/bench.png" + c.dataset.b;
        }));
    },
  };

  function backendsTable(backends, U) {
    const rows = (backends || []).map((b) =>
      "<tr><td><strong>" + U.esc(b.name) + "</strong><br>" +
      '<span class="small faint">' + U.esc(b.runtime) + "</span></td>" +
      "<td>" + (b.available
        ? '<span class="chip green">ativo</span>'
        : '<span class="chip amber">indisponível</span>') + "</td>" +
      '<td class="small muted">' + U.esc(b.reason || "—") + "</td></tr>").join("");
    return '<div class="table-wrap"><table><thead><tr><th>Backend</th>' +
      "<th>Estado</th><th>Observação</th></tr></thead><tbody>" + rows +
      "</tbody></table></div>";
  }

  function paramsTable(params, U) {
    const rows = Object.entries(params || {}).map(([k, v]) =>
      '<tr><td class="mono small">' + U.esc(k) + '</td><td class="num">' +
      U.esc(String(v)) + "</td></tr>").join("");
    return '<div class="table-wrap"><table><tbody>' +
      (rows || '<tr><td>—</td></tr>') + "</tbody></table></div>";
  }

  function benchTable(rows, U) {
    const body = (rows || []).map((r) =>
      "<tr><td>" + U.esc(r.urban_class) + '</td><td class="num">' +
      U.num(r.seed) + '</td><td class="num">' + U.num(r.truth) +
      '</td><td class="num">' + U.num(r.pred) +
      '</td><td class="num">' + U.pct(r.precision, 1) +
      '</td><td class="num">' + U.pct(r.recall, 1) +
      '</td><td class="num">' + U.num(r.f1, 3) +
      '</td><td class="num">' + U.num(r.mask_iou, 3) +
      '</td><td class="num">' + U.signed(r.area_rel_error, 3) +
      '</td><td class="num">' + U.num(r.tiles) +
      '</td><td class="num">' + U.num(r.duplicates_removed) +
      '</td><td class="num">' + U.num(r.total_kwp, 1) + "</td></tr>").join("");
    return '<div class="table-wrap"><table><thead><tr><th>Classe urbana</th>' +
      '<th class="num">semente</th><th class="num">verdade</th>' +
      '<th class="num">pred.</th><th class="num">precisão</th>' +
      '<th class="num">revocação</th><th class="num">F1</th>' +
      '<th class="num">IoU másc.</th><th class="num">erro área</th>' +
      '<th class="num">ladrilhos</th><th class="num">dupl. rem.</th>' +
      '<th class="num">kWp</th></tr></thead><tbody>' + body +
      "</tbody></table></div>";
  }

  // ============================================== 10. CLASSES DE CONSUMO
  V.classes = {
    title: "Classes de consumo e assinatura da curva",
    subtitle: "Perfis canônicos e decomposição da curva de carga verificada "
            + "por mínimos quadrados não negativos",
    loadingText: "Decompondo a curva de carga por subsistema…",
    async render(root, S, U) {
      const body = await Api.get("mapa/classes");
      const d = body.data;
      const canon = d.canonical || {};
      const subs = d.subsystems || [];

      root.innerHTML =
        '<div class="note-strip">' + U.esc(d.note) + "</div>" +

        '<div class="grid g-2-1" style="margin-bottom:14px">' +
          U.card("Perfis canônicos por classe", '<div id="ch-canon"></div>',
                 { note: U.esc(canon.note) }) +
          U.card("Assinatura de fim de semana", weekendTable(canon, U),
                 { note: "Segunda assinatura, independente da forma horária: " +
                         "é o que separa comercial de industrial quando as " +
                         "duas têm platô diurno." }) +
        "</div>" +

        '<div class="grid g2" style="margin-bottom:14px">' +
          subs.map((s, i) =>
            U.card(U.esc(s.subsystem) + " · " + U.esc(s.name),
                   '<div id="ch-sub' + i + '"></div>' +
                   '<div style="margin-top:10px">' + weightBars(s.weights, U) +
                   "</div>",
                   { hint: U.esc(s.label) + " · R² " + U.num(s.r2, 3) +
                           " (" + U.esc(s.fit_quality || "—") + ")",
                     note: s.fit_warning ? U.esc(s.fit_warning) : "" })
          ).join("") +
        "</div>" +

        U.card("Composição por subsistema", subTable(subs, U),
               { hint: "método: " + U.esc((subs[0] || {}).method || "—") }) +

        '<div class="grid g2" style="margin-top:14px">' +
          U.card("Limiares de área de telhado", footprintTable(canon, U),
                 { note: "Usados na evidência morfológica do Mapa " +
                         "Inteligente. A ponderação é por ÁREA, não por " +
                         "contagem: um galpão de 5.000 m² pesa muito mais na " +
                         "carga do que uma casa de 120 m²." }) +
          U.card("Notas de cada classe", classNotes(canon, U)) +
        "</div>" +
        U.provenanceBlock(body);

      const hours = (canon.hours || []).map((h) =>
        String(h).padStart(2, "0") + "h");
      Charts.lineChart(document.getElementById("ch-canon"), {
        index: hours, height: 280, digits: 4, xTicks: 8,
        formatTime: (v) => v, zeroBase: true,
        series: (canon.classes || []).map((c) => ({
          label: c.label, values: c.profile,
          color: CLASS_COLORS[c.key] || "teal", digits: 4,
        })),
      });

      subs.forEach((s, i) => {
        Charts.lineChart(document.getElementById("ch-sub" + i), {
          index: hours, height: 200, digits: 4, xTicks: 6,
          formatTime: (v) => v,
          series: [
            { label: "observado", values: s.observed, color: "ink", width: 2.2,
              digits: 4 },
            { label: "ajustado", values: s.fitted, color: "teal",
              style: "dash", digits: 4 },
          ],
        });
      });
    },
  };

  function weekendTable(canon, U) {
    const rows = (canon.classes || []).map((c) =>
      "<tr><td>" + U.esc(c.label) + '</td><td class="num">' +
      U.num(c.weekend_ratio, 2) + "</td></tr>").join("");
    return '<div class="table-wrap"><table><thead><tr><th>Classe</th>' +
      '<th class="num">fim de semana / dia útil</th></tr></thead><tbody>' +
      rows + "</tbody></table></div>";
  }

  function subTable(subs, U) {
    const rows = (subs || []).map((s) =>
      "<tr><td><strong>" + U.esc(s.subsystem) + "</strong> " +
      '<span class="small faint">' + U.esc(s.name) + "</span></td>" +
      "<td>" + U.esc(s.label) + "</td>" +
      '<td class="num">' + U.pct(s.weights.residencial, 1) + "</td>" +
      '<td class="num">' + U.pct(s.weights.comercial, 1) + "</td>" +
      '<td class="num">' + U.pct(s.weights.industrial, 1) + "</td>" +
      '<td class="num">' + U.pct(s.weights.rural, 1) + "</td>" +
      '<td class="num">' + U.num(s.r2, 3) + "</td>" +
      '<td class="num">' + U.num(s.weekend_ratio, 3) + "</td>" +
      '<td class="num">' + U.num(s.samples) + "</td></tr>").join("");
    return '<div class="table-wrap"><table><thead><tr><th>Subsistema</th>' +
      '<th>Classe dominante</th><th class="num">resid.</th>' +
      '<th class="num">comerc.</th><th class="num">indust.</th>' +
      '<th class="num">rural</th><th class="num">R²</th>' +
      '<th class="num">fim de sem.</th><th class="num">amostras</th>' +
      "</tr></thead><tbody>" + rows + "</tbody></table></div>";
  }

  function footprintTable(canon, U) {
    const t = canon.footprint_thresholds_m2 || {};
    return U.statLines([
      ["Residencial", "até " + U.num(t.residencial_max) + " m²"],
      ["Comercial", U.num(t.residencial_max) + " a " +
                    U.num(t.comercial_max) + " m²"],
      ["Industrial", "acima de " + U.num(t.comercial_max) + " m²"],
    ]);
  }

  function classNotes(canon, U) {
    return (canon.classes || []).map((c) =>
      '<div class="stat-line" style="display:block">' +
      '<div style="color:var(--' + (CLASS_COLORS[c.key] || "teal") +
      ');font-weight:600">' + U.esc(c.label) + "</div>" +
      '<div class="small muted">' + U.esc(c.note) + "</div></div>").join("");
  }
})();
