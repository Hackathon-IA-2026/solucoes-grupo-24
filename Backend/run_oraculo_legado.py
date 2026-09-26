# -*- coding: utf-8 -*-
"""Sobe o servico do O.R.A.C.U.L.O.

    python run_api.py            # http://127.0.0.1:8000
    python run_api.py --port 9000
    ORACULO_OFFLINE=1 python run_api.py     # modo demonstrativo
"""
import argparse
import webbrowser

import uvicorn


def main() -> None:
    ap = argparse.ArgumentParser(description="Servico O.R.A.C.U.L.O.")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--open", action="store_true", help="abre o navegador")
    ap.add_argument("--reload", action="store_true")
    args = ap.parse_args()

    url = "http://%s:%d/" % (args.host, args.port)
    print("O.R.A.C.U.L.O. -> %s" % url)
    if args.open:
        webbrowser.open(url)
    uvicorn.run("oraculo.api.app:app", host=args.host, port=args.port,
                reload=args.reload, log_level="info")


if __name__ == "__main__":
    main()
