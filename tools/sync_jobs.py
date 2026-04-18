from db.connection import get_engine
from services.wanted_client import WantedClient
from services.remember_client import RememberClient
from services.job_service import JobService


def sync_jobs(
    source: str = "wanted",
    preset_name: str | None = None,
    job_group_id: int = 518,
    job_ids: list[int] | None = None,
    years: list[int] | None = None,
    locations: str = "all",
    limit_pages: int | None = None,
    job_category_names: list[dict] | None = None,
    min_experience: int = 0,
    max_experience: int = 10,
) -> str:
    """채용공고를 동기화한다.

    source: "wanted" (기본) 또는 "remember"
    Wanted: preset_name, job_group_id, job_ids, years, locations, limit_pages 사용
    Remeber: job_category_names, min_experience, max_experience 사용
    """
    engine = get_engine()
    service = JobService(engine)

    if preset_name:
        params = service.get_preset_params(preset_name)
        if params is None:
            return f"프리셋 '{preset_name}'을 찾을 수 없습니다."
        source = params.get("source", source)
        job_group_id = params.get("job_group_id", job_group_id)
        job_ids = params.get("job_ids", job_ids)
        years = params.get("years", years)
        locations = params.get("locations", locations)
        limit_pages = params.get("limit_pages", limit_pages)
        job_category_names = params.get("job_category_names", job_category_names)
        min_experience = params.get("min_experience", min_experience)
        max_experience = params.get("max_experience", max_experience)

    if source == "remember":
        if not job_category_names:
            return "Remeber 동기화에는 job_category_names가 필요합니다."
        client = RememberClient()
        jobs = client.fetch_jobs(
            job_category_names=job_category_names,
            min_experience=min_experience,
            max_experience=max_experience,
        )
        return service.upsert_jobs(jobs, source="remember", full_sync=True)

    client = WantedClient()
    full_sync = limit_pages is None
    jobs = client.fetch_jobs(
        job_group_id=job_group_id,
        job_ids=job_ids,
        years=years,
        locations=locations,
        limit_pages=limit_pages,
    )
    for job in jobs:
        if not job.get("job_group_id") and job_group_id:
            job["job_group_id"] = job_group_id
    return service.upsert_jobs(jobs, source="wanted", full_sync=full_sync)
