from db.connection import get_engine
from services.wanted_client import WantedClient
from services.job_service import JobService


def sync_jobs(
    preset_name: str | None = None,
    job_group_id: int = 518,
    job_ids: list[int] | None = None,
    years: list[int] | None = None,
    locations: str = "all",
    limit_pages: int | None = None,
) -> str:
    engine = get_engine()
    service = JobService(engine)
    client = WantedClient()

    if preset_name:
        params = service.get_preset_params(preset_name)
        if params is None:
            return f"프리셋 '{preset_name}'을 찾을 수 없습니다."
        job_group_id = params.get("job_group_id", job_group_id)
        job_ids = params.get("job_ids", job_ids)
        years = params.get("years", years)
        locations = params.get("locations", locations)
        limit_pages = params.get("limit_pages", limit_pages)

    full_sync = limit_pages is None
    jobs = client.fetch_jobs(
        job_group_id=job_group_id,
        job_ids=job_ids,
        years=years,
        locations=locations,
        limit_pages=limit_pages,
    )
    # API 응답 job 객체에 job_group_id가 없는 경우 요청 파라미터 값으로 보완
    for job in jobs:
        if not job.get("job_group_id") and job_group_id:
            job["job_group_id"] = job_group_id
    return service.upsert_jobs(jobs, full_sync=full_sync)
