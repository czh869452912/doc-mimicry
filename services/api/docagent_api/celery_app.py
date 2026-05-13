from __future__ import annotations

import os

from celery import Celery

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery("docagent", broker=REDIS_URL)

celery_app.conf.update(
    # Use Redis as broker only; track session status via Postgres, not Celery results
    task_ignore_result=True,
    # Acknowledge task only after it completes (not on receipt)
    task_acks_late=True,
    # Requeue task if worker process dies mid-execution
    task_reject_on_worker_lost=True,
    # Tasks requeued if worker is silent longer than this (must exceed max session runtime)
    broker_transport_options={"visibility_timeout": 3600},
    # OpenHands SDK dependencies expect sys.stdout/sys.stderr to behave like
    # real text streams (including .encoding). Celery's LoggingProxy omits that.
    worker_redirect_stdouts=False,
    # Import worker_tasks to register tasks
    imports=["docagent_api.worker_tasks"],
)
