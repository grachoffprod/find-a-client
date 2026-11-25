"""Guru job listings (HTML)."""
import re

import httpx
from selectolax.lexbor import LexborHTMLParser

from finder.http import parse_money
from finder.models import Job

BASE = "https://www.guru.com"
URL = BASE + "/d/jobs/"


def parse(raw: str) -> list[Job]:
    jobs = []
    for rec in LexborHTMLParser(raw).css("div.jobRecord"):
        gid = rec.attributes.get("data-gid")
        a = rec.css_first(".jobRecord__title a")
        if not gid or a is None:
            continue
        href = re.sub(r"&SearchUrl=.*$", "", a.attributes.get("href") or "")
        desc = rec.css_first(".jobRecord__desc")
        budget_node = rec.css_first(".jobRecord__budget")
        budget_text = budget_node.text(separator=" ", strip=True) if budget_node else ""
        budget = parse_money(budget_text)
        jobs.append(Job(
            id=f"guru:{gid}",
            source="guru",
            url=BASE + href,
            title=a.text(strip=True),
            description=(desc.text(strip=True) if desc else "") + (f"\nBudget: {budget_text}" if budget_text else ""),
            budget=budget,
            currency="USD" if budget else None,
            lang="en",
        ))
    return jobs


def fetch(client: httpx.Client) -> list[Job]:
    r = client.get(URL)
    r.raise_for_status()
    return parse(r.text)
