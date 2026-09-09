from __future__ import annotations

from olymping.models import Event, EventPreference, SourceKind, UserProfile

GROUP_FILTERS = {
    "group:vosh": SourceKind.VOSH.value,
    "group:mosh": SourceKind.MOSH.value,
}


def event_is_enabled(
    profile: UserProfile, event: Event, *, preference: EventPreference | None = None
) -> bool:
    settings = profile.category_settings or {}
    if not bool(settings.get(event.source_kind, True)):
        return False
    if (
        profile.school_grade is not None
        and event.max_grade is not None
        and event.max_grade < profile.school_grade
    ):
        return False
    selected_tags = {tag.casefold() for tag in (profile.tag_filters or [])}
    event_tags = {tag.casefold() for tag in (event.tags or [])}
    selected_group = any(
        tag in selected_tags and event.source_kind == source
        for tag, source in GROUP_FILTERS.items()
    )
    subject_tags = selected_tags - GROUP_FILTERS.keys()
    manual = preference is not None and (
        preference.interest == "registered"
        or (preference.origin == "manual" and preference.interest == "watching")
    )
    if not manual and selected_tags and not selected_group and subject_tags.isdisjoint(event_tags):
        return False
    if event.source_kind != SourceKind.CTF.value:
        return True
    filters = profile.ctf_filters or {}
    online = filters.get("online", "all")
    if online == "online" and event.is_online is not True:
        return False
    if online == "onsite" and event.is_online is not False:
        return False
    restrictions = filters.get("restrictions", "all")
    if restrictions == "open" and (event.restrictions or "").casefold() != "open":
        return False
    if (event.weight or 0) < float(filters.get("min_weight", 0)):
        return False
    formats = {str(item).casefold() for item in filters.get("formats", [])}
    return not formats or (event.format or "").casefold() in formats
