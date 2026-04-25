from constants import DEFAULT_LIMIT_PAGES
from db.connection import get_engine
from db.models import SearchPreset
from services.jobs.job_service import JobService
from services.wanted.wanted_constants import WantedJobGroupId, WANTED
from services.wanted.wanted_syncer import WantedSyncer


def wanted_sync_jobs(
        job_group_id: int = WantedJobGroupId.SERVER_DEVELOPER.value,
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

    preset: SearchPreset | None = service.get_preset_params(WANTED)
    if preset:
        p = preset.params
        job_group_id = p.get("job_group_id", job_group_id)
        job_ids = p.get("job_ids", job_ids)
        years = p.get("years", years)
        locations = p.get("locations", locations)
        limit_pages = p.get("limit_pages", limit_pages)
        job_sort = p.get("job_sort", job_sort)

    return WantedSyncer(service).sync(
        job_group_id=job_group_id,
        job_ids=job_ids,
        years=years,
        locations=locations,
        limit_pages=limit_pages,
        job_sort=job_sort,
    )
