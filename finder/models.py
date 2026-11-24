import re
from dataclasses import asdict, dataclass


@dataclass
class Job:
    id: str  # "<source>:<native id>"
    source: str
    url: str
    title: str
    description: str
    budget: float | None = None
    currency: str | None = None
    posted_at: str | None = None
    lang: str = "ru"
    direct: bool = False  # прямой заказчик (Telegram, HN) — возможна оплата криптой

    def __post_init__(self):
        # ссылки берутся с чужих сайтов: пропускаем только http(s), чтобы в панели не было javascript:-ссылок
        if not re.match(r"^https?://", self.url or "", re.I):
            self.url = ""

    def to_dict(self) -> dict:
        return asdict(self)
