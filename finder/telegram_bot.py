"""Сообщения в Telegram (parse_mode=HTML)."""
import time
from html import escape

import httpx

from finder.ai import Analysis
from finder.models import Job

MAX_LEN = 4096

SOURCE_NAMES = {
    "flru": "FL.ru", "kwork": "Kwork", "freelancer": "Freelancer.com", "hn": "Hacker News",
    "telegram": "Telegram", "freelance_ru": "Freelance.ru", "pph": "PeoplePerHour", "guru": "Guru",
}
TOPIC_NAMES = {
    "landing": "Лендинг", "shop": "Интернет-магазин", "tg_bot": "Telegram-бот", "mini_app": "Mini App",
    "crm": "CRM", "booking": "Онлайн-запись", "automation": "Автоматизация", "api_integration": "Интеграция API",
    "saas": "SaaS / веб-сервис", "calculator": "Калькулятор", "site_template": "Шаблон / вёрстка",
    "extension": "Расширение", "mvp": "MVP", "fixes": "Доработка",
}


def _cut(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: max(0, limit - 1)] + "…"


def _money(job: Job) -> str:
    if not job.budget:
        return "не указан"
    return f"{job.budget:,.0f}".replace(",", " ") + (f" {job.currency}" if job.currency else "")


def format_job(job: Job, a: Analysis | None) -> str:
    """Сообщение о заказе. Весь текст заказа и ИИ экранирован; итог ≤ 4096 символов."""
    topic = TOPIC_NAMES.get(a.topic, a.topic) if a and a.topic else "—"
    head = [
        f"<b>{escape(_cut(job.title, 300))}</b>",
        f"🏷 {escape(topic)} · {escape(SOURCE_NAMES.get(job.source, job.source))}"
        + (" · прямой заказчик" if job.direct else ""),
        f"💰 Бюджет: {escape(_money(job))}" + (f" · ⭐ {a.score}/10" if a else ""),
    ]
    tail = f'\n\n🔗 <a href="{escape(job.url, quote=True)}">Открыть заказ</a>'

    blocks: list[tuple[str, str, str]] = []  # (prefix, text, suffix) — text обрезается при нехватке места
    if a is None:
        head.append("⚠️ отклик не сгенерирован")
        blocks.append(("\n\n", job.description, ""))
    else:
        if a.summary_ru:
            blocks.append(("\n\n📝 ", a.summary_ru, ""))
        if a.reply:
            blocks.append(("\n\n<b>Отклик:</b>\n<blockquote expandable>", a.reply, "</blockquote>"))
        if job.lang != "ru" and a.reply_ru and a.reply_ru != a.reply:
            blocks.append(("\n\n<b>Перевод:</b>\n<blockquote expandable>", a.reply_ru, "</blockquote>"))
        if a.questions:
            blocks.append(("\n\n❓ ", "\n❓ ".join(a.questions), ""))

    fixed = "\n".join(head) + tail + sum(len(p) + len(s) for p, _, s in blocks) * " "
    budget = MAX_LEN - len(fixed)
    # делим оставшееся место поровну, остаток отдаём тем, кому не хватило
    sizes = [len(escape(t)) for _, t, _ in blocks]
    share = [0] * len(blocks)
    left = budget
    pending = sorted(range(len(blocks)), key=lambda i: sizes[i])
    while pending:
        each = left // len(pending)
        i = pending.pop(0)
        share[i] = min(sizes[i], each)
        left -= share[i]

    body = ""
    for (prefix, text, suffix), room in zip(blocks, share):
        esc = escape(text)
        if len(esc) > room:
            # режем исходный текст, чтобы не разорвать HTML-сущность
            t = text
            while len(escape(t)) > room - 1 and t:
                t = t[: int(len(t) * 0.9)]
            esc = escape(t) + "…"
        body += prefix + esc + suffix
    return ("\n".join(head) + body + tail)[:MAX_LEN]


def send(text: str, token: str, chat_id: str, client: httpx.Client) -> bool:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    for attempt in range(2):
        try:
            r = client.post(url, json=payload, timeout=20)
        except httpx.HTTPError:
            return False
        if r.status_code == 429 and attempt == 0:
            retry = (r.json().get("parameters") or {}).get("retry_after", 1)
            time.sleep(min(float(retry), 30))
            continue
        return r.status_code == 200 and r.json().get("ok", False)
    return False
