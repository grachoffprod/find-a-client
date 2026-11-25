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
    budget_min: float | None = None
    currency: str | None = None
    posted_at: str | None = None
    lang: str = "ru"
    project_type: str | None = None  # "fixed" | "hourly" (Freelancer.com)
    direct: bool = False  # Direct client (Telegram, HN); crypto payment may be possible.

    def __post_init__(self):
        # URLs come from external sites; allow only HTTP(S) to prevent javascript: links in the dashboard.
        if not re.match(r"^https?://", self.url or "", re.I):
            self.url = ""

    def to_dict(self) -> dict:
        return asdict(self)
