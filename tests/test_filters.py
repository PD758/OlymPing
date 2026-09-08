from olymping.models import Event, UserProfile
from olymping.services.filters import event_is_enabled


def test_ctf_filters() -> None:
    profile = UserProfile(
        telegram_user_id=1,
        timezone="Europe/Moscow",
        category_settings={"CTF": True},
        ctf_filters={"online": "online", "restrictions": "open", "min_weight": 25},
    )
    event = Event(
        id="ctftime:1",
        source_kind="CTF",
        title="CTF",
        category="cybersecurity",
        source_url="https://ctftime.org/event/1/",
        status="confirmed",
        is_online=True,
        restrictions="Open",
        weight=30,
    )
    assert event_is_enabled(profile, event)
    event.weight = 10
    assert not event_is_enabled(profile, event)


def test_whole_groups_are_additive_and_still_respect_grade_and_source() -> None:
    profile = UserProfile(
        telegram_user_id=1,
        school_grade=9,
        tag_filters=["group:vosh", "programming"],
    )
    event = Event(
        id="test:group",
        source_kind="VOSH",
        title="Literature",
        tags=["literature"],
        max_grade=11,
    )
    assert event_is_enabled(profile, event)
    event.max_grade = 8
    assert not event_is_enabled(profile, event)
    event.max_grade = 11
    event.source_kind = "MOSH"
    assert not event_is_enabled(profile, event)
    event.tags = ["programming"]
    assert event_is_enabled(profile, event)
    profile.tag_filters = ["group:mosh"]
    event.tags = []
    assert event_is_enabled(profile, event)
    profile.category_settings = {"MOSH": False}
    assert not event_is_enabled(profile, event)
    profile.category_settings = {}
    event.source_kind = "RSOSH"
    event.tags = ["group:mosh", "mosh"]
    assert not event_is_enabled(profile, event)
