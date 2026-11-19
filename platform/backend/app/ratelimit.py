"""A simple per-address limit on public endpoints, on top of the per-account login lockout.

Counts live in this process, which is fine while the app runs as one instance.
"""

import time
from collections import defaultdict, deque

from fastapi import Depends, HTTPException, Request, status

from app.config import get_settings

WINDOW_SECONDS = 60
_hits: dict[str, deque[float]] = defaultdict(deque)


def reset() -> None:
    _hits.clear()


def _check(request: Request) -> None:
    address = request.client.host if request.client else "unknown"
    now = time.monotonic()
    hits = _hits[address]
    while hits and hits[0] <= now - WINDOW_SECONDS:
        hits.popleft()
    if len(hits) >= get_settings().login_attempts_per_minute:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many attempts. Please wait a minute and try again.",
            headers={"Retry-After": str(WINDOW_SECONDS)},
        )
    hits.append(now)
    # Addresses that have gone quiet shouldn't stay in memory forever
    if len(_hits) > 10_000:
        for key in [key for key, value in _hits.items() if not value or value[-1] <= now - WINDOW_SECONDS]:
            del _hits[key]


PublicLimit = Depends(_check)
