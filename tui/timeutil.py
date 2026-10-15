"""Время МСК и обратный отсчёт до дропа (с NTP-поправкой из run_fast)."""
from datetime import datetime, timedelta

from run_fast import MSK, seconds_until_msk


def now_msk(offset: float = 0.0) -> datetime:
    return datetime.now(MSK) + timedelta(seconds=offset)


def countdown_parts(h: int, m: int, s: int, offset: float = 0.0):
    """('HH:MM:SS', секунд) до ближайшего h:m:s по МСК."""
    left = int(seconds_until_msk(h, m, s, offset))
    return f"{left // 3600:02d}:{left % 3600 // 60:02d}:{left % 60:02d}", left
