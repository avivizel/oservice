from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(300), index=True)
    org_type: Mapped[str] = mapped_column(String(40), default="private")
    notes: Mapped[str] = mapped_column(Text, default="")

    services: Mapped[list["Service"]] = relationship(back_populates="organization")


class Locality(Base):
    __tablename__ = "localities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    kind: Mapped[str] = mapped_column(String(40), default="locality", index=True)


class Service(Base):
    __tablename__ = "services"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"), nullable=True)
    external_id: Mapped[str] = mapped_column(String(120), default="", index=True)
    name: Mapped[str] = mapped_column(String(400), index=True)
    org_type: Mapped[str] = mapped_column(String(40), default="private", index=True)
    kind: Mapped[str] = mapped_column(String(40), default="other", index=True)
    address: Mapped[str] = mapped_column(String(500), default="")
    city: Mapped[str] = mapped_column(String(120), default="", index=True)
    district: Mapped[str] = mapped_column(String(40), default="", index=True)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    phone: Mapped[str] = mapped_column(String(200), default="")
    phone2: Mapped[str] = mapped_column(String(200), default="")
    email: Mapped[str] = mapped_column(String(200), default="")
    website: Mapped[str] = mapped_column(String(500), default="")
    hours: Mapped[str] = mapped_column(Text, default="")
    cost_type: Mapped[str] = mapped_column(String(40), default="")
    cost_info: Mapped[str] = mapped_column(Text, default="")
    eligibility: Mapped[str] = mapped_column(Text, default="")
    waitlist_info: Mapped[str] = mapped_column(Text, default="")
    languages: Mapped[str] = mapped_column(Text, default="[]")
    referral_process: Mapped[str] = mapped_column(Text, default="")
    target_audience: Mapped[str] = mapped_column(Text, default="")
    licensing: Mapped[str] = mapped_column(String(200), default="")
    addiction_types: Mapped[str] = mapped_column(Text, default="[]")
    age_group: Mapped[str] = mapped_column(String(40), default="all")
    gender: Mapped[str] = mapped_column(String(40), default="all")
    sector: Mapped[str] = mapped_column(String(40), default="general")
    manager: Mapped[str] = mapped_column(String(200), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    source_name: Mapped[str] = mapped_column(String(200), default="")
    source_url: Mapped[str] = mapped_column(String(600), default="")
    authority: Mapped[str] = mapped_column(String(40), default="ngo")
    confidence: Mapped[str] = mapped_column(String(20), default="medium")
    status: Mapped[str] = mapped_column(String(20), default="approved", index=True)
    last_updated: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_verified: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    rating: Mapped[str] = mapped_column(String(20), default="")
    rating_comment: Mapped[str] = mapped_column(Text, default="")
    operator_type: Mapped[str] = mapped_column(String(40), default="")
    operator_name: Mapped[str] = mapped_column(String(300), default="")
    supervision_text: Mapped[str] = mapped_column(Text, default="")
    service_types: Mapped[str] = mapped_column(Text, default="[]")
    population: Mapped[str] = mapped_column(Text, default="[]")

    organization: Mapped[Organization | None] = relationship(back_populates="services")
    sources: Mapped[list["ServiceSource"]] = relationship(back_populates="service", cascade="all, delete-orphan")
    conflicts: Mapped[list["FieldConflict"]] = relationship(back_populates="service", cascade="all, delete-orphan")
    ratings: Mapped[list["Rating"]] = relationship(back_populates="service", cascade="all, delete-orphan")
    favorites: Mapped[list["Favorite"]] = relationship(back_populates="service", cascade="all, delete-orphan")


class ServiceSource(Base):
    __tablename__ = "service_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    service_id: Mapped[int] = mapped_column(ForeignKey("services.id"))
    name: Mapped[str] = mapped_column(String(200))
    url: Mapped[str] = mapped_column(String(600), default="")
    authority: Mapped[str] = mapped_column(String(40), default="ngo")
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    excerpt: Mapped[str] = mapped_column(Text, default="")

    service: Mapped[Service] = relationship(back_populates="sources")


class FieldConflict(Base):
    __tablename__ = "field_conflicts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    service_id: Mapped[int] = mapped_column(ForeignKey("services.id"))
    field: Mapped[str] = mapped_column(String(80))
    official_value: Mapped[str] = mapped_column(Text, default="")
    other_value: Mapped[str] = mapped_column(Text, default="")
    other_source: Mapped[str] = mapped_column(String(200), default="")
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)

    service: Mapped[Service] = relationship(back_populates="conflicts")


class Rating(Base):
    __tablename__ = "ratings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    service_id: Mapped[int] = mapped_column(ForeignKey("services.id"))
    score: Mapped[str] = mapped_column(String(20))
    comment: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    service: Mapped[Service] = relationship(back_populates="ratings")


class Favorite(Base):
    __tablename__ = "favorites"
    __table_args__ = (UniqueConstraint("service_id", name="uq_favorite_service"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    service_id: Mapped[int] = mapped_column(ForeignKey("services.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    service: Mapped[Service] = relationship(back_populates="favorites")


class ScanRun(Base):
    __tablename__ = "scan_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="running")
    stats_json: Mapped[str] = mapped_column(Text, default="{}")
    log_text: Mapped[str] = mapped_column(Text, default="")


class MunicipalitySite(Base):
    __tablename__ = "municipality_sites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    authority_type: Mapped[str] = mapped_column(String(80), default="")
    district: Mapped[str] = mapped_column(String(80), default="")
    website: Mapped[str] = mapped_column(String(500), default="")
    last_scanned: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_status: Mapped[str] = mapped_column(String(40), default="pending")
    pages_visited: Mapped[int] = mapped_column(Integer, default=0)
    services_found: Mapped[int] = mapped_column(Integer, default=0)
    error_text: Mapped[str] = mapped_column(Text, default="")


class AgentCandidate(Base):
    __tablename__ = "agent_candidates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scan_id: Mapped[int | None] = mapped_column(ForeignKey("scan_runs.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(20), default="new", index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    matched_service_id: Mapped[int | None] = mapped_column(ForeignKey("services.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(400), default="")
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    diff_json: Mapped[str] = mapped_column(Text, default="[]")
    source_name: Mapped[str] = mapped_column(String(200), default="")
    source_url: Mapped[str] = mapped_column(String(600), default="")
    authority: Mapped[str] = mapped_column(String(40), default="ngo")
    confidence: Mapped[str] = mapped_column(String(20), default="medium")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
