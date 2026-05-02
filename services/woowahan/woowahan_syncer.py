from services.base_syncer import BaseSyncer
from services.woowahan.woowahan_client import WoowahanClient
from services.woowahan.woowahan_constants import WOOWAHAN, WOOWAHAN_DEFAULT_JOB_GROUP


class WoowahanSyncer(BaseSyncer):
    def sync(
        self,
        job_group_codes: str = WOOWAHAN_DEFAULT_JOB_GROUP,
        limit_pages: int | None = None,
    ) -> str:
        client = WoowahanClient()
        jobs = client.fetch_jobs(job_group_codes=job_group_codes, limit_pages=limit_pages)
        return self.service.upsert_jobs(jobs, source=WOOWAHAN, full_sync=True)
