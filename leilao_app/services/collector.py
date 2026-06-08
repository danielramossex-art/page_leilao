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
from .geocoding import geocode
from .neighborhood import classify_neighborhood
from .scoring import calculate_score

logger = logging.getLogger(__name__)


TRACKED_FIELDS = [
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
    item = prepare_item(item)
    existing = find_existing(session, item)
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
            if old != new and new is not None:
                session.add(ChangeHistory(property_id=prop.id, field_name=field, old_value=str(old), new_value=str(new)))
                setattr(prop, field, new)
        prop.updated_at = datetime.utcnow()
        prop.collected_at = datetime.utcnow()
        price_reduced = bool(old_minimum and prop.minimum_value and prop.minimum_value < old_minimum)

    replace_images(session, prop, item.get("images", []))
    append_histories(session, prop)
    create_alerts_for_property(session, prop, is_new, price_reduced)
    return True


def prepare_item(item: dict[str, Any]) -> dict[str, Any]:
    if not item.get("latitude") or not item.get("longitude"):
        lat, lon = geocode(item.get("address"), item.get("city"), item.get("state"))
        item["latitude"] = item.get("latitude") or lat
        item["longitude"] = item.get("longitude") or lon

    neighborhood_classification, neighborhood_reason = classify_neighborhood(
        item.get("city"),
        item.get("neighborhood"),
        {"discount_percent": item.get("discount_percent"), "minimum_value": item.get("minimum_value")},
    )
    item["neighborhood_classification"] = neighborhood_classification
    item["neighborhood_reason"] = neighborhood_reason

    score = calculate_score(item)
    item["score_financial"] = score.financial
    item["score_legal"] = score.legal
    item["score_liquidity"] = score.liquidity
    item["score_location"] = score.location
    item["score_overall"] = score.overall
    item["score_explanation"] = score.explanation
    item["automatic_summary"] = score.summary
    item["status"] = item.get("status") or "Ativo"
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
    session.add(
        ScoreHistory(
            property_id=prop.id,
            score_financial=prop.score_financial,
            score_legal=prop.score_legal,
            score_liquidity=prop.score_liquidity,
            score_location=prop.score_location,
            score_overall=prop.score_overall,
            explanation=prop.score_explanation,
        )
    )


def replace_images(session: Session, prop: Property, images: list[str]) -> None:
    current = {image.image_url for image in prop.images}
    incoming = [url for url in images if url]
    if current == set(incoming):
        return
    for image in list(prop.images):
        session.delete(image)
    for index, url in enumerate(incoming[:20]):
        session.add(PropertyImage(property_id=prop.id, image_url=url, is_primary=index == 0))
