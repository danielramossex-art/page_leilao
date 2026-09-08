"""Importa uma lista oficial CAIXA previamente baixada e informa cobertura real."""
import sys
import json
from pathlib import Path
from collections import Counter
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from leilao_app.db import init_db, session_scope
from leilao_app.services.parsing import parse_caixa_csv
from leilao_app.services.collector import upsert_property
from leilao_app.services.catalog import load_catalog, filter_properties
from leilao_app.geography import STATES
rows = parse_caixa_csv(Path(sys.argv[1]).read_bytes())
init_db()
for offset in range(0, len(rows), 250):
    with session_scope() as session:
        for row in rows[offset:offset+250]:
            upsert_property(session, row)
    print(f"Importados {min(offset+250,len(rows))}/{len(rows)}", flush=True)
items = load_catalog()
report = {"imported": len(rows), "states": dict(sorted(Counter(i['state'] for i in items).items())),
          "capitals": {uf: {"city": capital, "results": len(filter_properties(items, {"state": uf, "city": capital}))} for uf, (_, capital) in STATES.items()}}
Path('data/validation/national_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=True,indent=2))
