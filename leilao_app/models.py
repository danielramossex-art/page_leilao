from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class Property(Base):
    __tablename__ = "properties"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(80), index=True)
    source_internal_id: Mapped[str | None] = mapped_column(String(160), index=True)
    source_url: Mapped[str] = mapped_column(Text)
    bank_or_auctioneer: Mapped[str] = mapped_column(String(160), index=True)
    state: Mapped[str | None] = mapped_column(String(2), index=True)
    city: Mapped[str | None] = mapped_column(String(120), index=True)
    neighborhood: Mapped[str | None] = mapped_column(String(160), index=True)
    address: Mapped[str | None] = mapped_column(Text)
    postal_code: Mapped[str | None] = mapped_column(String(16))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    registry_number: Mapped[str | None] = mapped_column(String(160))
    property_type: Mapped[str | None] = mapped_column(String(100))
    built_area_m2: Mapped[float | None] = mapped_column(Float)
    land_area_m2: Mapped[float | None] = mapped_column(Float)
    appraisal_value: Mapped[float | None] = mapped_column(Float)
    minimum_value: Mapped[float | None] = mapped_column(Float)
    current_bid_value: Mapped[float | None] = mapped_column(Float)
    discount_percent: Mapped[float | None] = mapped_column(Float)
    auction_date: Mapped[datetime | None] = mapped_column(DateTime)
    notice_url: Mapped[str | None] = mapped_column(Text)
    occupancy: Mapped[str | None] = mapped_column(String(160))
    notes: Mapped[str | None] = mapped_column(Text)
    auction_modality: Mapped[str] = mapped_column(String(40), default="Não informado")
    has_debts: Mapped[str] = mapped_column(String(40), default="Não informado")
    debt_value: Mapped[float | None] = mapped_column(Float)
    debt_description: Mapped[str | None] = mapped_column(Text)
    debt_information_source: Mapped[str | None] = mapped_column(Text)
    neighborhood_classification: Mapped[str] = mapped_column(String(40), default="Bairro Médio")
    neighborhood_reason: Mapped[str | None] = mapped_column(Text)
    score_financial: Mapped[float] = mapped_column(Float, default=0)
    score_legal: Mapped[float] = mapped_column(Float, default=0)
    score_liquidity: Mapped[float] = mapped_column(Float, default=0)
    score_location: Mapped[float] = mapped_column(Float, default=0)
    score_overall: Mapped[float] = mapped_column(Float, default=0, index=True)
    score_explanation: Mapped[str | None] = mapped_column(Text)
    automatic_summary: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(60), default="Ativo", index=True)
    fingerprint: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    collected_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    images: Mapped[list["PropertyImage"]] = relationship(back_populates="property", cascade="all, delete-orphan")
    price_history: Mapped[list["PriceHistory"]] = relationship(back_populates="property", cascade="all, delete-orphan")
    status_history: Mapped[list["StatusHistory"]] = relationship(back_populates="property", cascade="all, delete-orphan")
    score_history: Mapped[list["ScoreHistory"]] = relationship(back_populates="property", cascade="all, delete-orphan")
    change_history: Mapped[list["ChangeHistory"]] = relationship(back_populates="property", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_properties_city_score", "city", "score_overall"),
        UniqueConstraint("source", "source_internal_id", name="uq_source_internal_id"),
    )


class PropertyImage(Base):
    __tablename__ = "property_images"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    property_id: Mapped[int] = mapped_column(ForeignKey("properties.id"), index=True)
    image_url: Mapped[str] = mapped_column(Text)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    collected_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    property: Mapped[Property] = relationship(back_populates="images")


class PriceHistory(Base):
    __tablename__ = "price_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    property_id: Mapped[int] = mapped_column(ForeignKey("properties.id"), index=True)
    appraisal_value: Mapped[float | None] = mapped_column(Float)
    minimum_value: Mapped[float | None] = mapped_column(Float)
    current_bid_value: Mapped[float | None] = mapped_column(Float)
    discount_percent: Mapped[float | None] = mapped_column(Float)
    captured_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    property: Mapped[Property] = relationship(back_populates="price_history")


class StatusHistory(Base):
    __tablename__ = "status_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    property_id: Mapped[int] = mapped_column(ForeignKey("properties.id"), index=True)
    status: Mapped[str] = mapped_column(String(80))
    captured_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    property: Mapped[Property] = relationship(back_populates="status_history")


class ScoreHistory(Base):
    __tablename__ = "score_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    property_id: Mapped[int] = mapped_column(ForeignKey("properties.id"), index=True)
    score_financial: Mapped[float] = mapped_column(Float)
    score_legal: Mapped[float] = mapped_column(Float)
    score_liquidity: Mapped[float] = mapped_column(Float)
    score_location: Mapped[float] = mapped_column(Float)
    score_overall: Mapped[float] = mapped_column(Float)
    explanation: Mapped[str | None] = mapped_column(Text)
    captured_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    property: Mapped[Property] = relationship(back_populates="score_history")


class ChangeHistory(Base):
    __tablename__ = "change_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    property_id: Mapped[int] = mapped_column(ForeignKey("properties.id"), index=True)
    field_name: Mapped[str] = mapped_column(String(120))
    old_value: Mapped[str | None] = mapped_column(Text)
    new_value: Mapped[str | None] = mapped_column(Text)
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    property: Mapped[Property] = relationship(back_populates="change_history")


class CollectionRun(Base):
    __tablename__ = "collection_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(80), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    success: Mapped[bool] = mapped_column(Boolean, default=False)
    items_found: Mapped[int] = mapped_column(Integer, default=0)
    items_saved: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)


class CollectionError(Base):
    __tablename__ = "collection_errors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(80), index=True)
    url: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CollectionQueue(Base):
    __tablename__ = "collection_queue"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(80), index=True)
    url: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(40), default="pending", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    property_id: Mapped[int | None] = mapped_column(ForeignKey("properties.id"), index=True)
    alert_type: Mapped[str] = mapped_column(String(80), index=True)
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)
