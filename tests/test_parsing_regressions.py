from contextlib import closing
import json
import sqlite3
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from bs4 import BeautifulSoup
from sqlalchemy import create_engine, text, inspect
from leilao_app import db
from leilao_app.services.parsing import parse_mega, parse_html


class SourceBoundaries(unittest.TestCase):
    def test_next_round_discount_is_not_current_price_or_appraisal(self):
        markup = '''<div class="card"><a class="card-title" href="https://www.megaleiloes.com.br/imoveis/casas/sp/jundiai/casa-j12345">Casa - Centro - Jundiaí - SP</a>
        <a class="card-locality">Jundiaí, SP</a><a class="card-image" data-bg="https://cdn1.megaleiloes.com.br/batches/12345/photo.jpg"></a>
        <div>50% abaixo na 2ª praça</div><div class="card-price">R$ 500.000,00</div>
        <div><span class="card-first-instance-date">1ª Praça: 01/10/2026 às 14:00</span><span class="card-instance-value">R$ 500.000,00</span></div>
        <div><span class="card-second-instance-date">2ª Praça: 15/10/2026 às 14:00</span><span class="card-instance-value">R$ 250.000,00</span></div>
        <div>Judicial Em breve</div></div>'''
        row = parse_mega(BeautifulSoup(markup, "lxml"), "https://www.megaleiloes.com.br/imoveis/sp/jundiai", datetime(2026, 9, 8))[0]
        self.assertEqual(row["minimum_value"], 500000)
        self.assertIsNone(row["appraisal_value"])
        self.assertEqual(row["status"], "Em breve")
        self.assertEqual(row["ends_at"], datetime(2026, 10, 15, 14))

    def test_images_from_another_lot_are_ignored(self):
        markup = '''<div class="card"><a class="card-title" href="https://www.megaleiloes.com.br/imoveis/casas/sp/jundiai/casa-j12345">Casa - Centro - Jundiaí - SP</a>
        <a class="card-locality">Jundiaí, SP</a><a class="card-image" data-bg="https://cdn1.megaleiloes.com.br/batches/99999/photo.jpg"></a><div class="card-price">R$ 500.000,00</div></div>'''
        row = parse_mega(BeautifulSoup(markup, "lxml"), "https://www.megaleiloes.com.br/imoveis/sp/jundiai")[0]
        self.assertEqual(row["images"], [])

    def test_structured_data_is_bound_to_property_url(self):
        url = "https://www.portalzuk.com.br/imovel/apartamento-123"
        record = {"@type": "Apartment", "url": url, "name": "Apartamento", "address": {"addressLocality": "Jundiaí", "addressRegion": "SP"},
                  "offers": {"price": 245000, "priceCurrency": "BRL"}, "image": ["https://cdn.portalzuk.com.br/123.jpg"]}
        markup = f'<link rel="canonical" href="{url}"><script type="application/ld+json">{json.dumps(record)}</script>'
        row = parse_html(markup)[0]
        self.assertEqual(row["minimum_value"], 245000)
        self.assertNotIn("appraisal_value", row)
        unrelated = markup.replace(f'href="{url}"', 'href="https://www.portalzuk.com.br/imovel/outro-999"')
        with self.assertRaises(ValueError):
            parse_html(unrelated)


class Migration(unittest.TestCase):
    def test_additive_migration_backup_and_idempotency(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "data").mkdir()
            path = root / "data" / "legacy.db"
            engine = create_engine("sqlite:///" + path.as_posix())
            with engine.begin() as connection:
                connection.execute(text("CREATE TABLE properties (id INTEGER PRIMARY KEY, source TEXT)"))
                connection.execute(text("INSERT INTO properties VALUES (42, 'existing')"))
            with patch.object(db, "engine", engine), patch.object(db, "BASE_DIR", root):
                db.init_db()
                db.init_db()
            with engine.connect() as connection:
                self.assertEqual(connection.execute(text("SELECT id,source,data_quality FROM properties")).one(), (42, "existing", "legacy"))
            backups = list((root / "data" / "backups").glob("*.db"))
            self.assertEqual(len(backups), 1)
            with closing(sqlite3.connect(backups[0])) as backup:
                self.assertEqual(backup.execute("SELECT id,source FROM properties").fetchone(), (42, "existing"))
            self.assertIn("opportunity_score", {column["name"] for column in inspect(engine).get_columns("properties")})
            engine.dispose()
