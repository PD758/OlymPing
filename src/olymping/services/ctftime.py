from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
from pydantic import TypeAdapter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from olymping.models import DatePrecision, Event, MilestoneKind, RecordStatus, SourceKind, SyncRun
from olymping.schemas import CTFtimeEvent, EventSeed, MilestoneSeed
from olymping.services.importer import ImportSummary, upsert_event

CTFTIME_EVENTS = TypeAdapter(list[CTFtimeEvent])


def _status_for(title: str) -> RecordStatus:
    lowered = title.casefold()
    if "cancelled" in lowered or "canceled" in lowered:
        return RecordStatus.CANCELLED
    if "postponed" in lowered:
        return RecordStatus.TENTATIVE
    return RecordStatus.CONFIRMED


def ctftime_to_seed(item: CTFtimeEvent) -> EventSeed:
    status = _status_for(item.title)
    event_id = f"ctftime:{item.id}"
    description = item.description.strip()
    if len(description) > 2000:
        description = f"{description[:1997]}..."
    return EventSeed(
        id=event_id,
        source_kind=SourceKind.CTF,
        external_id=str(item.id),
        title=item.title,
        description=description,
        category="cybersecurity",
        tags=["ctf", item.format.casefold()] if item.format else ["ctf"],
        url=item.url or item.ctftime_url,
        source_url=item.ctftime_url,
        status=status,
        format=item.format or None,
        location=item.location or None,
        is_online=not item.onsite,
        restrictions=item.restrictions,
        weight=item.weight,
        milestones=[
            MilestoneSeed(
                id=f"{event_id}:competition",
                kind=MilestoneKind.COMPETITION,
                advancement_paths=[],
                terminal=True,
                title="Соревнование",
                starts_at=item.start,
                ends_at=item.finish,
                precision=DatePrecision.EXACT,
                status=status,
                format=item.format or None,
                location=item.location or None,
                is_online=not item.onsite,
                source_url=item.ctftime_url,
            )
        ],
    )


async def sync_ctftime(
    session: AsyncSession,
    *,
    base_url: str,
    lookahead_days: int,
    client: httpx.AsyncClient | None = None,
    now: datetime | None = None,
) -> ImportSummary:
    now = now or datetime.now(UTC)
    started = now
    run = SyncRun(source="ctftime", started_at=started)
    session.add(run)
    await session.flush()
    owned_client = client is None
    if client is None:
        client = httpx.AsyncClient(
            timeout=httpx.Timeout(30),
            headers={"User-Agent": "OlymPing/0.1 personal calendar (+https://github.com/)"},
        )
    try:
        start = int((now - timedelta(days=1)).timestamp())
        finish = int((now + timedelta(days=lookahead_days)).timestamp())
        response = await client.get(
            f"{base_url.rstrip('/')}/events/",
            params={"limit": 1000, "start": start, "finish": finish},
        )
        response.raise_for_status()
        events = CTFTIME_EVENTS.validate_python(response.json())
        existing_ctf = (
            await session.execute(
                select(Event.id).where(Event.source_kind == SourceKind.CTF.value).limit(1)
            )
        ).scalar_one_or_none()
        create_new_event_notices = existing_ctf is not None
        summary = ImportSummary()
        for item in events:
            summary.merge(
                await upsert_event(
                    session,
                    ctftime_to_seed(item),
                    checked_at=now,
                    create_new_event_notices=create_new_event_notices,
                )
            )
        run.success = True
        run.finished_at = datetime.now(UTC)
        run.details = str(summary)
        return summary
    except Exception as exc:
        run.success = False
        run.finished_at = datetime.now(UTC)
        run.details = f"{type(exc).__name__}: {exc}"[:2000]
        raise
    finally:
        if owned_client:
            await client.aclose()
