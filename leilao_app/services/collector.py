from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..connectors import get_connectors
from ..db import init_db, session_scope
from ..models import (
    ChangeHistory,
    CollectionError,
    CollectionRun,
    PriceHistory,
    Property,
    PropertyImage,
    ScoreHistory,
    StatusHistory,
)
from .alerts import create_alerts_for_property
from .scoring import calculate_score
from .quality import city_name, financing, is_inactive, occupancy, optional_count, positive_number, safe_url, state_name
from ..utils import calculate_discount, make_fingerprint

logger = logging.getLogger(__name__)

INACTIVE_AUCTION_TERMS = ("encerrado", "finalizado", "sustado", "cancelado", "suspenso", "arrematado")


TRACKED_FIELDS = [
    "institution", "source_name", "official_url", "bedrooms", "parking_spaces", "accepts_financing",
    "data_quality", "verified_at", "source_updated_at", "ends_at", "opportunity_score",
    "score_explanation", "automatic_summary",
    "source_url",
    "bank_or_auctioneer",
    "state",
    "city",
    "neighborhood",
    "address",
    "postal_code",
    "latitude",
    "longitude",
    "registry_number",
    "property_type",
    "built_area_m2",
    "land_area_m2",
    "appraisal_value",
    "minimum_value",
    "current_bid_value",
    "discount_percent",
    "auction_date",
    "notice_url",
    "occupancy",
    "notes",
    "auction_modality",
    "has_debts",
    "debt_value",
    "debt_description",
    "debt_information_source",
    "status",
]


def run_collection(selected_sources: list[str] | None = None) -> dict[str, Any]:
    init_db()
    summary = {"sources": 0, "items_found": 0, "items_saved": 0, "errors": 0}
    connectors = get_connectors()
    if selected_sources:
        connectors = [connector for connector in connectors if connector.source in selected_sources]

    for connector in connectors:
        summary["sources"] += 1
        with session_scope() as session:
            run = CollectionRun(source=connector.source)
            session.add(run)
            session.flush()
            run_id = run.id
        try:
            logger.info("collection_start source=%s", connector.source)
            items = connector.fetch()
            if not items:
                raise RuntimeError("Coleta sem registros estruturados; disponibilidade não foi atualizada.")
            saved = 0
            with session_scope() as session:
                run = session.get(CollectionRun, run_id)
                for item in items:
                    if upsert_property(session, item):
                        saved += 1
                run.items_found = len(items)
                run.items_saved = saved
                run.success = True
                run.finished_at = datetime.utcnow()
            summary["items_found"] += len(items)
            summary["items_saved"] += saved
            logger.info("collection_finished source=%s found=%s saved=%s", connector.source, len(items), saved)
        except Exception as exc:
            logger.exception("collection_failed source=%s", connector.source)
            with session_scope() as session:
                run = session.get(CollectionRun, run_id)
                run.success = False
                run.finished_at = datetime.utcnow()
                run.error_message = str(exc)
                session.add(CollectionError(source=connector.source, url=None, error_message=str(exc)))
            summary["errors"] += 1
    return summary


def upsert_property(session: Session, item: dict[str, Any]) -> bool:
    item = dict(item)
    item["source_url"] = safe_url(item.get("source_url"))
    if not item["source_url"]:
        return False
    item["source_internal_id"] = str(item["source_internal_id"]).strip() if item.get("source_internal_id") else None
    item["fingerprint"] = make_fingerprint([item.get("source"), item.get("source_internal_id") or item["source_url"]])
    existing = find_existing(session, item)
    if existing is not None:
        merged = {key: getattr(existing, key) for key in property_columns()}
        if existing.data_quality == "legacy":
            for field in ("appraisal_value", "minimum_value", "current_bid_value", "latitude", "longitude", "occupancy", "debt_value"):
                merged[field] = None
            merged["has_debts"] = "Não informado"
            item.setdefault("images", [])
        merged.update(item)
        item = merged
    item = prepare_item(item)
    is_new = existing is None
    price_reduced = False

    if existing is None:
        prop = Property(**{field: item.get(field) for field in property_columns() if field in item})
        prop.first_seen_at = datetime.utcnow()
        session.add(prop)
        session.flush()
        add_initial_history(session, prop)
    else:
        prop = existing
        old_minimum = prop.minimum_value
        for field in TRACKED_FIELDS:
            if field not in item:
                continue
            old = getattr(prop, field)
            new = item.get(field)
            if old != new:
                session.add(ChangeHistory(property_id=prop.id, field_name=field, old_value=str(old), new_value=str(new)))
                setattr(prop, field, new)
                if field == "status":
                    session.add(StatusHistory(property_id=prop.id, status=new))
        prop.updated_at = datetime.utcnow()
        prop.collected_at = datetime.utcnow()
        price_reduced = bool(old_minimum and prop.minimum_value and prop.minimum_value < old_minimum)

    if "images" in item:
        replace_images(session, prop, item["images"])
    append_histories(session, prop)
    create_alerts_for_property(session, prop, is_new, price_reduced)
    return True


def prepare_item(item: dict[str, Any]) -> dict[str, Any]:
    item = dict(item)
    item["city"] = city_name(item.get("city"))
    item["state"] = state_name(item.get("state"))
    for field in ("minimum_value", "appraisal_value", "current_bid_value", "built_area_m2", "land_area_m2"):
        item[field] = positive_number(item.get(field))
    for field in ("bedrooms", "parking_spaces"):
        item[field] = optional_count(item.get(field))
    item["accepts_financing"] = financing(item.get("accepts_financing"))
    item["occupancy"] = occupancy(item.get("occupancy"))
    item["notice_url"] = safe_url(item.get("notice_url"))
    item["official_url"] = safe_url(item.get("official_url"))
    item["discount_percent"] = calculate_discount(item.get("appraisal_value"), item.get("minimum_value"))
    item["data_quality"] = item.get("data_quality") or "imported"
    item["neighborhood_classification"] = "Não avaliado"
    item["neighborhood_reason"] = "Sem dados de mercado/localização confiáveis para pontuar."
    item["status"] = "Encerrado" if is_inactive(item) else (item.get("status") or "Ativo")
    score = calculate_score(item)
    item["score_financial"] = score.financial
    item["score_legal"] = score.legal
    item["score_liquidity"] = score.liquidity
    item["score_location"] = score.location
    item["score_overall"] = score.overall or 0  # legacy NOT NULL compatibility
    item["opportunity_score"] = score.overall  # nullable authoritative indicator
    item["score_explanation"] = score.explanation
    item["automatic_summary"] = score.summary
    item["collected_at"] = datetime.utcnow()
    item["updated_at"] = datetime.utcnow()
    return item


def find_existing(session: Session, item: dict[str, Any]) -> Property | None:
    if item.get("source_internal_id"):
        found = session.execute(
            select(Property).where(
                Property.source == item["source"],
                Property.source_internal_id == item["source_internal_id"],
            )
        ).scalar_one_or_none()
        if found:
            return found
    found = session.scalar(select(Property).where(Property.source == item["source"], Property.source_url == item["source_url"]).order_by(Property.id).limit(1))
    if found:
        return found
    return session.execute(select(Property).where(Property.fingerprint == item["fingerprint"])).scalar_one_or_none()


def property_columns() -> set[str]:
    return {column.name for column in Property.__table__.columns}


def add_initial_history(session: Session, prop: Property) -> None:
    session.add(StatusHistory(property_id=prop.id, status=prop.status))


def append_histories(session: Session, prop: Property) -> None:
    session.add(
        PriceHistory(
            property_id=prop.id,
            appraisal_value=prop.appraisal_value,
            minimum_value=prop.minimum_value,
            current_bid_value=prop.current_bid_value,
            discount_percent=prop.discount_percent,
        )
    )
    if prop.opportunity_score is not None:
        session.add(
            ScoreHistory(
                property_id=prop.id,
                score_financial=prop.score_financial,
                score_legal=prop.score_legal,
                score_liquidity=prop.score_liquidity,
                score_location=prop.score_location,
                score_overall=prop.opportunity_score,
                explanation=prop.score_explanation,
            )
        )



def replace_images(session: Session, prop: Property, images: list[str]) -> None:
    current = {image.image_url for image in prop.images}
    incoming = list(dict.fromkeys(url for url in images if safe_url(url)))
    if current == set(incoming):
        return
    prop.images[:] = [PropertyImage(image_url=url, is_primary=index == 0) for index, url in enumerate(incoming[:20])]
