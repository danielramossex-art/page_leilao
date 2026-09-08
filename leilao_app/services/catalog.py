from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ..db import session_scope
from ..models import Property
from ..utils import calculate_discount
from .quality import city_name, is_inactive, normalized_key, safe_url, source_label
from .scoring import calculate_score


def property_dict(prop: Property) -> dict:
    item = {column.name: getattr(prop, column.name) for column in Property.__table__.columns}
    item["city"] = city_name(item.get("city"))
    images = sorted(prop.images, key=lambda image: (not image.is_primary, image.id))
    item["images"] = list(dict.fromkeys(image.image_url for image in images if safe_url(image.image_url)))
    if item.get("data_quality") in (None, "legacy"):
        item["data_quality"] = "legacy"
        item["images"] = []
        if not is_inactive(item):
            item["status"] = "Revisão pendente"
    item["discount_percent"] = calculate_discount(item.get("appraisal_value"), item.get("minimum_value"))
    item["source_label"] = source_label(item)
    item["analysis"] = calculate_score(item)
    item["opportunity_score"] = item["analysis"].overall
    item["inactive"] = is_inactive(item)
    return item


def load_catalog(include_history=False) -> list[dict]:
    with session_scope() as session:
        query = select(Property).options(selectinload(Property.images)).where(Property.source != "demo")
        if not include_history:
            query = query.where(Property.data_quality.is_not(None), Property.data_quality != "legacy")
        items = [property_dict(prop) for prop in session.scalars(query).all()]
    return items if include_history else [item for item in items if not item["inactive"]]


def load_detail(property_id: int) -> dict | None:
    with session_scope() as session:
        prop = session.scalar(select(Property).options(selectinload(Property.images)).where(Property.id == property_id))
        return property_dict(prop) if prop else None


def toggle_favorite(property_id: int) -> None:
    with session_scope() as session:
        prop = session.get(Property, property_id)
        if prop:
            prop.is_favorite = not prop.is_favorite


def filter_properties(items: list[dict], filters: dict) -> list[dict]:
    minimum, maximum = filters.get("min_price", 0), filters.get("max_price", 0)
    if maximum and minimum > maximum:
        raise ValueError("O valor mínimo não pode ser maior que o preço máximo.")
    result = []
    for item in items:
        if any(filters.get(key) not in (None, "", "Todos", "Todas") and normalized_key(item.get(field)) != normalized_key(filters[key])
               for key, field in [("state", "state"), ("city", "city"), ("kind", "property_type"),
                                  ("source", "source_name"), ("modality", "auction_modality"), ("occupancy", "occupancy")]):
            continue
        price, discount = item.get("minimum_value"), item.get("discount_percent")
        if minimum and (price is None or price < minimum):
            continue
        if maximum and (price is None or price > maximum):
            continue
        if filters.get("discount", 0) and (discount is None or discount < filters["discount"]):
            continue
        finance = filters.get("financing", "Todos")
        if finance != "Todos" and item.get("accepts_financing") is not (finance == "Sim"):
            continue
        result.append(item)
    return result


def sort_properties(items: list[dict], order="Mais interessantes") -> list[dict]:
    field, descending = {
        "Mais interessantes": ("opportunity_score", True), "Maior desconto": ("discount_percent", True),
        "Menor preço": ("minimum_value", False), "Maior preço": ("minimum_value", True),
        "Mais recentes": ("first_seen_at", True),
    }[order]
    present = [item for item in items if item.get(field) is not None]
    absent = [item for item in items if item.get(field) is None]
    return sorted(present, key=lambda item: item[field], reverse=descending) + absent
