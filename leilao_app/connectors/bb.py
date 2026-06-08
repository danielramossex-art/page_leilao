from __future__ import annotations

from .base import BaseConnector


class BancoBrasilConnector(BaseConnector):
    source = "bb"
    bank_or_auctioneer = "Banco do Brasil"
    start_urls = ["https://www.seuimovelbb.com.br/"]
    source_type = "scraping"
    maintenance_notes = "Consulta pública do portal Seu Imóvel BB; pode usar conteúdo dinâmico e exigir Selenium."

    def fetch(self) -> list[dict]:
        keywords = ["imovel", "imóvel", "lote", "venda", "leil"]
        items = []
        for url in self.start_urls:
            items.extend(self.fetch_detail_pages(url, keywords))
        return items
