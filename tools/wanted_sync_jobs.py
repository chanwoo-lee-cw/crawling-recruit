from constants import DEFAULT_LIMIT_PAGES
from db.connection import get_engine
from services.jobs.job_service import JobService
from services.wanted.wanted_syncer import WantedSyncer


def wanted_sync_jobs(
        preset_name: str | None = None,
        job_group_id: int = 518,
        job_ids: list[int] | None = None,
        years: list[int] | None = None,
        locations: str = "all",
        limit_pages: int | None = DEFAULT_LIMIT_PAGES,
        job_sort: str = "job.popularity_order",
) -> str:
    """
    채용공고를 동기화한다.
    """
    engine = get_engine()
    service = JobService(engine)

    params = service.get_preset_params(preset_name)
    if params is None:
        return f"프리셋 '{preset_name}'을 찾을 수 없습니다."
    job_group_id = params.get("job_group_id", job_group_id)
    job_ids = params.get("job_ids", job_ids)
    years = params.get("years", years)
    locations = params.get("locations", locations)
    limit_pages = params.get("limit_pages", limit_pages)
    job_sort = params.get("job_sort", job_sort)

    return WantedSyncer(service).sync(
        job_group_id=job_group_id,
        job_ids=job_ids,
        years=years,
        locations=locations,
        limit_pages=limit_pages,
        job_sort=job_sort,
    )
