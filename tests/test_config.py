from finder.config import load_profile, load_settings, load_topics
from finder.models import Job


def test_topics_cover_all_14():
    t = load_topics()
    assert len(t["topics"]) == 14
    for name, words in t["topics"].items():
        assert len(words) >= 8, name
        assert all(w == w.lower() for w in words), name
    assert t["stop"]


def test_profile_name():
    assert load_profile()["name"] == "Yakov"


def test_settings_defaults():
    s = load_settings()
    assert s["ai"]["max_per_run"] == 40
    assert s["notify"]["min_score"] == 6
    assert s["history"]["max_items"] == 500
    assert s["health"]["fail_threshold"] == 3


def test_job_id_and_dict():
    j = Job(id="freelancer:1", source="freelancer", url="https://freelancer.com/x", title="t", description="d")
    d = j.to_dict()
    assert d["id"] == "freelancer:1"
    assert d["budget"] is None
