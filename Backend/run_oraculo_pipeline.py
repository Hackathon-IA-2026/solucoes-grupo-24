# -*- coding: utf-8 -*-
"""Executa a cadeia completa em lote e imprime um relatorio no terminal.

    python run_pipeline.py                 # area padrao (SIN)
    python run_pipeline.py --area SE
    python run_pipeline.py --demo           # forca modo demonstrativo
"""
from __future__ import annotations

import argparse
import json

from oraculo import config
from oraculo.api.service import SERVICE


def head(title: str) -> None:
    print("\n" + "=" * 74)
    print(title)
    print("=" * 74)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--area", default=config.DEFAULT_AREA)
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--json", action="store_true", help="imprime payloads brutos")
    args = ap.parse_args()

    SERVICE.ensure(force_demo=args.demo)
    h = SERVICE.health()
    head("SAUDE DO SERVICO")
    print("modo:", h["mode"], "| rede:", h["network"],
          "| cache:", h["cache_entries"], "recursos,",
          round(h["cache_bytes"] / 1e6, 1), "MB")
    for d in h["datasets"]:
        print("  -", d["dataset"], "|", d["resource"], "|", d["mode"],
              "| linhas:", d["rows"])

    head("DECOMPOSICAO — %s" % args.area)
    dec = SERVICE.decomposition_payload(args.area, hours=24 * 7)
    for k in ("identity_residual_max", "mmgd_share_peak", "min_supervised_mw",
              "min_supervised_at", "max_ramp_mw_h", "implied_capacity_mwp"):
        print("  %-24s %s" % (k, dec.get(k)))
    print("  MMGD:", json.dumps(dec["mmgd"], ensure_ascii=False))

    head("PREVISAO")
    for hz in config.HORIZONS:
        try:
            f = SERVICE.forecast_payload(args.area, hz)
            m = f["metrics"]
            print("  %-6s MAE %8.1f  RMSE %8.1f  MAPE %5.2f%%  "
                  "skill_persist %+.3f  skill_sazonal %+.3f"
                  % (hz, m["mae"], m["rmse"], m["mape"],
                     f["skill"]["vs_persistence"], f["skill"]["vs_seasonal"]))
        except Exception as exc:
            print("  %-6s indisponivel: %s" % (hz, exc))

    head("EFEITO DA PERDA ASSIMETRICA (3 h)")
    val = SERVICE.validation_payload(args.area)
    eff = val["asymmetry_effect"]
    for label in ("assimetrica", "simetrica"):
        e = eff.get(label, {})
        pat = e.get("by_patamar", {})
        print("  %-12s MAE %8.1f | ponta_noturna MAE %8.1f vies %+8.1f"
              % (label, e.get("mae") or 0,
                 (pat.get("ponta_noturna") or {}).get("mae") or 0,
                 (pat.get("ponta_noturna") or {}).get("bias") or 0))

    head("BACKTEST")
    print("  split:", json.dumps(val["split"], ensure_ascii=False))
    for hz in val["horizons"]:
        print("  %-6s MAE %8.1f  pinball %7.2f  skill_persist %s"
              % (hz["horizon"], hz.get("mae") or 0, hz.get("pinball") or 0,
                 (hz.get("skill") or {}).get("persistencia")))

    head("RISCO DE CURTAILMENT")
    risk = SERVICE.risk_payload()
    print("  areas modeladas:", risk["model"].get("areas_modeled"),
          "| AUC mediana:", risk["model"].get("auc_oos_median"))
    for r in risk["areas"][:8]:
        print("  %-4s P=%.2f  E[corte]=%7.1f MW  sev=%.3f  razao=%s"
              % (r["area"], r["probability"], r["expected_mw"], r["severity"],
                 r["reason"]))

    head("TRIANGULACAO")
    tri = SERVICE.triangulation_payload()
    for a in tri["areas"]:
        print("  %-4s unidades=%4d  fator=%.3f  cobertura=%.2f  "
              "nao_homologada=%.1f MW"
              % (a["area"], a["units_total"], a["correction_factor"],
                 a["coverage"], a["capacity_unhomologated_mw"]))

    if args.json:
        head("PAYLOAD DE PREVISAO (bruto)")
        print(json.dumps(SERVICE.forecast_payload(args.area, "3h"),
                         ensure_ascii=False, indent=2)[:4000])

    print("\nConcluido.")


if __name__ == "__main__":
    main()
