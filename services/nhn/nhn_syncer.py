from services.base_syncer import BaseSyncer
from services.nhn.nhn_client import NHNClient
from services.nhn.nhn_constants import NHN, NHNClientConst


class NHNSyncer(BaseSyncer):
    def sync(
        self,
        job_group_id: str = NHNClientConst.TECH_GROUP_ID,
        job_series_ids: list[str] | None = None,
        limit_pages: int | None = None,
    ) -> str:
        try:
            client = NHNClient()
        except ValueError as e:
            return str(e)
        jobs = client.fetch_jobs(
            job_group_id=job_group_id,
            job_series_ids=job_series_ids,
            limit_pages=limit_pages,
        )
        full_sync = limit_pages is None
        return self.service.upsert_jobs(jobs, source=NHN, full_sync=full_sync)
