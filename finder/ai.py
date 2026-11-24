"""Оценка заказа и черновик отклика через Claude API или OpenRouter."""
import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import httpx

from finder.models import Job
from finder.prompt import build_prompt
from finder.state import read_json, write_json

MAX_TOKENS = 1200


@dataclass
class Analysis:
    relevant: bool
    topic: str
    score: int
    summary_ru: str
    reply: str
    reply_ru: str
    questions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return self.__dict__.copy()


def parse_analysis(text: str) -> Analysis:
    start = text.find("{")
    if start < 0:
        raise ValueError("no JSON object in model output")
    try:
        data, _ = json.JSONDecoder().raw_decode(text[start:])
    except json.JSONDecodeError as e:
        raise ValueError(f"bad JSON from model: {e}") from e
    try:
        score = int(round(float(data.get("score", 1))))
    except (TypeError, ValueError):
        score = 1
    q = data.get("questions") or []
    return Analysis(
        relevant=bool(data.get("relevant", False)),
        topic=str(data.get("topic") or ""),
        score=min(10, max(1, score)),
        summary_ru=str(data.get("summary_ru") or ""),
        reply=str(data.get("reply") or ""),
        reply_ru=str(data.get("reply_ru") or ""),
        questions=[str(x) for x in q] if isinstance(q, list) else [str(q)],
    )


def _call_anthropic(system: str, user: str, settings: dict) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    msg = client.messages.create(
        model=settings["ai"]["model"],
        max_tokens=MAX_TOKENS,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")


def _call_openrouter(system: str, user: str, settings: dict) -> str:
    r = httpx.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}"},
        json={
            "model": settings["ai"]["model"],
            "max_tokens": MAX_TOKENS,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        },
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


PROVIDERS: dict[str, Callable[[str, str, dict], str]] = {
    "anthropic": _call_anthropic,
    "openrouter": _call_openrouter,
}


def analyze(job: Job, profile: dict, settings: dict, topics: list[str],
            call: Callable[[str, str, dict], str] | None = None) -> Analysis:
    if call is None:
        provider = settings["ai"]["provider"]
        if provider not in PROVIDERS:
            raise ValueError(f"unknown AI provider: {provider}")
        call = PROVIDERS[provider]
    system, user = build_prompt(job, profile, topics)
    return parse_analysis(call(system, user, settings))


class UsageCounter:
    """Сколько запросов к ИИ сделано в этом месяце; сбрасывается с новым месяцем."""

    def __init__(self, path: Path, limit: int, month: str | None = None):
        self.path = Path(path)
        self.limit = limit
        self.month = month or datetime.now(timezone.utc).strftime("%Y-%m")
        data = read_json(self.path, {})
        self.count = data.get("count", 0) if data.get("month") == self.month else 0

    def can_spend(self) -> bool:
        return self.count < self.limit

    def spend(self) -> None:
        self.count += 1

    def save(self) -> None:
        write_json(self.path, {"month": self.month, "count": self.count})
