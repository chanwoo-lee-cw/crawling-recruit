from db.connection import get_engine
from services.cj.cj_syncer import CJSyncer
from services.jobs.job_service import JobService


async def cj_sync_jobs() -> str:
    """CJ 채용공고를 동기화한다."""
    return await CJSyncer(JobService(get_engine())).sync()
