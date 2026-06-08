from __future__ import annotations

from .base import BaseConnector


class SantanderConnector(BaseConnector):
    source = "santander"
    bank_or_auctioneer = "Santander"
    start_urls = [
        "https://www.santanderimoveis.com.br/",
        "https://www.santander.com.br/hotsite/santanderimoveis/",
    ]
    source_type = "scraping"
    maintenance_notes = "O Santander alterna páginas próprias e leiloeiros parceiros; a coleta pode exigir manutenção por domínio."

    def fetch(self) -> list[dict]:
        keywords = ["imovel", "imóvel", "leil", "venda", "lote"]
        items = []
        for url in self.start_urls:
            try:
                items.extend(self.fetch_detail_pages(url, keywords))
            except Exception:
                continue
        return items
