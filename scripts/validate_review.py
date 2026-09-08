"""Repeatable local verification. No network, no production data changes by default."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from leilao_app.services.parsing import parse_html
from leilao_app.services.catalog import load_catalog, filter_properties
from leilao_app.services.collector import upsert_property
from leilao_app.db import init_db, session_scope

parser = argparse.ArgumentParser()
parser.add_argument("--import-verified-captures", action="store_true")
args = parser.parse_args()
root = Path(__file__).resolve().parents[1] / "data" / "validation"
expected = {"J127385": 596025.74, "J128502": 648396.0, "J128529": 538051.41}
rows = parse_html((root / "mega_jundiai.html").read_text(encoding="utf-8"))
assert len(rows) == 5
report = []
for path in sorted(root.glob("mega_detail_*.html")):
    item = parse_html(path.read_text(encoding="utf-8"))[0]
    code = item["source_internal_id"]
    assert item["city"] == "Jundiaí" and item["state"] == "SP"
    assert item["minimum_value"] == expected[code]
    assert item["appraisal_value"] == expected[code]
    assert item["notice_url"] and item["images"]
    assert all(f"/batches/{code[1:]}/" in image for image in item["images"])
    assert code.lower() in item["official_url"]
    item["verified_at"] = datetime.utcnow()
    rows.append(item)
    report.append({"code": code, "price": item["minimum_value"], "appraisal": item["appraisal_value"],
                   "city": item["city"], "source_url": item["official_url"], "image": item["images"][0],
                   "images": len(item["images"]), "comparison": "PASS"})
if args.import_verified_captures:
    init_db()
    # Commit each capture, preserving relationship state and audit histories.
    for row in rows:
        with session_scope() as session:
            assert upsert_property(session, row)
    results = filter_properties(load_catalog(), {"state": "SP", "city": "Jundiaí", "source": "Mega Leilões"})
    assert len(results) == 5
    print("Search SP/Jundiaí:", len(results))
(root / "source_comparison.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(report, ensure_ascii=True, indent=2))
