"""Job history for the web dashboard, newest first in docs/data/jobs.json."""
from pathlib import Path

from finder.state import read_json, write_json


def append_history(path: Path, items: list[dict], max_items: int) -> None:
    old = read_json(path, [])
    ids = {i["id"] for i in items}
    merged = items + [o for o in old if o.get("id") not in ids]
    write_json(path, merged[:max_items])
