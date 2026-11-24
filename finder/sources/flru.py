"""FL.ru — RSS всех новых заказов."""
import html
import re

import feedparser
import httpx

from finder.http import clean_text, parse_money
from finder.models import Job

URL = "https://www.fl.ru/rss/all.xml"
_BUDGET = re.compile(r"\s*\(Бюджет:\s*([^)]*?)(?:,\s*для всех)?\)\s*$")
_FOR_ALL = re.compile(r"\s*\(для всех\)\s*$")


def parse(raw: str | bytes) -> list[Job]:
    feed = feedparser.parse(raw.encode() if isinstance(raw, str) else raw)
    jobs = []
    for e in feed.entries:
        title = html.unescape(e.get("title", ""))
        budget = None
        m = _BUDGET.search(title)
        if m:
            budget = parse_money(m.group(1))
            title = title[: m.start()]
        title = _FOR_ALL.sub("", title).strip()
        link = e.get("link", "")
        nid = re.search(r"/projects/(\d+)", link)
        jobs.append(Job(
            id=f"flru:{nid.group(1) if nid else link}",
            source="flru",
            url=link,
            title=title,
            description=clean_text(e.get("summary", "")),
            budget=budget,
            currency="RUB" if budget else None,
            posted_at=e.get("published"),
        ))
    return jobs


def fetch(client: httpx.Client) -> list[Job]:
    r = client.get(URL)
    r.raise_for_status()
    return parse(r.content)
