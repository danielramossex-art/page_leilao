from __future__ import annotations

import logging
import re

from .base import BaseConnector
from ..utils import TARGET_STATES, calculate_discount, infer_debts, infer_modality, make_fingerprint, normalize_text, parse_money

logger = logging.getLogger(__name__)


class CaixaConnector(BaseConnector):
    source = "caixa"
    bank_or_auctioneer = "Caixa Econômica Federal"
    start_urls = ["https://venda-imoveis.caixa.gov.br/sistema/busca-imovel.asp"]
    source_type = "scraping"
    maintenance_notes = "A Caixa não publica API oficial para esta consulta; o HTML/ASP pode exigir manutenção."

    def fetch(self) -> list[dict]:
        items: list[dict] = []
        for state in TARGET_STATES:
            url = f"{self.start_urls[0]}?hdn_estado={state}"
            try:
                soup = self.get_soup(url)
                text = normalize_text(soup.get_text(" ")) or ""
                rows = soup.select("tr, .card, .resultado-busca, .imovel")
                parsed = 0
                for row in rows:
                    row_text = normalize_text(row.get_text(" ")) or ""
                    if "R$" not in row_text:
                        continue
                    link = None
                    anchor = row.select_one("a[href]")
                    if anchor:
                        link = self.absolute_url(url, anchor.get("href"))
                    source_url = link or url
                    raw = self.normalize_from_text(source_url, source_url, row_text, self.extract_images(row, url))
                    if raw:
                        raw.state = state
                        raw.bank_or_auctioneer = self.bank_or_auctioneer
                        if raw.discount_percent is None:
                            raw.discount_percent = calculate_discount(raw.appraisal_value, raw.minimum_value)
                        items.append(raw.as_dict())
                        parsed += 1
                if parsed == 0 and "R$" in text:
                    items.extend(self._parse_text_blocks(url, state, text))
            except Exception as exc:
                logger.warning("caixa_fetch_failed state=%s error=%s", state, exc)
                raise
        return items

    def _parse_text_blocks(self, url: str, state: str, text: str) -> list[dict]:
        blocks = re.split(r"(?=Im[oó]vel|Lote|Código|Codigo)", text)
        items = []
        for block in blocks:
            if state not in block or "R$" not in block:
                continue
            raw = self.normalize_from_text(url, url, block, [])
            if raw:
                raw.state = state
                items.append(raw.as_dict())
        return items
