from __future__ import annotations

import os
from typing import Any

import requests

from ..config import get_settings
from ..db import init_db, session_scope
from ..utils import calculate_discount, infer_debts, infer_modality, make_fingerprint, normalize_text, parse_area, parse_date, parse_money, parse_percent
from .collector import upsert_property


DEFAULT_URLS = [
    "https://www.leilaoimovel.com.br/leilao-de-imoveis/sp",
    "https://www.leilaoimovel.com.br/leilao-de-imoveis/mg",
    "https://www.leilaoimovel.com.br/leilao-de-imoveis/pr",
    "https://www.leilaoimovel.com.br/leilao-de-imoveis/sc",
]


def _env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value in (None, "") or str(value).startswith("COLE_"):
        return default
    return value


def _first(data: dict[str, Any], keys: list[str]) -> Any:
    for key in keys:
        if key in data and data[key] not in (None, ""):
            return data[key]
    return None


def _images(data: dict[str, Any]) -> list[str]:
    value = _first(data, ["images", "imageUrls", "photos", "pictures", "image", "imageUrl", "photo"])
    if not value:
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.split("|") if part.strip()]
    if isinstance(value, list):
        result = []
        for item in value:
            if isinstance(item, str):
                result.append(item)
            elif isinstance(item, dict):
                url = _first(item, ["url", "src", "imageUrl"])
                if url:
                    result.append(str(url))
        return result
    return []


def _infer_type(title: str | None) -> str | None:
    if not title:
        return None
    low = title.lower()
    for kind in ["apartamento", "casa", "terreno", "galpão", "galpao", "loja", "sobrado", "chácara", "chacara"]:
        if kind in low:
            return kind.title()
    return None


def normalize_apify_item(data: dict[str, Any]) -> dict[str, Any] | None:
    source_url = _first(data, ["url", "sourceUrl", "link", "detailUrl", "auctionUrl"])
    title = normalize_text(str(_first(data, ["title", "name", "description"]) or ""))
    city = _first(data, ["city", "cidade"])
    state = _first(data, ["state", "uf", "estado"])
    if not source_url:
        return None

    raw_text = " ".join(str(value) for value in data.values() if isinstance(value, (str, int, float)))
    debts, debt_value, debt_source = infer_debts(raw_text)
    appraisal = parse_money(_first(data, ["appraisalValue", "evaluationValue", "valorAvaliacao", "valor_avaliacao", "valuation"]))
    minimum = parse_money(_first(data, ["minimumBid", "minimumValue", "valorMinimo", "valorVenda", "price", "currentPrice"]))
    discount = parse_percent(_first(data, ["discount", "discountPercent", "desconto", "percentualDesconto"]))

    item = {
        "source": "leilaoimovel_apify",
        "source_internal_id": str(_first(data, ["id", "propertyId", "code", "codigo"]) or source_url).strip()[:160],
        "bank_or_auctioneer": _first(data, ["bank", "banco", "auctioneer", "leiloeiro", "seller"]) or "Leilão Imóvel",
        "source_url": source_url,
        "state": str(state).upper()[:2] if state else None,
        "city": city,
        "neighborhood": _first(data, ["neighborhood", "bairro"]),
        "address": _first(data, ["address", "endereco", "location"]),
        "postal_code": _first(data, ["postalCode", "cep"]),
        "latitude": float(_first(data, ["latitude", "lat"])) if _first(data, ["latitude", "lat"]) else None,
        "longitude": float(_first(data, ["longitude", "lng", "lon"])) if _first(data, ["longitude", "lng", "lon"]) else None,
        "registry_number": _first(data, ["registry", "matricula", "registration"]),
        "property_type": _first(data, ["propertyType", "tipo", "type"]) or _infer_type(title),
        "built_area_m2": parse_area(_first(data, ["builtArea", "areaConstruida", "privateArea"])),
        "land_area_m2": parse_area(_first(data, ["landArea", "areaTerreno", "totalArea"])),
        "appraisal_value": appraisal,
        "minimum_value": minimum,
        "current_bid_value": parse_money(_first(data, ["currentBid", "lanceAtual"])) or minimum,
        "discount_percent": discount or calculate_discount(appraisal, minimum),
        "auction_date": parse_date(_first(data, ["auctionDate", "dataLeilao", "closingDate", "endDate"])),
        "notice_url": _first(data, ["noticeUrl", "edital", "documentUrl"]),
        "occupancy": _first(data, ["occupancy", "ocupacao", "statusOcupacao"]),
        "notes": raw_text[:2000],
        "images": _images(data),
        "auction_modality": _first(data, ["modality", "modalidade"]) or infer_modality(raw_text),
        "has_debts": _first(data, ["hasDebts", "possuiDividas"]) or debts,
        "debt_value": parse_money(_first(data, ["debtValue", "valorDividas"])) or debt_value,
        "debt_description": _first(data, ["debtDescription", "descricaoDividas"]),
        "debt_information_source": _first(data, ["debtSource", "fonteInformacaoDividas"]) or debt_source,
    }
    item["fingerprint"] = make_fingerprint(
        [item["source"], item["source_internal_id"], item["source_url"], item["state"], item["city"], item["address"], item["minimum_value"]]
    )
    return item


def import_from_apify(urls: list[str] | None = None, max_items: int | None = None) -> dict[str, int]:
    init_db()
    get_settings()
    token = _env("APIFY_TOKEN")
    actor_id = _env("APIFY_LEILAOIMOVEL_ACTOR_ID", "gio21~leilaoimovel-scraper")
    max_items = max_items or int(_env("APIFY_MAX_ITEMS", "100") or "100")
    if not token:
        raise RuntimeError("Configure APIFY_TOKEN no .env para coleta automática via Apify.")

    payload = {"startUrls": [{"url": url} for url in (urls or DEFAULT_URLS)], "maxItems": max_items}
    endpoint = f"https://api.apify.com/v2/acts/{actor_id}/run-sync-get-dataset-items"
    response = requests.post(endpoint, params={"token": token, "clean": "true"}, json=payload, timeout=180)
    response.raise_for_status()
    rows = response.json()
    saved = 0
    with session_scope() as session:
        for row in rows:
            item = normalize_apify_item(row)
            if item:
                upsert_property(session, item)
                saved += 1
    return {"rows": len(rows), "saved": saved}
