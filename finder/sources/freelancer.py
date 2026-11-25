"""Freelancer.com public API for active projects."""
import json
from datetime import datetime, timezone

import httpx

from finder.http import clean_text
from finder.models import Job

URL = (
    "https://www.freelancer.com/api/projects/0.1/projects/active/"
    "?limit=50&full_description=true&job_details=true&sort_field=time_updated"
)


def parse(raw: str) -> list[Job]:
    data = json.loads(raw)
    jobs = []
    for p in data["result"]["projects"]:
        b = p.get("budget") or {}
        budget = b.get("maximum") or b.get("minimum")
        ts = p.get("time_submitted")
        jobs.append(Job(
            id=f"freelancer:{p['id']}",
            source="freelancer",
            url=f"https://www.freelancer.com/projects/{p.get('seo_url') or p['id']}",
            title=clean_text(p.get("title")),
            description=clean_text(p.get("description") or p.get("preview_description")),
            budget=float(budget) if budget else None,
            currency=(p.get("currency") or {}).get("code"),
            posted_at=datetime.fromtimestamp(ts, timezone.utc).isoformat() if ts else None,
            lang=p.get("language") or "en",
        ))
    return jobs


def fetch(client: httpx.Client) -> list[Job]:
    r = client.get(URL)
    r.raise_for_status()
    return parse(r.text)
