from __future__ import annotations

from .base import BaseConnector


class ItauConnector(BaseConnector):
    source = "itau"
    bank_or_auctioneer = "Itaú"
    start_urls = ["https://www.itau.com.br/imoveis-itau"]
    source_type = "scraping"
    maintenance_notes = "Página institucional com redirecionamentos para leiloeiros parceiros; detalhes podem exigir manutenção."

    def fetch(self) -> list[dict]:
        keywords = ["imoveis", "imóveis", "leil", "venda", "lote", "edital"]
        items = []
        for url in self.start_urls:
            items.extend(self.fetch_detail_pages(url, keywords))
        return items
