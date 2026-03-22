"""App-wide config: paths, constants, api_config.json I/O."""

import json
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
CONFIG_PATH = BASE_DIR / "api_config.json"
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "youtube_stats.db"
QUOTA_PATH = DATA_DIR / "quota.json"

QUOTA_DAILY_LIMIT = 10_000
QUOTA_WARNING_THRESHOLD = 8_000
CACHE_HOURS = 6


def load_config() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_config(data: dict) -> None:
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def get_api_key() -> str | None:
    return load_config().get("api_key")
