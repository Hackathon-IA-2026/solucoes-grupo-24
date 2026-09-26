# 05 · Contrato da API

Base: `http://127.0.0.1:8000`. Todas as respostas são JSON UTF-8.

## 5.1 Envelope obrigatório

Toda resposta de sucesso segue este envelope. A ausência de `provenance` é falha
de contrato e é verificada por teste (RNF-04).

```json
{
  "ok": true,
  "mode": "live | cache | demo",
  "generated_at": "2026-09-13T22:41:07Z",
  "data": { "...": "payload específico da rota" },
  "provenance": [
    {
      "dataset": "balanco-energia-subsistema",
      "resource": "BALANCO_ENERGIA_SUBSISTEMA_2025.csv",
      "url": "https://ons-aws-prod-opendata.s3.amazonaws.com/...",
      "fetched_at": "2026-09-13T22:38:55Z",
      "rows": 43824,
      "bytes_read": 4077517,
      "mode": "cache",
      "lag_note": "Publicação consolidada; verificar defasagem de fechamento mensal."
    }
  ],
  "notes": ["Valores de MMGD são estimados, não medidos."]
}
```

Erro:

```json
{ "ok": false, "error": { "code": "UPSTREAM_UNAVAILABLE", "message": "...", "hint": "..." } }
```

Códigos: `BAD_REQUEST`, `NOT_FOUND`, `UPSTREAM_UNAVAILABLE`,
`INSUFFICIENT_DATA`, `INTERNAL`.

## 5.2 Rotas

### `GET /api/health`

Estado do serviço, modo corrente, conectividade com o Portal e estado do cache.

```json
{ "ok": true, "mode": "cache", "data": {
  "version": "0.1.0", "network": true, "cache_entries": 6,
  "cache_bytes": 20431109, "datasets_ready": ["balanco", "coff_fv", "coff_eol"] } }
```

### `GET /api/catalog`

Catálogo do Portal de Dados Abertos. `?refresh=1` força consulta à API CKAN.

`data`: `{ "packages": [ { "id", "title", "notes", "curated", "role",
"resources": [ { "name", "format", "url", "year", "month" } ] } ], "count": 85 }`

Atende RF-01 e RF-54.

### `GET /api/series`

Séries canônicas por área e janela.

| Parâmetro | Default | Descrição |
|---|---|---|
| `area` | `SIN` | `SIN`, `N`, `NE`, `S`, `SE` |
| `start`, `end` | últimos 30 dias disponíveis | `YYYY-MM-DD` |
| `fields` | todas | lista separada por vírgula |

`data`: `{ "area", "index": [ISO...], "series": { "carga_supervisionada": [...],
"mmgd_estimada": [...], "carga_global": [...], "ger_solar_centralizada": [...],
"ger_eolica": [...] }, "units": "MWmed", "gaps": 0 }`

### `GET /api/decomposition`

Decomposição da carga em janela de 24 h, com verificação da identidade (RF-10).

`data`: `{ "area", "index", "carga_global", "mmgd_estimada",
"carga_supervisionada", "identity_residual_max", "mmgd_share_peak",
"mmgd_peak_hour", "min_supervised", "min_supervised_hour", "ramp_mw_h" }`

### `GET /api/forecast`

Previsão probabilística da carga supervisionada (RF-20, RF-21, RF-23).

| Parâmetro | Valores |
|---|---|
| `area` | `SIN`, `N`, `NE`, `S`, `SE` |
| `horizon` | `30min`, `3h`, `d1` |
| `asymmetric` | `1` (default) ou `0` para comparar com perda simétrica |

`data`: `{ "area", "horizon", "index", "p10", "p50", "p90",
"baseline_persistence", "baseline_seasonal", "drivers": [ { "group", "weight" } ],
"loss": { "kind": "pinball_asimetrico", "weights_by_patamar": {...} },
"skill": { "vs_persistence": 0.41, "vs_seasonal": 0.23 } }`

Garantia verificada por teste: `p10 ≤ p50 ≤ p90` em todos os pontos.

### `GET /api/risk`

Risco de curtailment por razão energética (RF-30 a RF-33).

| Parâmetro | Valores |
|---|---|
| `horizon` | `30min`, `3h`, `d1` |
| `level` | `subsistema` (default) ou `estado` |
| `min_probability` | `0.0`–`1.0`, filtro da lista de eventos |

`data`:

```json
{
  "horizon": "d1",
  "areas": [ { "area": "BA", "probability": 0.78, "expected_mw": 412.0,
               "severity": 0.71, "reason": "ENE",
               "reason_weights": { "ENE": 0.62, "CNF": 0.24, "REL": 0.14 },
               "window": ["2026-09-14T09:00:00", "2026-09-14T15:00:00"] } ],
  "events": [ { "id", "area", "point_of_connection", "probability",
                "expected_mw", "severity", "reason", "window",
                "evidence": [ { "label", "value", "source" } ],
                "recommended_actions": ["..."] } ],
  "model": { "kind": "regressao_logistica_regularizada", "auc_oos": 0.84,
             "trained_on": { "rows": 51840, "period": ["2025-06", "2025-08"] } }
}
```

Cada evento traz `evidence` com a proveniência de cada peça, e
`recommended_actions` é apoio à decisão humana — não comando.

### `GET /api/profiles`

Perfis representativos para o Eixo 1 (RF-12).

`data`: `{ "area", "typedays": [ { "kind": "util|sabado|domingo_feriado",
"hours": [0..23], "carga_p50": [...], "carga_p10": [...], "carga_p90": [...],
"mmgd_p50": [...], "samples": [...] } ], "clm_inputs": { "load_factor",
"solar_penetration_peak", "night_anchor_mw", "ramp_max_mw_h" } }`

`clm_inputs` são os parâmetros agregados propostos como insumo à parametrização
de modelos equivalentes. **Não** são parâmetros do CLM prontos para simulação.

### `GET /api/triangulation`

Triangulação de evidências e fator de correção de capacidade (RF-40 a RF-42).

`data`: `{ "areas": [ { "area", "units_total", "matrix": { "confirmada",
"lag_de_sistema", "nao_homologada", "cadastro_sem_evidencia", "sem_evidencia" },
"capacity_declared_mw", "capacity_corrected_mw", "correction_factor",
"coverage" } ], "layers": [ { "layer", "source", "question", "cadence",
"limitation" } ] }`

### `GET /api/validation`

Resultado do backtest (RF-50 a RF-52).

`data`: `{ "split": { "train": [...], "test": [...], "leakage_free": true },
"horizons": [ { "horizon", "mae", "rmse", "mape", "pinball",
"ramp_mae_mw_h", "skill_vs_persistence", "skill_vs_seasonal",
"by_patamar": { "minima_diurna": {...}, "rampa": {...}, "ponta_noturna": {...} } } ],
"calibration": [ { "quantile": 0.1, "nominal": 0.10, "empirical": 0.11 } ],
"baselines": [ { "name", "mae", "rmse" } ] }`

### `GET /api/provenance`

Manifesto completo do cache: cada recurso baixado, quando, tamanho e hash.
É a rota de auditoria da regra "nenhum alerta sem evidência rastreável".

### `POST /api/ingest`

Dispara ingestão. Corpo: `{ "datasets": ["balanco","coff_fv","coff_eol"],
"year": 2025, "months": ["07","08"], "force": false }`.
Resposta: relatório por recurso com `rows`, `discarded`, `duplicates`, `gaps`.

## 5.3 Estáticos

`GET /` serve `web/index.html`; `GET /css/*`, `GET /js/*` servem a interface.
Nenhum recurso externo é requisitado pela página (RF-53).
