from db.connection import get_engine
from services.jobs.job_service import JobService
from services.sk.sk_syncer import SKSyncer


async def sk_sync_jobs() -> str:
    """SK 채용공고를 동기화한다."""
    return await SKSyncer(JobService(get_engine())).sync()
