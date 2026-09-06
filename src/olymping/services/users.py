from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from secrets import token_urlsafe
from typing import Any, cast
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from olymping.models import (
    AccessStatus,
    Invitation,
    MilestoneKind,
    ReminderMode,
    ReminderRule,
    SourceKind,
    UserProfile,
    UserRole,
)

DEFAULT_CATEGORY_SETTINGS = {kind.value: True for kind in SourceKind}
DEFAULT_CTF_FILTERS: dict[str, Any] = {
    "online": "all",
    "restrictions": "all",
    "min_weight": 0,
    "formats": [],
}


class AccessDeniedError(PermissionError):
    """Raised when an actor attempts an administrator-only state change."""


async def require_admin_profile(
    session: AsyncSession,
    telegram_user_id: int,
) -> UserProfile:
    profile = await session.get(UserProfile, telegram_user_id)
    if (
        profile is None
        or profile.role != UserRole.ADMIN.value
        or profile.access_status != AccessStatus.ACTIVE.value
    ):
        raise AccessDeniedError("active administrator role is required")
    return profile


async def ensure_user_profile(
    session: AsyncSession,
    telegram_user_id: int,
    timezone: str,
    *,
    role: UserRole = UserRole.USER,
    onboarding_completed: bool = False,
    school_grade: int | None = None,
    username: str | None = None,
    display_name: str | None = None,
) -> UserProfile:
    profile = await session.get(UserProfile, telegram_user_id)
    if profile is not None:
        category_settings = {**DEFAULT_CATEGORY_SETTINGS, **profile.category_settings}
        if category_settings != profile.category_settings:
            profile.category_settings = category_settings
        configured_result = await session.execute(
            select(ReminderRule.source_kind)
            .where(
                ReminderRule.telegram_user_id == telegram_user_id,
                ReminderRule.source_kind.is_not(None),
            )
            .distinct()
        )
        configured = set(configured_result.scalars())
        missing = [kind for kind in SourceKind if kind.value not in configured]
        await _create_default_rules(session, telegram_user_id, missing)
        if username is not None:
            profile.username = username
        if display_name is not None:
            profile.display_name = display_name
        return profile
    profile = UserProfile(
        telegram_user_id=telegram_user_id,
        role=role.value,
        access_status=AccessStatus.ACTIVE.value,
        onboarding_completed=onboarding_completed,
        username=username,
        display_name=display_name,
        timezone=timezone,
        category_settings=DEFAULT_CATEGORY_SETTINGS.copy(),
        ctf_filters=DEFAULT_CTF_FILTERS.copy(),
        school_grade=school_grade,
        tag_filters=[],
    )
    session.add(profile)
    await session.flush()
    await _create_default_rules(session, telegram_user_id, SourceKind)
    return profile


async def ensure_admin_profile(
    session: AsyncSession,
    telegram_user_id: int,
    timezone: str,
) -> UserProfile:
    profile = await ensure_user_profile(
        session,
        telegram_user_id,
        timezone,
        role=UserRole.ADMIN,
    )
    profile.role = UserRole.ADMIN.value
    profile.access_status = AccessStatus.ACTIVE.value
    return profile


async def create_invitation(
    session: AsyncSession,
    *,
    created_by: int,
    lifetime: timedelta = timedelta(days=7),
) -> Invitation:
    await require_admin_profile(session, created_by)
    invitation = Invitation(
        token=token_urlsafe(12),
        created_by=created_by,
        expires_at=datetime.now(UTC) + lifetime,
    )
    session.add(invitation)
    await session.flush()
    return invitation


async def set_user_access(
    session: AsyncSession,
    *,
    actor_id: int,
    target_id: int,
    status: AccessStatus,
) -> UserProfile | None:
    """Change another user's access after authorizing the actor in this transaction."""

    await require_admin_profile(session, actor_id)
    target = await session.get(UserProfile, target_id)
    if target is None or target.role == UserRole.ADMIN.value:
        return None
    target.access_status = status.value
    return target


async def redeem_invitation(
    session: AsyncSession,
    *,
    token: str,
    telegram_user_id: int,
    timezone: str,
    username: str | None,
    display_name: str,
) -> UserProfile | None:
    now = datetime.now(UTC)
    existing = await session.get(UserProfile, telegram_user_id)
    if existing is not None and existing.access_status != AccessStatus.ACTIVE.value:
        return None
    claim = cast(
        CursorResult[Any],
        await session.execute(
            update(Invitation)
            .where(
                Invitation.token == token,
                Invitation.used_at.is_(None),
                Invitation.expires_at >= now,
            )
            .values(used_by=telegram_user_id, used_at=now)
        ),
    )
    if claim.rowcount != 1:
        return None
    profile = existing
    if profile is None:
        profile = await ensure_user_profile(
            session,
            telegram_user_id,
            timezone,
            username=username,
            display_name=display_name,
        )
    return profile


async def active_user_ids(session: AsyncSession) -> list[int]:
    result = await session.execute(
        select(UserProfile.telegram_user_id)
        .where(
            UserProfile.access_status == AccessStatus.ACTIVE.value,
            UserProfile.onboarding_completed.is_(True),
        )
        .order_by(UserProfile.telegram_user_id)
    )
    return list(result.scalars())


async def _create_default_rules(
    session: AsyncSession,
    telegram_user_id: int,
    source_kinds: Iterable[SourceKind],
) -> None:
    for source_kind in source_kinds:
        rules = [
            (1, "20:00", None),
            (0, "08:00", None),
            (3, "20:00", MilestoneKind.REGISTRATION_DEADLINE.value),
        ]
        for days_before, local_time, milestone_kind in rules:
            session.add(
                ReminderRule(
                    id=f"default:{telegram_user_id}:{source_kind.value}:{uuid4().hex[:10]}",
                    telegram_user_id=telegram_user_id,
                    source_kind=source_kind.value,
                    milestone_kind=milestone_kind,
                    mode=ReminderMode.CALENDAR.value,
                    days_before=days_before,
                    local_time=local_time,
                )
            )


async def get_owner_profile(session: AsyncSession, telegram_user_id: int) -> UserProfile | None:
    result = await session.execute(
        select(UserProfile).where(UserProfile.telegram_user_id == telegram_user_id)
    )
    return result.scalar_one_or_none()
