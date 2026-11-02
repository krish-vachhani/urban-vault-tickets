"""Celery application used by the worker, the Beat scheduler, and Django."""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

celery_app = Celery("urban_vault")

# Read every Django setting that starts with "CELERY_" (e.g. CELERY_BROKER_URL).
celery_app.config_from_object("django.conf:settings", namespace="CELERY")

# Find tasks.py modules inside the installed Django apps.
celery_app.autodiscover_tasks()
