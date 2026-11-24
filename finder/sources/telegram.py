"""Публичные Telegram-каналы с заказами — через веб-превью t.me/s/<канал>."""
import re

import httpx
from selectolax.lexbor import LexborHTMLParser

from finder.models import Job

URL = "https://t.me/s/{channel}"
_ZW = re.compile("[​‌‍⁠﻿]")


def _title(text: str) -> str:
    """Первая содержательная строка: не хештеги и не пустяк."""
    for line in text.split("\n"):
        s = line.strip()
        if not s.startswith("#") and len(re.sub(r"\W", "", s)) >= 3:
            return s
    return text.split("\n", 1)[0].strip()


def parse(raw: str, channel: str = "") -> list[Job]:
    jobs = []
    for msg in LexborHTMLParser(raw).css(".tgme_widget_message"):
        post = msg.attributes.get("data-post")  # "channel/123"
        node = msg.css_first(".tgme_widget_message_text")
        if not post or node is None:
            continue
        text = _ZW.sub("", node.text(separator="\n"))
        text = re.sub(r"\n\s*\n+", "\n", text).strip()
        if not text:
            continue
        tm = msg.css_first("time")
        first_line = _title(text)
        jobs.append(Job(
            id=f"telegram:{post}",
            source="telegram",
            url=f"https://t.me/{post}",
            title=first_line[:200],
            description=text,
            posted_at=tm.attributes.get("datetime") if tm else None,
            direct=True,
        ))
    return jobs


def fetch(client: httpx.Client, channels: list[str]) -> list[Job]:
    jobs = []
    for ch in channels:
        r = client.get(URL.format(channel=ch))
        r.raise_for_status()
        jobs.extend(parse(r.text, ch))
    return jobs
