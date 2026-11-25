import httpx

from finder.ai import Analysis
from finder.models import Job
from finder.telegram_bot import MAX_LEN, format_job, send


def job(title="Бот", desc="Описание", budget=None, lang="ru", source="freelancer"):
    return Job(id="freelancer:1", source=source, url="https://freelancer.com/projects/1", title=title,
               description=desc, budget=budget, currency="RUB" if budget else None, lang=lang)


A = Analysis(True, "tg_bot", 8, "Нужен бот для записи", "Hello, I can build it. Yakov", "Привет, сделаю. Yakov", ["Сроки?"])


def test_escapes_html():
    out = format_job(job(title="<b>Бот & CRM</b>"), A)
    assert "&lt;b&gt;Бот &amp; CRM&lt;/b&gt;" in out


def test_length_limit():
    long = Analysis(True, "tg_bot", 8, "s" * 3000, "r" * 5000, "п" * 5000, [])
    out = format_job(job(desc="d" * 20000), long)
    assert len(out) <= MAX_LEN


def test_no_analysis_marker():
    out = format_job(job(desc="Подробности заказа"), None)
    assert "отклик не сгенерирован" in out
    assert "Подробности заказа" in out


def test_budget_none_shows_not_specified():
    assert "не указан" in format_job(job(budget=None), A)
    assert "5 000" in format_job(job(budget=5000), A)


def test_translation_only_for_foreign():
    assert "Перевод" not in format_job(job(lang="ru"), A)
    assert "Перевод" in format_job(job(lang="en", source="pph"), A)


def test_send_retries_once_on_429():
    calls = []

    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(429, json={"ok": False, "parameters": {"retry_after": 0}})
        return httpx.Response(200, json={"ok": True})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    assert send("hi", "TOKEN", "1", client) is True
    assert len(calls) == 2


def test_send_returns_false_on_error():
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(400, json={"ok": False})))
    assert send("hi", "TOKEN", "1", client) is False
