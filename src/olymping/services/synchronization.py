from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from olymping.config import Settings
from olymping.models import SyncRun
from olymping.services.availability import queue_open_event_notices
from olymping.services.ctftime import sync_ctftime
from olymping.services.importer import ImportSummary, import_data_directory
from olymping.services.reviews import collect_review_batch

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SynchronizationResult:
    imported: ImportSummary
    ctftime: ImportSummary | None
    open_notices: int
    review_batch_id: int | None


async def synchronize_calendar(
    factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> SynchronizationResult:
    # A remote outage must not roll back the reviewed local calendar.
    async with factory() as session:
        imported = await import_data_directory(session, settings.data_dir)
        open_notices = await queue_open_event_notices(session, event_ids=imported.changed_event_ids)
        await session.commit()
    started = datetime.now(UTC)
    ctftime: ImportSummary | None = None
    try:
        async with factory() as session:
            ctftime = await sync_ctftime(
                session,
                base_url=settings.ctftime_base_url,
                lookahead_days=settings.ctftime_lookahead_days,
            )
            open_notices += await queue_open_event_notices(
                session, event_ids=ctftime.changed_event_ids
            )
            await session.commit()
    except Exception as exc:
        logger.warning("Manual CTFtime synchronization failed (%s)", type(exc).__name__)
        async with factory() as session:
            session.add(
                SyncRun(
                    source="ctftime",
                    started_at=started,
                    finished_at=datetime.now(UTC),
                    success=False,
                    details=type(exc).__name__,
                )
            )
            await session.commit()
    async with factory() as session:
        review_batch_id = await collect_review_batch(session)
        await session.commit()
    return SynchronizationResult(imported, ctftime, open_notices, review_batch_id)
