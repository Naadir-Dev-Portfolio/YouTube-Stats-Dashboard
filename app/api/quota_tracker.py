"""Daily YouTube Data API quota tracker (10,000 units/day limit)."""

import json
from datetime import date
from app.config import QUOTA_PATH, QUOTA_DAILY_LIMIT, QUOTA_WARNING_THRESHOLD


class QuotaTracker:
    def __init__(self):
        QUOTA_PATH.parent.mkdir(parents=True, exist_ok=True)
        self._data = self._load()

    def _load(self) -> dict:
        today = str(date.today())
        if QUOTA_PATH.exists():
            try:
                with open(QUOTA_PATH, encoding="utf-8") as f:
                    data = json.load(f)
                if data.get("date") == today:
                    return data
            except (json.JSONDecodeError, KeyError):
                pass
        return {"date": today, "used": 0}

    def _save(self) -> None:
        with open(QUOTA_PATH, "w", encoding="utf-8") as f:
            json.dump(self._data, f)

    def add(self, units: int) -> None:
        today = str(date.today())
        if self._data.get("date") != today:
            self._data = {"date": today, "used": 0}
        self._data["used"] += units
        self._save()

    def used(self) -> int:
        return self._data.get("used", 0)

    def remaining(self) -> int:
        return max(0, QUOTA_DAILY_LIMIT - self.used())

    def is_near_limit(self) -> bool:
        return self.used() >= QUOTA_WARNING_THRESHOLD

    def reset(self) -> None:
        self._data = {"date": str(date.today()), "used": 0}
        self._save()
