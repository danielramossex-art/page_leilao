from __future__ import annotations

import argparse
import json

from .db import init_db
from .logging_config import configure_logging
from .services.apify_importer import DEFAULT_URLS, import_from_apify
from .services.collector import run_collection
from .services.importer import import_inbox, import_properties_csv


def main() -> None:
    parser = argparse.ArgumentParser(description="Portal local de leilões imobiliários")
    parser.add_argument("command", choices=["init-db", "collect", "import-csv", "import-inbox", "collect-apify"])
    parser.add_argument("--source", action="append", help="Fonte específica: caixa, bb, santander, itau, leiloeiros")
    parser.add_argument("--file", help="Caminho do CSV para importação manual")
    parser.add_argument("--url", action="append", help="URL de cidade/fonte para coleta Apify")
    parser.add_argument("--max-items", type=int, help="Máximo de itens na coleta Apify")
    args = parser.parse_args()

    configure_logging()
    if args.command == "init-db":
        init_db()
        print("Banco inicializado.")
    elif args.command == "collect":
        result = run_collection(args.source)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == "import-csv":
        if not args.file:
            raise SystemExit("Informe --file caminho/do/arquivo.csv")
        with open(args.file, "rb") as file_obj:
            result = import_properties_csv(file_obj)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == "import-inbox":
        result = import_inbox()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == "collect-apify":
        result = import_from_apify(args.url or DEFAULT_URLS, args.max_items)
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
