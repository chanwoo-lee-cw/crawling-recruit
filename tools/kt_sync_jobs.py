from db.connection import get_engine
from services.jobs.job_service import JobService
from services.kt.kt_syncer import KTSyncer


async def kt_sync_jobs() -> str:
    """KT 채용공고를 동기화한다."""
    return await KTSyncer(JobService(get_engine())).sync()
