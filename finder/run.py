"""One finder run: collect → filter → AI → Telegram → history.

Run with: python -m finder.run
"""
import os
import sys
import time
from datetime import datetime, timezone
from functools import partial
from pathlib import Path
from typing import Callable

from finder.ai import Analysis, UsageCounter, analyze
from finder.config import ROOT, load_profile, load_settings, load_topics
from finder.filter import match_topics, passes_budget
from finder.health import update_health
from finder.history import append_history
from finder.models import Job
from finder.state import SeenStore, read_json, write_json
from finder.telegram_bot import format_job

Analyzer = Callable[[Job, dict, dict, list[str]], Analysis]


def _log(msg: str) -> None:
    print(msg, flush=True)


def _collect(sources: dict[str, Callable[[], list[Job]]], health: dict, threshold: int,
             notifier: Callable[[str], bool], stats: dict) -> tuple[list[Job], set[str]]:
    """Fetch sources and return jobs plus sources that succeeded for the first time."""
    jobs: list[Job] = []
    first_success: set[str] = set()
    for name, fetch in sources.items():
        error = ""
        try:
            got = fetch()
        except Exception as e:  # noqa: BLE001 — catch failures from any source
            got, error = None, f"{type(e).__name__}: {e}"
            stats["errors"] += 1
            _log(f"[{name}] ERROR {error}")
        rec = health.setdefault(name, {"fails": 0})
        ever_worked = "last_count" in rec
        ok = got is not None and (len(got) > 0 or not rec.get("last_count"))
        if got is not None and not ok:
            error = "source returned 0 jobs"
        if ok:
            rec["last_count"] = len(got)
            if not ever_worked and got:
                first_success.add(name)
        alert = update_health(health, name, ok, threshold, error)
        if alert:
            notifier(alert)
        if got:
            _log(f"[{name}] {len(got)} jobs")
            jobs.extend(got)
    return jobs, first_success


def run(sources: dict[str, Callable[[], list[Job]]], settings: dict, topics: dict, profile: dict,
        notifier: Callable[[str], bool], analyzer: Analyzer, state_dir: Path, history_path: Path) -> dict:
    state_dir = Path(state_dir)
    stats = {"fetched": 0, "new": 0, "matched": 0, "analyzed": 0, "sent": 0, "send_failed": 0, "errors": 0}
    health = read_json(state_dir / "health.json", {})
    seen = SeenStore(state_dir / "seen.json")
    seen.load()
    first_run = seen.is_empty

    jobs, first_success = _collect(sources, health, settings["health"]["fail_threshold"], notifier, stats)
    stats["fetched"] = len(jobs)
    write_json(state_dir / "health.json", health)

    # 1. First run: mark everything as seen without analyzing it.
    if first_run:
        if jobs:
            for j in jobs:
                seen.add(j.id)
            seen.save()
            notifier(f"✅ Finder started. Jobs already in the database: {len(jobs)}. Only new jobs will be sent.")
        return stats

    # 2. Also mark jobs from newly available sources as seen without sending them.
    for j in jobs:
        if j.source in first_success:
            seen.add(j.id)
    if first_success:
        _log(f"Available for the first time: {', '.join(sorted(first_success))} — current jobs marked as seen")

    # 3. Find new jobs that match the topics.
    new = [j for j in jobs if seen.is_new(j.id)]
    stats["new"] = len(new)
    matched = []
    for j in new:
        t = match_topics(j, topics["topics"], topics["stop"])
        if t and passes_budget(j, settings["filter"]["min_budget"]):
            matched.append((j, t))
        else:
            seen.add(j.id)
    stats["matched"] = len(matched)

    # 4. Analyze within the limits and send. State is saved even if the run fails midway.
    ai = settings["ai"]
    usage = UsageCounter(state_dir / "usage.json", ai["monthly_limit"])
    deadline = time.monotonic() + ai.get("time_budget_s", 360)
    min_score = settings["notify"]["min_score"]
    delay = settings["notify"].get("delay_s", 1)
    found_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    history = []
    notify_cfg = settings["notify"]
    priority = set(notify_cfg.get("priority_sources") or [])
    bonus = notify_cfg.get("priority_bonus", 0)
    max_send = notify_cfg.get("max_per_run") or 0  # 0 = no limit
    candidates: list[tuple[float, Job, Analysis | None]] = []
    # Priority sources are analyzed first so they get the AI budget before the others.
    matched.sort(key=lambda m: m[0].source not in priority)
    try:
        for j, t in matched:
            seen.add(j.id)
            a: Analysis | None = None
            if stats["analyzed"] < ai["max_per_run"] and usage.can_spend() and time.monotonic() < deadline:
                usage.spend()
                stats["analyzed"] += 1
                try:
                    a = analyzer(j, profile, settings, t)
                except Exception as e:  # noqa: BLE001 — keep the job even if analysis fails
                    _log(f"[ai] ERROR {j.id}: {type(e).__name__}: {e}")
            history.append({**j.to_dict(), "topics": t, "analysis": a.to_dict() if a else None, "found_at": found_at})
            if a is None:
                candidates.append((-1, j, None))
            elif a.relevant and a.score >= min_score:
                candidates.append((a.score + (bonus if j.source in priority else 0), j, a))
        # Send only the best jobs (all of them when max_per_run is 0).
        candidates.sort(key=lambda c: -c[0])
        for _, j, a in (candidates[:max_send] if max_send else candidates):
            if stats["sent"] or stats["send_failed"]:
                time.sleep(delay)
            if notifier(format_job(j, a)):
                stats["sent"] += 1
            else:
                stats["send_failed"] += 1
                _log(f"[telegram] not sent: {j.id} (available in the web dashboard)")
    finally:
        usage.save()
        seen.save()
        if history:
            append_history(history_path, history, settings["history"]["max_items"])
    return stats


def build_sources(settings: dict, client) -> dict[str, Callable[[], list[Job]]]:
    """Build sources from settings.yaml, skipping unknown names with a warning."""
    from finder.sources import SOURCES

    sources = {}
    for name in settings["sources"]["enabled"]:
        fetch = SOURCES.get(name)
        if fetch is None:
            _log(f"⚠️ Unknown source in settings.yaml: {name!r} — skipping. Available: {', '.join(SOURCES)}")
            continue
        sources[name] = partial(fetch, client)
    return sources


def _load_dotenv() -> None:
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"'))


def main() -> int:
    from finder.http import make_client
    from finder.telegram_bot import send

    _load_dotenv()
    settings, topics, profile = load_settings(), load_topics(), load_profile()
    client = make_client()
    sources = build_sources(settings, client)

    token, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if token and chat:
        notifier = lambda text: send(text, token, chat, client)  # noqa: E731
    else:
        _log("TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID not set — messages will be printed to the console")

        def notifier(text: str) -> bool:
            _log("---- telegram ----\n" + text)
            return True

    key = {"anthropic": "ANTHROPIC_API_KEY", "openrouter": "OPENROUTER_API_KEY"}.get(settings["ai"]["provider"])
    if key and not os.environ.get(key):
        _log(f"{key} not set — jobs will arrive without generated replies")

        def analyzer(*_):
            raise RuntimeError(f"{key} not set")
    else:
        analyzer = analyze

    stats = run(sources, settings, topics, profile, notifier, analyzer,
                ROOT / "state", ROOT / "docs" / "data" / "jobs.json")
    _log(f"Summary: {stats}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
