"""Небольшие JSON-файлы состояния в папке state/ (коммитятся обратно в репозиторий)."""
import json
from pathlib import Path


def read_json(path: Path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def write_json(path: Path, data) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)


class SeenStore:
    """Какие заказы уже видели. Хранит последние max_items id в порядке добавления."""

    def __init__(self, path: Path, max_items: int = 20000):
        self.path = Path(path)
        self.max_items = max_items
        self._ids: dict[str, None] = {}

    def load(self) -> None:
        self._ids = dict.fromkeys(read_json(self.path, []))

    @property
    def is_empty(self) -> bool:
        return not self._ids

    def is_new(self, job_id: str) -> bool:
        return job_id not in self._ids

    def add(self, job_id: str) -> None:
        self._ids.pop(job_id, None)
        self._ids[job_id] = None

    def save(self) -> None:
        write_json(self.path, list(self._ids)[-self.max_items:])
