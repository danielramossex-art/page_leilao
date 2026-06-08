from __future__ import annotations

import argparse
import json

from .db import init_db
from .logging_config import configure_logging
from .services.collector import run_collection


def main() -> None:
    parser = argparse.ArgumentParser(description="Portal local de leilões imobiliários")
    parser.add_argument("command", choices=["init-db", "collect"])
    parser.add_argument("--source", action="append", help="Fonte específica: caixa, bb, santander, itau, leiloeiros")
    args = parser.parse_args()

    configure_logging()
    if args.command == "init-db":
        init_db()
        print("Banco inicializado.")
    elif args.command == "collect":
        result = run_collection(args.source)
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
