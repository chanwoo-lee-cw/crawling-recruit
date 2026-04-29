from db.connection import get_engine
from services.jobs.job_service import JobService
from services.nhn.nhn_constants import NHN
from services.nhn.nhn_detail_syncer import NHNDetailSyncer
from services.remember.remember_constants import REMEMBER
from services.remember.remember_detail_syncer import RememberDetailSyncer
from services.wanted.wanted_constants import WANTED
from services.wanted.wanted_detail_syncer import WantedDetailSyncer


def sync_job_details(
    source: str = WANTED,
    job_ids: list[int] | None = None,
    limit: int | None = None,
) -> str:
    """공고 상세정보를 동기화한다. source: WANTED (기본), NHN. REMEMBER는 미지원."""
    service = JobService(get_engine())
    if source == REMEMBER:
        return RememberDetailSyncer(service).sync()
    if source == NHN:
        return NHNDetailSyncer(service).sync(job_ids=job_ids, limit=limit)
    return WantedDetailSyncer(service).sync(job_ids=job_ids, limit=limit)


if __name__ == "__main__":
    sync_job_details(NHN)