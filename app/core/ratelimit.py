"""In-memory sliding-window rate limiter.

SMS-bombing va brute-force himoyasi uchun OTP/telefon so'rovlarini chegaralaydi.
Yagona worker'li (uvicorn --workers 1) muhit uchun mo'ljallangan; prod'da Redis
(DB qatorlari yoki alohida shu turdagi xizmat) o'rnatilishi tavsiya etiladi.
"""

import threading
import time
from collections import defaultdict, deque

_lock = threading.Lock()
_events: dict[str, deque[float]] = defaultdict(deque)
_last: dict[str, float] = {}


class RateLimitExceeded(Exception):
    """So'rovlar chegarasi oshib ketdi yoki cooldown tugamagan."""

    def __init__(self, retry_after: float, message: str | None = None):
        self.retry_after = max(0.0, retry_after)
        super().__init__(
            message
            or f"Ko'p so'rov yuborildi — {int(self.retry_after)} soniq keyin qayta urinib ko'ring"
        )


def limit(
    key: str, max_calls: int, window_seconds: float, cooldown_seconds: float = 0.0
) -> None:
    """`key` uchun oxirgi `window_seconds` ichida `max_calls` so'rovdan oshmasin.

    `cooldown_seconds` > 0 bo'lsa, ketma-ket ikkita so'rov orasidagi minimal tanaffus.
    Chegara oshsa `RateLimitExceeded` ko'tariladi.
    """
    now = time.monotonic()
    with _lock:
        bucket = _events[key]
        while bucket and now - bucket[0] > window_seconds:
            bucket.popleft()

        if len(bucket) >= max_calls:
            oldest = bucket[0] if bucket else now
            raise RateLimitExceeded(window_seconds - (now - oldest))

        last = _last.get(key)
        if cooldown_seconds and last is not None and now - last < cooldown_seconds:
            raise RateLimitExceeded(cooldown_seconds - (now - last))

        bucket.append(now)
        _last[key] = now

        # Eski kalitlarni tozalaymiz — xotira o'sib ketmasligi uchun.
        if len(_events) > 50_000:
            cutoff = now - max(window_seconds, 3600)
            for stale_key in list(_events):
                if _events[stale_key] and now - _events[stale_key][-1] > cutoff:
                    del _events[stale_key]
                    _last.pop(stale_key, None)
