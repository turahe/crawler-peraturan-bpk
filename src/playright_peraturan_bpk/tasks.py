from __future__ import annotations

from .celery_app import app


@app.task(bind=True, name="playright_peraturan_bpk.crawl_regulation", max_retries=3)
def crawl_regulation(self, regulation_id: int) -> bool:
    # Import lazily so Celery can load the task without initializing crawler modules.
    from .main import BPKCrawler

    if BPKCrawler().process_regulation(regulation_id):
        return True
    raise self.retry(countdown=min(300, 2 ** (self.request.retries + 1)))
