import unittest
from datetime import datetime
from unittest.mock import patch
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from leilao_app.db import Base
from leilao_app.models import Property, PropertyImage, ScoreHistory, StatusHistory
from leilao_app.services.collector import upsert_property
from leilao_app.services.catalog import filter_properties, sort_properties, property_dict
from leilao_app.services.parsing import parse_caixa_csv, parse_html
from leilao_app.services.quality import is_inactive, safe_url
from leilao_app.services.scoring import calculate_score
from leilao_app.utils import calculate_discount, parse_date, parse_money, infer_debts


def offer(**changes):
    return {"source": "test", "source_url": "https://example.org/imovel/42", "source_internal_id": "42",
            "bank_or_auctioneer": "Fonte", "city": "Jundiaí", "state": "SP", "property_type": "Apartamento",
            "minimum_value": 300000, "appraisal_value": 500000, "occupancy": "Desocupado", "accepts_financing": True,
            "auction_modality": "Venda Direta", "notice_url": "https://example.org/edital.pdf", **changes}


class NumbersAndScore(unittest.TestCase):
    def test_numbers_discount_and_iso_time(self):
        self.assertEqual(parse_money("R$ 245.000,00"), 245000)
        self.assertEqual(parse_money("350.000"), 350000)
        self.assertIsNone(parse_money(float("nan")))
        self.assertEqual(calculate_discount(350000, 245000), 30)
        self.assertEqual(calculate_discount(100000, 120000), -20)
        self.assertIsNone(calculate_discount(0, 100))
        self.assertEqual(parse_date("2026-09-08T14:30:45").hour, 14)

    def test_vacant_not_occupied(self):
        vacant = calculate_score(offer())
        occupied = calculate_score(offer(occupancy="Ocupado"))
        self.assertGreater(vacant.overall, occupied.overall)
        self.assertEqual(vacant.classification, "Oportunidade interessante")
        self.assertNotEqual(occupied.classification, "Oportunidade interessante")
        self.assertFalse(any("possíveis custos" in reason for reason in vacant.reasons))

    def test_no_fake_score_and_no_neighborhood_effect(self):
        for changes in ({"minimum_value": None}, {"appraisal_value": 0}, {"city": None}, {"property_type": None}, {"data_quality": "legacy"}):
            self.assertIsNone(calculate_score(offer(**changes)).overall)
        self.assertEqual(calculate_score(offer(neighborhood_classification="Bairro Bom")).overall,
                         calculate_score(offer(neighborhood_classification="Bairro de Atenção")).overall)
        self.assertLessEqual(calculate_score(offer(occupancy=None)).overall, 74)

    def test_status_does_not_confuse_notes_or_first_round(self):
        self.assertFalse(is_inactive(offer(notes="O leilão anterior foi encerrado", auction_date=datetime(2020, 1, 1))))
        self.assertTrue(is_inactive(offer(status="Indisponível")))
        self.assertTrue(is_inactive(offer(ends_at=datetime(2020, 1, 1))))
        self.assertEqual(infer_debts("Confira IPTU e condomínio. Preço R$ 300.000,00")[0], "Não informado")
        self.assertIsNone(safe_url("javascript:alert(1)"))


class Persistence(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)

    def tearDown(self):
        self.session.close()
        self.engine.dispose()

    def test_update_recalculates_score_keeps_images_and_favorite(self):
        upsert_property(self.session, offer(images=["https://example.org/photo42.jpg"]))
        self.session.commit()
        prop = self.session.scalar(select(Property))
        prop.is_favorite = True
        original_score = prop.opportunity_score
        upsert_property(self.session, {"source": "test", "source_internal_id": "42", "source_url": prop.source_url, "minimum_value": 450000})
        self.session.commit()
        self.session.expire_all()
        prop = self.session.scalar(select(Property))
        self.assertLess(prop.opportunity_score, original_score)
        self.assertEqual(prop.discount_percent, 10)
        self.assertEqual(len(prop.images), 1)
        self.assertTrue(prop.is_favorite)

    def test_no_duplicate_when_price_changes_without_code(self):
        upsert_property(self.session, offer(source_internal_id=None))
        self.session.commit()
        upsert_property(self.session, offer(source_internal_id=None, minimum_value=200000))
        self.session.commit()
        self.assertEqual(len(self.session.scalars(select(Property)).all()), 1)

    def test_legacy_favorite_does_not_promote_unverified_images_or_status(self):
        upsert_property(self.session, offer(images=["https://example.org/unknown.jpg"]))
        self.session.commit()
        prop = self.session.scalar(select(Property))
        prop.data_quality = "legacy"
        prop.is_favorite = True
        result = property_dict(prop)
        self.assertEqual(result["images"], [])
        self.assertEqual(result["status"], "Revisão pendente")
        self.assertIsNone(result["opportunity_score"])

    def test_missing_appraisal_clears_score_and_explicit_unavailable_is_historical(self):
        upsert_property(self.session, offer())
        self.session.commit()
        upsert_property(self.session, offer(appraisal_value=None, status="Indisponível"))
        self.session.commit()
        prop = self.session.scalar(select(Property))
        self.assertIsNone(prop.opportunity_score)
        self.assertIsNone(prop.appraisal_value)
        self.assertGreaterEqual(len(self.session.scalars(select(StatusHistory)).all()), 2)
        self.assertEqual(len(self.session.scalars(select(ScoreHistory)).all()), 1)


class Search(unittest.TestCase):
    def test_state_city_accent_price_and_unknown_financing(self):
        items = [offer(id=1, discount_percent=40), offer(id=2, state="MG", discount_percent=40),
                 offer(id=3, minimum_value=None, accepts_financing=None, discount_percent=None)]
        result = filter_properties(items, {"state": "SP", "city": "jundiai", "max_price": 350000, "financing": "Sim"})
        self.assertEqual([x["id"] for x in result], [1])
        self.assertEqual(len(filter_properties(items, {"financing": "Não"})), 0)
        with self.assertRaises(ValueError):
            filter_properties(items, {"min_price": 500000, "max_price": 100000})

    def test_null_scores_last(self):
        items = [offer(id=1, opportunity_score=None), offer(id=2, opportunity_score=60), offer(id=3, opportunity_score=90)]
        self.assertEqual([x["id"] for x in sort_properties(items)], [3, 2, 1])


class Parsers(unittest.TestCase):
    def test_official_csv_named_columns_and_unknowns(self):
        csv = '''Lista de Imóveis da Caixa;;Data de geração:;04/09/2026
Nº do imóvel;UF;Cidade;Bairro;Endereço;Preço;Valor de avaliação;Financiamento;Descrição;Modalidade de venda;Link de acesso
123;SP;JUNDIAI;CENTRO;;245.000,00;350.000,00;Sim;Apartamento, 65.00 de área privativa, 2 qto(s), 1 vaga.;Venda Direta;https://venda-imoveis.caixa.gov.br/sistema/detalhe-imovel.asp?hdnimovel=123
'''
        row = parse_caixa_csv(csv)[0]
        self.assertEqual(row["city"], "Jundiaí")
        self.assertEqual(row["minimum_value"], 245000)
        self.assertEqual(row["appraisal_value"], 350000)
        self.assertEqual(row["bedrooms"], 2)
        self.assertEqual(row["built_area_m2"], 65)
        self.assertIsNone(row["address"])
        self.assertNotIn("images", row)

    def test_blocked_page_cannot_be_successful_empty_import(self):
        with self.assertRaises(ValueError):
            parse_caixa_csv("<title>Radware Bot Manager Block</title>")
        with self.assertRaises(ValueError):
            parse_html("<html>Sorry, you have been blocked</html>")


if __name__ == "__main__":
    unittest.main()
