"""Freelance.ru — лента заданий (HTML)."""
import re

import httpx
from selectolax.lexbor import LexborHTMLParser

from finder.http import parse_money
from finder.models import Job

BASE = "https://freelance.ru"
URL = BASE + "/task"


def parse(raw: str) -> list[Job]:
    jobs = []
    for card in LexborHTMLParser(raw).css("article.task-card"):
        a = card.css_first("a.task-card__title-link")
        if a is None:
            continue
        href = a.attributes.get("href") or ""
        m = re.search(r"/task/view/(\d+)", href)
        if not m:
            continue
        desc = card.css_first(".task-card__desc")
        price = card.css_first("[class*=price], [class*=budget]")
        budget = parse_money(price.text()) if price else None
        when = card.css_first(".task-card__foot-item[title]")
        jobs.append(Job(
            id=f"freelance_ru:{m.group(1)}",
            source="freelance_ru",
            url=BASE + href,
            title=a.text(strip=True),
            description=desc.text(strip=True) if desc else "",
            budget=budget,
            currency="RUB" if budget else None,
            posted_at=when.attributes.get("title") if when else None,
        ))
    return jobs


def fetch(client: httpx.Client) -> list[Job]:
    r = client.get(URL)
    r.raise_for_status()
    return parse(r.text)
