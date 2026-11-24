from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config"


def _load(name: str) -> dict:
    with open(CONFIG / name, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_settings() -> dict:
    return _load("settings.yaml")


def load_topics() -> dict:
    data = _load("topics.yaml")
    data["topics"] = {k: [w.lower() for w in v] for k, v in data["topics"].items()}
    data["stop"] = [w.lower() for w in data.get("stop", [])]
    return data


def load_profile() -> dict:
    return _load("profile.yaml")
