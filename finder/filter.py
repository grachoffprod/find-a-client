"""Filter jobs by topic before AI analysis to control costs."""
import re
from functools import lru_cache

from finder.models import Job

_L = "a-zа-яё0-9"


@lru_cache(maxsize=4096)
def _pattern(word: str) -> re.Pattern:
    """Match words from their start, with short Latin terms matched as whole words."""
    p = rf"(?<![{_L}]){re.escape(word)}"
    if len(word) <= 4 and re.fullmatch(r"[a-z0-9]+", word):
        p += rf"(?![{_L}])"
    return re.compile(p)


def _text(job: Job) -> str:
    return f"{job.title}\n{job.description}".lower()


def match_topics(job: Job, topics: dict[str, list[str]], stop: list[str]) -> list[str]:
    text = _text(job)
    if any(_pattern(w).search(text) for w in stop):
        return []
    return [name for name, words in topics.items() if any(_pattern(w).search(text) for w in words)]


def passes_budget(job: Job, min_budget: float) -> bool:
    return job.budget is None or job.budget >= min_budget
