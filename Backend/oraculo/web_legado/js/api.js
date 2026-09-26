/* O.R.A.C.U.L.O. — camada de dados.
   Toda resposta traz o envelope de proveniencia; a interface nunca calcula
   grandeza analitica, apenas apresenta e navega. */
(function (global) {
  "use strict";

  const CACHE = new Map();

  function qs(params) {
    const p = [];
    for (const k in params) {
      if (params[k] === undefined || params[k] === null || params[k] === "") continue;
      p.push(encodeURIComponent(k) + "=" + encodeURIComponent(params[k]));
    }
    return p.length ? "?" + p.join("&") : "";
  }

  async function get(path, params, opts) {
    const o = opts || {};
    const url = "/api/" + path + qs(params);
    if (!o.fresh && CACHE.has(url)) return CACHE.get(url);
    let res, body;
    try {
      res = await fetch(url, { headers: { Accept: "application/json" } });
    } catch (err) {
      throw new ApiError("NETWORK", "Não foi possível falar com o serviço.",
                         "Verifique se o processo do O.R.A.C.U.L.O. está em execução.");
    }
    try {
      body = await res.json();
    } catch (err) {
      throw new ApiError("PARSE", "Resposta inválida do serviço.", "");
    }
    if (!body || body.ok !== true) {
      const e = (body && body.error) || {};
      throw new ApiError(e.code || "INTERNAL", e.message || "Falha desconhecida.", e.hint || "");
    }
    if (!Array.isArray(body.provenance)) {
      throw new ApiError("CONTRACT",
        "Resposta sem envelope de proveniência — falha de contrato.",
        "Ver RNF-04 na especificação.");
    }
    CACHE.set(url, body);
    return body;
  }

  async function post(path, payload) {
    const res = await fetch("/api/" + path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload || {}),
    });
    const body = await res.json();
    if (!body || body.ok !== true) {
      const e = (body && body.error) || {};
      throw new ApiError(e.code || "INTERNAL", e.message || "Falha.", e.hint || "");
    }
    CACHE.clear();
    return body;
  }

  class ApiError extends Error {
    constructor(code, message, hint) {
      super(message);
      this.code = code;
      this.hint = hint;
    }
  }

  function clearCache() { CACHE.clear(); }

  global.Api = {
    get, post, clearCache, ApiError,
    meta: () => get("meta"),
    health: (fresh) => get("health", null, { fresh: fresh }),
    catalog: (refresh) => get("catalog", refresh ? { refresh: 1 } : null, { fresh: !!refresh }),
    packageDetail: (pkg) => get("catalog/" + encodeURIComponent(pkg)),
    series: (area, hours) => get("series", { area, hours }),
    decomposition: (area, hours) => get("decomposition", { area, hours }),
    forecast: (area, horizon, asymmetric) =>
      get("forecast", { area, horizon, asymmetric: asymmetric ? 1 : 0 }),
    profiles: (area) => get("profiles", { area }),
    risk: (horizon, level, minProb) =>
      get("risk", { horizon, level, min_probability: minProb }),
    validation: (area, asymmetric) =>
      get("validation", { area, asymmetric: asymmetric ? 1 : 0 }),
    triangulation: () => get("triangulation"),
    provenance: () => get("provenance", null, { fresh: true }),
    ingest: (payload) => post("ingest", payload),
  };
})(window);
