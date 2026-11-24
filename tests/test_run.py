import json

import pytest

from finder.ai import Analysis
from finder.config import load_profile, load_topics
from finder.health import update_health
from finder.history import append_history
from finder.models import Job
from finder.run import run

TOPICS = load_topics()
PROFILE = load_profile()


def settings(max_per_run=40, monthly=3000, time_budget=600):
    return {
        "ai": {"provider": "anthropic", "model": "m", "max_per_run": max_per_run, "monthly_limit": monthly,
               "time_budget_s": time_budget},
        "notify": {"min_score": 6, "delay_s": 0}, "filter": {"min_budget": 0}, "history": {"max_items": 500},
        "health": {"fail_threshold": 3},
    }


def bot_job(i: int, source="kwork") -> Job:
    return Job(id=f"{source}:{i}", source=source, url=f"https://x/{i}", title=f"Нужен телеграм бот {i}", description="")


def good(score=8):
    return lambda job, profile, settings, topics: Analysis(True, "tg_bot", score, "s", "r", "r", [])


class Box:
    def __init__(self):
        self.msgs = []

    def __call__(self, text):
        self.msgs.append(text)
        return True


@pytest.fixture
def paths(tmp_path):
    seen = tmp_path / "state" / "seen.json"
    seen.parent.mkdir()
    seen.write_text('["init:0"]', encoding="utf-8")  # не первый запуск
    known = {n: {"fails": 0, "last_count": 5} for n in ("kwork", "flru", "telegram")}
    (seen.parent / "health.json").write_text(json.dumps(known), encoding="utf-8")  # источники уже работали
    return tmp_path / "state", tmp_path / "jobs.json"


def go(sources, analyzer, paths, **kw):
    box = Box()
    stats = run(sources, kw.get("settings", settings()), TOPICS, PROFILE, box, analyzer, paths[0], paths[1])
    return stats, box


def test_first_run_marks_all_seen_sends_one(tmp_path):
    called = []
    box = Box()
    stats = run({"kwork": lambda: [bot_job(i) for i in range(30)]}, settings(), TOPICS, PROFILE, box,
                lambda *a: called.append(1), tmp_path / "state", tmp_path / "jobs.json")
    assert len(box.msgs) == 1 and "30" in box.msgs[0]
    assert called == []
    stats2 = run({"kwork": lambda: [bot_job(i) for i in range(30)]}, settings(), TOPICS, PROFILE, box,
                 good(), tmp_path / "state", tmp_path / "jobs.json")
    assert stats2["new"] == 0


def test_new_matching_job_is_analyzed_and_sent(paths):
    stats, box = go({"kwork": lambda: [bot_job(1)]}, good(), paths)
    assert stats["sent"] == 1 and len(box.msgs) == 1
    hist = json.loads(paths[1].read_text(encoding="utf-8"))
    assert hist[0]["id"] == "kwork:1" and hist[0]["analysis"]["score"] == 8


def test_unrelated_job_not_analyzed(paths):
    called = []
    job = Job(id="kwork:9", source="kwork", url="https://x", title="Посадить огород", description="")
    stats, box = go({"kwork": lambda: [job]}, lambda *a: called.append(1), paths)
    assert called == [] and box.msgs == [] and stats["matched"] == 0


def test_ai_failure_still_notifies(paths):
    def boom(*a):
        raise RuntimeError("api down")

    stats, box = go({"kwork": lambda: [bot_job(1)]}, boom, paths)
    assert stats["sent"] == 1 and "не сгенерирован" in box.msgs[0]
    stats2, _ = go({"kwork": lambda: [bot_job(1)]}, good(), paths)
    assert stats2["new"] == 0  # заказ помечен виденным даже при сбое ИИ


def test_low_score_not_sent_but_in_history(paths):
    stats, box = go({"kwork": lambda: [bot_job(1)]}, good(score=3), paths)
    assert box.msgs == []
    assert json.loads(paths[1].read_text(encoding="utf-8"))[0]["id"] == "kwork:1"


def test_irrelevant_not_sent(paths):
    an = lambda *a: Analysis(False, "", 9, "s", "", "", [])
    stats, box = go({"kwork": lambda: [bot_job(1)]}, an, paths)
    assert box.msgs == []


def test_broken_source_does_not_stop_others(paths):
    def broken():
        raise RuntimeError("layout changed")

    stats, box = go({"flru": broken, "kwork": lambda: [bot_job(1)]}, good(), paths)
    assert stats["errors"] == 1 and stats["sent"] == 1


def test_ai_cap_per_run(paths):
    calls = []

    def counting(*a):
        calls.append(1)
        return Analysis(True, "tg_bot", 8, "s", "r", "r", [])

    stats, box = go({"kwork": lambda: [bot_job(i) for i in range(50)]}, counting, paths,
                    settings=settings(max_per_run=40))
    assert len(calls) == 40
    assert stats["sent"] == 50
    assert sum("не сгенерирован" in m for m in box.msgs) == 10


def test_monthly_limit_stops_ai(paths):
    calls = []
    stats, box = go({"kwork": lambda: [bot_job(i) for i in range(5)]},
                    lambda *a: calls.append(1) or Analysis(True, "tg_bot", 8, "s", "r", "r", []),
                    paths, settings=settings(monthly=2))
    assert len(calls) == 2


def test_health_alert_once_at_threshold():
    h = {}
    alerts = [update_health(h, "kwork", ok=False, threshold=3) for _ in range(5)]
    assert [a is not None for a in alerts] == [False, False, True, False, False]
    assert update_health(h, "kwork", ok=True, threshold=3) is None
    assert h["kwork"]["fails"] == 0


def test_zero_jobs_after_nonzero_counts_as_failure(paths):
    state = {"n": 5}

    def src():
        return [bot_job(i + 100 * state["n"]) for i in range(state["n"])]

    go({"kwork": src}, good(), paths)
    state["n"] = 0
    msgs = []
    for _ in range(3):
        _, box = go({"kwork": src}, good(), paths)
        msgs += box.msgs
    assert any("Kwork" in m or "kwork" in m for m in msgs)


def test_history_capped(tmp_path):
    p = tmp_path / "h.json"
    append_history(p, [{"id": str(i)} for i in range(10)], max_items=5)
    append_history(p, [{"id": "new"}], max_items=5)
    data = json.loads(p.read_text(encoding="utf-8"))
    assert len(data) == 5 and data[0]["id"] == "new"


# ---- fix pass after final review ----

def test_state_saved_even_if_run_crashes(paths):
    def boom_notify(text):
        raise RuntimeError("telegram exploded")

    with pytest.raises(RuntimeError):
        run({"kwork": lambda: [bot_job(1)]}, settings(), TOPICS, PROFILE, boom_notify, good(), paths[0], paths[1])
    seen = json.loads((paths[0] / "seen.json").read_text(encoding="utf-8"))
    usage = json.loads((paths[0] / "usage.json").read_text(encoding="utf-8"))
    assert "kwork:1" in seen and usage["count"] == 1


def test_time_budget_stops_ai(paths):
    calls = []
    stats, box = go({"kwork": lambda: [bot_job(i) for i in range(5)]},
                    lambda *a: calls.append(1) or Analysis(True, "tg_bot", 8, "s", "r", "r", []),
                    paths, settings=settings(time_budget=0))
    assert calls == [] and stats["sent"] == 5


def test_source_first_success_is_baselined_silently(paths):
    calls = []
    stats, box = go({"guru": lambda: [bot_job(i, source="guru") for i in range(20)]},
                    lambda *a: calls.append(1), paths)
    assert box.msgs == [] and calls == []
    stats2, box2 = go({"guru": lambda: [bot_job(i, source="guru") for i in range(21)]}, good(), paths)
    assert stats2["new"] == 1 and len(box2.msgs) == 1


def test_failed_send_is_counted(paths):
    stats = run({"kwork": lambda: [bot_job(1)]}, settings(), TOPICS, PROFILE, lambda t: False, good(),
                paths[0], paths[1])
    assert stats["sent"] == 0 and stats["send_failed"] == 1


def test_unknown_source_name_is_skipped():
    from finder.run import build_sources
    s = {"sources": {"enabled": ["kwork", "kworkk"], "telegram_channels": []}}
    assert list(build_sources(s, client=None)) == ["kwork"]


def test_non_http_url_is_dropped():
    j = Job(id="flru:1", source="flru", url="javascript:alert(1)", title="t", description="")
    assert j.url == ""
    assert Job(id="a:1", source="a", url="https://ok", title="t", description="").url == "https://ok"
