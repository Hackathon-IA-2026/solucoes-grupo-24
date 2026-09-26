/* Fronteira T–D: subestações de distribuição (ANEEL) × SE de fronteira da
   rede básica (ONS). Dois painéis novos; nenhuma view anterior é alterada,
   exceto o atalho para o cartão CLM, que recebe a SE daqui. */
(function () {
  "use strict";
  const V = window.App.VIEWS;

  const CLASSES = ["residencial", "comercial", "industrial", "rural"];
  const CLASS_COLORS = {
    residencial: "teal", comercial: "navy",
    industrial: "amber", rural: "green",
  };
  const MONTHS = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago",
                  "set", "out", "nov", "dez"];

  // ------------------------------------------------------------ estado
  /* A base leva ~1 min na primeira construção. Enquanto isso, a tela mostra
     o progresso por etapa e se redesenha sozinha quando fica pronta. */
  let POLL = null;

  async function ready(root, S, U, viewId) {
    const body = await Api.get("fronteira/status", null, { fresh: true });
    const st = body.data;
    if (st.state === "ready") return body;
    const stages = st.stages || [];
    const cur = stages.findIndex((x) => x.key === st.stage);
    root.innerHTML =
      '<div class="note-strip' + (st.state === "error" ? " warn" : "") + '">' +
      (st.state === "error"
        ? "<strong>Falha ao construir a base da fronteira T–D.</strong> " +
          U.esc(st.error) + ' <button class="ghost small" id="fr-retry">' +
          "tentar de novo</button>"
        : "<strong>Construindo a base da fronteira T–D.</strong> A primeira " +
          "vez baixa ~270 MB da ANEEL e do IBGE, agrega e guarda só o " +
          "agregado no cache. Leva cerca de um minuto; depois, a resposta é " +
          "imediata.") + "</div>" +
      U.card("Progresso", stages.map((x, i) => {
        const done = i < cur;
        const on = i === cur;
        const frac = done ? 1 : on ? st.progress || 0 : 0;
        return U.barRow(x.label, frac,
          done ? "concluído" : on ? U.pct(st.progress, 0) : "—",
          done ? "green" : "teal");
      }).join(""), { hint: st.elapsed_s !== null && st.elapsed_s !== undefined
                     ? U.num(st.elapsed_s, 0) + " s decorridos" : "" });
    const btn = root.querySelector("#fr-retry");
    if (btn) {
      btn.addEventListener("click", async () => {
        try { await Api.post("fronteira/reconstruir"); } catch (e) { /* status mostra */ }
        App.render();
      });
    }
    clearTimeout(POLL);
    if (st.state !== "error") {
      POLL = setTimeout(() => {
        if (S.view === viewId) App.render();
      }, 2000);
    }
    return null;
  }

  function classBars(weights, U) {
    return CLASSES.map((k) => U.barRow(k, (weights || {})[k] || 0,
      U.pct((weights || {})[k] || 0, 1), CLASS_COLORS[k])).join("");
  }

  function loadChip(f, U) {
    if (f.loading === null || f.loading === undefined) {
      return '<span class="chip">—</span>';
    }
    const c = f.loading_flag === "acima da faixa" ? "crimson"
      : f.loading_flag === "abaixo da faixa" ? "amber" : "green";
    return '<span class="chip ' + c + '" title="' + U.esc(f.loading_flag ||
      "dentro da faixa plausível") + '">' + U.pct(f.loading, 0) + "</span>";
  }

  function probColor(p) {
    return p >= 0.7 ? "green" : p >= 0.5 ? "teal" : p >= 0.3 ? "amber" : "crimson";
  }

  // ------------------------------------------------------------ mapa
  /* Projeção equiretangular com correção de cos(lat): suficiente na escala
     de um estado ou do país, e sem dependência de biblioteca. */
  function drawMap(host, map, S, onPick) {
    const fr = map.frontier || [], seds = map.seds || [];
    const pts = fr.map((f) => [f.lat, f.lon]).concat(seds.map((s) => [s.lat, s.lon]));
    if (!pts.length) { host.innerHTML = '<div class="empty">Sem pontos.</div>'; return; }
    const lats = pts.map((p) => p[0]), lons = pts.map((p) => p[1]);
    let la0 = Math.min.apply(null, lats), la1 = Math.max.apply(null, lats);
    let lo0 = Math.min.apply(null, lons), lo1 = Math.max.apply(null, lons);
    const padLa = (la1 - la0) * 0.05 + 0.05, padLo = (lo1 - lo0) * 0.05 + 0.05;
    la0 -= padLa; la1 += padLa; lo0 -= padLo; lo1 += padLo;
    const k = Math.cos(((la0 + la1) / 2) * Math.PI / 180);
    const W = 640;
    const H = Math.max(260, Math.min(560, W * (la1 - la0) / ((lo1 - lo0) * k)));
    const sx = (lo) => ((lo - lo0) / (lo1 - lo0)) * W;
    const sy = (la) => H - ((la - la0) / (la1 - la0)) * H;
    const byIdx = {};
    fr.forEach((f) => { byIdx[f.i] = f; });
    const sel = fr.find((f) => f.id === S.frSel);
    const maxMva = Math.max.apply(null, fr.map((f) => f.mva || 1).concat([1]));

    let s = '<svg viewBox="0 0 ' + W + " " + H.toFixed(0) + '" width="100%" ' +
      'role="img" aria-label="Mapa de SEs de fronteira e subestações de ' +
      'distribuição" style="display:block">';
    // vínculos da SE selecionada
    if (sel) {
      seds.forEach((d) => {
        if (d.f !== sel.i) return;
        s += '<line x1="' + sx(d.lon).toFixed(1) + '" y1="' + sy(d.lat).toFixed(1) +
          '" x2="' + sx(sel.lon).toFixed(1) + '" y2="' + sy(sel.lat).toFixed(1) +
          '" stroke="' + Charts.color(probColor(d.p)) + '" stroke-width="0.8" ' +
          'opacity="0.7"/>';
      });
    }
    seds.forEach((d) => {
      const on = sel && d.f === sel.i;
      s += '<circle cx="' + sx(d.lon).toFixed(1) + '" cy="' + sy(d.lat).toFixed(1) +
        '" r="' + (on ? 2.6 : 1.5) + '" fill="' +
        Charts.color(d.f < 0 ? "muted" : probColor(d.p)) + '" opacity="' +
        (sel && !on ? 0.35 : 0.8) + '"><title>SED · ' + App.num(d.e, 1) +
        " GWh/ano · p=" + App.num(d.p, 2) +
        (d.f >= 0 && byIdx[d.f] ? " → " + App.esc(byIdx[d.f].name) : " · sem SE no raio") +
        "</title></circle>";
    });
    fr.forEach((f) => {
      const r = 3 + 7 * Math.sqrt((f.mva || 0) / maxMva);
      const on = sel && f.i === sel.i;
      s += '<circle data-fr="' + App.esc(f.id) + '" cx="' + sx(f.lon).toFixed(1) +
        '" cy="' + sy(f.lat).toFixed(1) + '" r="' + r.toFixed(1) + '" fill="' +
        Charts.color(f.n ? "navy" : "muted") + '" fill-opacity="' +
        (on ? 0.95 : 0.55) + '" stroke="' + Charts.color(on ? "teal" : "navy") +
        '" stroke-width="' + (on ? 2.4 : 1) + '" style="cursor:pointer"><title>' +
        App.esc(f.name) + " · " + App.num(f.mva) + " MVA · " + App.num(f.n) +
        " SEDs · " + App.num(f.e, 0) + " GWh/ano</title></circle>";
    });
    s += "</svg>";
    host.innerHTML = s +
      '<div class="chips small" style="margin-top:8px;gap:10px">' +
      legendDot("navy", "SE de fronteira (tamanho ∝ √MVA)") +
      legendDot("green", "SED, p ≥ 0,7") + legendDot("teal", "0,5–0,7") +
      legendDot("amber", "0,3–0,5") + legendDot("crimson", "< 0,3 ambígua") +
      legendDot("muted", "sem SE no raio") + "</div>";
    host.querySelectorAll("[data-fr]").forEach((c) =>
      c.addEventListener("click", () => onPick(c.getAttribute("data-fr"))));
  }

  function legendDot(color, label) {
    return '<span class="small muted" style="display:inline-flex;align-items:center;gap:5px">' +
      '<span style="width:9px;height:9px;border-radius:50%;background:' +
      Charts.color(color) + '"></span>' + App.esc(label) + "</span>";
  }

  // ============================================== CORRELAÇÃO SE × SED
  V.fronteira = {
    title: "Fronteira T–D: SE da rede básica × subestação de distribuição",
    subtitle: "Cada subestação de distribuição da BDGD associada à SE de "
            + "fronteira do ONS que a alimenta, com a carga e a MMGD que ela leva",
    loadingText: "Correlacionando subestações de distribuição e de fronteira…",
    async render(root, S, U) {
      const st = await ready(root, S, U, "fronteira");
      if (!st) return;
      const body = await Api.get("fronteira/resumo", {
        uf: S.frUf || "", order: S.frOrder || "energia",
      });
      const d = body.data;
      const k = d.kpis || {};
      const rep = d.report || {};
      const rows = d.rows || [];
      if (!S.frSel || !rows.some((r) => r.sub_id === S.frSel)) {
        const first = rows.find((r) => r.n_sed > 0) || rows[0];
        S.frSel = first ? first.sub_id : null;
      }

      root.innerHTML =
        '<div class="note-strip">O ONS publica a <strong>rede básica</strong>; ' +
        "a subestação de distribuição está na <strong>BDGD da ANEEL</strong>. " +
        "Cada SED é reconstruída das unidades consumidoras de média e alta " +
        "tensão que ela atende (código <span class=\"mono\">SUB</span>, classe, " +
        "12 meses de energia e demanda, coordenada) e associada à SE de " +
        "fronteira que a alimenta. A associação é <strong>inferida</strong> — " +
        "a topologia de subtransmissão não é dado público — e cada vínculo sai " +
        "com probabilidade e alternativas.</div>" +

        '<div class="grid g4" style="margin-bottom:14px">' +
          U.kpi("SEs de fronteira com carga", U.num(k.frontier_with_sed), "",
                "de " + U.num(k.frontier) + " no filtro · secundário ≤ 138 kV",
                "teal") +
          U.kpi("SEDs associadas", U.num(k.seds), "",
                U.pct(k.ambiguous_rate, 0) + " ambíguas (p < 0,5) · distância " +
                "mediana " + U.num(k.median_distance_km, 1) + " km", "navy") +
          U.kpi("Energia alocada", U.num(k.energy_twh, 1), "TWh/ano",
                U.pct(k.measured_share, 0) + " medida por UC (MT/AT) · resto " +
                "baixa tensão rateada", "green") +
          U.kpi("MMGD alocada", U.num(k.gd_mw, 0), "MW",
                U.pct(k.gd_direct_share, 0) + " por vínculo direto CEG_GD → UC → SED",
                "amber") +
        "</div>" +

        '<div class="chips" style="margin-bottom:12px">' +
          '<span class="chip clickable' + (!S.frUf ? " on" : "") +
          '" data-uf="">todas as UF</span>' +
          (d.ufs || []).map((u) =>
            '<span class="chip clickable' + (S.frUf === u ? " on" : "") +
            '" data-uf="' + u + '">' + u + "</span>").join("") +
          '<select id="fr-order" class="chip clickable" style="margin-left:auto">' +
            [["energia", "ordenar por energia"], ["gd", "por penetração de MMGD"],
             ["carregamento", "por carregamento"], ["ambiguidade", "por ambiguidade"],
             ["nome", "por nome"]].map((o) =>
              '<option value="' + o[0] + '"' +
              ((S.frOrder || "energia") === o[0] ? " selected" : "") + ">" +
              o[1] + "</option>").join("") +
          "</select>" +
        "</div>" +

        '<div class="grid g2" style="margin-bottom:14px">' +
          U.card("Mapa", '<div id="fr-map"></div>',
                 { hint: "clique numa SE de fronteira",
                   note: "Posição da SED = mediana das UCs de média e alta " +
                         "tensão que ela atende, não a coordenada do barramento." }) +
          U.card("SEs de fronteira", '<div class="table-wrap scroll-y" ' +
                 'id="fr-table" style="max-height:520px"></div>',
                 { hint: U.num(rows.length) + " no filtro" }) +
        "</div>" +

        '<div id="fr-detail"></div>' +

        '<div class="grid g2" style="margin-top:14px">' +
          U.card("Pipeline replicável", "<ol class=\"actions\" style=\"padding-left:20px\">" +
                 (d.pipeline || []).map((x) => "<li>" + U.esc(x) + "</li>").join("") +
                 "</ol>",
                 { note: "Base agregada reconstruída a cada " +
                         U.num(st.data.ttl_days, 0) + " dias. Construída em " +
                         U.when(st.data.built_at) + " (" + U.esc(st.data.base_mode) +
                         ")." }) +
          U.card("Premissas da associação", U.statLines((d.premises || []).map((p) =>
                 [p.k, U.esc(p.v)])),
                 { note: "Versionadas em <span class=\"mono\">config.FRONTEIRA</span>. " +
                         "α e λ foram escolhidos pela varredura do painel " +
                         "<a href=\"#/correlacao\">Qualidade da correlação</a>." }) +
        "</div>" +
        U.provenanceBlock(body);

      drawMap(document.getElementById("fr-map"), d.map, S, pick);
      drawTable(rows, S, U, pick);
      await drawDetail(S, U);

      async function pick(id) {
        S.frSel = id;
        drawMap(document.getElementById("fr-map"), d.map, S, pick);
        document.querySelectorAll("#fr-table tr[data-fr]").forEach((tr) =>
          tr.classList.toggle("sel", tr.dataset.fr === id));
        await drawDetail(S, U);
      }

      root.querySelectorAll("[data-uf]").forEach((c) =>
        c.addEventListener("click", () => {
          S.frUf = c.dataset.uf; S.frSel = null; App.render();
        }));
      const ord = root.querySelector("#fr-order");
      if (ord) ord.addEventListener("change", () => { S.frOrder = ord.value; App.render(); });
    },
  };

  function drawTable(rows, S, U, pick) {
    const host = document.getElementById("fr-table");
    host.innerHTML = "<table><thead><tr><th>SE de fronteira</th>" +
      '<th class="num">SEDs</th><th class="num">GWh/ano</th>' +
      "<th>Classe dominante</th><th class=\"num\">MMGD</th><th>Carreg.</th>" +
      "</tr></thead><tbody>" + rows.map((r) =>
        '<tr data-fr="' + U.esc(r.sub_id) + '" class="' +
        (r.sub_id === S.frSel ? "sel" : "") + '" style="cursor:pointer">' +
        "<td><strong>" + U.esc(r.name) + "</strong><br>" +
        '<span class="small faint">' + U.esc(r.uf) + " · " + U.num(r.frontier_mva) +
        " MVA · " + U.num(r.voltage_kv) + "/" + U.num(r.secondary_kv) + " kV</span></td>" +
        '<td class="num">' + U.num(r.n_sed) + "</td>" +
        '<td class="num">' + U.num(r.e_total_gwh, 0) + "</td>" +
        '<td class="small">' + U.esc(r.dominant || "—") + '<br><span class="faint">' +
        U.pct((r.weights || {})[r.dominant], 0) + "</span></td>" +
        '<td class="num">' + U.num(r.gd_kw / 1000, 0) + ' MW<br><span class="small faint">' +
        U.pct(r.gd_penetration, 0) + " da carga média</span></td>" +
        "<td>" + loadChip(r, U) + "</td></tr>").join("") + "</tbody></table>";
    host.querySelectorAll("tr[data-fr]").forEach((tr) =>
      tr.addEventListener("click", () => pick(tr.dataset.fr)));
  }

  async function drawDetail(S, U) {
    const host = document.getElementById("fr-detail");
    if (!host || !S.frSel) return;
    host.innerHTML = App.loading("Montando o detalhe da SE…");
    let body;
    try {
      body = await Api.get("fronteira/se/" + encodeURIComponent(S.frSel));
    } catch (err) {
      host.innerHTML = App.errorBlock(err);
      return;
    }
    const f = body.data;
    const cmp = f.comparison;
    const clm = f.clm || {};
    if (!f.n_sed) {
      host.innerHTML = U.card("Detalhe · " + U.esc(f.name) + " (" + U.esc(f.uf) + ")",
        '<div class="empty">Nenhuma subestação de distribuição foi associada a ' +
        "esta SE. Ou ela interliga transmissão sem entregar carga local, ou a " +
        "carga da área foi atraída por uma SE vizinha — confira as alternativas " +
        "das SEDs próximas.</div>");
      return;
    }

    host.innerHTML = U.card(
      "Detalhe · " + U.esc(f.name) + " (" + U.esc(f.uf) + ")",
      '<div class="grid g4" style="gap:12px;margin-bottom:12px">' +
        U.kpi("SEDs associadas", U.num(f.n_sed), "",
              U.num(f.n_uc) + " UCs de média/alta tensão · " +
              U.pct(f.ambiguous_share, 0) + " da energia medida em vínculo ambíguo") +
        U.kpi("Energia", U.num(f.e_total_gwh, 0), "GWh/ano",
              U.pct(f.measured_share, 0) + " medida · " + U.num(f.e_bt_gwh, 0) +
              " GWh de baixa tensão rateada") +
        U.kpi("Carga média", U.num(f.mw_avg, 0), "MW",
              "carregamento implícito " + (f.loading === null ? "—"
                : U.pct(f.loading, 0)) + " de " + U.num(f.frontier_mva) + " MVA" +
              (f.loading_flag ? ' · <span class="neg">' + U.esc(f.loading_flag) +
                "</span>" : "")) +
        U.kpi("MMGD instalada", U.num(f.gd_kw / 1000, 1), "MW",
              U.num(f.gd_n) + " unidades · " + U.pct(f.gd_penetration, 0) +
              " da carga média · " + U.pct(f.gd_direct_share, 0) + " vínculo direto") +
      "</div>" +
      '<div class="grid g2" style="gap:12px">' +
        "<div>" +
          '<div class="kpi-label" style="margin-bottom:6px">Composição por classe · ' +
          "medida (MT/AT) e rateada (BT), GWh/ano</div>" +
          '<div id="fr-comp"></div>' +
        "</div>" +
        "<div>" +
          '<div class="kpi-label" style="margin-bottom:6px">Sazonalidade · ' +
          "energia mensal, GWh</div>" +
          '<div id="fr-month"></div>' +
        "</div>" +
      "</div>",
      { hint: U.esc(f.agent) + " · " + U.num(f.voltage_kv) + "/" +
              U.num(f.secondary_kv) + " kV · " + U.num(f.pop_served) +
              " habitantes rateados" }) +

      '<div class="grid g2" style="margin-top:14px">' +
        U.card("Duas representações da mesma SE", compareBlock(cmp, U),
               { note: cmp
                   ? "O Mapa Inteligente estima a composição pela morfologia " +
                     "de ortoimagem (sintética no protótipo) com prior do " +
                     "subsistema. Aqui ela vem de <strong>energia faturada " +
                     "real</strong>. A diferença é o ganho de representação " +
                     "que esta seção entrega ao modelo de carga."
                   : "SE fora do lote do Mapa Inteligente." }) +
        U.card("Insumo ao Modelo de Carga Composta", U.statLines([
            ["Fração de motor estimada", U.num(clm.fracao_motor_estimada, 3)],
            ["MMGD instalada", U.num((clm.mmgd_kw_instalada || 0) / 1000, 1) + " MW"],
            ["Pdg ao meio-dia (teto)", U.num(clm.pdg_mw_meio_dia, 1) + " MW"],
            ["Penetração (GD ÷ carga média)", U.pct(clm.mmgd_penetracao, 0)],
            ["Carga média", U.num(clm.carga_media_mw, 1) + " MW"],
            ["Parcela medida por UC", U.pct(clm.parcela_medida, 0)],
          ]) + classBars(clm.composicao_classe, U) +
          '<div style="margin-top:12px"><button id="fr-to-clm">Abrir no cartão ' +
          "CLM com esta composição →</button></div>",
          { hint: U.esc(clm.fonte || ""), note: U.esc(clm.aviso || "") }) +
      "</div>" +

      U.card("Subestações de distribuição associadas", sedTable(f.seds, U),
             { hint: "ordenadas por energia · p = probabilidade do vínculo",
               note: "Alternativas: as SEs de fronteira seguintes no modelo " +
                     "gravitacional. Um vínculo ambíguo não é erro — é a " +
                     "informação de que ali há mais de uma SE plausível e a " +
                     "topologia precisa ser confirmada com a distribuidora." });

    Charts.stackedBars(document.getElementById("fr-comp"), {
      labels: CLASSES,
      stacks: [
        { label: "medida (MT/AT)", color: "navy",
          values: CLASSES.map((c) => (f.e_mtat_class_kwh[c] || 0) / 1e6) },
        { label: "rateada (BT)", color: "teal",
          values: CLASSES.map((c) => (f.e_bt_class_kwh[c] || 0) / 1e6) },
      ], height: 220, unit: "GWh",
    });
    Charts.stackedBars(document.getElementById("fr-month"), {
      labels: f.months || MONTHS,
      stacks: [
        { label: "medida (MT/AT)", color: "navy", values: f.e_month_mtat_gwh },
        { label: "rateada (BT)", color: "teal", values: f.e_month_bt_gwh },
      ], height: 220, unit: "GWh",
    });
    const btn = document.getElementById("fr-to-clm");
    if (btn) {
      btn.addEventListener("click", () => {
        App.STATE.clmHandoff = { subId: f.sub_id, name: f.name, fonte: "bdgd" };
        location.hash = "#/clm";
      });
    }
  }

  function compareBlock(cmp, U) {
    if (!cmp) return '<div class="empty">Sem comparação disponível.</div>';
    const m = cmp.mapa || {}, b = cmp.bdgd || {};
    const rows = CLASSES.map((c) => {
      const dv = (cmp.diff || {})[c] || 0;
      return "<tr><td>" + U.esc(c) + '</td><td class="num">' +
        U.pct((m.weights || {})[c], 1) + '</td><td class="num">' +
        U.pct((b.weights || {})[c], 1) + '</td><td class="num ' +
        (Math.abs(dv) >= 0.1 ? (dv > 0 ? "pos" : "neg") : "") + '">' +
        (dv > 0 ? "+" : "") + U.num(dv * 100, 1) + " p.p.</td></tr>";
    }).join("");
    return '<div class="table-wrap"><table><thead><tr><th>Classe</th>' +
      '<th class="num">Mapa Inteligente</th><th class="num">BDGD + SAMP</th>' +
      '<th class="num">Δ</th></tr></thead><tbody>' + rows +
      '<tr><td><strong>dominante</strong></td><td class="num">' + U.esc(m.dominant || "—") +
      '</td><td class="num">' + U.esc(b.dominant || "—") + "</td><td></td></tr>" +
      '<tr><td><strong>MMGD</strong></td><td class="num">' +
      U.num((m.mmgd_kw || 0) / 1000, 1) + ' MW</td><td class="num">' +
      U.num((b.mmgd_kw || 0) / 1000, 1) + ' MW</td><td class="num">' +
      (cmp.mmgd_ratio ? "×" + U.num(cmp.mmgd_ratio, 1)
        : '<span class="small neg">amostra sem painel</span>') + "</td></tr>" +
      "</tbody></table></div>" +
      '<div class="card-note">Distância entre composições (variação total): <strong>' +
      U.pct(cmp.l1, 0) + "</strong>. MMGD do Mapa: detecção em amostra " +
      "extrapolada; aqui: cadastro homologado da ANEEL.</div>";
  }

  function sedTable(seds, U) {
    return '<div class="table-wrap scroll-y"><table><thead><tr>' +
      "<th>SED</th><th>Distribuidora</th><th class=\"num\">UCs</th>" +
      '<th class="num">GWh/ano</th><th>Classe</th><th class="num">MMGD direta</th>' +
      '<th class="num">km</th><th class="num">p</th><th>Alternativas</th>' +
      "</tr></thead><tbody>" + (seds || []).slice(0, 150).map((s) =>
        "<tr><td class=\"mono small\">" + U.esc(s.sub) + "</td>" +
        '<td class="small">' + U.esc(s.distribuidora) +
        (s.agent_match ? ' <span class="chip teal" title="mesmo grupo econômico ' +
          'do agente da SE no ONS">grupo</span>' : "") + "</td>" +
        '<td class="num">' + U.num(s.n_uc) + "</td>" +
        '<td class="num">' + U.num(s.e_gwh, 1) + "</td>" +
        '<td class="small">' + U.esc(s.dominant) + "</td>" +
        '<td class="num">' + (s.gd_kw_direct ? U.num(s.gd_kw_direct / 1000, 2) + " MW" : "—") + "</td>" +
        '<td class="num">' + U.num(s.d_km, 1) + "</td>" +
        '<td class="num"><span class="chip ' + probColor(s.p) + '">' +
        U.num(s.p, 2) + "</span></td>" +
        '<td class="small faint">' + (s.alternatives || []).map((a) =>
          U.esc(a.name) + " " + U.num(a.p, 2)).join(" · ") + "</td></tr>").join("") +
      "</tbody></table></div>";
  }

  // ============================================== QUALIDADE DA CORRELAÇÃO
  V.correlacao = {
    title: "Qualidade da correlação SE × SED",
    subtitle: "Sem verdade de campo para a topologia: validação externa contra "
            + "a carga do ONS, coerência física e sensibilidade às premissas",
    loadingText: "Calculando a validação e a varredura de sensibilidade…",
    async render(root, S, U) {
      const st = await ready(root, S, U, "correlacao");
      if (!st) return;
      const body = await Api.get("fronteira/qualidade");
      const d = body.data;
      const r = d.report || {};
      const sens = d.sensitivity || [];
      const cur = sens.find((x) => x.current) || {};
      const cov = d.ons_coverage || [];

      root.innerHTML =
        '<div class="note-strip">Nenhuma base pública diz de qual SE de ' +
        "fronteira cada SED recebe energia. Por isso a validação é " +
        "<strong>indireta</strong>, em três frentes: (1) a energia alocada " +
        "contra a carga verificada do ONS, calculada de forma independente; " +
        "(2) a coerência física do carregamento implícito das SEs; (3) a " +
        "sensibilidade do resultado às duas premissas que mais pesam.</div>" +

        '<div class="grid g4" style="margin-bottom:14px">' +
          U.kpi("SEDs associadas", U.num(r.seds_associated), "",
                "de " + U.num(r.seds_used) + " · " + U.num(r.seds_unassociated) +
                " sem SE de fronteira no raio", "teal") +
          U.kpi("Vínculos ambíguos", U.pct(r.seds_associated
                  ? r.seds_ambiguous / r.seds_associated : null, 0), "",
                "p < 0,5: mais de uma SE plausível", "amber") +
          U.kpi("Mesma UF", U.pct(r.same_uf_rate, 1), "",
                "concessão é quase sempre intraestadual", "green") +
          U.kpi("SE mais próxima escolhida", U.pct(cur.nearest_rate, 0), "",
                "no restante, a capacidade pesou mais que a distância", "navy") +
        "</div>" +

        '<div class="grid g2" style="margin-bottom:14px">' +
          U.card("Validação externa · energia alocada × carga do ONS",
            cov.map((c) => U.barRow(c.subsystem + " — " + c.name,
              Math.min(1, c.ratio || 0), U.pct(c.ratio, 0), "teal")).join("") +
            '<div class="table-wrap" style="margin-top:10px"><table><thead><tr>' +
            '<th>Subsistema</th><th class="num">Alocada (TWh)</th>' +
            '<th class="num">ONS verificada (TWh)</th><th class="num">Razão</th>' +
            "</tr></thead><tbody>" + cov.map((c) =>
              "<tr><td>" + U.esc(c.subsystem) + '</td><td class="num">' +
              U.num(c.allocated_gwh / 1000, 1) + '</td><td class="num">' +
              U.num((c.ons_gwh || 0) / 1000, 1) + '</td><td class="num">' +
              U.pct(c.ratio, 0) + "</td></tr>").join("") + "</tbody></table></div>",
            { hint: "ano " + U.esc((cov[0] || {}).ano || ""),
              note: "A razão fica abaixo de 100% <strong>por construção</strong>: " +
                    "perdas técnicas e não técnicas, autoconsumo da MMGD e carga " +
                    "ligada direto na rede básica não aparecem no faturamento " +
                    "da distribuidora. No Norte, parte relevante da carga é " +
                    "eletrointensiva e conectada à rede básica. O que se verifica " +
                    "é a ordem de grandeza e a estabilidade entre subsistemas." }) +
          U.card("Sensibilidade às premissas", sensTable(sens, U),
            { hint: "atratividade = MVA^α · e^(−d/λ)",
              note: "Sem verdade de campo, o critério é coerência física: " +
                    "carregamento homogêneo (CV baixo), nenhuma SE acima de 100% " +
                    "e poucas SEs sem carga. Com α = 1 a SE grande atrai demais " +
                    "e esvazia as vizinhas; com α = 0 (só distância) há SEs " +
                    "sobrecarregadas. A linha destacada é a configuração em uso." }) +
        "</div>" +

        '<div class="grid g3" style="margin-bottom:14px">' +
          U.card("Distância SED → SE", '<div id="h-dist"></div>', { hint: "km" }) +
          U.card("Probabilidade do vínculo", '<div id="h-prob"></div>',
                 { hint: "p do vínculo primário" }) +
          U.card("Carregamento implícito", '<div id="h-load"></div>',
                 { hint: "carga média ÷ (MVA × 0,92)" }) +
        "</div>" +

        '<div class="grid g2" style="margin-bottom:14px">' +
          U.card("SEs fora da faixa plausível", flaggedTable(d.flagged, U),
                 { hint: U.num((d.flagged || []).length) + " SEs",
                   note: "Acima da faixa: provável SE vizinha ausente do " +
                         "cadastro de fronteira, ou atração excessiva. Abaixo: " +
                         "SE que interliga transmissão e entrega pouca carga local." }) +
          U.card("MMGD e baixa tensão", U.statLines([
              ["MMGD no cadastro ANEEL", U.num(r.gd_total_mw, 0) + " MW"],
              ["· vínculo direto UC → SED", U.num(r.gd_direct_mw, 0) + " MW"],
              ["· rateada pelo município", U.num(r.gd_municipal_allocated_mw, 0) + " MW"],
              ["· sem SE no raio", U.num(r.gd_unallocated_mw, 0) + " MW"],
              ["Baixa tensão alocada (SAMP)", U.num(r.bt_allocated_twh, 1) + " TWh"],
              ["· sem destino", U.num(r.bt_unallocated_twh, 1) + " TWh"],
              ["Municípios ligados pelo centroide", U.num(r.municipios_por_centroide)],
              ["Energia MT/AT associada", U.pct(r.energy_mtat_associated_share, 1)],
            ]), { note: "Município sem nenhuma SED na BDGD aberta (só há pessoa " +
                        "jurídica) desce direto à SE de fronteira pelo centroide." }) +
        "</div>" +

        '<div class="grid g3">' +
          U.card("Premissas", U.statLines((d.premises || []).map((p) => [p.k, U.esc(p.v)]))) +
          U.card("Privacidade", '<ul class="actions" style="padding-left:18px">' +
                 (d.privacy || []).map((x) => "<li>" + U.esc(x) + "</li>").join("") + "</ul>") +
          U.card("Limites declarados", '<ul class="actions" style="padding-left:18px">' +
                 (d.limits || []).map((x) => "<li>" + U.esc(x) + "</li>").join("") + "</ul>") +
        "</div>" +
        U.provenanceBlock(body);

      hist("h-dist", d.hist_distance, (b) => U.num(b.from) + "–" + U.num(b.to), "navy");
      hist("h-prob", d.hist_probability, (b) => U.num(b.from, 1), "teal");
      hist("h-load", d.hist_loading, (b) => U.pct(b.from, 0), "amber");
    },
  };

  function hist(id, bins, label, color) {
    const host = document.getElementById(id);
    if (!host) return;
    Charts.barChart(host, {
      labels: (bins || []).map(label), values: (bins || []).map((b) => b.count),
      color: color, height: 190, digits: 0, seriesLabel: "contagem",
    });
  }

  function sensTable(sens, U) {
    return '<div class="table-wrap"><table><thead><tr>' +
      '<th class="num" style="text-transform:none">α</th>' +
      '<th class="num" style="text-transform:none">λ (km)</th><th class="num">ambíguas</th>' +
      '<th class="num">mais próxima</th><th class="num">SEs sem carga</th>' +
      '<th class="num">CV carreg.</th><th class="num">máx.</th><th class="num">&gt;100%</th>' +
      "</tr></thead><tbody>" + sens.map((x) =>
        '<tr class="' + (x.current ? "sel" : "") + '"><td class="num">' +
        U.num(x.alpha, 1) + '</td><td class="num">' + U.num(x.lambda_km) +
        '</td><td class="num">' + U.pct(x.ambiguous_rate, 0) +
        '</td><td class="num">' + U.pct(x.nearest_rate, 0) +
        '</td><td class="num">' + U.num(x.frontier_no_load) +
        '</td><td class="num">' + U.num(x.loading_cv, 2) +
        '</td><td class="num ' + (x.loading_max > 1 ? "neg" : "") + '">' +
        U.pct(x.loading_max, 0) + '</td><td class="num ' +
        (x.over_100 ? "neg" : "") + '">' + U.num(x.over_100) + "</td></tr>").join("") +
      "</tbody></table></div>";
  }

  function flaggedTable(rows, U) {
    if (!rows || !rows.length) return '<div class="empty">Nenhuma SE fora da faixa.</div>';
    return '<div class="table-wrap scroll-y"><table><thead><tr><th>SE</th>' +
      '<th class="num">MVA</th><th class="num">MW médio</th><th>Carreg.</th>' +
      '<th class="num">SEDs</th></tr></thead><tbody>' + rows.map((r) =>
        "<tr><td>" + U.esc(r.name) + ' <span class="small faint">' + U.esc(r.uf) +
        '</span></td><td class="num">' + U.num(r.frontier_mva) +
        '</td><td class="num">' + U.num(r.mw_avg, 0) + "</td><td>" +
        loadChip(r, U) + '</td><td class="num">' + U.num(r.n_sed) + "</td></tr>").join("") +
      "</tbody></table></div>";
  }
})();
