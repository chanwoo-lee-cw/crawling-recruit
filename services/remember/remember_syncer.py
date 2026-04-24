from services.remember.remember_client import RememberClient
from services.remember.remember_constants import REMEMBER
from services.base_syncer import BaseSyncer


class RememberSyncer(BaseSyncer):
    def sync(
        self,
        job_category_names: list[dict] | None = None,
        min_experience: int = 0,
        max_experience: int = 10,
        limit_pages: int | None = None,
    ) -> str:
        if not job_category_names:
            return "Remember 동기화에는 job_category_names가 필요합니다."
        client = RememberClient()
        jobs = client.fetch_jobs(
            job_category_names=job_category_names,
            min_experience=min_experience,
            max_experience=max_experience,
            limit_pages=limit_pages,
        )
        result = self.service.upsert_jobs(jobs, source=REMEMBER, full_sync=True)
        self.service.upsert_remember_details(jobs)
        return result
