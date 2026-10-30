from __future__ import annotations

from datetime import date, datetime
from urllib.parse import parse_qs

import httpx
import pytest

from olymping.services.vos_news import MOSCOW, fetch_vos_news, html_to_text


def _news(news_id: int, day: str, time: str, *, link: str = "") -> dict[str, str]:
    return {
        "id": str(news_id),
        "name": f"Новость &laquo;{news_id}&raquo;",
        "psevdo": f"news-{news_id}",
        "date": day,
        "time": time,
        "text": "<p>Пройдет <strong>5<span>&nbsp;</span>ноября</strong></p><p>Второй абзац</p>",
        "link": link,
        "subjects": "6",
        "on_site": "1",
    }


@pytest.mark.asyncio
async def test_fetch_vos_news_pages_until_since() -> None:
    pages = [
        [_news(3, "2026-10-30", "21:00:00"), _news(2, "2026-10-29", "15:08:00")],
        [
            _news(1, "2026-10-28", "10:00:00", link="https://example.org/x"),
            _news(0, "2026-10-20", "09:00:00"),
        ],
        [_news(-1, "2026-10-19", "09:00:00")],
    ]
    requests: list[dict[str, list[str]]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/news_list"
        form = parse_qs(request.content.decode())
        requests.append(form)
        index = int(form["start"][0]) // int(form["cnt"][0])
        return httpx.Response(200, json={"query": "", "data": pages[index]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        items = await fetch_vos_news(
            client, since=date(2026, 10, 28), base_url="https://vos.test", page_size=2
        )

    assert len(requests) == 2
    assert [item.id for item in items] == [3, 2, 1]
    assert items[0].published_at == datetime(2026, 10, 30, 21, 0, tzinfo=MOSCOW)
    assert items[0].title == "Новость «3»"
    assert items[0].url == "https://vos.test/news/news-3"
    assert items[2].url == "https://example.org/x"
    assert items[0].text == "Пройдет 5 ноября\nВторой абзац"


def test_html_to_text_keeps_table_cells_apart() -> None:
    markup = "<table><tr><td>Физика</td><td>8 ноября</td></tr><tr><td>Химия</td></tr></table>"
    assert html_to_text(markup) == "Физика 8 ноября\nХимия"
