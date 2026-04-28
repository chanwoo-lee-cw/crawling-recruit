import time

from constants import CRAWL_DELAY_SECONDS
from domain import JobDetail
from services.base_syncer import BaseSyncer
from services.wanted.wanted_client import WantedClient
from services.wanted.wanted_constants import WANTED


class WantedDetailSyncer(BaseSyncer):
    def sync(
        self,
        job_ids: list[int] | None = None,
        limit: int | None = None,
    ) -> str:
        client = WantedClient()
        target_ids = self.service.get_jobs_without_details(
            source=WANTED, job_ids=job_ids, limit=limit
        )
        if not target_ids:
            return "처리할 공고가 없습니다."

        fetched: list[JobDetail] = []
        for i, job_id in enumerate(target_ids):
            if i > 0:
                time.sleep(CRAWL_DELAY_SECONDS)
            detail = client.fetch_job_detail(job_id)
            if detail is None:
                continue
            fetched.append(detail)

        if not fetched:
            return "상세 정보를 가져온 공고가 없습니다."
        return self.service.upsert_job_details(fetched)
