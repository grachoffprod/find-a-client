from pathlib import Path

import pytest

from finder.http import clean_text, parse_money
from finder.sources import flru, freelance_ru, freelancer, guru, hn, kwork, pph, telegram

FIX = Path(__file__).parent / "fixtures"


def read(name: str) -> str:
    return (FIX / name).read_text(encoding="utf-8")


CASES = [
    ("flru", lambda: flru.parse((FIX / "flru.xml").read_bytes())),
    ("kwork", lambda: kwork.parse(read("kwork.html"))),
    ("freelancer", lambda: freelancer.parse(read("freelancer.json"))),
    ("hn", lambda: hn.parse(read("hn_item.json"))),
    ("telegram", lambda: telegram.parse(read("telegram.html"), "freelancetaverna")),
    ("freelance_ru", lambda: freelance_ru.parse(read("freelance_ru.html"))),
    ("pph", lambda: pph.parse(read("pph.html"))),
    ("guru", lambda: guru.parse(read("guru.html"))),
]


@pytest.mark.parametrize("name,parse", CASES, ids=[c[0] for c in CASES])
def test_source_parses_fixture(name, parse):
    jobs = parse()
    assert len(jobs) >= 1
    ids = [j.id for j in jobs]
    assert len(ids) == len(set(ids)), "duplicate ids"
    for j in jobs:
        assert j.id.startswith(name + ":")
        assert j.source == name
        assert j.url.startswith("http")
        assert j.title.strip()
        assert j.budget is None or j.budget > 0


def test_flru_budget_extracted_and_title_cleaned():
    jobs = flru.parse((FIX / "flru.xml").read_bytes())
    with_budget = [j for j in jobs if j.budget]
    assert with_budget
    assert all("Бюджет" not in j.title and "для всех" not in j.title for j in jobs)


def test_budget_absent_is_none():
    jobs = flru.parse((FIX / "flru.xml").read_bytes())
    assert any(j.budget is None for j in jobs)


def test_hn_keeps_only_contract_posts():
    jobs = hn.parse(read("hn_item.json"))
    assert all(hn._CONTRACT.search(j.title) for j in jobs)
    assert all(j.direct and j.lang == "en" for j in jobs)


def test_hn_latest_thread_is_who_is_hiring():
    assert hn.latest_thread_id(read("hn_search.json"))


def test_telegram_jobs_are_direct():
    jobs = telegram.parse(read("telegram.html"), "freelancetaverna")
    assert all(j.direct for j in jobs)
    assert all(j.url.startswith("https://t.me/freelancetaverna/") for j in jobs)


def test_kwork_missing_state_raises():
    with pytest.raises(ValueError):
        kwork.parse("<html>изменили вёрстку</html>")


@pytest.mark.parametrize("text,value", [
    ("3 000 ₽", 3000), ("до 15000 руб", 15000), ("$250", 250), ("Under $250", 250),
    ("25 000  ₽", 25000), ("договорная", None), ("", None), ("1.500", 1500),
])
def test_parse_money(text, value):
    assert parse_money(text) == value


def test_clean_text_strips_tags():
    out = clean_text("<p>Привет <b>мир</b> &amp; ко</p><br>ок")
    assert out.startswith("Привет мир & ко")
    assert out.endswith("ок")
    assert "<" not in out
