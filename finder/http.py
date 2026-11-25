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
    """Convert HTML to plain text, preserving breaks and decoding entities."""
    if not raw:
        return ""
    s = re.sub(r"(?i)<br\s*/?>|</p>|<p[^>]*>", "\n", raw)
    s = html.unescape(_TAG.sub("", s))
    s = _WS.sub(" ", s)
    s = re.sub(r"\n\s*\n+", "\n\n", s)
    return s.strip()


def parse_money(text: str | None) -> float | None:
    """Return the first amount in a string such as '3 000 USD' or '$250', or None."""
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
