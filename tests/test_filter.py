from finder.config import load_topics
from finder.filter import match_topics, passes_budget
from finder.models import Job
from finder.state import SeenStore

T = load_topics()


def job(title: str, desc: str = "", budget=None) -> Job:
    return Job(id="x:1", source="x", url="https://x", title=title, description=desc, budget=budget)


def m(title: str, desc: str = "") -> list[str]:
    return match_topics(job(title, desc), T["topics"], T["stop"])


def test_bot_order_matches_tg_bot():
    assert "tg_bot" in m("Нужен телеграм бот для записи")


def test_english_landing():
    assert "landing" in m("Need a landing page for my SaaS")


def test_stop_word_blocks():
    assert m("Нарисовать логотип для лендинга") == []


def test_unrelated_is_empty():
    assert m("Написать статью про садоводство", "Нужен текст 5000 знаков") == []


def test_short_keyword_needs_word_boundary():
    # "api" не должно срабатывать внутри "capital", "rapid", "therapist"
    assert m("Capital markets therapist", "rapid growth") == []
    assert "api_integration" in m("Connect Stripe API to the site")


def test_no_budget_passes():
    assert passes_budget(job("t", budget=None), 1000)


def test_budget_threshold():
    assert not passes_budget(job("t", budget=500), 1000)
    assert passes_budget(job("t", budget=1500), 1000)
    assert passes_budget(job("t", budget=10), 0)


def test_seen_roundtrip(tmp_path):
    p = tmp_path / "seen.json"
    s = SeenStore(p)
    s.load()
    assert s.is_empty
    s.add("a:1")
    s.save()
    s2 = SeenStore(p)
    s2.load()
    assert not s2.is_new("a:1")
    assert s2.is_new("a:2")
    assert not s2.is_empty


def test_seen_caps_size(tmp_path):
    s = SeenStore(tmp_path / "seen.json", max_items=5)
    s.load()
    for i in range(10):
        s.add(f"a:{i}")
    s.save()
    s2 = SeenStore(tmp_path / "seen.json", max_items=5)
    s2.load()
    assert s2.is_new("a:0")
    assert not s2.is_new("a:9")
