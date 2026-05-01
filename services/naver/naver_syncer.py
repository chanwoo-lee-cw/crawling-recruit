from services.base_syncer import BaseSyncer
from services.naver.naver_client import NaverClient
from services.naver.naver_constants import NAVER


class NaverSyncer(BaseSyncer):
    def sync(self, limit_pages: int | None = None) -> str:
        jobs = NaverClient().fetch_jobs(limit_pages=limit_pages)
        full_sync = limit_pages is None
        return self.service.upsert_jobs(jobs, source=NAVER, full_sync=full_sync)
