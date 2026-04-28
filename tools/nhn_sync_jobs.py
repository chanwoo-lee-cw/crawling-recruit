from constants import DEFAULT_LIMIT_PAGES
from db.connection import get_engine
from db.models import SearchPreset
from services.jobs.job_service import JobService
from services.nhn.nhn_constants import NHN, NHNClientConst
from services.nhn.nhn_syncer import NHNSyncer


def nhn_sync_jobs(
    job_group_id: str = NHNClientConst.TECH_GROUP_ID,
    job_series_ids: list[str] | None = None,
    limit_pages: int | None = DEFAULT_LIMIT_PAGES,
) -> str:
    """NHN 채용공고를 동기화한다."""
    engine = get_engine()
    service = JobService(engine)

    preset: SearchPreset | None = service.get_preset_params(NHN)
    if preset:
        p = preset.params
        job_group_id = p.get("job_group_id", job_group_id)
        job_series_ids = p.get("job_series_ids", job_series_ids)
        limit_pages = p.get("limit_pages", limit_pages)

    return NHNSyncer(service).sync(
        job_group_id=job_group_id,
        job_series_ids=job_series_ids,
        limit_pages=limit_pages,
    )
