import html
import re

import httpx

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
)


def make_client() -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": UA, "Accept-Language": "ru,en;q=0.8"},
        timeout=20,
        follow_redirects=True,
    )


_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"[ \t\r\f\v]+")


def clean_text(raw: str | None) -> str:
    """HTML → обычный текст: <br>/<p> в переносы, сущности раскрыты, лишние пробелы убраны."""
    if not raw:
        return ""
    s = re.sub(r"(?i)<br\s*/?>|</p>|<p[^>]*>", "\n", raw)
    s = html.unescape(_TAG.sub("", s))
    s = _WS.sub(" ", s)
    s = re.sub(r"\n\s*\n+", "\n\n", s)
    return s.strip()


def parse_money(text: str | None) -> float | None:
    """Первое число из строки вида '3 000 ₽', 'до 15000 руб', '$250'. Нет числа → None."""
    if not text:
        return None
    m = re.search(r"\d[\d\s .,]*", text)
    if not m:
        return None
    digits = re.sub(r"[\s ]", "", m.group()).replace(",", ".")
    if digits.count(".") > 1 or re.fullmatch(r"\d{1,3}(\.\d{3})+", digits):
        digits = digits.replace(".", "")
    try:
        value = float(digits.rstrip("."))
    except ValueError:
        return None
    return value or None
