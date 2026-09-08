import unittest
from leilao_app.geography import STATES, TARGET_STATES
from leilao_app.services.quality import state_name
from leilao_app.services.catalog import filter_properties
from leilao_app.sources import get_capture_urls
from leilao_app.connectors.caixa import CaixaConnector

class NationalTests(unittest.TestCase):
    def test_every_state_and_capital(self):
        self.assertEqual(len(TARGET_STATES), 27)
        for uf, (name, capital) in STATES.items():
            self.assertEqual(state_name(name), uf)
            self.assertEqual(state_name(uf), uf)
            rows = [{"state": uf, "city": capital}]
            self.assertEqual(filter_properties(rows, {"state":uf,"city":capital}),rows)
            self.assertTrue(any(f"/imoveis/{uf.lower()}" in url for url in get_capture_urls([uf])))
    def test_caixa_uses_national_list(self):
        from unittest.mock import Mock, patch
        http=Mock()
        with patch('leilao_app.connectors.caixa.parse_caixa_csv', return_value=[{'state':'AM'}]):
            rows=CaixaConnector(http=http).fetch()
        self.assertEqual(rows,[{'state':'AM'}])
        http.get.assert_called_once_with('https://venda-imoveis.caixa.gov.br/listaweb/Lista_imoveis_Geral.csv')
