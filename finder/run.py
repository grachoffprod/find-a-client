"""Один запуск искателя: собрать → отобрать → ИИ → Telegram → история.

Запуск: python -m finder.run
"""
import os
import sys
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


def run(sources: dict[str, Callable[[], list[Job]]], settings: dict, topics: dict, profile: dict,
        notifier: Callable[[str], bool], analyzer: Analyzer, state_dir: Path, history_path: Path) -> dict:
    state_dir = Path(state_dir)
    stats = {"fetched": 0, "new": 0, "matched": 0, "analyzed": 0, "sent": 0, "errors": 0}
    health = read_json(state_dir / "health.json", {})
    threshold = settings["health"]["fail_threshold"]

    # 1. Сбор: каждый источник отдельно, сбой одного не мешает остальным
    jobs: list[Job] = []
    for name, fetch in sources.items():
        error = ""
        try:
            got = fetch()
        except Exception as e:  # noqa: BLE001 — любой сбой площадки
            got, error = None, f"{type(e).__name__}: {e}"
            stats["errors"] += 1
            _log(f"[{name}] ERROR {error}")
        rec = health.setdefault(name, {"fails": 0})
        ok = got is not None and (len(got) > 0 or not rec.get("last_count"))
        if got is not None and not ok:
            error = "площадка вернула 0 заказов"
        if ok:
            rec["last_count"] = len(got)
        alert = update_health(health, name, ok, threshold, error)
        if alert:
            notifier(alert)
        if got:
            _log(f"[{name}] {len(got)} заказов")
            jobs.extend(got)
    stats["fetched"] = len(jobs)
    write_json(state_dir / "health.json", health)

    seen = SeenStore(state_dir / "seen.json")
    seen.load()

    # 2. Первый запуск: запоминаем всё, ничего не анализируем
    if seen.is_empty:
        for j in jobs:
            seen.add(j.id)
        seen.save()
        notifier(f"✅ Искатель запущен. Заказов уже в базе: {len(jobs)}. Дальше присылаю только новые.")
        return stats

    # 3. Новые и подходящие по темам
    new = []
    for j in jobs:
        if seen.is_new(j.id):
            seen.add(j.id)
            new.append(j)
    stats["new"] = len(new)
    matched = []
    for j in new:
        t = match_topics(j, topics["topics"], topics["stop"])
        if t and passes_budget(j, settings["filter"]["min_budget"]):
            matched.append((j, t))
    stats["matched"] = len(matched)

    # 4. ИИ (с лимитами) и отправка
    usage = UsageCounter(state_dir / "usage.json", settings["ai"]["monthly_limit"])
    per_run = settings["ai"]["max_per_run"]
    min_score = settings["notify"]["min_score"]
    found_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    history = []
    for j, t in matched:
        a: Analysis | None = None
        if stats["analyzed"] < per_run and usage.can_spend():
            usage.spend()
            stats["analyzed"] += 1
            try:
                a = analyzer(j, profile, settings, t)
            except Exception as e:  # noqa: BLE001 — заказ не теряем
                _log(f"[ai] ERROR {j.id}: {type(e).__name__}: {e}")
        if a is None or (a.relevant and a.score >= min_score):
            if notifier(format_job(j, a)):
                stats["sent"] += 1
        history.append({**j.to_dict(), "topics": t, "analysis": a.to_dict() if a else None, "found_at": found_at})

    usage.save()
    seen.save()
    if history:
        append_history(history_path, history, settings["history"]["max_items"])
    return stats


def _load_dotenv() -> None:
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"'))


def main() -> int:
    from finder.http import make_client
    from finder.sources import SOURCES
    from finder.telegram_bot import send

    _load_dotenv()
    settings, topics, profile = load_settings(), load_topics(), load_profile()
    client = make_client()

    sources = {}
    for name in settings["sources"]["enabled"]:
        fetch = SOURCES[name]
        if name == "telegram":
            sources[name] = partial(fetch, client, settings["sources"].get("telegram_channels") or [])
        else:
            sources[name] = partial(fetch, client)

    token, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if token and chat:
        notifier = lambda text: send(text, token, chat, client)  # noqa: E731
    else:
        _log("TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID не заданы — сообщения печатаются в консоль")

        def notifier(text: str) -> bool:
            _log("---- telegram ----\n" + text)
            return True

    key = {"anthropic": "ANTHROPIC_API_KEY", "openrouter": "OPENROUTER_API_KEY"}.get(settings["ai"]["provider"])
    if key and not os.environ.get(key):
        _log(f"{key} не задан — заказы придут без откликов")

        def analyzer(*_):
            raise RuntimeError(f"{key} не задан")
    else:
        analyzer = analyze

    stats = run(sources, settings, topics, profile, notifier, analyzer,
                ROOT / "state", ROOT / "docs" / "data" / "jobs.json")
    _log(f"Итог: {stats}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
