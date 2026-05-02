from db.connection import get_engine
from services.jobs.job_service import JobService
from services.woowahan.woowahan_constants import WOOWAHAN_DEFAULT_JOB_GROUP
from services.woowahan.woowahan_syncer import WoowahanSyncer


def woowahan_sync_jobs(
    job_group_codes: str = WOOWAHAN_DEFAULT_JOB_GROUP,
) -> str:
    """우아한형제들 채용공고를 동기화한다."""
    return WoowahanSyncer(JobService(get_engine())).sync(job_group_codes=job_group_codes)
