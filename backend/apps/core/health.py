"""Operational health endpoints."""
from __future__ import annotations

from django.db import connection
from django.http import JsonResponse
from django.views.decorators.http import require_GET


@require_GET
def live(request):
    """Process is up (liveness)."""
    return JsonResponse({"status": "ok"})


@require_GET
def ready(request):
    """Dependencies reachable (readiness)."""
    checks = {}
    try:
        with connection.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"error: {exc}"
        return JsonResponse({"status": "degraded", "checks": checks}, status=503)

    try:
        from django.core.cache import cache

        cache.set("healthcheck", "1", 5)
        checks["cache"] = "ok" if cache.get("healthcheck") == "1" else "miss"
    except Exception as exc:
        checks["cache"] = f"error: {exc}"

    return JsonResponse({"status": "ok", "checks": checks})
