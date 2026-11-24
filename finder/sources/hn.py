"""Hacker News — свежая ветка «Who is hiring?»; берём только контракт/фриланс/частичную занятость.

Ветка «Freelancer? Seeking Freelancer?» перестала выходить в октябре 2025.
"""
import json
import re

import httpx

from finder.http import clean_text
from finder.models import Job

SEARCH = "https://hn.algolia.com/api/v1/search_by_date?tags=story,author_whoishiring&hitsPerPage=10"
ITEM = "https://hn.algolia.com/api/v1/items/{id}"
_CONTRACT = re.compile(r"\b(contract(or)?|freelanc\w*|part[- ]time|project[- ]based)\b", re.I)


def latest_thread_id(search_json: str) -> str:
    for h in json.loads(search_json)["hits"]:
        if h.get("title", "").startswith("Ask HN: Who is hiring?"):
            return h["objectID"]
    raise ValueError("hn: no 'Who is hiring?' thread found")


def parse(raw: str) -> list[Job]:
    thread = json.loads(raw)
    jobs = []
    for c in thread.get("children", []):
        text = clean_text(c.get("text"))
        if not text:
            continue
        first_line, _, rest = text.partition("\n")
        if not _CONTRACT.search(first_line):
            continue
        jobs.append(Job(
            id=f"hn:{c['id']}",
            source="hn",
            url=f"https://news.ycombinator.com/item?id={c['id']}",
            title=first_line[:200],
            description=rest.strip() or first_line,
            posted_at=c.get("created_at"),
            lang="en",
            direct=True,
        ))
    return jobs


def fetch(client: httpx.Client) -> list[Job]:
    s = client.get(SEARCH)
    s.raise_for_status()
    r = client.get(ITEM.format(id=latest_thread_id(s.text)))
    r.raise_for_status()
    return parse(r.text)
