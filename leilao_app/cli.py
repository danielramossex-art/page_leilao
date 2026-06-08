from __future__ import annotations

import argparse
import json

from .db import init_db
from .logging_config import configure_logging
from .services.apify_importer import DEFAULT_URLS, import_from_apify
from .services.browser_capture import DEFAULT_CAPTURE_URLS, capture_and_import
from .services.collector import run_collection
from .services.importer import import_inbox, import_properties_csv
from .sources import get_capture_urls


def main() -> None:
    parser = argparse.ArgumentParser(description="Portal local de leiloes imobiliarios")
    parser.add_argument("command", choices=["init-db", "collect", "import-csv", "import-inbox", "collect-apify", "capture-url"])
    parser.add_argument("--source", action="append", help="Fonte especifica: caixa, bb, santander, itau, leiloeiros")
    parser.add_argument("--file", help="Caminho do CSV para importacao manual")
    parser.add_argument("--url", action="append", help="URL de cidade/fonte para coleta Apify ou captura por navegador")
    parser.add_argument("--max-items", type=int, help="Maximo de itens na coleta Apify")
    parser.add_argument("--headless", action="store_true", help="Executa navegador em modo invisivel quando possivel")
    parser.add_argument("--state", action="append", help="Filtra captura por estado: SP, MG, PR ou SC")
    parser.add_argument("--category", action="append", help="Filtra captura por categoria: banco, agregador, leiloeiro ou cidade")
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
    elif args.command == "capture-url":
        urls = args.url or get_capture_urls(args.state, args.category) or DEFAULT_CAPTURE_URLS
        result = capture_and_import(urls, headless=args.headless)
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
