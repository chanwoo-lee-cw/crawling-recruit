from constants import DEFAULT_LIMIT_PAGES
from db.connection import get_engine
from db.models import SearchPreset
from services.jobs.job_service import JobService
from services.remember.remember_constants import REMEMBER
from services.remember.remember_syncer import RememberSyncer


def remember_sync_jobs(
        limit_pages: int | None = DEFAULT_LIMIT_PAGES,
        job_category_names: list[dict] | None = None,
        min_experience: int = 0,
        max_experience: int = 10,
) -> str:
    """
    채용공고를 동기화한다.
    """
    engine = get_engine()
    service = JobService(engine)

    preset: SearchPreset | None = service.get_preset_params(REMEMBER)
    if preset:
        p = preset.params
        limit_pages = p.get("limit_pages", limit_pages)
        job_category_names = p.get("job_category_names", job_category_names)
        min_experience = p.get("min_experience", min_experience)
        max_experience = p.get("max_experience", max_experience)

    return RememberSyncer(service).sync(
        job_category_names=job_category_names,
        min_experience=min_experience,
        max_experience=max_experience,
        limit_pages=limit_pages,
    )
