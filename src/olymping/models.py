from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, ClassVar

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now() -> datetime:
    return datetime.now(UTC)


class SourceKind(StrEnum):
    VOSH = "VOSH"
    RSOSH = "RSOSH"
    MOSH = "MOSH"
    NPK = "NPK"
    NTO = "NTO"
    CTF = "CTF"
    OTHER = "OTHER"


class RecordStatus(StrEnum):
    CONFIRMED = "confirmed"
    TENTATIVE = "tentative"
    TBD = "tbd"
    CANCELLED = "cancelled"


class DatePrecision(StrEnum):
    EXACT = "exact"
    DATE = "date"
    WINDOW = "window"
    UNKNOWN = "unknown"


class MilestoneKind(StrEnum):
    REGISTRATION_OPEN = "registration_open"
    REGISTRATION_DEADLINE = "registration_deadline"
    QUALIFIER = "qualifier"
    TEAM_STAGE = "team_stage"
    FINAL = "final"
    COMPETITION = "competition"
    OTHER = "other"


class EventInterest(StrEnum):
    WATCHING = "watching"
    REGISTERED = "registered"
    IGNORED = "ignored"


class StageOutcome(StrEnum):
    PARTICIPATED = "participated"
    PASSED = "passed"
    NOT_PASSED = "not_passed"
    SKIPPED = "skipped"
    AWAITING_RESULTS = "awaiting_results"


class NoticeKind(StrEnum):
    NEW_EVENT = "new_event"
    EVENT_UPDATED = "event_updated"


class ReminderMode(StrEnum):
    OFFSET = "offset"
    CALENDAR = "calendar"


class DeliveryStatus(StrEnum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    SUPERSEDED = "superseded"


class UserRole(StrEnum):
    ADMIN = "admin"
    USER = "user"


class AccessStatus(StrEnum):
    ACTIVE = "active"
    BLOCKED = "blocked"


class Base(DeclarativeBase):
    type_annotation_map: ClassVar[dict[Any, Any]] = {dict[str, Any]: JSON, list[str]: JSON}


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class Event(TimestampMixin, Base):
    __tablename__ = "events"
    __table_args__ = (
        UniqueConstraint("source_kind", "external_id", name="uq_event_source_external"),
        Index("ix_events_status_kind", "status", "source_kind"),
    )

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    source_kind: Mapped[str] = mapped_column(String(20), index=True)
    external_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(80), default="general", index=True)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    source_url: Mapped[str] = mapped_column(String(1000))
    source_checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), default=RecordStatus.TBD.value)
    format: Mapped[str | None] = mapped_column(String(100), nullable=True)
    location: Mapped[str | None] = mapped_column(String(300), nullable=True)
    is_online: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    restrictions: Mapped[str | None] = mapped_column(String(100), nullable=True)
    min_grade: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_grade: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    weight: Mapped[float | None] = mapped_column(Float, nullable=True)

    milestones: Mapped[list[Milestone]] = relationship(
        back_populates="event", cascade="all, delete-orphan", lazy="selectin"
    )


class Milestone(TimestampMixin, Base):
    __tablename__ = "milestones"
    __table_args__ = (Index("ix_milestones_due", "status", "starts_at"),)

    id: Mapped[str] = mapped_column(String(160), primary_key=True)
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(40), index=True)
    title: Mapped[str] = mapped_column(String(300))
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    precision: Mapped[str] = mapped_column(String(20), default=DatePrecision.UNKNOWN.value)
    status: Mapped[str] = mapped_column(String(20), default=RecordStatus.TBD.value)
    format: Mapped[str | None] = mapped_column(String(100), nullable=True)
    location: Mapped[str | None] = mapped_column(String(300), nullable=True)
    is_online: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    results_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # OR between paths, AND within each path. None means not yet curated.
    advancement_paths: Mapped[list[list[str]] | None] = mapped_column(JSON, nullable=True)
    terminal: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    event: Mapped[Event] = relationship(back_populates="milestones")


class UserProfile(TimestampMixin, Base):
    __tablename__ = "user_profiles"

    telegram_user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    role: Mapped[str] = mapped_column(String(20), default=UserRole.USER.value, index=True)
    access_status: Mapped[str] = mapped_column(
        String(20), default=AccessStatus.ACTIVE.value, index=True
    )
    onboarding_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    timezone: Mapped[str] = mapped_column(String(80), default="Europe/Moscow")
    category_settings: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    ctf_filters: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    school_grade: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tag_filters: Mapped[list[str]] = mapped_column(JSON, default=list)
    notify_new_events: Mapped[bool] = mapped_column(Boolean, default=True)
    auto_subscribe_new_events: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_event_updates: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_open_events: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")


class Invitation(TimestampMixin, Base):
    __tablename__ = "invitations"

    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_by: Mapped[int] = mapped_column(
        ForeignKey("user_profiles.telegram_user_id", ondelete="CASCADE"), index=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    used_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ReminderRule(TimestampMixin, Base):
    __tablename__ = "reminder_rules"
    __table_args__ = (Index("ix_rule_scope", "telegram_user_id", "source_kind", "event_id"),)

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(
        ForeignKey("user_profiles.telegram_user_id", ondelete="CASCADE"), index=True
    )
    source_kind: Mapped[str | None] = mapped_column(String(20), nullable=True)
    event_id: Mapped[str | None] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), nullable=True
    )
    milestone_kind: Mapped[str | None] = mapped_column(String(40), nullable=True)
    mode: Mapped[str] = mapped_column(String(20))
    offset_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    days_before: Mapped[int | None] = mapped_column(Integer, nullable=True)
    local_time: Mapped[str | None] = mapped_column(String(5), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class EventPreference(TimestampMixin, Base):
    __tablename__ = "event_preferences"

    telegram_user_id: Mapped[int] = mapped_column(
        ForeignKey("user_profiles.telegram_user_id", ondelete="CASCADE"), primary_key=True
    )
    event_id: Mapped[str] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), primary_key=True
    )
    interest: Mapped[str] = mapped_column(String(20), default=EventInterest.WATCHING.value)
    origin: Mapped[str] = mapped_column(String(20), default="manual", server_default="manual")


class StageProgress(TimestampMixin, Base):
    __tablename__ = "stage_progress"

    telegram_user_id: Mapped[int] = mapped_column(
        ForeignKey("user_profiles.telegram_user_id", ondelete="CASCADE"), primary_key=True
    )
    milestone_id: Mapped[str] = mapped_column(
        ForeignKey("milestones.id", ondelete="CASCADE"), primary_key=True
    )
    outcome: Mapped[str] = mapped_column(String(20))


class WorkflowNotice(TimestampMixin, Base):
    __tablename__ = "workflow_notices"

    key: Mapped[str] = mapped_column(String(220), primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(
        ForeignKey("user_profiles.telegram_user_id", ondelete="CASCADE"), index=True
    )
    milestone_id: Mapped[str] = mapped_column(
        ForeignKey("milestones.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)


class NotificationDelivery(TimestampMixin, Base):
    __tablename__ = "notification_deliveries"
    __table_args__ = (
        UniqueConstraint(
            "telegram_user_id",
            "milestone_id",
            "reminder_rule_id",
            "scheduled_for",
            name="uq_delivery_occurrence",
        ),
        Index("ix_delivery_pending", "status", "scheduled_for"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    milestone_id: Mapped[str] = mapped_column(
        ForeignKey("milestones.id", ondelete="CASCADE"), index=True
    )
    reminder_rule_id: Mapped[str] = mapped_column(
        ForeignKey("reminder_rules.id", ondelete="CASCADE")
    )
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default=DeliveryStatus.PENDING.value)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class CatalogNotice(TimestampMixin, Base):
    __tablename__ = "catalog_notices"
    __table_args__ = (
        Index("ix_catalog_notice_unsent", "telegram_user_id", "sent_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_user_id: Mapped[int] = mapped_column(
        ForeignKey("user_profiles.telegram_user_id", ondelete="CASCADE"), index=True
    )
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"))
    milestone_id: Mapped[str | None] = mapped_column(
        ForeignKey("milestones.id", ondelete="CASCADE"), nullable=True
    )
    kind: Mapped[str] = mapped_column(String(30))
    summary: Mapped[str] = mapped_column(Text)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_batch_id: Mapped[int | None] = mapped_column(
        ForeignKey("notification_reviews.id"), nullable=True, index=True
    )


class OpenEventNotice(TimestampMixin, Base):
    __tablename__ = "open_event_notices"
    __table_args__ = (
        UniqueConstraint("telegram_user_id", "event_id", "phase", name="uq_open_event_notice"),
        Index("ix_open_notice_pending", "telegram_user_id", "status", "next_attempt_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_user_id: Mapped[int] = mapped_column(
        ForeignKey("user_profiles.telegram_user_id", ondelete="CASCADE")
    )
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"))
    milestone_id: Mapped[str | None] = mapped_column(
        ForeignKey("milestones.id", ondelete="CASCADE"), nullable=True
    )
    phase: Mapped[str] = mapped_column(String(180))
    status: Mapped[str] = mapped_column(String(20), default="pending", server_default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_batch_id: Mapped[int | None] = mapped_column(
        ForeignKey("notification_reviews.id"), nullable=True, index=True
    )


class NotificationReview(TimestampMixin, Base):
    __tablename__ = "notification_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", server_default="pending")
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)


class ReviewSelection(Base):
    __tablename__ = "review_selections"

    review_batch_id: Mapped[int] = mapped_column(
        ForeignKey("notification_reviews.id", ondelete="CASCADE"), primary_key=True
    )
    event_id: Mapped[str] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), primary_key=True
    )
    selected: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    snapshot_hash: Mapped[str] = mapped_column(String(64))
    summary: Mapped[str] = mapped_column(Text)


class ReviewDelivery(Base):
    __tablename__ = "review_deliveries"
    review_batch_id: Mapped[int] = mapped_column(
        ForeignKey("notification_reviews.id", ondelete="CASCADE"), primary_key=True
    )
    telegram_user_id: Mapped[int] = mapped_column(
        ForeignKey("user_profiles.telegram_user_id", ondelete="CASCADE"), primary_key=True
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    status: Mapped[str] = mapped_column(String(20), default="pending", server_default="pending")
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SyncRun(Base):
    __tablename__ = "sync_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(50), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    success: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    details: Mapped[str] = mapped_column(Text, default="")
