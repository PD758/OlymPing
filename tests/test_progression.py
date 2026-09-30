from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from aiogram.exceptions import TelegramForbiddenError
from aiogram.methods import SendMessage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from olymping.models import Event, EventPreference, Milestone, StageOutcome, WorkflowNotice
from olymping.schemas import CalendarDocument, EventSeed
from olymping.services.calendar import upcoming_events
from olymping.services.delivery import DeliveryDeferred
from olymping.services.importer import (
    CalendarImportError,
    import_document,
    load_calendar_document,
    validate_progression,
)
from olymping.services.progression import (
    completed_for_user,
    dispatch_workflow_notices,
    result_request_time,
    stage_access,
)
from olymping.services.reminders import dispatch_due_reminders
from olymping.services.user_state import set_stage_outcome
from olymping.services.users import ensure_admin_profile, ensure_user_profile

NOW = datetime(2026, 10, 7, 17, tzinfo=UTC)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("filename", "event_id", "first_rounds"),
    [
        (
            "11_law_olympiads.yaml",
            "other:hse-highest-test-law-2026",
            ("qualifier-1a", "qualifier-1b"),
        ),
        (
            "12_economics_olympiads.yaml",
            "other:hse-economics-2026",
            ("qualifier-1", "qualifier-1b"),
        ),
        ("12_economics_olympiads.yaml", "other:hse-financial-literacy-2026", ("qualifier-1",)),
        ("12_economics_olympiads.yaml", "other:hse-business-basics-2026", ("qualifier-1",)),
    ],
)
async def test_hse_import_resolves_first_round_gaps_and_accepts_either_date(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
    filename: str,
    event_id: str,
    first_rounds: tuple[str, ...],
) -> None:
    _, factory = database
    seed = next(
        event
        for event in load_calendar_document(Path("data/calendar") / filename).events
        if event.id == event_id
    )
    old = seed.model_copy(
        update={
            "milestones": [
                stage.model_copy(update={"advancement_paths": None}) for stage in seed.milestones
            ]
        }
    )
    sent: list[str] = []

    async def send(_user: int, _text: str, stage: str, kind: str) -> None:
        assert kind == "gap"
        sent.append(stage)

    async with factory() as session:
        admin = await ensure_admin_profile(session, 1, "Europe/Moscow")
        admin.onboarding_completed = True
        admin.auto_subscribe_new_events = False
        await import_document(session, CalendarDocument(calendar_version=1, events=[old]))
        await session.commit()
        assert await dispatch_workflow_notices(
            session, user_id=1, admin_id=1, send=send, now=NOW
        ) == len(first_rounds)

    async with factory() as session:
        current = CalendarDocument(calendar_version=1, events=[seed])
        await import_document(session, current)
        await session.commit()
        assert (
            await dispatch_workflow_notices(session, user_id=1, admin_id=1, send=send, now=NOW) == 0
        )
        notices = list(await session.scalars(select(WorkflowNotice)))
        assert len(notices) == len(first_rounds)
        assert all(notice.status == "resolved" for notice in notices)
        event = await session.get(Event, event_id)
        assert event is not None
        stages = {stage.id: stage for stage in event.milestones}
        second = stages[f"{event_id}:qualifier-2"]
        assert stage_access(second, stages, {}) == "unknown"
        for suffix in first_rounds:
            outcomes = {f"{event_id}:{other}": "skipped" for other in first_rounds}
            outcomes[f"{event_id}:{suffix}"] = "passed"
            assert stage_access(second, stages, outcomes) == "eligible"
        failed = {f"{event_id}:{suffix}": "not_passed" for suffix in first_rounds}
        assert stage_access(second, stages, failed) == "blocked"
        assert (await import_document(session, current)).updated_milestones == 0
    assert len(sent) == len(first_rounds)


@pytest.mark.asyncio
async def test_ai_challenge_import_resolves_gaps_and_shares_final_admission(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = database
    seed = next(
        event
        for event in load_calendar_document(Path("data/calendar/08_ai_olympiads.yaml")).events
        if event.id == "other:ai-challenge-2026"
    )
    old = seed.model_copy(
        update={
            "milestones": [
                stage.model_copy(update={"advancement_paths": None}) for stage in seed.milestones
            ]
        }
    )
    now = datetime(2026, 9, 18, 12, tzinfo=UTC)
    sent: list[str] = []

    async def send(_user: int, _text: str, stage: str, kind: str) -> None:
        assert kind == "gap"
        sent.append(stage)

    async with factory() as session:
        admin = await ensure_admin_profile(session, 1, "Europe/Moscow")
        admin.onboarding_completed = True
        admin.auto_subscribe_new_events = False
        await import_document(session, CalendarDocument(calendar_version=1, events=[old]))
        await session.commit()
        assert (
            await dispatch_workflow_notices(session, user_id=1, admin_id=1, send=send, now=now) == 2
        )
    async with factory() as session:
        current = CalendarDocument(calendar_version=1, events=[seed])
        await import_document(session, current)
        await session.commit()
        assert (
            await dispatch_workflow_notices(session, user_id=1, admin_id=1, send=send, now=now) == 0
        )
        rows = list(await session.scalars(select(WorkflowNotice)))
        assert len(rows) == 2 and all(row.status == "resolved" for row in rows)
        event = await session.get(Event, seed.id)
        assert event is not None
        stages = {stage.id: stage for stage in event.milestones}
        for suffix in ("final", "defense"):
            stage = stages[f"{seed.id}:{suffix}"]
            assert stage_access(stage, stages, {f"{seed.id}:qualifier": "not_passed"}) == "blocked"
            assert stage_access(stage, stages, {f"{seed.id}:team-stage": "passed"}) == "eligible"
        assert (await import_document(session, current)).updated_milestones == 0
    assert len(sent) == 2


@pytest.mark.asyncio
async def test_rosfin_import_resolves_reported_gaps_without_repeating_alerts(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = database
    current = load_calendar_document(Path("data/calendar/13_rosfin_olympiad.yaml"))
    seed = current.events[0]
    old = seed.model_copy(
        update={
            "milestones": [
                stage.model_copy(update={"advancement_paths": None}) for stage in seed.milestones
            ]
        }
    )
    now = datetime(2026, 9, 9, 18, 44, tzinfo=UTC)
    sent: list[str] = []

    async def send(_user: int, _text: str, stage: str, kind: str) -> None:
        assert kind == "gap"
        sent.append(stage)

    async with factory() as session:
        admin = await ensure_admin_profile(session, 1, "Europe/Moscow")
        admin.onboarding_completed = True
        admin.auto_subscribe_new_events = False
        await import_document(session, CalendarDocument(calendar_version=1, events=[old]))
        await session.commit()
        assert (
            await dispatch_workflow_notices(session, user_id=1, admin_id=1, send=send, now=now) == 3
        )
    async with factory() as session:
        await import_document(session, current)
        await session.commit()
        assert (
            await dispatch_workflow_notices(session, user_id=1, admin_id=1, send=send, now=now) == 0
        )
        rows = list(await session.scalars(select(WorkflowNotice)))
        assert len(rows) == 3 and all(row.status == "resolved" for row in rows)
        event = await session.get(Event, seed.id)
        assert event is not None
        stages = {stage.id: stage for stage in event.milestones}
        final = stages[f"{seed.id}:final"]
        assert stage_access(final, stages, {f"{seed.id}:round-2": "not_passed"}) == "blocked"
        assert (
            stage_access(final, stages, {f"{seed.id}:qualification-selection": "passed"})
            == "eligible"
        )
        assert (await import_document(session, current)).updated_milestones == 0
    assert len(sent) == 3


def event_with_paths() -> Event:
    event = Event(
        id="test:paths",
        title="Paths",
        source_kind="NTO",
        source_url="https://example.org/",
        status="confirmed",
        tags=["informatics"],
    )
    event.milestones = [
        Milestone(
            id="test:a",
            kind="qualifier",
            title="First attempt",
            status="confirmed",
            starts_at=NOW - timedelta(days=7),
            ends_at=NOW - timedelta(days=6),
            advancement_paths=[],
            terminal=False,
        ),
        Milestone(
            id="test:b",
            kind="qualifier",
            title="Second attempt",
            status="confirmed",
            starts_at=NOW - timedelta(days=5),
            ends_at=NOW - timedelta(days=4),
            advancement_paths=[],
            terminal=False,
        ),
        Milestone(
            id="test:final",
            kind="final",
            title="Final",
            status="confirmed",
            starts_at=NOW + timedelta(days=3),
            ends_at=NOW + timedelta(days=4),
            advancement_paths=[["test:a"], ["test:b"]],
            terminal=True,
        ),
    ]
    return event


def test_alternative_paths_and_restoration() -> None:
    event = event_with_paths()
    stages = {s.id: s for s in event.milestones}
    final = stages["test:final"]
    assert stage_access(final, stages, {}) == "unknown"
    assert stage_access(final, stages, {"test:a": "not_passed"}) == "unknown"
    assert stage_access(final, stages, {"test:a": "not_passed", "test:b": "passed"}) == "eligible"
    failed = {"test:a": "not_passed", "test:b": "skipped"}
    assert stage_access(final, stages, failed) == "blocked"
    assert completed_for_user(event, failed, NOW)
    final.advancement_paths = [["test:a", "test:b"]]
    assert stage_access(final, stages, {"test:a": "passed"}) == "unknown"
    assert stage_access(final, stages, {"test:a": "passed", "test:b": "not_passed"}) == "blocked"


@pytest.mark.parametrize("paths", [[["missing"]], [["test:root"]]])
def test_invalid_graph_is_rejected(paths: list[list[str]]) -> None:
    seed = EventSeed.model_validate(
        {
            "id": "test:graph",
            "title": "Graph",
            "source_kind": "NTO",
            "source_url": "https://example.org/",
            "milestones": [
                {
                    "id": "test:root",
                    "title": "Root",
                    "kind": "qualifier",
                    "advancement_paths": paths,
                }
            ],
        }
    )
    with pytest.raises(CalendarImportError):
        validate_progression(seed)


def test_publication_date_takes_precedence() -> None:
    event = event_with_paths()
    stage = event.milestones[0]
    assert result_request_time(stage, event, "Europe/Moscow")[0] == NOW
    stage.results_at = NOW - timedelta(days=1)
    assert result_request_time(stage, event, "Europe/Moscow")[0] == stage.results_at


@pytest.mark.asyncio
async def test_result_requests_restart_snooze_and_cutoff(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = database
    messages: list[str] = []

    async def send(_user: int, _text: str, stage: str, _kind: str) -> None:
        messages.append(stage)

    async with factory() as session:
        await ensure_user_profile(session, 2, "Europe/Moscow", onboarding_completed=True)
        event = event_with_paths()
        session.add(event)
        await session.flush()
        session.add(EventPreference(telegram_user_id=2, event_id=event.id, interest="registered"))
        await session.commit()
        assert (
            await dispatch_workflow_notices(
                session, user_id=2, admin_id=1, send=send, now=NOW - timedelta(minutes=1)
            )
            == 0
        )
        assert (
            await dispatch_workflow_notices(session, user_id=2, admin_id=1, send=send, now=NOW) == 2
        )
    async with factory() as session:
        assert (
            await dispatch_workflow_notices(session, user_id=2, admin_id=1, send=send, now=NOW) == 0
        )
        await set_stage_outcome(
            session,
            actor_id=2,
            milestone_id="test:a",
            outcome=StageOutcome.AWAITING_RESULTS,
            now=NOW,
        )
        await set_stage_outcome(
            session, actor_id=2, milestone_id="test:b", outcome=StageOutcome.NOT_PASSED, now=NOW
        )
        await session.commit()
    async with factory() as session:
        assert (
            await dispatch_workflow_notices(
                session, user_id=2, admin_id=1, send=send, now=NOW + timedelta(hours=23)
            )
            == 0
        )
        assert (
            await dispatch_workflow_notices(
                session, user_id=2, admin_id=1, send=send, now=NOW + timedelta(days=1)
            )
            == 1
        )
        await set_stage_outcome(
            session,
            actor_id=2,
            milestone_id="test:a",
            outcome=StageOutcome.AWAITING_RESULTS,
            now=NOW + timedelta(days=2),
        )
        await session.commit()
        assert (
            await dispatch_workflow_notices(
                session, user_id=2, admin_id=1, send=send, now=NOW + timedelta(days=3)
            )
            == 0
        )
    assert messages == ["test:a", "test:b", "test:a"]


@pytest.mark.asyncio
async def test_missing_next_date_notifies_admin_once_and_resolves(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = database
    messages: list[str] = []

    async def send(_user: int, _text: str, stage: str, kind: str) -> None:
        assert kind == "gap"
        messages.append(stage)

    async with factory() as session:
        admin = await ensure_admin_profile(session, 1, "Europe/Moscow")
        admin.onboarding_completed = True
        event = event_with_paths()
        event.milestones[-1].starts_at = None
        event.milestones[-1].status = "tbd"
        session.add(event)
        await session.commit()
        assert (
            await dispatch_workflow_notices(session, user_id=1, admin_id=1, send=send, now=NOW) == 2
        )
    async with factory() as session:
        assert (
            await dispatch_workflow_notices(
                session, user_id=1, admin_id=1, send=send, now=NOW + timedelta(days=1)
            )
            == 0
        )
        stage = await session.get(Milestone, "test:final")
        assert stage is not None
        stage.starts_at = NOW + timedelta(days=3)
        stage.status = "confirmed"
        await session.commit()
        await dispatch_workflow_notices(session, user_id=1, admin_id=1, send=send, now=NOW)
        rows = list(await session.scalars(select(WorkflowNotice)))
        assert all(n.status == "resolved" for n in rows)
    assert len(messages) == 2


@pytest.mark.asyncio
async def test_reported_result_exposes_gap_even_without_known_stage_dates(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = database
    sent: list[str] = []

    async def send(_user: int, _text: str, stage: str, kind: str) -> None:
        assert kind == "gap"
        sent.append(stage)

    async with factory() as session:
        admin = await ensure_admin_profile(session, 1, "Europe/Moscow")
        admin.onboarding_completed = True
        await ensure_user_profile(session, 2, "Europe/Moscow", onboarding_completed=True)
        event = event_with_paths()
        for stage in event.milestones:
            stage.starts_at = stage.ends_at = None
            stage.status = "tbd"
        session.add(event)
        await session.flush()
        await set_stage_outcome(
            session, actor_id=2, milestone_id="test:a", outcome=StageOutcome.PASSED
        )
        await session.commit()
        assert (
            await dispatch_workflow_notices(session, user_id=1, admin_id=1, send=send, now=NOW) == 1
        )
        assert sent == ["test:a"]


@pytest.mark.asyncio
async def test_failed_paths_hide_calendar_and_stop_reminders_but_restore(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = database
    sent: list[str] = []

    async def send(_user: int, text: str) -> None:
        sent.append(text)

    async with factory() as session:
        profile = await ensure_user_profile(session, 2, "Europe/Moscow", onboarding_completed=True)
        event = event_with_paths()
        session.add(event)
        await session.flush()
        session.add(EventPreference(telegram_user_id=2, event_id=event.id, interest="watching"))
        for stage_id in ("test:a", "test:b"):
            await set_stage_outcome(
                session, actor_id=2, milestone_id=stage_id, outcome=StageOutcome.NOT_PASSED
            )
        await session.commit()
        assert not await upcoming_events(
            session, profile, starts_at=NOW, ends_at=NOW + timedelta(days=5)
        )
        assert (
            await dispatch_due_reminders(
                session, owner_id=2, send=send, now=NOW + timedelta(days=2)
            )
            == 0
        )
        await set_stage_outcome(
            session, actor_id=2, milestone_id="test:b", outcome=StageOutcome.PASSED
        )
        await session.commit()
        assert (
            len(
                await upcoming_events(
                    session, profile, starts_at=NOW, ends_at=NOW + timedelta(days=5)
                )
            )
            == 1
        )
        assert (
            await dispatch_due_reminders(
                session, owner_id=2, send=send, now=NOW + timedelta(days=2)
            )
            == 1
        )
    assert len(sent) == 1


@pytest.mark.asyncio
async def test_own_terminal_outcome_hides_it_but_awaiting_result_keeps_it_visible(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = database
    async with factory() as session:
        profile = await ensure_user_profile(session, 2, "Europe/Moscow", onboarding_completed=True)
        event = event_with_paths()
        session.add(event)
        await session.flush()
        await set_stage_outcome(
            session, actor_id=2, milestone_id="test:a", outcome=StageOutcome.PASSED
        )
        await set_stage_outcome(
            session, actor_id=2, milestone_id="test:final", outcome=StageOutcome.SKIPPED
        )
        await session.commit()

        outcomes = {"test:a": "passed", "test:final": "skipped"}
        assert not await upcoming_events(
            session, profile, starts_at=NOW, ends_at=NOW + timedelta(days=5)
        )
        assert completed_for_user(event, outcomes, NOW)

        await set_stage_outcome(
            session,
            actor_id=2,
            milestone_id="test:final",
            outcome=StageOutcome.AWAITING_RESULTS,
        )
        await session.commit()
        assert [
            milestone.id
            for _, milestone in await upcoming_events(
                session, profile, starts_at=NOW, ends_at=NOW + timedelta(days=5)
            )
        ] == ["test:final"]
        assert not completed_for_user(
            event, {"test:a": "passed", "test:final": "awaiting_results"}, NOW
        )

        await set_stage_outcome(
            session, actor_id=2, milestone_id="test:final", outcome=StageOutcome.PASSED
        )
        await session.commit()
        assert not await upcoming_events(
            session, profile, starts_at=NOW, ends_at=NOW + timedelta(days=5)
        )
        assert completed_for_user(event, {"test:a": "passed", "test:final": "passed"}, NOW)


@pytest.mark.asyncio
async def test_workflow_flood_wait_survives_restart(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = database

    async def limited(_user: int, _text: str, _stage: str, _kind: str) -> None:
        raise DeliveryDeferred(120)

    async with factory() as session:
        await ensure_user_profile(session, 2, "Europe/Moscow", onboarding_completed=True)
        event = event_with_paths()
        session.add(event)
        await session.flush()
        session.add(EventPreference(telegram_user_id=2, event_id=event.id, interest="watching"))
        await session.commit()
        with pytest.raises(DeliveryDeferred):
            await dispatch_workflow_notices(session, user_id=2, admin_id=1, send=limited, now=NOW)
    async with factory() as session:
        row = await session.get(WorkflowNotice, "result:2:test:a")
        assert row is not None and row.attempts == 0 and row.status == "pending"
        assert row.next_attempt_at is not None


@pytest.mark.asyncio
async def test_workflow_retries_transient_failures_past_five_attempts(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = database
    attempts = 0
    sent: list[str] = []

    async def unavailable(_user: int, _text: str, stage: str, _kind: str) -> None:
        nonlocal attempts
        if stage == "test:a":
            attempts += 1
            raise RuntimeError("network outage")
        sent.append(stage)

    async def recovered(_user: int, _text: str, stage: str, _kind: str) -> None:
        sent.append(stage)

    async with factory() as session:
        await ensure_user_profile(session, 2, "Europe/Moscow", onboarding_completed=True)
        event = event_with_paths()
        session.add(event)
        await session.flush()
        session.add(EventPreference(telegram_user_id=2, event_id=event.id, interest="watching"))
        await session.commit()
        for offset in (0, 2, 6, 14, 30):
            assert await dispatch_workflow_notices(
                session,
                user_id=2,
                admin_id=1,
                send=unavailable,
                now=NOW + timedelta(minutes=offset),
            ) == (1 if offset == 0 else 0)
            assert attempts == (0, 2, 6, 14, 30).index(offset) + 1
            assert (
                await dispatch_workflow_notices(
                    session,
                    user_id=2,
                    admin_id=1,
                    send=unavailable,
                    now=NOW + timedelta(minutes=offset + 1),
                )
                == 0
            )
            assert attempts == (0, 2, 6, 14, 30).index(offset) + 1
        row = await session.get(WorkflowNotice, "result:2:test:a")
        assert row is not None and row.status == "pending" and row.attempts == 5
        assert row.next_attempt_at is not None
        assert row.next_attempt_at.replace(tzinfo=UTC) == NOW + timedelta(minutes=62)
        assert (
            await dispatch_workflow_notices(
                session,
                user_id=2,
                admin_id=1,
                send=recovered,
                now=NOW + timedelta(minutes=62),
            )
            == 1
        )
        row = await session.get(WorkflowNotice, "result:2:test:a")
        assert row is not None and row.status == "sent" and row.attempts == 6
    assert sent == ["test:b", "test:a"]


@pytest.mark.asyncio
async def test_workflow_stops_after_permanent_telegram_error(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = database
    calls = 0

    async def forbidden(_user: int, _text: str, stage: str, _kind: str) -> None:
        nonlocal calls
        if stage == "test:a":
            calls += 1
            raise TelegramForbiddenError(SendMessage(chat_id=2, text="notice"), "bot blocked")

    async def unexpected(_user: int, _text: str, stage: str, _kind: str) -> None:
        if stage == "test:a":
            pytest.fail("permanent workflow failure must not retry")

    async with factory() as session:
        await ensure_user_profile(session, 2, "Europe/Moscow", onboarding_completed=True)
        event = event_with_paths()
        session.add(event)
        await session.flush()
        session.add(EventPreference(telegram_user_id=2, event_id=event.id, interest="watching"))
        await session.commit()
        await dispatch_workflow_notices(session, user_id=2, admin_id=1, send=forbidden, now=NOW)
        row = await session.get(WorkflowNotice, "result:2:test:a")
        assert row is not None and row.status == "failed" and row.attempts == 1
        assert row.next_attempt_at is None
        await session.commit()
    async with factory() as session:
        await dispatch_workflow_notices(
            session, user_id=2, admin_id=1, send=unexpected, now=NOW + timedelta(days=1)
        )
    assert calls == 1
