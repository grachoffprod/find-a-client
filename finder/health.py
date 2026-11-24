"""Счётчик сбоев источников: одно предупреждение, когда площадка перестала читаться."""
from html import escape

from finder.telegram_bot import SOURCE_NAMES


def update_health(health: dict, source: str, ok: bool, threshold: int, error: str = "") -> str | None:
    rec = health.setdefault(source, {"fails": 0})
    if ok:
        rec["fails"] = 0
        return None
    rec["fails"] += 1
    if rec["fails"] == threshold:
        name = SOURCE_NAMES.get(source, source)
        why = f"\nОшибка: {escape(error[:300])}" if error else ""
        return (f"⚠️ Площадка <b>{escape(name)}</b> не читается {threshold} запуска подряд."
                f"{why}\nОстальные площадки работают. Возможно, сайт поменял вёрстку или закрыл доступ.")
    return None
