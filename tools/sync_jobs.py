from db.connection import get_engine
from services.job_service import JobService
from services.syncer import WantedSyncer, RememberSyncer
from constants import DEFAULT_LIMIT_PAGES


def sync_jobs(
    source: str = "wanted",
    preset_name: str | None = None,
    job_group_id: int = 518,
    job_ids: list[int] | None = None,
    years: list[int] | None = None,
    locations: str = "all",
    limit_pages: int | None = DEFAULT_LIMIT_PAGES,
    job_category_names: list[dict] | None = None,
    min_experience: int = 0,
    max_experience: int = 10,
    job_sort: str = "job.popularity_order",
) -> str:
    """채용공고를 동기화한다.

    source: "wanted" (기본) 또는 "remember"
    Wanted: preset_name, job_group_id, job_ids, years, locations, limit_pages 사용
    Remember: job_category_names, min_experience, max_experience 사용
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
        job_sort = params.get("job_sort", job_sort)

    if source == "remember":
        return RememberSyncer(service).sync(
            job_category_names=job_category_names,
            min_experience=min_experience,
            max_experience=max_experience,
            limit_pages=limit_pages,
        )

    return WantedSyncer(service).sync(
        job_group_id=job_group_id,
        job_ids=job_ids,
        years=years,
        locations=locations,
        limit_pages=limit_pages,
        job_sort=job_sort,
    )
