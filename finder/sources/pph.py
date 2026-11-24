"""PeoplePerHour — список заказов (HTML, классы с хешами, поэтому ищем по началу имени класса)."""
import re

import httpx
from selectolax.lexbor import LexborHTMLParser

from finder.models import Job

URL = "https://www.peopleperhour.com/freelance-jobs"
_JOB = re.compile(r"^https://www\.peopleperhour\.com/freelance-jobs/.+-(\d+)$")


def parse(raw: str) -> list[Job]:
    jobs, seen = [], set()
    for a in LexborHTMLParser(raw).css("h6 a"):
        href = a.attributes.get("href") or ""
        m = _JOB.match(href)
        if not m or m.group(1) in seen:
            continue
        seen.add(m.group(1))
        h6 = a.parent
        desc = h6.next if h6 is not None else None
        while desc is not None and desc.tag != "p":
            desc = desc.next
        jobs.append(Job(
            id=f"pph:{m.group(1)}",
            source="pph",
            url=href,
            title=a.text(strip=True),
            description=desc.text(strip=True) if desc is not None else "",
            lang="en",
        ))
    return jobs


def fetch(client: httpx.Client) -> list[Job]:
    r = client.get(URL)
    r.raise_for_status()
    return parse(r.text)
