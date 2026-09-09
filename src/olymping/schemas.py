from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator

from olymping.models import DatePrecision, MilestoneKind, RecordStatus, SourceKind


class MilestoneSeed(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=3, max_length=160, pattern=r"^[a-z0-9][a-z0-9:_-]+$")
    kind: MilestoneKind
    title: str = Field(min_length=1, max_length=300)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    precision: DatePrecision = DatePrecision.UNKNOWN
    status: RecordStatus = RecordStatus.TBD
    format: str | None = Field(default=None, max_length=100)
    location: str | None = Field(default=None, max_length=300)
    is_online: bool | None = None
    source_url: HttpUrl | None = None
    results_at: datetime | None = None
    advancement_paths: list[list[str]] | None = None
    terminal: bool | None = None

    @model_validator(mode="after")
    def validate_dates(self) -> MilestoneSeed:
        if self.results_at is not None and self.results_at.tzinfo is None:
            raise ValueError("results_at must contain a timezone offset")
        if self.advancement_paths is not None and any(not path for path in self.advancement_paths):
            raise ValueError("advancement paths must not contain an empty alternative")
        if self.starts_at is not None and self.starts_at.tzinfo is None:
            raise ValueError("starts_at must contain a timezone offset")
        if self.ends_at is not None and self.ends_at.tzinfo is None:
            raise ValueError("ends_at must contain a timezone offset")
        if self.starts_at and self.ends_at and self.ends_at < self.starts_at:
            raise ValueError("ends_at must not precede starts_at")
        if self.status == RecordStatus.CONFIRMED and self.starts_at is None:
            raise ValueError("a confirmed milestone must have starts_at")
        return self


class EventSeed(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=3, max_length=120, pattern=r"^[a-z0-9][a-z0-9:_-]+$")
    source_kind: SourceKind
    external_id: str | None = Field(default=None, max_length=120)
    title: str = Field(min_length=1, max_length=300)
    description: str = ""
    category: str = Field(default="general", min_length=1, max_length=80)
    tags: list[str] = Field(default_factory=list)
    url: HttpUrl | None = None
    source_url: HttpUrl
    status: RecordStatus = RecordStatus.TBD
    format: str | None = Field(default=None, max_length=100)
    location: str | None = Field(default=None, max_length=300)
    is_online: bool | None = None
    restrictions: str | None = Field(default=None, max_length=100)
    min_grade: int | None = Field(default=None, ge=1, le=11)
    max_grade: int | None = Field(default=None, ge=1, le=11)
    weight: float | None = Field(default=None, ge=0)
    milestones: list[MilestoneSeed] = Field(default_factory=list[MilestoneSeed])

    @model_validator(mode="after")
    def unique_milestones(self) -> EventSeed:
        if (self.min_grade is None) != (self.max_grade is None):
            raise ValueError("min_grade and max_grade must be specified together")
        if (
            self.min_grade is not None
            and self.max_grade is not None
            and self.min_grade > self.max_grade
        ):
            raise ValueError("min_grade must not exceed max_grade")
        ids = [item.id for item in self.milestones]
        if len(ids) != len(set(ids)):
            raise ValueError(f"event {self.id} contains duplicate milestone IDs")
        return self


class CalendarDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    calendar_version: int = Field(ge=1, le=1)
    events: list[EventSeed]

    @model_validator(mode="after")
    def unique_events(self) -> CalendarDocument:
        ids = [item.id for item in self.events]
        if len(ids) != len(set(ids)):
            raise ValueError("calendar document contains duplicate event IDs")
        return self


class CTFtimeOrganizer(BaseModel):
    id: int
    name: str


class CTFtimeDuration(BaseModel):
    hours: int = 0
    days: int = 0


class CTFtimeEvent(BaseModel):
    id: int
    title: str
    description: str = ""
    start: datetime
    finish: datetime
    ctftime_url: HttpUrl
    url: HttpUrl | None = None
    weight: float = 0
    format: str = ""
    onsite: bool = False
    restrictions: str = "Open"
    location: str = ""
    organizers: list[CTFtimeOrganizer] = Field(default_factory=list[CTFtimeOrganizer])
    duration: CTFtimeDuration = Field(default_factory=CTFtimeDuration)

    @field_validator("url", mode="before")
    @classmethod
    def empty_url_is_none(cls, value: object) -> object:
        return None if value == "" else value
