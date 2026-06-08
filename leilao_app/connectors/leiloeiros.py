from __future__ import annotations

from .base import BaseConnector


class LeiloeirosConnector(BaseConnector):
    source = "leiloeiros"
    bank_or_auctioneer = "Leiloeiros oficiais"
    start_urls = [
        "https://www.megaleiloes.com.br/leiloes/imoveis",
        "https://www.zuk.com.br/imoveis",
        "https://www.leilaovip.com.br/",
        "https://www.freitasleiloeiro.com.br/leiloes/imoveis",
    ]
    source_type = "scraping"
    maintenance_notes = "Agregação defensiva de leiloeiros públicos; cada casa tem marcação e termos próprios."

    def fetch(self) -> list[dict]:
        keywords = ["sp", "mg", "pr", "sc", "imovel", "imóvel", "lote", "apartamento", "casa"]
        items = []
        for url in self.start_urls:
            try:
                items.extend(self.fetch_detail_pages(url, keywords))
            except Exception:
                continue
        return items
