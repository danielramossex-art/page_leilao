from __future__ import annotations
from .base import BaseConnector
from ..utils import TARGET_STATES
from ..services.parsing import parse_caixa_csv

class CaixaConnector(BaseConnector):
    source = "caixa"
    bank_or_auctioneer = "CAIXA"
    start_urls = ["https://venda-imoveis.caixa.gov.br/sistema/download-lista.asp"]
    source_type = "official_csv"
    maintenance_notes = "CSV oficial com cabeçalhos. Bloqueios e arquivos inválidos são erros, nunca imóveis."
    def fetch(self) -> list[dict]:
        items = []
        for state in sorted(TARGET_STATES):
            response = self.http.get(f"https://venda-imoveis.caixa.gov.br/listaweb/Lista_imoveis_{state}.csv")
            items.extend(parse_caixa_csv(response.content))
        return items
