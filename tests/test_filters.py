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
