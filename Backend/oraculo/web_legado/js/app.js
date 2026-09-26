/* O.R.A.C.U.L.O. — casca da aplicacao: roteador, estado e utilitarios de UI. */
(function (global) {
  "use strict";

  const STATE = {
    meta: null,
    health: null,
    area: "SIN",
    horizon: "3h",
    asymmetric: true,
    theme: localStorage.getItem("oraculo.theme") || "dark",
    view: "operacao",
  };

  const VIEWS = {};          // preenchido por views.js
  const NAV = [
    { group: "Operação" },
    { id: "operacao", label: "Despacho preditivo", icon: "wave" },
    { id: "risco", label: "Risco e excedentes", icon: "alert" },
    { id: "pato", label: "Curva do pato · tempo", icon: "sun" },
    { group: "Análise" },
    { id: "curtailment", label: "Curtailment", icon: "cut" },
    { id: "perfis", label: "Perfis e CLM", icon: "layers" },
    { id: "triangulacao", label: "Triangulação", icon: "target" },
    { group: "Mapa Inteligente" },
    { id: "mapa", label: "Perfis por subestação", icon: "pin" },
    { id: "visao", label: "Visão computacional", icon: "eye" },
    { id: "classes", label: "Classes de consumo", icon: "pie" },
    { id: "clm", label: "Parametrização CLM", icon: "sliders" },
    { group: "Fronteira T–D" },
    { id: "fronteira", label: "SE × distribuição", icon: "link" },
    { id: "correlacao", label: "Qualidade da correlação", icon: "check" },
    { group: "Investimento" },
    { id: "bess", label: "Alocação de BESS", icon: "battery" },
    { id: "bessmetodo", label: "Método e sensibilidade", icon: "sliders" },
    { id: "projecao", label: "Projeção do corte ENE", icon: "wave" },
    { group: "Confiança" },
    { id: "validacao", label: "Validação", icon: "check" },
    { id: "dados", label: "Dados abertos", icon: "db" },
  ];

  const ICONS = {
    wave: "M2 12c2.5 0 3-6 5.5-6S11 18 13.5 18 17 12 22 12",
    alert: "M12 3 2 20h20L12 3Zm0 6v6m0 3v.5",
    cut: "M4 20 20 4M8 6a2.5 2.5 0 1 1-3.5 3.5A2.5 2.5 0 0 1 8 6Zm12 10a2.5 2.5 0 1 1-3.5 3.5A2.5 2.5 0 0 1 20 16Z",
    layers: "M12 3 3 8l9 5 9-5-9-5Zm-9 9 9 5 9-5m-18 4.5 9 5 9-5",
    target: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18Zm0 4.5a4.5 4.5 0 1 0 0 9 4.5 4.5 0 0 0 0-9Zm0 3.5a1 1 0 1 0 0 2 1 1 0 0 0 0-2Z",
    check: "M4 12.5 9.5 18 20 6",
    db: "M12 3c4.4 0 8 1.3 8 3s-3.6 3-8 3-8-1.3-8-3 3.6-3 8-3Zm8 6c0 1.7-3.6 3-8 3s-8-1.3-8-3m16 6c0 1.7-3.6 3-8 3s-8-1.3-8-3M4 6v12m16-12v12",
    pin: "M12 21s7-6.4 7-11a7 7 0 1 0-14 0c0 4.6 7 11 7 11Zm0-8.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5Z",
    eye: "M2 12s3.8-6.5 10-6.5S22 12 22 12s-3.8 6.5-10 6.5S2 12 2 12Zm10 2.8a2.8 2.8 0 1 0 0-5.6 2.8 2.8 0 0 0 0 5.6Z",
    pie: "M12 3a9 9 0 1 0 9 9h-9V3Z",
    sun: "M12 7.5a4.5 4.5 0 1 0 0 9 4.5 4.5 0 0 0 0-9ZM12 2v2.5M12 19.5V22M2 12h2.5M19.5 12H22M4.9 4.9l1.8 1.8M17.3 17.3l1.8 1.8M4.9 19.1l1.8-1.8M17.3 6.7l1.8-1.8",
    battery: "M3 8h15v8H3zM18 11h2.5v2H18M6.5 10.5v3M9.5 10.5v3M12.5 10.5v3",
    link: "M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1",
    sliders: "M4 7h10m4 0h2M4 12h3m4 0h13M4 17h8m4 0h4M14 7a2 2 0 1 0 4 0 2 2 0 0 0-4 0Zm-7 5a2 2 0 1 0 4 0 2 2 0 0 0-4 0Zm5 5a2 2 0 1 0 4 0 2 2 0 0 0-4 0Z",
  };

  // ------------------------------------------------------------- helpers
  function h(html) {
    const t = document.createElement("template");
    t.innerHTML = html.trim();
    return t.content.firstElementChild;
  }

  function esc(s) {
    return String(s === null || s === undefined ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function num(v, d) {
    if (v === null || v === undefined || !isFinite(v)) return "—";
    return Number(v).toLocaleString("pt-BR", {
      minimumFractionDigits: d === undefined ? 0 : d,
      maximumFractionDigits: d === undefined ? 0 : d,
    });
  }

  function pct(v, d) {
    if (v === null || v === undefined || !isFinite(v)) return "—";
    return num(v * 100, d === undefined ? 1 : d) + "%";
  }

  function signed(v, d) {
    if (v === null || v === undefined || !isFinite(v)) return "—";
    return (v > 0 ? "+" : "") + num(v, d === undefined ? 3 : d);
  }

  function bytes(n) {
    if (!n) return "—";
    if (n > 1e6) return num(n / 1e6, 1) + " MB";
    if (n > 1e3) return num(n / 1e3, 0) + " kB";
    return n + " B";
  }

  function when(iso) {
    if (!iso) return "—";
    return String(iso).replace("T", " ").replace("Z", "").slice(0, 16);
  }

  function kpi(label, value, unit, foot, accent) {
    return '<div class="card"><div class="kpi ' + (accent ? "accent-" + accent : "") + '">' +
      '<div class="kpi-label">' + esc(label) + "</div>" +
      '<div class="kpi-value">' + value +
      (unit ? '<span class="unit">' + esc(unit) + "</span>" : "") + "</div>" +
      (foot ? '<div class="kpi-foot">' + foot + "</div>" : "") +
      "</div></div>";
  }

  function card(title, bodyHtml, opts) {
    const o = opts || {};
    return '<div class="card' + (o.flush ? " flush" : "") + '">' +
      (title ? '<div class="card-head"><h3>' + esc(title) + "</h3>" +
        (o.hint ? '<span class="hint">' + esc(o.hint) + "</span>" : "") + "</div>" : "") +
      bodyHtml +
      (o.note ? '<div class="card-note">' + o.note + "</div>" : "") +
      "</div>";
  }

  function barRow(label, frac, valueText, color) {
    const f = Math.max(0, Math.min(1, frac || 0));
    return '<div class="bar-row"><span>' + esc(label) + "</span>" +
      '<span class="bar-track"><span class="bar-fill" style="width:' +
      (f * 100).toFixed(1) + "%;background:" +
      (color ? "var(--" + color + ")" : "var(--teal)") + '"></span></span>' +
      '<span class="v">' + valueText + "</span></div>";
  }

  function statLines(pairs) {
    return pairs.map((p) =>
      '<div class="stat-line"><span class="k">' + esc(p[0]) +
      '</span><span class="v">' + p[1] + "</span></div>").join("");
  }

  function provenanceBlock(body) {
    const prov = (body && body.provenance) || [];
    const notes = (body && body.notes) || [];
    if (!prov.length && !notes.length) return "";
    const rows = prov.map((p) =>
      "<tr><td>" + esc(p.dataset) + "</td><td>" + esc(p.resource) +
      '</td><td><span class="chip ' + modeClass(p.mode) + '">' + esc(p.mode) +
      '</span></td><td class="num">' + num(p.rows) + '</td><td class="num">' +
      bytes(p.bytes_read) + "</td><td>" + when(p.fetched_at) +
      '</td><td class="small muted">' + esc(p.lag_note || "") + "</td></tr>").join("");
    return '<details class="prov"><summary>Proveniência e notas (' +
      prov.length + ")</summary><div class=\"prov-body\">" +
      (notes.length ? '<div class="note-strip' +
        (body.mode === "demo" ? " warn" : "") + '">' +
        notes.map(esc).join(" · ") + "</div>" : "") +
      (rows ? '<div class="table-wrap"><table><thead><tr><th>Conjunto</th>' +
        "<th>Recurso</th><th>Modo</th><th class=\"num\">Linhas</th>" +
        "<th class=\"num\">Bytes</th><th>Extraído</th><th>Defasagem declarada</th>" +
        "</tr></thead><tbody>" + rows + "</tbody></table></div>" : "") +
      "</div></details>";
  }

  function modeClass(mode) {
    return mode === "live" ? "green" : mode === "cache" ? "teal" : "amber";
  }

  function errorBlock(err) {
    return '<div class="error"><h4>' + esc(err.code || "ERRO") + "</h4><div>" +
      esc(err.message) + "</div>" +
      (err.hint ? '<div class="hint">' + esc(err.hint) + "</div>" : "") + "</div>";
  }

  function loading(text) {
    return '<div class="loading"><div class="spinner"></div>' +
      esc(text || "Carregando dados do Portal do ONS…") + "</div>";
  }

  function reasonTag(code) {
    const c = String(code || "").toLowerCase();
    return '<span class="tag tag-' + (["ene", "cnf", "rel", "par"].includes(c) ? c : "par") +
      '">' + esc(code || "—") + "</span>";
  }

  // ------------------------------------------------------------- shell
  function icon(name) {
    return '<svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
      'stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">' +
      '<path d="' + (ICONS[name] || "") + '"/></svg>';
  }

  function renderNav() {
    const nav = document.getElementById("nav");
    nav.innerHTML = NAV.map((n) => n.group
      ? '<div class="nav-group">' + esc(n.group) + "</div>"
      : '<a href="#/' + n.id + '" data-view="' + n.id + '">' + icon(n.icon) +
        "<span>" + esc(n.label) + "</span></a>").join("");
    highlightNav();
  }

  function highlightNav() {
    document.querySelectorAll("#nav a").forEach((a) => {
      a.classList.toggle("active", a.dataset.view === STATE.view);
    });
  }

  function renderTopbar() {
    const meta = STATE.meta || {};
    const health = STATE.health || {};
    const areas = meta.areas || [{ id: "SIN", name: "SIN" }];
    const mode = health.mode || "demo";
    const modeText = { live: "dados ao vivo", cache: "cache local", demo: "demonstrativo" }[mode] || mode;
    const top = document.getElementById("top");
    top.innerHTML =
      '<div><h1 id="view-title">—</h1><div class="sub" id="view-sub"></div></div>' +
      '<div class="spacer"></div>' +
      '<span class="badge badge-' + mode + '" title="Origem dos dados exibidos">' +
        '<span class="badge-dot"></span>' + esc(modeText) + "</span>" +
      (mode === "demo" ? '<span class="badge badge-demo">' +
        esc(meta.demo_banner || "DADOS DEMONSTRATIVOS") + "</span>" : "") +
      '<div class="field"><label for="sel-area">Área</label>' +
        '<select id="sel-area">' + areas.map((a) =>
          '<option value="' + a.id + '"' + (a.id === STATE.area ? " selected" : "") +
          ">" + esc(a.id) + " — " + esc(a.name) + "</option>").join("") +
        "</select></div>" +
      '<button id="btn-theme" class="ghost" title="Alternar tema">' +
        (STATE.theme === "dark" ? "☾" : "☀") + "</button>" +
      '<button id="btn-help" class="ghost" ' +
        'title="Documentação deste painel (F1)">?</button>' +
      '<button id="btn-reload" class="ghost" title="Recarregar do serviço">↻</button>';

    document.getElementById("sel-area").addEventListener("change", (ev) => {
      STATE.area = ev.target.value;
      render();
    });
    document.getElementById("btn-theme").addEventListener("click", toggleTheme);
    document.getElementById("btn-help").addEventListener("click", function () {
      toggleHelp();
    });
    document.getElementById("btn-reload").addEventListener("click", async () => {
      Api.clearCache();
      STATE.health = (await Api.health(true)).data;
      renderTopbar();
      render();
    });
  }

  function toggleTheme() {
    STATE.theme = STATE.theme === "dark" ? "light" : "dark";
    localStorage.setItem("oraculo.theme", STATE.theme);
    applyTheme();
    render();
  }

  function applyTheme() {
    document.documentElement.setAttribute("data-theme", STATE.theme);
  }

  // ------------------------------------------------------------- router
  function parseHash() {
    const raw = (location.hash || "#/operacao").replace(/^#\/?/, "");
    const id = raw.split("?")[0] || "operacao";
    return VIEWS[id] ? id : "operacao";
  }

  async function render() {
    const id = STATE.view;
    const view = VIEWS[id];
    const content = document.getElementById("content");
    const title = document.getElementById("view-title");
    const sub = document.getElementById("view-sub");
    if (title) title.textContent = view.title;
    if (sub) sub.textContent = view.subtitle || "";
    highlightNav();
    content.innerHTML = loading(view.loadingText);
    Charts.hideTip();
    try {
      await view.render(content, STATE, { h, esc, num, pct, signed, bytes, when,
        kpi, card, barRow, statLines, provenanceBlock, errorBlock, modeClass,
        reasonTag, loading });
    } catch (err) {
      if (err instanceof Api.ApiError) {
        content.innerHTML = errorBlock(err);
      } else {
        content.innerHTML = errorBlock({ code: "INTERNAL", message: String(err && err.message || err), hint: "" });
        console.error(err);
      }
    }
  }

  function onHashChange() {
    STATE.view = parseHash();
    render();
  }

  // ------------------------------------------------------------- ajuda
  /* Ajuda contextual. F1 abre a página da documentação do painel corrente,
     sem sair da aplicação: quem tem uma dúvida olhando um gráfico não deve
     precisar procurar um diretório e abrir um arquivo.

     O mapeamento painel -> página vem do SERVIDOR (/api/docs/status), não
     daqui. Um único lugar a corrigir quando uma página é renomeada, e o
     teste pode exigir que todo painel tenha página e que o arquivo exista. */
  const HELP = { info: null, open: false, lastFocus: null };

  async function loadHelpInfo() {
    if (HELP.info) return HELP.info;
    try {
      HELP.info = (await Api.get("docs/status")).data;
    } catch (err) {
      HELP.info = { disponivel: false, construida: false, prefixo: "/docs",
                    paineis: {}, geral: {},
                    nota: "Não foi possível consultar o estado da documentação." };
    }
    return HELP.info;
  }

  function helpUrl(info, panelId) {
    const pref = String(info.prefixo || "/docs").replace(/\/$/, "");
    const rel = (info.paineis || {})[panelId] || (info.geral || {}).inicio
                || "index.html";
    return pref + "/" + rel;
  }

  const HELP_LINKS = [
    ["como_ler", "Como ler os painéis"],
    ["proveniencia", "Proveniência"],
    ["limitacoes", "Limitações"],
    ["glossario", "Glossário"],
    ["api", "API"],
    ["referencia", "Código"],
  ];

  async function openHelp(panelId) {
    if (HELP.open) return;
    const info = await loadHelpInfo();
    const id = panelId || STATE.view;
    const view = VIEWS[id] || {};
    const url = helpUrl(info, id);
    const geral = info.geral || {};
    const pref = String(info.prefixo || "/docs").replace(/\/$/, "");
    const atalhos = HELP_LINKS.filter((a) => geral[a[0]]);
    const faltando = info.paginas_faltando || [];

    const corpo = info.construida
      ? '<iframe id="help-frame" src="' + esc(url) + '" title="Documentação"></iframe>'
      : '<div class="help-missing"><h3>Documentação ainda não construída</h3>'
        + "<p>" + esc(info.nota || "") + "</p>"
        + "<p><code>" + esc(info.como_construir
            || "cd 03-DOCUMENTACAO && python build_docs.py") + "</code></p>"
        + (info.diretorio
            ? '<p class="small muted">Diretório esperado: <code>'
              + esc(info.diretorio) + "</code></p>"
            : "")
        + "</div>";

    const ov = h(
      '<div class="help-overlay" role="dialog" aria-modal="true" '
      + 'aria-label="Documentação do painel">'
      + '<div class="help-panel">'
      + '<div class="help-head">'
      + '<div class="help-title"><strong>Documentação</strong>'
      + '<span class="help-ctx">' + esc(view.title || id) + "</span></div>"
      + '<div class="help-actions">'
      + atalhos.map(function (a) {
          return '<button class="ghost small help-go" data-rel="'
            + esc(geral[a[0]]) + '">' + esc(a[1]) + "</button>";
        }).join("")
      + '<a class="ghost small" id="help-new" href="' + esc(url)
      + '" target="_blank" rel="noopener" title="Abrir em nova aba">&#8599;</a>'
      + '<button class="ghost small" id="help-close" title="Fechar (Esc)">&#10005;</button>'
      + "</div></div>"
      + corpo
      + '<div class="help-foot"><span><kbd>F1</kbd> abre e fecha &middot; '
      + "<kbd>Esc</kbd> fecha</span>"
      + (faltando.length
          ? '<span class="chip crimson">' + faltando.length
            + " página(s) de painel ausente(s)</span>"
          : "")
      + "</div></div></div>");

    HELP.lastFocus = document.activeElement;
    document.body.appendChild(ov);
    document.body.classList.add("help-locked");
    HELP.open = true;

    ov.addEventListener("click", function (ev) {
      if (ev.target === ov) closeHelp();
    });
    const btn = ov.querySelector("#help-close");
    if (btn) btn.addEventListener("click", closeHelp);

    ov.querySelectorAll(".help-go").forEach(function (b) {
      b.addEventListener("click", function () {
        const dest = pref + "/" + b.getAttribute("data-rel");
        const fr = ov.querySelector("#help-frame");
        if (fr) fr.setAttribute("src", dest);
        const na = ov.querySelector("#help-new");
        if (na) na.setAttribute("href", dest);
      });
    });

    if (btn) btn.focus();
  }

  function closeHelp() {
    const ov = document.querySelector(".help-overlay");
    if (ov) ov.remove();
    document.body.classList.remove("help-locked");
    HELP.open = false;
    if (HELP.lastFocus && HELP.lastFocus.focus) HELP.lastFocus.focus();
  }

  function toggleHelp() {
    if (HELP.open) closeHelp(); else openHelp(STATE.view);
  }

  function bindHelpKeys() {
    /* preventDefault no F1 é necessário: sem ele o navegador abre a própria
       ajuda numa aba nova e o usuário perde o contexto. */
    window.addEventListener("keydown", function (ev) {
      if (ev.key === "F1") {
        ev.preventDefault();
        toggleHelp();
        return;
      }
      if (ev.key === "Escape" && HELP.open) {
        ev.preventDefault();
        closeHelp();
      }
    });
  }

  // ------------------------------------------------------------- boot
  async function boot() {
    applyTheme();
    renderNav();
    try {
      STATE.meta = (await Api.meta()).data;
      STATE.health = (await Api.health()).data;
    } catch (err) {
      document.getElementById("content").innerHTML = errorBlock(
        err instanceof Api.ApiError ? err
          : { code: "BOOT", message: "Serviço indisponível.", hint: "Execute python run_api.py" });
      return;
    }
    renderTopbar();
    STATE.view = parseHash();
    window.addEventListener("hashchange", onHashChange);
    bindHelpKeys();
    loadHelpInfo();          // aquece o mapeamento, sem bloquear a primeira tela
    let t = null;
    window.addEventListener("resize", () => {
      clearTimeout(t);
      t = setTimeout(render, 220);
    });
    render();
  }

  global.App = { STATE, VIEWS, boot, render, h, esc, num, pct, signed, bytes, when,
                 kpi, card, barRow, statLines, provenanceBlock, errorBlock,
                 modeClass, reasonTag, loading,
                 openHelp, closeHelp, toggleHelp };
})(window);
