from abc import ABC, abstractmethod

from services.job_service import JobService
from services.wanted_client import WantedClient
from services.remember_client import RememberClient


class BaseSyncer(ABC):
    def __init__(self, service: JobService):
        self.service = service

    @abstractmethod
    def sync(self, **kwargs) -> str:
        ...


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
        return self.service.upsert_jobs(jobs, source="wanted", full_sync=full_sync)


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
        result = self.service.upsert_jobs(jobs, source="remember", full_sync=True)
        self.service.upsert_remember_details(jobs)
        return result
