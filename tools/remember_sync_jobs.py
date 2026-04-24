from constants import DEFAULT_LIMIT_PAGES
from db.connection import get_engine
from services.jobs.job_service import JobService
from services.remember.remember_syncer import RememberSyncer


def sync_jobs(
        preset_name: str | None = None,
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

    params = service.get_preset_params(preset_name)
    if params is None:
        return f"프리셋 '{preset_name}'을 찾을 수 없습니다."
    limit_pages = params.get("limit_pages", limit_pages)
    job_category_names = params.get("job_category_names", job_category_names)
    min_experience = params.get("min_experience", min_experience)
    max_experience = params.get("max_experience", max_experience)

    return RememberSyncer(service).sync(
        job_category_names=job_category_names,
        min_experience=min_experience,
        max_experience=max_experience,
        limit_pages=limit_pages,
    )
