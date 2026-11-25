"""Track source failures and send one alert when a source stops working."""
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
        why = f"\nError: {escape(error[:300])}" if error else ""
        return (f"⚠️ Source <b>{escape(name)}</b> has failed for {threshold} consecutive runs."
                f"{why}\nOther sources are still working. The site may have changed its layout or blocked access.")
    return None
