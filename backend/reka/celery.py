"""Celery application — ADR-0003 one image, many roles."""
from __future__ import annotations

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "reka.settings")

app = Celery("reka")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
