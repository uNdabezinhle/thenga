"""Serve the Northbound web client from Django in local/dev."""
from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404, HttpResponse
from django.views.decorators.http import require_GET

# repo_root/frontend — backend/ is parent of reka/
FRONTEND_DIR = Path(settings.BASE_DIR).parent / "frontend"


@require_GET
def welcome_page(request):
    page = FRONTEND_DIR / "site" / "index.html"
    if not page.exists():
        raise Http404("Reka site is not built.")
    return HttpResponse(page.read_text(encoding="utf-8"), content_type="text/html; charset=utf-8")


@require_GET
def spa_index(request):
    index = FRONTEND_DIR / "index.html"
    if not index.exists():
        raise Http404("Frontend not built. See README.")
    html = index.read_text(encoding="utf-8")
    # Point the client at same-origin API when served by Django
    html = html.replace(
        "window.REKA_API_BASE || 'http://127.0.0.1:8000'",
        "window.REKA_API_BASE ?? ''",
    ).replace(
        "window.REKA_API_BASE ?? 'http://127.0.0.1:8000'",
        "window.REKA_API_BASE ?? ''",
    )
    return HttpResponse(html, content_type="text/html; charset=utf-8")


@require_GET
def spa_asset(request, path):
    # only allow files that live under frontend/
    target = (FRONTEND_DIR / path).resolve()
    if not str(target).startswith(str(FRONTEND_DIR.resolve())):
        raise Http404()
    if not target.is_file():
        raise Http404()
    content_type = "application/javascript" if path.endswith(".js") else None
    return FileResponse(target.open("rb"), content_type=content_type)
