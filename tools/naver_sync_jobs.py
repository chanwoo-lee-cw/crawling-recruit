from constants import DEFAULT_LIMIT_PAGES
from db.connection import get_engine
from db.models import SearchPreset
from services.jobs.job_service import JobService
from services.naver.naver_constants import NAVER
from services.naver.naver_syncer import NaverSyncer


def naver_sync_jobs(
    limit_pages: int | None = DEFAULT_LIMIT_PAGES,
) -> str:
    """네이버 채용공고를 동기화한다."""
    engine = get_engine()
    service = JobService(engine)

    preset: SearchPreset | None = service.get_preset_params(NAVER)
    if preset:
        p = preset.params
        limit_pages = p.get("limit_pages", limit_pages)

    return NaverSyncer(service).sync(limit_pages=limit_pages)
