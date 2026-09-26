/* Parametrização do Modelo de Carga Composta (CMPLDW).
   Página nova. Não altera nenhuma view anterior. */
(function () {
  "use strict";
  const V = window.App.VIEWS;

  const ORIGIN_STYLE = {
    WECC: "teal", REF: "", DERIVADO: "green",
    PREMISSA: "amber", A_CALIBRAR: "crimson",
  };
  const ORIGIN_LABEL = {
    WECC: "WECC", REF: "referência", DERIVADO: "derivado",
    PREMISSA: "premissa", A_CALIBRAR: "a calibrar",
  };
  const COMP_COLOR = {
    Fma: "navy-2", Fmb: "teal", Fmc: "green",
    Fmd: "crimson", Fel: "purple", estatica: "muted",
  };
  const CLASS_COLOR = {
    residencial: "teal", comercial: "navy-2",
    industrial: "amber", rural: "green",
  };

  // Estado local do painel. Só o que o usuário controla.
  const S = {
    subId: "", subName: "", acFactor: 1, block: "fracoes", fonte: "",
    mix: { residencial: 0.55, comercial: 0.25, industrial: 0.12, rural: 0.08 },
    vstall: 0.6, vd1: 0.8, vd2: 0.7, frcel: 0,
  };

  function originChip(origem) {
    const c = ORIGIN_STYLE[origem] === undefined ? "" : ORIGIN_STYLE[origem];
    return '<span class="chip ' + c + '" title="' + App.esc(origem) + '">' +
      App.esc(ORIGIN_LABEL[origem] || origem) + "</span>";
  }

  function fmtVal(v) {
    if (v === null || v === undefined) return "—";
    if (typeof v !== "number") return App.esc(String(v));
    if (v === 0) return "0";
    if (Math.abs(v) >= 100) return App.num(v, 2);
    if (Math.abs(v) >= 1) return App.num(v, 4);
    return App.num(v, 6);
  }

  // ------------------------------------------------------------- topologia
  /* O ponto que costuma passar em branco: metade do efeito dinâmico do CLM
     vem da rede ENTRE o barramento de transmissão e o uso final. Vale um
     desenho, não um parágrafo. */
  function topologyDiagram(topo) {
    const comps = topo.componentes || [];
    const rowH = 26, top = 34;
    const h = top + comps.length * rowH + 26;
    let s = '<svg viewBox="0 0 640 ' + h + '" width="100%" height="' + h +
      '" role="img" aria-label="Topologia do CMPLDW" style="overflow:visible">';

    const xSys = 56, xLow = 232, xLoad = 392, xComp = 470;
    const yBus0 = top - 14, yBus1 = top + comps.length * rowH - 6;
    const mid = (yBus0 + yBus1) / 2;

    function bus(x, label, sub) {
      let o = '<line x1="' + x + '" y1="' + yBus0 + '" x2="' + x + '" y2="' +
        yBus1 + '" stroke="var(--ink-2)" stroke-width="3"/>';
      o += '<text x="' + x + '" y="' + (yBus0 - 16) +
        '" text-anchor="middle" font-size="10.5" font-weight="600" ' +
        'fill="var(--ink)">' + App.esc(label) + "</text>";
      if (sub) {
        o += '<text x="' + x + '" y="' + (yBus0 - 5) +
          '" text-anchor="middle" font-size="9" fill="var(--muted)">' +
          App.esc(sub) + "</text>";
      }
      return o;
    }

    s += bus(xSys, "Barramento do sistema", "230 · 115 · 69 kV");
    s += bus(xLow, "Barramento de baixa", "criado na inicialização");
    s += bus(xLoad, "Barramento de carga", "extremidade do alimentador");

    // Transformador com comutação em carga.
    s += '<line x1="' + xSys + '" y1="' + mid + '" x2="' + xLow + '" y2="' +
      mid + '" stroke="var(--line-2)" stroke-width="1.6"/>';
    s += '<rect x="' + (xSys + 46) + '" y="' + (mid - 11) + '" width="42" ' +
      'height="22" rx="3" fill="var(--panel-2)" stroke="var(--teal)" ' +
      'stroke-width="1.4"/>';
    s += '<text x="' + (xSys + 67) + '" y="' + (mid + 4) +
      '" text-anchor="middle" font-size="9.5" fill="var(--teal)">jXxf</text>';
    s += '<text x="' + (xSys + 126) + '" y="' + (mid - 6) +
      '" text-anchor="middle" font-size="9" fill="var(--muted)">1:T</text>';
    s += '<text x="' + (xSys + 126) + '" y="' + (mid + 8) +
      '" text-anchor="middle" font-size="8.5" fill="var(--amber)">LTC</text>';

    // Alimentador.
    s += '<line x1="' + xLow + '" y1="' + mid + '" x2="' + xLoad + '" y2="' +
      mid + '" stroke="var(--line-2)" stroke-width="1.6"/>';
    s += '<rect x="' + (xLow + 44) + '" y="' + (mid - 11) + '" width="72" ' +
      'height="22" rx="3" fill="var(--panel-2)" stroke="var(--green)" ' +
      'stroke-width="1.4"/>';
    s += '<text x="' + (xLow + 80) + '" y="' + (mid + 4) +
      '" text-anchor="middle" font-size="9.5" fill="var(--green)">' +
      "Rfdr + jXfdr</text>";

    // Shunts: Bss na baixa, Bfdr repartido pelas duas pontas.
    function shunt(x, label, cor) {
      let o = '<line x1="' + x + '" y1="' + (yBus1 + 2) + '" x2="' + x +
        '" y2="' + (yBus1 + 12) + '" stroke="' + cor + '" stroke-width="1.3"/>';
      o += '<line x1="' + (x - 7) + '" y1="' + (yBus1 + 12) + '" x2="' +
        (x + 7) + '" y2="' + (yBus1 + 12) + '" stroke="' + cor +
        '" stroke-width="1.8"/>';
      o += '<line x1="' + (x - 7) + '" y1="' + (yBus1 + 16) + '" x2="' +
        (x + 7) + '" y2="' + (yBus1 + 16) + '" stroke="' + cor +
        '" stroke-width="1.8"/>';
      o += '<text x="' + x + '" y="' + (yBus1 + 27) +
        '" text-anchor="middle" font-size="8.5" fill="' + cor + '">' +
        App.esc(label) + "</text>";
      return o;
    }
    s += shunt(xLow, "Bss", "var(--amber)");
    s += shunt(xLow + 92, "Fb·Bfdr", "var(--muted)");
    s += shunt(xLoad - 16, "(1−Fb)·Bfdr", "var(--muted)");

    // Os seis componentes.
    comps.forEach((c, i) => {
      const y = top + i * rowH;
      const cor = c.tipo === "monofasico" ? "var(--crimson)"
        : c.tipo === "trifasico" ? "var(--navy-2)" : "var(--purple)";
      s += '<line x1="' + xLoad + '" y1="' + y + '" x2="' + xComp +
        '" y2="' + y + '" stroke="var(--line-2)" stroke-width="1.2"/>';
      if (c.tipo === "trifasico" || c.tipo === "monofasico") {
        s += '<circle cx="' + (xComp + 10) + '" cy="' + y + '" r="9" ' +
          'fill="var(--panel-2)" stroke="' + cor + '" stroke-width="1.4"/>';
        s += '<text x="' + (xComp + 10) + '" y="' + (y + 3.5) +
          '" text-anchor="middle" font-size="9" fill="' + cor + '">M</text>';
      } else {
        s += '<rect x="' + (xComp + 1) + '" y="' + (y - 8) + '" width="18" ' +
          'height="16" rx="2" fill="var(--panel-2)" stroke="' + cor +
          '" stroke-width="1.4"/>';
      }
      s += '<text x="' + (xComp + 26) + '" y="' + (y + 3.5) +
        '" font-size="10" fill="var(--ink)">' + App.esc(c.nome) + "</text>";
      s += '<text x="' + (xComp + 26) + '" y="' + (y + 13) +
        '" font-size="8.5" fill="var(--muted)">' +
        App.esc(c.tipo) + "</text>";
    });

    // Injeção de geração distribuída no barramento de carga.
    s += '<text x="' + (xLoad - 4) + '" y="' + (yBus1 + 40) +
      '" text-anchor="end" font-size="9" fill="var(--green)">' +
      "Pdg + jQdg (MMGD)</text>";
    s += "</svg>";
    return s;
  }

  // -------------------------------------------------------------- tabelas
  function paramTable(params, U) {
    const rows = params.map((p) =>
      "<tr><td><code>" + U.esc(p.nome) + "</code></td>" +
      '<td class="num">' + fmtVal(p.valor) + "</td>" +
      '<td class="num muted small">' + fmtVal(p.referencia) + "</td>" +
      "<td>" + U.esc(p.unidade) + "</td>" +
      "<td>" + originChip(p.origem) + "</td>" +
      '<td class="small muted">' + U.esc(p.descricao) +
      (p.nota ? ' <span class="muted">· ' + U.esc(p.nota) + "</span>" : "") +
      "</td></tr>").join("");
    return '<div class="table-wrap scroll-y"><table>' +
      "<thead><tr><th>campo</th><th>valor</th><th>referência</th>" +
      "<th>un.</th><th>procedência</th><th>o que é</th></tr></thead>" +
      "<tbody>" + rows + "</tbody></table></div>";
  }

  function wecTable(ex, U) {
    const rows = ex.linhas.map((l) =>
      "<tr><td>" + U.esc(l.componente) + "</td>" +
      '<td class="num">' + U.num(l.mw, 0) + "</td>" +
      '<td class="num">' + U.num(l.mvar, 0) + "</td>" +
      '<td class="num">' + U.num(l.peso, 2) + "</td>" +
      '<td class="num">' + U.num(l.admitancia_calculada, 4) + "</td>" +
      '<td class="num muted">' + U.num(l.admitancia_publicada, 4) + "</td>" +
      '<td class="num">' + U.num(l.fracao_em_servico, 2) + "</td>" +
      '<td class="num">' + U.num(l.remanescente_calculada, 4) + "</td>" +
      '<td class="num muted">' + U.num(l.remanescente_publicada, 4) + "</td>" +
      "</tr>").join("");
    return '<div class="table-wrap"><table><thead><tr>' +
      "<th>componente</th><th>MW</th><th>Mvar</th><th>peso</th>" +
      "<th>B calc.</th><th>B publ.</th><th>em serviço</th>" +
      "<th>rem. calc.</th><th>rem. publ.</th></tr></thead><tbody>" + rows +
      "<tr><td><strong>total</strong></td><td></td><td></td><td></td>" +
      '<td class="num"><strong>' + U.num(ex.total_calculado, 4) +
      '</strong></td><td class="num muted">' + U.num(ex.total_publicado, 4) +
      '</td><td></td><td class="num"><strong>' +
      U.num(ex.remanescente_calculado, 4) + '</strong></td>' +
      '<td class="num muted">' + U.num(ex.remanescente_publicado, 4) +
      "</td></tr></tbody></table></div>";
  }

  function coherenceTable(co, U) {
    const rows = co.linhas.map((l) =>
      "<tr><td>" + U.esc(l.classe) + "</td>" +
      '<td class="num">' + U.pct(l.motora_clm, 1) + "</td>" +
      '<td class="num">' + U.pct(l.motora_mapa, 1) + "</td>" +
      '<td class="num">' + (l.desvio === 0 ? "0" : U.num(l.desvio, 8)) +
      "</td></tr>").join("");
    return '<div class="table-wrap"><table><thead><tr><th>classe</th>' +
      "<th>motora · CLM</th><th>motora · Mapa</th><th>desvio</th>" +
      "</tr></thead><tbody>" + rows + "</tbody></table></div>";
  }

  function checkList(items, U) {
    return items.map((c) =>
      '<div class="stat-line"><span class="k">' +
      '<span class="chip ' + (c.ok ? "green" : "crimson") + '">' +
      (c.ok ? "confere" : "falha") + "</span> " + U.esc(c.nome) +
      '</span><span class="v">' + U.esc(c.obtido) + "</span></div>" +
      '<div class="small muted" style="margin:-2px 0 8px">' +
      U.esc(c.porque) + "</div>").join("");
  }

  function fractionBars(fr, U) {
    const keys = ["Fma", "Fmb", "Fmc", "Fmd", "Fel", "estatica"];
    const nomes = {
      Fma: "Motor A · trifásico", Fmb: "Motor B · trifásico",
      Fmc: "Motor C · trifásico", Fmd: "Motor D · monofásico",
      Fel: "Eletrônica", estatica: "Estática",
    };
    return keys.map((k) =>
      U.barRow(nomes[k], fr[k] || 0, U.pct(fr[k] || 0, 1), COMP_COLOR[k])
    ).join("");
  }

  function contributionTable(fr, U) {
    const classes = Object.keys(fr.mix || {}).filter((c) => fr.mix[c] > 0);
    const comps = ["Fma", "Fmb", "Fmc", "Fmd", "Fel"];
    const head = "<thead><tr><th>componente</th>" +
      classes.map((c) => "<th>" + U.esc(c) + "</th>").join("") +
      "<th>total</th></tr></thead>";
    const rows = comps.map((k) => {
      const cells = classes.map((c) =>
        '<td class="num muted">' +
        U.pct((fr.contribuicao[k] || {})[c] || 0, 1) + "</td>").join("");
      return "<tr><td><code>" + k + "</code></td>" + cells +
        '<td class="num">' + U.pct(fr[k] || 0, 1) + "</td></tr>";
    }).join("");
    return '<div class="table-wrap"><table>' + head + "<tbody>" + rows +
      "</tbody></table></div>";
  }

  // --------------------------------------------------------------- curvas
  function drawCurves(cv) {
    const vs = cv.tensao;
    const vfmt = (v) => Number(v).toFixed(2);

    const host = (id) => document.getElementById(id);

    if (host("ch-estatica")) {
      Charts.lineChart(host("ch-estatica"), {
        index: vs, height: 220, digits: 2, yLabel: "fator de P e Q",
        formatTime: vfmt, xTicks: 9,
        series: [
          { label: "P / Po", values: cv.estatica.p, color: "teal" },
          { label: "Q / Qo", values: cv.estatica.q, color: "amber" },
        ],
      });
    }

    /* Motor D: as duas características no mesmo eixo. O que importa é onde
       uma cruza a outra — é ali que o compressor trava. */
    if (host("ch-motor-d")) {
      const iBrk = vs.findIndex((v) => v >= cv.motor_d.vstallbrk);
      const iStall = vs.findIndex((v) => v >= cv.motor_d.vstall);
      Charts.lineChart(host("ch-motor-d"), {
        index: vs, height: 250, digits: 2, yLabel: "P (pu)",
        formatTime: vfmt, xTicks: 9, zeroBase: true,
        spans: [
          { from: 0, to: Math.max(iBrk, 0), color: "crimson", opacity: 0.07,
            label: "abaixo de Vstallbrk" },
          { from: Math.max(iStall, 0), to: Math.max(iStall, 0) + 1,
            color: "amber", opacity: 0.9, label: "Vstall" },
        ],
        series: [
          { label: "regime", values: cv.motor_d.regime_p, color: "teal" },
          { label: "rotor bloqueado", values: cv.motor_d.travado_p,
            color: "crimson", style: "dash" },
        ],
      });
    }

    if (host("ch-motor-d-q")) {
      Charts.lineChart(host("ch-motor-d-q"), {
        index: vs, height: 200, digits: 2, yLabel: "Q (pu)",
        formatTime: vfmt, xTicks: 9,
        series: [
          { label: "regime", values: cv.motor_d.regime_q, color: "teal" },
          { label: "rotor bloqueado", values: cv.motor_d.travado_q,
            color: "crimson", style: "dash" },
        ],
      });
    }

    if (host("ch-eletronica")) {
      Charts.lineChart(host("ch-eletronica"), {
        index: vs, height: 200, digits: 2, yLabel: "fração em serviço",
        formatTime: vfmt, xTicks: 9, zeroBase: true,
        series: [
          { label: "descida", values: cv.eletronica.descida, color: "teal" },
          { label: "recuperação", values: cv.eletronica.subida,
            color: "amber", style: "dash" },
        ],
      });
    }

    if (host("ch-termica")) {
      Charts.lineChart(host("ch-termica"), {
        index: cv.termica.temperatura, height: 190, digits: 2,
        yLabel: "fração não desligada", zeroBase: true, xTicks: 7,
        formatTime: (t) => Number(t).toFixed(1),
        series: [{ label: "fth", values: cv.termica.fracao, color: "crimson" }],
      });
    }

    if (host("ch-contator")) {
      Charts.lineChart(host("ch-contator"), {
        index: vs, height: 190, digits: 2, yLabel: "fração fechada",
        formatTime: vfmt, xTicks: 9, zeroBase: true,
        series: [{ label: "fcn", values: cv.contator.fracao, color: "amber" }],
      });
    }

    if (host("ch-conjugado")) {
      Charts.lineChart(host("ch-conjugado"), {
        index: cv.conjugado.velocidade, height: 190, digits: 2,
        yLabel: "Tm (pu)", zeroBase: true, xTicks: 7,
        formatTime: (w) => Number(w).toFixed(2),
        series: [
          { label: "Etrq = 0 · motor A", values: cv.conjugado.etrq_0,
            color: "navy-2" },
          { label: "Etrq = 2 · motores B e C", values: cv.conjugado.etrq_2,
            color: "green" },
        ],
      });
    }
  }

  // ----------------------------------------------------------------- view
  V.clm = {
    title: "Parametrização do Modelo de Carga Composta",
    subtitle: "CMPLDW segundo a especificação do WECC: estrutura, equações e "
            + "cartão de parâmetros com procedência campo a campo",
    loadingText: "Montando o registro de parâmetros e as curvas do modelo…",

    async render(root, ST, U) {
      const [specBody, subsBody] = await Promise.all([
        Api.get("clm/spec"),
        Api.get("mapa/substations?limit=60").catch(() => null),
      ]);
      const sp = specBody.data;
      const lista = subsBody ? (subsBody.data.rows || []) : [];

      /* Entrega vinda da seção Fronteira T–D: SE escolhida lá, composição
         pela BDGD/ANEEL. A SE pode não estar entre as 60 do Mapa. */
      const hand = ST.clmHandoff;
      if (hand) {
        S.subId = hand.subId; S.subName = hand.name || hand.subId;
        S.fonte = hand.fonte || "";
        ST.clmHandoff = null;
      }
      if (S.subId && !lista.some((s) => s.sub_id === S.subId)) {
        lista.unshift({ sub_id: S.subId, name: S.subName || S.subId, uf: "—" });
      }

      const q = [];
      if (S.subId) q.push("sub_id=" + encodeURIComponent(S.subId));
      if (S.subId && S.fonte) q.push("fonte=" + encodeURIComponent(S.fonte));
      q.push("ac_factor=" + S.acFactor);
      if (!S.subId) {
        Object.keys(S.mix).forEach((k) => q.push(k + "=" + S.mix[k]));
      }
      const [cardBody, curvesBody, valBody] = await Promise.all([
        Api.get("clm/cartao?" + q.join("&")),
        Api.get("clm/curvas?vstall=" + S.vstall + "&vd1=" + S.vd1 +
                "&vd2=" + S.vd2 + "&frcel=" + S.frcel),
        Api.get("clm/validacao"),
      ]);
      const card = cardBody.data;
      const cv = curvesBody.data;
      const val = valBody.data;
      const fr = card.fracoes;
      const cob = card.cobertura || {};

      const blocos = card.blocos || {};
      const byBlock = {};
      (card.parametros || []).forEach((p) => {
        (byBlock[p.bloco] = byBlock[p.bloco] || []).push(p);
      });
      const blockKeys = Object.keys(blocos).filter((b) => byBlock[b]);
      if (!byBlock[S.block]) S.block = blockKeys[0];

      const subOpts = ['<option value="">Composição livre</option>'].concat(
        lista.map((s) =>
          '<option value="' + U.esc(s.sub_id) + '"' +
          (s.sub_id === S.subId ? " selected" : "") + ">" +
          U.esc(s.name) + " · " + U.esc(s.uf) + "</option>")
      ).join("");

      root.innerHTML =
        '<div class="note-strip">Cartão de parâmetros <strong>com ' +
        "procedência</strong>, não caso pronto para simulação. Destino: " +
        "parametrização do CLM no <strong>ORGANON</strong> — os campos do " +
        "CMPLDW são os mesmos em PSS/E, PSLF, PowerWorld e DSATools, e por " +
        "isso o cartão é neutro. Os " + (cob.A_CALIBRAR || 0) + " campos " +
        "marcados <em>a calibrar</em> trazem o valor do conjunto de " +
        "referência publicado e <strong>não são afirmação desta " +
        "ferramenta</strong>.</div>" +

        '<div class="grid g4" style="margin-bottom:14px">' +
          U.kpi("Campos do modelo", U.num(sp.total_parametros, 0), "",
                "registro completo do CMPLDW") +
          U.kpi("Derivados de dado nosso", U.num(cob.DERIVADO || 0, 0), "",
                "composição de classe e capacidade de fronteira", "green") +
          U.kpi("Premissa versionada", U.num(cob.PREMISSA || 0, 0), "",
                "hipótese declarada, com o motivo escrito", "amber") +
          U.kpi("A calibrar", U.num(cob.A_CALIBRAR || 0, 0), "",
                "exigem ensaio ou base cadastral", "crimson") +
        "</div>" +

        U.card("Estrutura do modelo",
          topologyDiagram(sp.topologia),
          { note: "Metade do efeito dinâmico do CLM vem da <strong>rede " +
                  "entre</strong> o barramento de transmissão e o uso final: " +
                  "é a impedância do transformador e do alimentador que faz " +
                  "a tensão no uso final cair mais do que a medida na " +
                  "subestação — e é o que leva o compressor a travar." }) +

        '<div class="grid g-2-1" style="margin:14px 0">' +
          U.card("Composição da carga",
            '<div class="chips" style="margin-bottom:12px">' +
              '<select id="clm-sub" class="chip clickable" ' +
              'style="min-width:220px">' + subOpts + "</select>" +
              '<label class="chip" style="gap:6px">motor D ×' +
              '<input id="clm-ac" type="range" min="0" max="2" step="0.05" ' +
              'value="' + S.acFactor + '" style="width:92px">' +
              '<span id="clm-ac-v">' + U.num(S.acFactor, 2) + "</span>" +
              "</label>" +
            "</div>" +
            (S.subId
              ? '<div class="chips" style="margin:-4px 0 12px">' +
                '<span class="small muted" style="align-self:center">' +
                "composição por</span>" +
                '<span class="chip clickable' + (!S.fonte ? " on" : "") +
                '" data-fonte="">Mapa Inteligente</span>' +
                '<span class="chip clickable' + (S.fonte === "bdgd" ? " on" : "") +
                '" data-fonte="bdgd">BDGD + SAMP (ANEEL)</span></div>'
              : "") +
            fractionBars(fr, U) +
            '<div style="margin-top:12px">' + contributionTable(fr, U) +
            "</div>",
            { hint: card.fonte_composicao,
              note: "A soma das quatro frações de motor reproduz exatamente " +
                    "a fração motora que o Mapa Inteligente publica — as " +
                    "duas telas não podem divergir sobre a mesma grandeza. " +
                    "O cursor do <strong>motor D</strong> existe porque é o " +
                    "parâmetro mais consequente e o menos conhecido aqui: a " +
                    "penetração de ar condicionado no Brasil não é a do " +
                    "sudoeste norte-americano de onde vem o modelo." }) +

          U.card("Contexto e aplicabilidade",
            U.statLines([
              ["subestação", U.esc(card.subestacao.nome)],
              ["UF · subsistema", U.esc(card.subestacao.uf) + " · " +
                U.esc(card.subestacao.subsistema)],
              ["MVA de fronteira", U.num(card.subestacao.mva_fronteira, 1)],
              ["secundário", U.num(card.subestacao.kv_secundario, 1) + " kV"],
              ["raio de influência", U.num(card.subestacao.raio_km, 2) + " km"],
              ["escala do alimentador", "×" + U.num(card.escala_alimentador, 3)],
              ["confiança da classe", U.esc(card.subestacao.confianca)],
              ["adequação da amostra",
                U.esc(card.subestacao.adequacao_amostra)],
            ]) +
            '<div style="margin-top:10px">' +
              (card.aplicabilidade.testes || []).map((t) =>
                '<div class="stat-line"><span class="k">' +
                '<span class="chip ' + (t.ok ? "green" : "amber") + '">' +
                (t.ok ? "ok" : "atenção") + "</span> " + U.esc(t.criterio) +
                '</span><span class="v">' + U.num(t.valor, 2) + " · " +
                U.esc(t.limite) + "</span></div>").join("") +
            "</div>",
            { note: "O CLM não deve ser aplicado a qualquer barra: carga " +
                    "pequena, tensão baixa ou relação P/Q desfavorável " +
                    "produzem erro de inicialização." }) +
        "</div>" +

        U.card("Cartão de parâmetros",
          '<div class="chips" style="margin-bottom:10px">' +
            blockKeys.map((b) =>
              '<span class="chip clickable' + (b === S.block ? " on" : "") +
              '" data-block="' + U.esc(b) + '">' + U.esc(blocos[b]) +
              " · " + byBlock[b].length + "</span>").join("") +
          "</div>" +
          '<div id="clm-params">' + paramTable(byBlock[S.block], U) + "</div>",
          { hint: "procedência campo a campo",
            note: "<strong>derivado</strong> vem de dado que esta ferramenta " +
                  "observa · <strong>WECC</strong> está fixado na " +
                  "especificação · <strong>referência</strong> é o conjunto " +
                  "publicado em arXiv:1708.00939 · <strong>premissa</strong> " +
                  "é hipótese nossa, declarada · <strong>a calibrar</strong> " +
                  "não é afirmado." }) +

        '<div class="grid g2" style="margin:14px 0">' +
          U.card("Motor A, B e C: o que de fato os distingue",
            '<div id="ch-conjugado"></div>' +
            '<div style="margin-top:10px">' +
              Object.keys(sp.motores_3f || {}).map((k) => {
                const m = sp.motores_3f[k];
                return '<div class="stat-line"><span class="k">' +
                  U.esc(blocos[k] || k) + '</span><span class="v">H = ' +
                  U.num(m.h, 1) + " s · Etrq = " + U.num(m.etrq, 0) +
                  "</span></div>" +
                  '<div class="small muted" style="margin:-2px 0 6px">' +
                  "leitura convencional: " + U.esc(m.leitura) +
                  (m.trip_uv ? " · com desligamento por subtensão"
                             : " · sem desligamento por subtensão") + "</div>";
              }).join("") +
            "</div>",
            { note: "Não existe campo “tipo de equipamento” no CMPLDW. A " +
                    "diferença entre os três motores trifásicos está " +
                    "<strong>inteiramente</strong> em H e Etrq. A leitura de " +
                    "equipamento é a convencional da literatura, e está " +
                    "rotulada como tal — não é dado." }) +

          U.card("Carga estática", '<div id="ch-estatica"></div>',
            { hint: "P1c=" + U.num(cv.estatica.p1c, 2) + " · P1e=" +
                    U.num(cv.estatica.p1e, 2),
              note: U.esc(cv.estatica.nota) }) +
        "</div>" +

        U.card("Motor D · compressor monofásico",
          '<div class="grid g-2-1">' +
            "<div>" +
              '<div id="ch-motor-d"></div>' +
              '<div id="ch-motor-d-q" style="margin-top:10px"></div>' +
            "</div>" +
            "<div>" +
              U.statLines([
                ["Vstallbrk · bissecção",
                  U.num(cv.motor_d.vstallbrk_bisseccao, 4) + " pu"],
                ["Vstallbrk · laço publicado",
                  U.num(cv.motor_d.vstallbrk_laco_publicado, 4) + " pu"],
                ["Vstall ajustado", U.num(cv.motor_d.vstall, 3) + " pu"],
                ["tensão de quebra", U.num(cv.motor_d.v_quebra, 2) + " pu"],
                ["Gstall", U.num(cv.motor_d.gstall, 4)],
                ["Bstall", U.num(cv.motor_d.bstall, 4)],
                ["Q'o inicial", U.num(cv.motor_d.qo, 4)],
              ]) +
              '<div class="chips" style="margin-top:10px">' +
                '<label class="chip" style="gap:6px">Vstall' +
                '<input id="clm-vstall" type="range" min="0.40" max="0.75" ' +
                'step="0.01" value="' + S.vstall + '" style="width:86px">' +
                '<span id="clm-vstall-v">' + U.num(S.vstall, 2) +
                "</span></label>" +
              "</div>" +
              '<div class="small muted" style="margin-top:10px">' +
              U.esc(cv.motor_d.nota) + "</div>" +
            "</div>" +
          "</div>",
          { hint: "modelo por desempenho, obtido em ensaio de laboratório",
            note: "É este o componente que governa a recuperação lenta de " +
                  "tensão: travado, o compressor vira um rotor bloqueado e " +
                  "passa a absorver reativo em vez de produzir trabalho." }) +

        '<div class="grid g2" style="margin:14px 0">' +
          U.card("Carga eletrônica: descida ≠ subida",
            '<div id="ch-eletronica"></div>' +
            '<div class="chips" style="margin-top:8px">' +
              '<label class="chip" style="gap:6px">Frcel' +
              '<input id="clm-frcel" type="range" min="0" max="1" step="0.05" ' +
              'value="' + S.frcel + '" style="width:86px">' +
              '<span id="clm-frcel-v">' + U.num(S.frcel, 2) +
              "</span></label>" +
            "</div>",
            { note: U.esc(cv.eletronica.nota) }) +
          U.card("Proteções agregadas",
            '<div id="ch-termica"></div>' +
            '<div id="ch-contator" style="margin-top:10px"></div>',
            { note: "Protecão térmica (acima) e contatores (abaixo). O laço " +
                    "de histerese dos contatores é o que impede religamento " +
                    "instantâneo e oscilação numérica na fronteira." }) +
        "</div>" +

        U.card("O que prova que a implementação está correta",
          '<div class="note-strip' + (val.exemplo_wecc.confere ? "" : " warn") +
          '">A especificação publica um exemplo numérico de 100 MW com a ' +
          "tabela de resultado. Reproduzi-la é a única forma de mostrar que " +
          "a implementação está <strong>correta</strong>, e não apenas " +
          "plausível. Desvio máximo nas 12 comparações: <strong>" +
          U.num(val.exemplo_wecc.desvio_maximo, 8) + "</strong>.</div>" +
          wecTable(val.exemplo_wecc, U) +
          '<div class="small muted" style="margin:8px 0 14px">' +
          U.esc(val.exemplo_wecc.fonte) + " · reativos extras de " +
          U.num(val.exemplo_wecc.extra_vars_mvar, 1) + " Mvar, que vêm do " +
          "balanço de rede da inicialização e não da soma dos reativos dos " +
          "componentes.</div>" +
          '<div class="grid g2">' +
            U.card("Conferências independentes", checkList(val.conferencias, U),
                   { flush: true }) +
            U.card("Coerência com o Mapa Inteligente",
                   coherenceTable(val.coerencia_mapa, U),
                   { flush: true,
                     note: "Duas telas que discordassem sobre a mesma " +
                           "grandeza destruiriam a credibilidade das duas." }) +
          "</div>") +

        '<div class="grid g2" style="margin:14px 0">' +
          U.card("Geração distribuída no CLM",
            U.statLines([
              ["MMGD estimada na área",
                U.num(card.geracao_distribuida.mmgd_kwp, 0) + " kWp"],
              ["equivalente",
                U.num(card.geracao_distribuida.mmgd_mw, 3) + " MW"],
            ]) +
            '<div class="small" style="margin-top:10px"><strong>Entra ' +
            "como:</strong> " + U.esc(card.geracao_distribuida.entra_como) +
            "</div>" +
            '<div class="note-strip warn" style="margin-top:10px">' +
            U.esc(card.geracao_distribuida.nao_contemplado) + "</div>",
            { hint: "o que o CLM acomoda e o que não acomoda" }) +

          U.card("Limites desta parametrização",
            "<ul style=\"margin:0;padding-left:18px;font-size:12px;" +
            "line-height:1.65\">" +
            val.limites.map((l) => "<li>" + U.esc(l) + "</li>").join("") +
            "</ul>",
            { note: "Fontes: " +
                    Object.keys(card.fontes || {}).map((k) =>
                      "<strong>" + U.esc(k) + "</strong> " +
                      U.esc(card.fontes[k].titulo)).join(" · ") }) +
        "</div>" +

        U.card("Cartão em texto",
          '<pre class="code-block" style="max-height:340px;overflow:auto">' +
          U.esc(card.cartao_texto) + "</pre>",
          { hint: "formato neutro, com a procedência em cada linha",
            note: "Neutro de propósito: emitir a sintaxe de uma ferramenta " +
                  "específica daria a impressão de um caso pronto para " +
                  "rodar, que não é o que isto é." }) +

        U.provenanceBlock(cardBody);

      drawCurves(cv);

      // -------------------------------------------------------- interação
      const sel = root.querySelector("#clm-sub");
      if (sel) {
        sel.addEventListener("change", () => {
          S.subId = sel.value;
          const opt = sel.options[sel.selectedIndex];
          S.subName = opt ? opt.textContent.split(" · ")[0] : "";
          App.render();
        });
      }
      root.querySelectorAll("[data-fonte]").forEach((chip) => {
        chip.addEventListener("click", () => {
          S.fonte = chip.getAttribute("data-fonte");
          App.render();
        });
      });

      function slider(id, key, fmt) {
        const el = root.querySelector("#" + id);
        const out = root.querySelector("#" + id + "-v");
        if (!el) return;
        el.addEventListener("input", () => {
          if (out) out.textContent = App.num(parseFloat(el.value), fmt);
        });
        el.addEventListener("change", () => {
          S[key] = parseFloat(el.value);
          App.render();
        });
      }
      slider("clm-ac", "acFactor", 2);
      slider("clm-vstall", "vstall", 2);
      slider("clm-frcel", "frcel", 2);

      root.querySelectorAll("[data-block]").forEach((chip) => {
        chip.addEventListener("click", () => {
          S.block = chip.getAttribute("data-block");
          root.querySelectorAll("[data-block]").forEach((c) =>
            c.classList.toggle("on",
              c.getAttribute("data-block") === S.block));
          const holder = root.querySelector("#clm-params");
          if (holder) holder.innerHTML = paramTable(byBlock[S.block], U);
        });
      });
    },
  };
})();
