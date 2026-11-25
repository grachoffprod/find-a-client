from pathlib import Path

import pytest

from finder.http import clean_text, parse_money
from finder.sources import freelancer, guru, hn, pph

FIX = Path(__file__).parent / "fixtures"


def read(name: str) -> str:
    return (FIX / name).read_text(encoding="utf-8")


CASES = [
    ("freelancer", lambda: freelancer.parse(read("freelancer.json"))),
    ("hn", lambda: hn.parse(read("hn_item.json"))),
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


def test_hn_keeps_only_contract_posts():
    jobs = hn.parse(read("hn_item.json"))
    assert all(hn._CONTRACT.search(j.title) for j in jobs)
    assert all(j.direct and j.lang == "en" for j in jobs)


def test_hn_latest_thread_is_who_is_hiring():
    assert hn.latest_thread_id(read("hn_search.json"))


@pytest.mark.parametrize("text,value", [
    ("3 000 USD", 3000), ("up to 15000 USD", 15000), ("$250", 250), ("Under $250", 250),
    ("25 000 USD", 25000), ("negotiable", None), ("", None), ("1.500", 1500),
])
def test_parse_money(text, value):
    assert parse_money(text) == value


def test_clean_text_strips_tags():
    out = clean_text("<p>Hello <b>world</b> &amp; all</p><br>okay")
    assert out.startswith("Hello world & all")
    assert out.endswith("okay")
    assert "<" not in out
