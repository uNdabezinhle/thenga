"""Simple Redis/memory rate limiting for sensitive auth endpoints."""
from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock

from django.core.cache import cache
from django.http import JsonResponse


# process-local fallback when cache is LocMem / unavailable
_buckets: dict[str, deque] = defaultdict(deque)
_lock = Lock()


def _client_ip(request) -> str:
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR") or "unknown"


def hit(key: str, limit: int, window_seconds: int) -> tuple[bool, int]:
    """Return (allowed, remaining)."""
    cache_key = f"rl:{key}"
    try:
        data = cache.get(cache_key)
        now = time.time()
        if data is None:
            data = []
        # drop expired
        data = [t for t in data if now - t < window_seconds]
        if len(data) >= limit:
            cache.set(cache_key, data, window_seconds)
            return False, 0
        data.append(now)
        cache.set(cache_key, data, window_seconds)
        return True, max(0, limit - len(data))
    except Exception:
        with _lock:
            now = time.time()
            q = _buckets[key]
            while q and now - q[0] >= window_seconds:
                q.popleft()
            if len(q) >= limit:
                return False, 0
            q.append(now)
            return True, max(0, limit - len(q))


class RateLimitMiddleware:
    """Coarse limits aligned with API Design Standards §11."""

    RULES = {
        "/api/v1/auth/token/": (10, 60),  # 10 / min
        "/api/v1/auth/users/": (5, 3600),  # 5 / hour
        "/api/v1/auth/password-reset/": (3, 3600),
        "/api/v1/auth/mfa/verify/": (5, 300),
    }

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path if request.path.endswith("/") else request.path + "/"
        rule = self.RULES.get(path)
        if rule and request.method == "POST":
            limit, window = rule
            ip = _client_ip(request)
            allowed, remaining = hit(f"{path}:{ip}", limit, window)
            if not allowed:
                return JsonResponse(
                    {
                        "error": {
                            "code": "rate_limited",
                            "message": "Too many requests. Try again later.",
                            "request_id": getattr(request, "request_id", "-"),
                        }
                    },
                    status=429,
                    headers={"Retry-After": str(window)},
                )
            response = self.get_response(request)
            response["RateLimit-Limit"] = str(limit)
            response["RateLimit-Remaining"] = str(remaining)
            return response
        return self.get_response(request)
