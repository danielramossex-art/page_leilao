from __future__ import annotations

import logging
import re
import urllib.parse
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime

from bs4 import BeautifulSoup

from ..services.http_client import HttpClient
from ..utils import (
    TARGET_STATES,
    calculate_discount,
    infer_debts,
    infer_modality,
    infer_state,
    make_fingerprint,
    normalize_text,
    parse_area,
    parse_date,
    parse_money,
    parse_percent,
)

logger = logging.getLogger(__name__)


@dataclass
class RawProperty:
    source: str
    bank_or_auctioneer: str
    source_url: str
    source_internal_id: str | None = None
    state: str | None = None
    city: str | None = None
    neighborhood: str | None = None
    address: str | None = None
    postal_code: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    registry_number: str | None = None
    property_type: str | None = None
    built_area_m2: float | None = None
    land_area_m2: float | None = None
    appraisal_value: float | None = None
    minimum_value: float | None = None
    current_bid_value: float | None = None
    discount_percent: float | None = None
    auction_date: datetime | None = None
    notice_url: str | None = None
    occupancy: str | None = None
    notes: str | None = None
    images: list[str] = field(default_factory=list)
    auction_modality: str = "Não informado"
    has_debts: str = "Não informado"
    debt_value: float | None = None
    debt_description: str | None = None
    debt_information_source: str | None = None

    def as_dict(self) -> dict:
        data = self.__dict__.copy()
        data["fingerprint"] = make_fingerprint(
            [
                self.source,
                self.source_internal_id,
                self.source_url,
                self.state,
                self.city,
                self.address,
                self.minimum_value,
            ]
        )
        return data


class BaseConnector(ABC):
    source: str
    bank_or_auctioneer: str
    start_urls: list[str]
    source_type = "scraping"
    maintenance_notes = "Coleta por HTML público; pode exigir ajuste se a página alterar marcação."

    def __init__(self, http: HttpClient | None = None) -> None:
        self.http = http or HttpClient()

    @abstractmethod
    def fetch(self) -> list[dict]:
        raise NotImplementedError

    def get_soup(self, url: str) -> BeautifulSoup:
        response = self.http.get(url)
        return BeautifulSoup(response.text, "lxml")

    def absolute_url(self, base_url: str, href: str | None) -> str | None:
        if not href:
            return None
        return urllib.parse.urljoin(base_url, href)

    def extract_images(self, soup: BeautifulSoup, base_url: str) -> list[str]:
        images = []
        for img in soup.select("img"):
            src = img.get("src") or img.get("data-src") or img.get("data-original")
            absolute = self.absolute_url(base_url, src)
            if absolute and absolute not in images:
                images.append(absolute)
        return images[:20]

    def normalize_from_text(self, url: str, title: str, text: str, images: list[str] | None = None) -> RawProperty | None:
        state = infer_state(title, text, url)
        if state not in TARGET_STATES:
            return None

        money_values = re.findall(r"R\$\s*[\d\.\,]+", text)
        appraisal = parse_money(money_values[0]) if money_values else None
        minimum = parse_money(money_values[1]) if len(money_values) > 1 else appraisal
        discount_match = re.search(r"(\d{1,3}(?:,\d+)?)\s*%", text)
        discount = parse_percent(discount_match.group(1)) if discount_match else calculate_discount(appraisal, minimum)
        debt_status, debt_value, debt_source = infer_debts(text)

        city = self._infer_city(title, text, state)
        neighborhood = self._infer_after_label(text, ["Bairro", "Região"])
        address = self._infer_after_label(text, ["Endereço", "Endereco", "Localização", "Localizacao"])
        property_type = self._infer_property_type(title, text)
        built_area = self._infer_area(text, ["Área construída", "Area construida", "Área privativa"])
        land_area = self._infer_area(text, ["Área do terreno", "Area do terreno", "Terreno"])

        return RawProperty(
            source=self.source,
            bank_or_auctioneer=self.bank_or_auctioneer,
            source_url=url,
            source_internal_id=self._infer_id(url, text),
            state=state,
            city=city,
            neighborhood=neighborhood,
            address=address,
            property_type=property_type,
            built_area_m2=built_area,
            land_area_m2=land_area,
            appraisal_value=appraisal,
            minimum_value=minimum,
            current_bid_value=minimum,
            discount_percent=discount,
            auction_date=self._infer_date(text),
            notice_url=self._infer_notice_url(url, text),
            occupancy=self._infer_after_label(text, ["Ocupação", "Ocupacao", "Situação", "Situacao"]),
            notes=normalize_text(text[:2000]),
            images=images or [],
            auction_modality=infer_modality(text),
            has_debts=debt_status,
            debt_value=debt_value,
            debt_description="Informação detectada automaticamente no anúncio/edital." if debt_status == "Com dívidas" else None,
            debt_information_source=debt_source,
        )

    def parse_listing_links(self, soup: BeautifulSoup, base_url: str, keywords: list[str]) -> list[str]:
        links: list[str] = []
        for anchor in soup.select("a[href]"):
            href = self.absolute_url(base_url, anchor.get("href"))
            label = normalize_text(anchor.get_text(" ")) or ""
            joined = f"{href or ''} {label}".lower()
            if href and any(keyword.lower() in joined for keyword in keywords) and href not in links:
                links.append(href)
        return links[:100]

    def fetch_detail_pages(self, listing_url: str, keywords: list[str]) -> list[dict]:
        soup = self.get_soup(listing_url)
        links = self.parse_listing_links(soup, listing_url, keywords)
        items: list[dict] = []
        for url in links[:40]:
            try:
                detail = self.get_soup(url)
                title = normalize_text(detail.title.get_text(" ")) if detail.title else url
                text = normalize_text(detail.get_text(" ")) or ""
                raw = self.normalize_from_text(url, title or url, text, self.extract_images(detail, url))
                if raw:
                    items.append(raw.as_dict())
            except Exception as exc:
                logger.warning("detail_fetch_failed source=%s url=%s error=%s", self.source, url, exc)
        return items

    def _infer_after_label(self, text: str, labels: list[str]) -> str | None:
        for label in labels:
            match = re.search(rf"{label}\s*[:\-]\s*([^\|;\n\r]+)", text, flags=re.IGNORECASE)
            if match:
                return normalize_text(match.group(1)[:180])
        return None

    def _infer_city(self, title: str, text: str, state: str | None) -> str | None:
        match = re.search(r"([A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wÀ-ÿ\s\.\-]+)\s*/\s*(SP|MG|PR|SC)", f"{title} {text}")
        if match:
            return normalize_text(match.group(1))
        return self._infer_after_label(text, ["Cidade", "Município", "Municipio"])

    def _infer_id(self, url: str, text: str) -> str | None:
        match = re.search(r"(?:ID|Código|Codigo|Item|Lote)\s*[:#\-]?\s*([A-Za-z0-9\.\-_/]+)", text, flags=re.IGNORECASE)
        if match:
            return match.group(1)[:120]
        return urllib.parse.urlparse(url).path.strip("/").split("/")[-1][:120] or None

    def _infer_property_type(self, title: str, text: str) -> str | None:
        plain = f"{title} {text}".lower()
        for kind in ["apartamento", "casa", "terreno", "galpão", "galpao", "sala", "loja", "imóvel comercial"]:
            if kind in plain:
                return "Galpão" if kind == "galpao" else kind.title()
        return None

    def _infer_area(self, text: str, labels: list[str]) -> float | None:
        for label in labels:
            match = re.search(rf"{label}[^0-9]{{0,20}}([\d\.,]+)\s*m", text, flags=re.IGNORECASE)
            if match:
                return parse_area(match.group(1))
        return None

    def _infer_date(self, text: str):
        match = re.search(r"\b\d{2}/\d{2}/\d{4}(?:\s+\d{2}:\d{2})?\b", text)
        return parse_date(match.group(0)) if match else None

    def _infer_notice_url(self, base_url: str, text: str) -> str | None:
        match = re.search(r"https?://\S+\.pdf", text, flags=re.IGNORECASE)
        return match.group(0) if match else None
