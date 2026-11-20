"""The Celery worker. In Docker:   celery -A app.worker.celery_app worker --loglevel=INFO --concurrency=1
Celery is only switched on when CELERY_BROKER_URL is set (for example redis://redis:6379/0), so the API also runs on a laptop with no Redis."""
import os

try:
    from celery import Celery
except ImportError:                                  # Celery not installed: the API falls back to a thread
    Celery = None

celery_app = None
if Celery is not None and os.environ.get("CELERY_BROKER_URL"):
    celery_app = Celery("ledgerforge", broker=os.environ["CELERY_BROKER_URL"], backend=os.environ.get("CELERY_RESULT_BACKEND") or None)
    celery_app.conf.update(task_serializer="json", accept_content=["json"], worker_prefetch_multiplier=1,
                           task_acks_late=True, broker_connection_retry_on_startup=True)

    @celery_app.task(name="ledgerforge.run_job")
    def run_job_task(job_id):
        from app.deps import db_path
        from app.jobs import execute_job
        return execute_job(db_path(), job_id)["status"]
else:
    run_job_task = None
