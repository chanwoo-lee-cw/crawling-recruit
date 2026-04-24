from services.base_syncer import BaseSyncer
from services.wanted.wanted_client import WantedClient
from services.wanted.wanted_constants import WANTED


class WantedSyncer(BaseSyncer):
    def sync(
        self,
        job_group_id: int = 518,
        job_ids: list[int] | None = None,
        years: list[int] | None = None,
        locations: str = "all",
        limit_pages: int | None = None,
        job_sort: str = "job.popularity_order",
    ) -> str:
        client = WantedClient()
        full_sync = limit_pages is None
        jobs = client.fetch_jobs(
            job_group_id=job_group_id,
            job_ids=job_ids,
            years=years,
            locations=locations,
            limit_pages=limit_pages,
            job_sort=job_sort,
        )
        for job in jobs:
            if not job.get("job_group_id") and job_group_id:
                job["job_group_id"] = job_group_id
        return self.service.upsert_jobs(jobs, source=WANTED, full_sync=full_sync)