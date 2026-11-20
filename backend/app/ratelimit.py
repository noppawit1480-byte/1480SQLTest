"""In-process token-bucket rate limiter.

Good for a single backend instance. For horizontal scaling swap `_buckets` for Redis
(same interface) — documented in docs/02-architecture.md.
"""
from __future__ import annotations

import hmac
import threading
import time

from fastapi import HTTPException, Request, status

_buckets: dict[str, tuple[float, float]] = {}
_lock = threading.Lock()


def client_ip(request: Request) -> str:
    """The learner's IP. Behind the trusted Next.js proxy (shared secret verified) use the IP it forwards;
    never trust forwarded headers otherwise, since any client could set them."""
    from app.config import get_settings
    secret = get_settings().trusted_proxy_secret
    if secret and hmac.compare_digest(request.headers.get("x-sqlab-proxy-secret", ""), secret):
        fwd = request.headers.get("x-sqlab-client-ip", "").strip()
        if fwd and len(fwd) <= 64:
            return fwd
    return request.client.host if request.client else "unknown"


def _client_key(request: Request) -> str:
    uid = getattr(request.state, "user_id", None)
    if uid:
        return f"u:{uid}"
    return f"ip:{client_ip(request)}"


def check_rate(request: Request, bucket: str, per_minute: int) -> None:
    key = f"{bucket}:{_client_key(request)}"
    now = time.monotonic()
    rate = per_minute / 60.0
    with _lock:
        tokens, last = _buckets.get(key, (float(per_minute), now))
        tokens = min(float(per_minute), tokens + (now - last) * rate)
        if tokens < 1:
            retry = int((1 - tokens) / rate) + 1
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                                f"ส่งคำขอถี่เกินไป กรุณารอ {retry} วินาที", headers={"Retry-After": str(retry)})
        _buckets[key] = (tokens - 1, now)
        if len(_buckets) > 50_000:  # crude memory guard
            _buckets.clear()


def reset_all() -> None:
    with _lock:
        _buckets.clear()
