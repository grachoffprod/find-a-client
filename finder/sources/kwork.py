"""Kwork — биржа проектов; данные лежат в JSON window.stateData на странице."""
import json

import httpx

from finder.http import clean_text, parse_money
from finder.models import Job

URL = "https://kwork.ru/projects"
_MARK = "window.stateData="


def parse(raw: str) -> list[Job]:
    i = raw.find(_MARK)
    if i < 0:
        raise ValueError("kwork: window.stateData not found")
    state, _ = json.JSONDecoder().raw_decode(raw[i + len(_MARK):])
    wants = state.get("wants") or (state.get("wantsListData") or {}).get("wants") or []
    jobs = []
    for w in wants:
        budget = parse_money(str(w.get("priceLimit") or "")) or parse_money(str(w.get("possiblePriceLimit") or ""))
        jobs.append(Job(
            id=f"kwork:{w['id']}",
            source="kwork",
            url=f"https://kwork.ru/projects/{w['id']}",
            title=clean_text(w.get("name")),
            description=clean_text(w.get("description")),
            budget=budget,
            currency="RUB" if budget else None,
            posted_at=w.get("date_active") or w.get("date_create"),
            lang=w.get("lang") or "ru",
        ))
    return jobs


def fetch(client: httpx.Client) -> list[Job]:
    r = client.get(URL)
    r.raise_for_status()
    return parse(r.text)
