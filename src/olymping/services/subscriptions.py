from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from olymping.models import CatalogNotice, Event, EventPreference, UserProfile
from olymping.services.filters import event_is_enabled
from olymping.topics import TAG_LABELS


async def reapply_profile(
    session: AsyncSession,
    profile: UserProfile,
    *,
    subscribe_matches: bool | None = None,
) -> tuple[int, int]:
    """Reconcile automatic subscriptions after the owner changes their questionnaire.

    Explicit choices are durable: only an automatically-created ``watching``
    preference may be removed, and only missing automatic preferences may be
    added. ``subscribe_matches=None`` follows the saved new-event preference;
    pass ``True`` for an explicit onboarding reapply. Visibility checks still
    protect delivery, but keeping the stored set in sync avoids subscriptions
    unexpectedly returning after a later profile edit.
    """
    should_subscribe = (
        profile.auto_subscribe_new_events if subscribe_matches is None else subscribe_matches
    )
    preferences = {
        preference.event_id: preference
        for preference in await session.scalars(
            select(EventPreference).where(
                EventPreference.telegram_user_id == profile.telegram_user_id,
            )
        )
    }
    events = list(await session.scalars(select(Event)))
    added = removed = 0
    for event in events:
        preference = preferences.get(event.id)
        if preference is not None and (
            preference.origin != "automatic" or preference.interest != "watching"
        ):
            continue
        matches = event.status != "cancelled" and event_is_enabled(profile, event)
        if preference is not None and not matches:
            await session.delete(preference)
            removed += 1
        elif preference is None and matches and should_subscribe:
            session.add(
                EventPreference(
                    telegram_user_id=profile.telegram_user_id,
                    event_id=event.id,
                    interest="watching",
                    origin="automatic",
                )
            )
            added += 1
    await session.flush()
    return added, removed


async def reapply_event(session: AsyncSession, event: Event, *, old_tags: list[str]) -> int:
    """Reconcile only automatic choices; preserve all explicit user decisions."""
    count = 0
    profiles = await session.scalars(
        select(UserProfile).where(
            UserProfile.access_status == "active",
            UserProfile.onboarding_completed.is_(True),
        )
    )
    for profile in profiles:
        pref = await session.get(EventPreference, (profile.telegram_user_id, event.id))
        if pref is not None and (pref.origin != "automatic" or pref.interest != "watching"):
            continue
        matches = event.status != "cancelled" and event_is_enabled(profile, event)
        if matches and pref is None and profile.auto_subscribe_new_events:
            session.add(
                EventPreference(
                    telegram_user_id=profile.telegram_user_id,
                    event_id=event.id,
                    interest="watching",
                    origin="automatic",
                )
            )
            kind = "subscription_added"
            text = "Автоподписка добавлена: олимпиада подходит под твою анкету."
        elif not matches and pref is not None:
            await session.delete(pref)
            kind = "subscription_removed"
            text = (
                "Изменились темы олимпиады — она больше не подходит под твою анкету, "
                "поэтому автоподписка снята."
                if old_tags != event.tags
                else "Олимпиада больше не подходит под текущую анкету или отключена. "
                "Автоподписка снята."
            )
            text += " Можно подписаться вручную в карточке или изменить анкету."
        else:
            continue
        if old_tags != event.tags:
            before = ", ".join(TAG_LABELS[tag] for tag in old_tags if tag in TAG_LABELS) or "—"
            after = ", ".join(TAG_LABELS[tag] for tag in event.tags if tag in TAG_LABELS) or "—"
            text += f"\nТемы: {before} → {after}."
        session.add(
            CatalogNotice(
                telegram_user_id=profile.telegram_user_id,
                event_id=event.id,
                kind=kind,
                summary=text,
            )
        )
        count += 1
    await session.flush()
    return count
