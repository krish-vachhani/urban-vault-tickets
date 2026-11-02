# Load the Celery app whenever Django starts so that tasks published from
# Django code (for example in transaction.on_commit callbacks) use it.
from config.celery import celery_app

__all__ = ("celery_app",)
