import pytest
import sys
from types import SimpleNamespace

from finder.ai import Analysis, UsageCounter, _call_anthropic, analyze, parse_analysis
from finder.config import load_profile
from finder.models import Job
from finder.prompt import build_prompt

GOOD = ('{"relevant": true, "topic": "tg_bot", "score": 8, "summary_ru": "Бот для записи", '
        '"reply": "Hi", "reply_ru": "Привет", "questions": ["Сроки?"]}')


def job(desc="Нужен бот", lang="ru", direct=False):
    return Job(id="x:1", source="x", url="https://x", title="Бот", description=desc, lang=lang, direct=direct)


def test_parse_plain_json():
    a = parse_analysis(GOOD)
    assert a == Analysis(True, "tg_bot", 8, "Бот для записи", "Hi", "Привет", ["Сроки?"])


def test_parse_fenced_json():
    assert parse_analysis("Вот ответ:\n```json\n" + GOOD + "\n```").score == 8


def test_anthropic_truncated_response_raises_clear_error(monkeypatch):
    response = SimpleNamespace(content=[], stop_reason="max_tokens")
    client = SimpleNamespace(messages=SimpleNamespace(create=lambda **kwargs: response))
    monkeypatch.setitem(
        sys.modules,
        "anthropic",
        SimpleNamespace(Anthropic=lambda **kwargs: client),
    )
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    with pytest.raises(ValueError, match="truncated: max_tokens"):
        _call_anthropic("system", "user", {"ai": {"model": "test-model"}})


def test_parse_garbage_raises():
    with pytest.raises(ValueError):
        parse_analysis("я не знаю")


def test_score_clamped():
    assert parse_analysis(GOOD.replace('"score": 8', '"score": 15')).score == 10
    assert parse_analysis(GOOD.replace('"score": 8', '"score": -3')).score == 1


def test_missing_fields_default():
    a = parse_analysis('{"relevant": false, "score": 2}')
    assert a.relevant is False and a.reply == "" and a.questions == []


def test_prompt_truncates_description():
    system, user = build_prompt(job("я" * 10000), load_profile(), ["tg_bot"])
    assert user.count("я") <= 4000


def test_prompt_forbids_fake_experience_and_signs_yakov():
    system, _ = build_prompt(job(), load_profile(), ["tg_bot"])
    assert "Yakov" in system
    assert "выдумыва" in system.lower()


def test_prompt_mentions_crypto_only_for_direct():
    _, user_direct = build_prompt(job(direct=True), load_profile(), [])
    _, user_platform = build_prompt(job(direct=False), load_profile(), [])
    assert "USDT" in user_direct
    assert "USDT" not in user_platform


def test_usage_resets_on_new_month(tmp_path):
    u = UsageCounter(tmp_path / "u.json", limit=2, month="2026-11")
    u.spend(); u.spend()
    assert not u.can_spend()
    u.save()
    u2 = UsageCounter(tmp_path / "u.json", limit=2, month="2026-12")
    assert u2.can_spend()


def test_usage_persists_within_month(tmp_path):
    u = UsageCounter(tmp_path / "u.json", limit=5, month="2026-11")
    u.spend(); u.save()
    assert UsageCounter(tmp_path / "u.json", limit=5, month="2026-11").count == 1


def test_analyze_uses_injected_caller():
    calls = []

    def fake_call(system, user, settings):
        calls.append((system, user))
        return GOOD

    a = analyze(job(), load_profile(), {"ai": {"provider": "anthropic", "model": "m"}}, ["tg_bot"], call=fake_call)
    assert a.score == 8 and len(calls) == 1


def test_unknown_provider_raises():
    with pytest.raises(ValueError):
        analyze(job(), load_profile(), {"ai": {"provider": "nope", "model": "m"}}, [])


def test_relevant_string_false_is_false():
    assert parse_analysis('{"relevant": "false", "score": 7}').relevant is False
    assert parse_analysis('{"relevant": "true", "score": 7}').relevant is True
