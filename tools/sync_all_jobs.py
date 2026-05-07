import asyncio

from constants import DEFAULT_LIMIT_PAGES
from db.connection import get_engine
from db.models import SearchPreset
from services.jobs.job_service import JobService
from services.wanted.wanted_constants import WantedJobGroupId, WANTED
from services.wanted.wanted_syncer import WantedSyncer
from services.remember.remember_constants import REMEMBER
from services.remember.remember_syncer import RememberSyncer


async def sync_all_jobs(
    wanted_job_group_id: int = WantedJobGroupId.SERVER_DEVELOPER.value,
    wanted_job_ids: list[int] | None = None,
    wanted_years: list[int] | None = None,
    wanted_locations: str = "all",
    wanted_limit_pages: int | None = DEFAULT_LIMIT_PAGES,
    wanted_job_sort: str = "job.popularity_order",
    remember_limit_pages: int | None = DEFAULT_LIMIT_PAGES,
    remember_job_category_names: list[dict] | None = None,
    remember_min_experience: int = 0,
    remember_max_experience: int = 10,
) -> str:
    """모든 채용 사이트에서 채용공고를 병렬로 동기화한다."""
    engine = get_engine()
    wanted_service = JobService(engine)
    remember_service = JobService(engine)

    wanted_preset: SearchPreset | None = wanted_service.get_preset_params(WANTED)
    if wanted_preset:
        p = wanted_preset.params
        wanted_job_group_id = p.get("job_group_id", wanted_job_group_id)
        wanted_job_ids = p.get("job_ids", wanted_job_ids)
        wanted_years = p.get("years", wanted_years)
        wanted_locations = p.get("locations", wanted_locations)
        wanted_limit_pages = p.get("limit_pages", wanted_limit_pages)
        wanted_job_sort = p.get("job_sort", wanted_job_sort)

    remember_preset: SearchPreset | None = remember_service.get_preset_params(REMEMBER)
    if remember_preset:
        p = remember_preset.params
        remember_limit_pages = p.get("limit_pages", remember_limit_pages)
        remember_job_category_names = p.get("job_category_names", remember_job_category_names)
        remember_min_experience = p.get("min_experience", remember_min_experience)
        remember_max_experience = p.get("max_experience", remember_max_experience)

    wanted_result, remember_result = await asyncio.gather(
        WantedSyncer(wanted_service).sync(
            job_group_id=wanted_job_group_id,
            job_ids=wanted_job_ids,
            years=wanted_years,
            locations=wanted_locations,
            limit_pages=wanted_limit_pages,
            job_sort=wanted_job_sort,
        ),
        RememberSyncer(remember_service).sync(
            job_category_names=remember_job_category_names,
            min_experience=remember_min_experience,
            max_experience=remember_max_experience,
            limit_pages=remember_limit_pages,
        ),
        return_exceptions=True,
    )

    if isinstance(wanted_result, Exception):
        wanted_result = f"Wanted 오류: {wanted_result}"
    if isinstance(remember_result, Exception):
        remember_result = f"Remember 오류: {remember_result}"

    return f"[Wanted]\n{wanted_result}\n\n[Remember]\n{remember_result}"
