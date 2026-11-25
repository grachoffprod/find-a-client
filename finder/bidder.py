"""Auto-bid on Freelancer.com via the official API (POST /projects/0.1/bids/).

Safe by default: dry_run=True only reports what would be sent. Daily cap and
one-bid-per-project are enforced from state/bids.json.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

import httpx

from finder.models import Job

API = "https://www.freelancer.com/api/projects/0.1/bids/"


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


class BidLog:
    def __init__(self, path: Path):
        self.path = path
        self.data = {"day": _today(), "count": 0, "projects": []}
        if path.exists():
            try:
                self.data.update(json.loads(path.read_text(encoding="utf-8")))
            except ValueError:
                pass
        if self.data["day"] != _today():
            self.data.update(day=_today(), count=0)

    def can_bid(self, project_id: str, daily_limit: int) -> bool:
        return self.data["count"] < daily_limit and project_id not in self.data["projects"]

    def record(self, project_id: str) -> None:
        self.data["count"] += 1
        self.data["projects"] = (self.data["projects"] + [project_id])[-500:]

    def save(self) -> None:
        self.path.write_text(json.dumps(self.data), encoding="utf-8")


def compute_amount(job: Job, cfg: dict) -> float | None:
    """Hourly: fixed rate. Fixed: share of the client's max budget. None = skip."""
    if job.project_type == "hourly":
        return float(cfg.get("hourly_rate", 12))
    if not job.budget:
        return None
    return round(job.budget * float(cfg.get("fixed_budget_share", 0.8)), 2)


def place_bid(client: httpx.Client, token: str, user_id: int, job: Job, text: str, cfg: dict) -> tuple[bool, str]:
    amount = compute_amount(job, cfg)
    if amount is None:
        return False, "no budget, skipped"
    project_id = int(job.id.split(":", 1)[1])
    body = {
        "project_id": project_id,
        "bidder_id": int(user_id),
        "amount": amount,
        "period": int(cfg.get("period_days", 7)),
        "milestone_percentage": int(cfg.get("milestone_percentage", 100)),
        "description": text,
    }
    r = client.post(API, json=body, headers={"freelancer-oauth-v1": token})
    if r.status_code == 200:
        return True, f"{amount} {job.currency or ''}".strip()
    try:
        msg = r.json().get("message") or r.text
    except ValueError:
        msg = r.text
    return False, f"HTTP {r.status_code}: {str(msg)[:200]}"
