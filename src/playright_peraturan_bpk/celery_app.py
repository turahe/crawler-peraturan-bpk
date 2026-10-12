from __future__ import annotations

import os

from celery import Celery


app = Celery(
    "playright_peraturan_bpk",
    broker=os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/%2F"),
    include=["playright_peraturan_bpk.tasks"],
)
app.conf.update(
    task_default_queue=os.getenv("RABBITMQ_QUEUE", "regulation_crawl"),
    task_serializer="json",
    accept_content=["json"],
    result_backend=None,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_cancel_long_running_tasks_on_connection_loss=True,
    worker_prefetch_multiplier=1,
    task_publish_retry=True,
)
