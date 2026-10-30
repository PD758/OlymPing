from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from html import unescape
from html.parser import HTMLParser
from zoneinfo import ZoneInfo

import httpx
from pydantic import BaseModel, ConfigDict

VOS_BASE_URL = "https://vos.olimpiada.ru"
MOSCOW = ZoneInfo("Europe/Moscow")


class _RawVosNews(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    name: str
    psevdo: str
    date: date
    time: str
    text: str = ""
    link: str = ""


class _VosNewsPage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    data: list[_RawVosNews]


@dataclass(frozen=True, slots=True)
class VosNewsItem:
    id: int
    published_at: datetime
    title: str
    url: str
    text: str


class _TextExtractor(HTMLParser):
    _BLOCKS = frozenset({"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "table"})

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self._BLOCKS:
            self.parts.append("\n")
        elif tag == "td":
            self.parts.append(" ")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def html_to_text(markup: str) -> str:
    """Flatten a news body to plain lines; the site wraps dates in non-breaking spans."""
    extractor = _TextExtractor()
    extractor.feed(markup)
    extractor.close()
    text = unescape("".join(extractor.parts)).replace("\xa0", " ")
    lines = (re.sub(r"[ \t\r]+", " ", line).strip() for line in text.split("\n"))
    return "\n".join(line for line in lines if line)


def _to_item(raw: _RawVosNews, base_url: str) -> VosNewsItem:
    hour, minute, *_ = (int(part) for part in raw.time.split(":"))
    published = datetime(raw.date.year, raw.date.month, raw.date.day, hour, minute, tzinfo=MOSCOW)
    url = raw.link.strip() or f"{base_url}/news/{raw.psevdo}"
    return VosNewsItem(
        id=int(raw.id),
        published_at=published,
        title=unescape(raw.name).strip(),
        url=url,
        text=html_to_text(raw.text),
    )


async def fetch_vos_news(
    client: httpx.AsyncClient,
    *,
    since: date,
    base_url: str = VOS_BASE_URL,
    page_size: int = 50,
    max_pages: int = 20,
) -> list[VosNewsItem]:
    """Return news published on or after `since`, newest first.

    The API lists news by publication time, newest first, so paging stops at the first
    page that reaches past `since`.
    """
    items: list[VosNewsItem] = []
    for page in range(max_pages):
        response = await client.post(
            f"{base_url.rstrip('/')}/api/news_list",
            data={"start": page * page_size, "cnt": page_size},
        )
        response.raise_for_status()
        batch = _VosNewsPage.model_validate(response.json()).data
        items.extend(_to_item(raw, base_url) for raw in batch if raw.date >= since)
        if len(batch) < page_size or any(raw.date < since for raw in batch):
            break
    items.sort(key=lambda item: (item.published_at, item.id), reverse=True)
    return items
