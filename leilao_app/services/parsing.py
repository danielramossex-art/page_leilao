"""Source-bound parsers: never infer an appraisal from the order of prices."""
from __future__ import annotations

import csv
import io
import json
import re
from datetime import datetime
from urllib.parse import urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup

from ..utils import calculate_discount, infer_modality, normalize_text, parse_date, parse_money
from .quality import city_name, financing, normalized_key, safe_url, positive_number

SOURCE_NAMES = {
    "venda-imoveis.caixa.gov.br": "CAIXA", "portalzuk.com.br": "Portal Zuk", "zuk.com.br": "Portal Zuk",
    "megaleiloes.com.br": "Mega Leilões", "frazaoleiloes.com.br": "Frazão", "biasileiloes.com.br": "Biasi",
    "sodresantoro.com.br": "Sodré Santoro", "santanderimoveis.com.br": "Santander",
    "itau.com.br": "Itaú", "bradescocomercioeletronico.com.br": "Bradesco",
    "seuimovelbb.com.br": "Banco do Brasil", "freitasleiloeiro.com.br": "Freitas Leiloeiro",
    "spyleiloes.com.br": "Spy Leilões", "leiloesgold.com.br": "Gold Leilões",
    "cravoleiloes.com.br": "Cravo Leilões", "valeroleiloes.com.br": "Valero Leilões",
    "gustavomorettoleiloeiro.com.br": "Gustavo Moretto Leiloeiro", "kwara.com.br": "Kwara Leilões",
    "milanleiloes.com.br": "Milan Leilões", "leilaovip.com.br": "Leilão VIP",
}


def host(url: str) -> str:
    return (urlparse(url).hostname or "").removeprefix("www.")


def check_page(text: str) -> None:
    plain = normalized_key(text[:20000])
    if any(term in plain for term in ("radware bot manager", "sorry, you have been blocked", "just a moment...", "enable javascript and cookies", "comportamento malicioso")):
        raise ValueError("A fonte retornou uma página de bloqueio; nenhum imóvel foi atualizado.")


def first_money(text: str) -> float | None:
    match = re.search(r"R\$\s*([\d.,]+)", text)
    return positive_number(match.group(1)) if match else None


def labeled_money(text: str, labels: str) -> float | None:
    match = re.search(rf"(?:{labels})\s*:?\s*(R\$\s*[\d.,]+)", text, re.I)
    return first_money(match.group(1)) if match else None


def property_type(text: str) -> str | None:
    plain = normalized_key(text)
    for term, label in [("apartamento", "Apartamento"), ("direitos sobre terreno", "Direitos sobre terreno"),
                        ("conjunto comercial", "Sala comercial"), ("agencia", "Agência"), ("casa", "Casa"),
                        ("terreno", "Terreno"), ("galpao", "Galpão"), ("sobrado", "Sobrado"),
                        ("chacara", "Chácara"), ("loja", "Loja"), ("comercial", "Comercial")]:
        if term in plain:
            return label
    return None


def canonical(soup, fallback="") -> str:
    node = soup.select_one('link[rel="canonical"][href]')
    if node:
        return safe_url(node["href"]) or fallback
    node = soup.select_one('meta[property="og:url"][content]')
    return (safe_url(node["content"]) if node else None) or fallback


def parse_caixa_csv(content: bytes | str) -> list[dict]:
    if isinstance(content, bytes):
        try:
            content = content.decode("utf-8-sig")
        except UnicodeDecodeError:
            content = content.decode("cp1252")
    check_page(content)
    lines = content.splitlines()
    header_index = next((i for i, line in enumerate(lines) if "valor de avaliacao" in normalized_key(line) and ";" in line), None)
    if header_index is None:
        raise ValueError("Lista CAIXA sem cabeçalho reconhecido; nada foi importado.")
    date_match = re.search(r"\d{2}/\d{2}/\d{4}", " ".join(lines[:header_index]))
    generated = parse_date(date_match.group()) if date_match else None
    reader = csv.DictReader(io.StringIO("\n".join(lines[header_index:])), delimiter=";")
    rows = []
    for raw in reader:
        row = {normalized_key(key): (value or "").strip() for key, value in raw.items() if key}
        url = safe_url(row.get("link de acesso"))
        if not url or host(url) != "venda-imoveis.caixa.gov.br":
            continue
        code = next((value for key, value in row.items() if "do imovel" in key), None)
        description = row.get("descricao", "")
        bedrooms = re.search(r"(\d+)\s*qto", description, re.I)
        parking = re.search(r"(\d+)\s*vaga", description, re.I)
        private = re.search(r"([\d.,]+) de [áa]rea privativa", description, re.I)
        land = re.search(r"([\d.,]+) de [áa]rea do terreno", description, re.I)
        rows.append({
            "source": "caixa", "source_internal_id": code, "source_url": url, "official_url": url,
            "source_name": "CAIXA", "institution": "CAIXA", "bank_or_auctioneer": "CAIXA",
            "city": city_name(row.get("cidade")), "state": row.get("uf"), "neighborhood": row.get("bairro") or None,
            "address": row.get("endereco") or None, "minimum_value": positive_number(row.get("preco")),
            "appraisal_value": positive_number(row.get("valor de avaliacao")), "accepts_financing": financing(row.get("financiamento")),
            "property_type": property_type(description.split(",", 1)[0]), "bedrooms": int(bedrooms[1]) if bedrooms else None,
            "parking_spaces": int(parking[1]) if parking else None,
            "built_area_m2": positive_number(private[1]) if private else None, "land_area_m2": positive_number(land[1]) if land else None,
            "auction_modality": row.get("modalidade de venda") or "Não informado", "notes": description,
            "data_quality": "official_list", "source_updated_at": generated, "status": "Disponível na lista",
        })
    if not rows:
        raise ValueError("Lista CAIXA vazia ou sem links válidos; disponibilidade não alterada.")
    return rows


def _rounds(node) -> list[tuple[datetime, float, int]]:
    rounds = []
    for number, selector in [(1, ".card-first-instance-date"), (2, ".card-second-instance-date")]:
        date_node = node.select_one(selector)
        if not date_node:
            continue
        match = re.search(r"\d{2}/\d{2}/\d{4}\s+às\s+\d{2}:\d{2}", date_node.get_text(" ", strip=True))
        price_node = date_node.parent.select_one(".card-instance-value")
        date = parse_date(match.group().replace(" às ", " ")) if match else None
        price = first_money(price_node.get_text(" ")) if price_node else None
        if date and price:
            rounds.append((date, price, number))
    return rounds


def parse_mega(soup, page_url: str, now: datetime | None = None) -> list[dict]:
    now = now or datetime.now()
    detail = bool(soup.select_one("h1.section-header") and re.search(r"-([jx]\d+)$", urlparse(page_url).path, re.I))
    nodes = [soup] if detail else soup.select(".card")
    rows = []
    for node in nodes:
        anchor = node.select_one("a.card-title[href]")
        url = page_url if detail else (anchor.get("href") if anchor else "")
        if not safe_url(url) or host(url) != "megaleiloes.com.br":
            continue
        parsed = urlparse(url)
        url = urlunparse(parsed._replace(query="", fragment=""))
        code = re.search(r"-([jx]\d+)$", parsed.path, re.I)
        title_node = node.select_one("h1.section-header") if detail else anchor
        if not code or not title_node:
            continue
        title = title_node.get_text(" ", strip=True)
        location = node.select_one(".locality .value") if detail else node.select_one(".card-locality")
        location_text = location.get_text(" ", strip=True) if location else ""
        parts = [part.strip() for part in location_text.split(",")]
        if len(parts) < 2 or not re.fullmatch(r"[A-Z]{2}", parts[-1]):
            continue
        city, state = city_name(parts[-2]), parts[-1]
        rounds = _rounds(node)
        applicable = next((entry for entry in rounds if entry[0] >= now), rounds[-1] if rounds else None)
        price_node = node.select_one(".card-price")
        minimum = applicable[1] if applicable else first_money(price_node.get_text(" ")) if price_node else None
        rating = node.select_one(".rating-value .value") if detail else None
        appraisal = first_money(rating.get_text(" ")) if rating else None
        status_node = node.select_one(".instance-text")
        status = status_node.get_text(" ", strip=True) if status_node else "Não informado"
        text = node.get_text(" ", strip=True)
        if status == "Não informado":
            status = next((label for label in ("Em breve", "Aberto para lances", "Encerrado", "Arrematado", "Suspenso") if label in text), status)
        images = []
        if detail:
            og = node.select_one('meta[property="og:image"][content]')
            candidates = ([og["content"]] if og else []) + [img.get("src") or img.get("data-src") for img in node.select("img")]
        else:
            image_node = node.select_one(".card-image")
            candidates = [image_node.get("data-bg")] if image_node else []
        for image in candidates:
            if safe_url(image) and f"/batches/{code[1][1:]}/" in urlparse(image).path and image not in images:
                images.append(image)
        notice = next((urljoin(url, a["href"]) for a in node.select("a[href]") if normalized_key(a.get_text(" ", strip=True)) == "edital"), None)
        area = re.search(r"([\d.,]+)\s*m²", title)
        if detail:
            precise_area = re.search(r"área (?:útil )?privativa(?: coberta)? de ([\d.,]+)\s*m", text, re.I)
            if precise_area:
                area = precise_area
        # For lots advertised as land, title area is land, not built floor area.
        kind = property_type(title)
        parking = re.search(r"\((\d+)\s*vaga", title, re.I)
        # Conflicting title / registry counts remain unknown.
        if detail and "na realidade" in normalized_key(text):
            parking = None
        details = []
        for date, price, number in rounds:
            details.append(f"{number}ª praça: {date:%d/%m/%Y às %H:%M} — R$ {price:.2f}. Condição futura sujeita à disponibilidade.")
        rows.append({
            "source": "megaleiloes", "source_name": "Mega Leilões", "bank_or_auctioneer": "Mega Leilões",
            "source_internal_id": code[1].upper(), "source_url": url, "official_url": url,
            "city": city, "state": state, "neighborhood": parts[-3] if detail and len(parts) >= 4 else (title.split(" - ")[-3] if len(title.split(" - ")) >= 4 else None),
            "address": location_text if detail else None, "property_type": kind,
            "built_area_m2": positive_number(area[1]) if area and kind in {"Apartamento", "Sala comercial", "Galpão"} else None,
            "land_area_m2": positive_number(area[1]) if area and "terreno" in normalized_key(title) else None,
            "parking_spaces": int(parking[1]) if parking else None,
            "minimum_value": minimum, "appraisal_value": appraisal, "auction_date": applicable[0] if applicable else None,
            "ends_at": max(entry[0] for entry in rounds) if rounds else None,
            "auction_modality": f"{applicable[2]}º Leilão (Judicial)" if applicable and "Judicial" in text else infer_modality(text),
            "status": status, "images": images, "notice_url": notice,
            "notes": "\n".join(details), "data_quality": "official_detail" if detail else "official_list",
        })
    return rows



def parse_structured_detail(soup, page_url: str) -> list[dict]:
    source_name = SOURCE_NAMES.get(host(page_url))
    if not source_name:
        return []
    objects = []
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            document = json.loads(script.string or script.get_text())
        except (ValueError, TypeError):
            continue
        if isinstance(document, dict):
            objects.extend(document.get("@graph", [document]))
        elif isinstance(document, list):
            objects.extend(document)
    for record in objects:
        if not isinstance(record, dict):
            continue
        type_ = record.get("@type", "")
        types = type_ if isinstance(type_, list) else [type_]
        if not set(types).intersection({"RealEstateListing", "House", "Apartment", "Residence", "SingleFamilyResidence"}):
            continue
        if (record.get("url") or record.get("@id", "").split("#")[0]).rstrip("/") != page_url.rstrip("/"):
            continue
        address = record.get("address")
        offers = record.get("offers")
        if isinstance(offers, list):
            offers = offers[0] if len(offers) == 1 else None
        if not isinstance(address, dict) or not isinstance(offers, dict):
            continue
        if offers.get("priceCurrency") != "BRL":
            continue
        region = address.get("addressRegion")
        if not isinstance(region, str) or not re.fullmatch(r"[A-Za-z]{2}", region):
            continue
        pictures = record.get("image", [])
        pictures = pictures if isinstance(pictures, list) else [pictures]
        pictures = [value.get("url") if isinstance(value, dict) else value for value in pictures]
        availability = offers.get("availability", "")
        return [{
            "source": host(page_url), "source_name": source_name, "bank_or_auctioneer": source_name,
            "source_url": page_url, "official_url": page_url,
            "source_internal_id": str(record.get("identifier") or page_url)[:160],
            "city": city_name(address.get("addressLocality")), "state": region.upper(),
            "address": address.get("streetAddress"), "postal_code": address.get("postalCode"),
            "property_type": property_type(record.get("name", "")) or ("Apartamento" if "Apartment" in types else None),
            "minimum_value": positive_number(offers.get("price")),
            "images": [value for value in pictures if safe_url(value)], "data_quality": "official_structured",
            "status": "Indisponível" if availability.endswith(("SoldOut", "OutOfStock", "Discontinued")) else "Não informado",
        }]
    return []

def parse_html(content: str | bytes, page_url: str = "") -> list[dict]:
    soup = BeautifulSoup(content, "lxml")
    check_page(soup.get_text(" ", strip=True))
    page_url = canonical(soup, page_url)
    if host(page_url) == "megaleiloes.com.br":
        return parse_mega(soup, page_url)
    structured = parse_structured_detail(soup, page_url)
    if structured:
        return structured
    # Unknown layouts must not silently fabricate property rows from menus or ads.
    raise ValueError("Layout sem parser validado. Importe CSV com campos identificados; nenhum dado foi alterado.")
