import time
from db.connection import get_engine
from services.wanted_client import WantedClient
from services.job_service import JobService
from constants import CRAWL_DELAY_SECONDS


def sync_job_details(
    job_ids: list[int] | None = None,
    limit: int | None = None,
) -> str:
    engine = get_engine()
    service = JobService(engine)
    client = WantedClient()

    target_ids = service.get_jobs_without_details(job_ids=job_ids, limit=limit)
    if not target_ids:
        return "처리할 공고가 없습니다."

    fetched = []
    for i, job_id in enumerate(target_ids):
        if i > 0:
            time.sleep(CRAWL_DELAY_SECONDS)
        detail = client.fetch_job_detail(job_id)
        if detail is None:
            continue
        fetched.append(detail)

    if not fetched:
        return "상세 정보를 가져온 공고가 없습니다."
    return service.upsert_job_details(fetched)
