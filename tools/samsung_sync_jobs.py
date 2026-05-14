from db.connection import get_engine
from services.jobs.job_service import JobService
from services.samsung.samsung_syncer import SamsungSyncer


async def samsung_sync_jobs() -> str:
    """삼성 채용공고를 동기화한다."""
    return await SamsungSyncer(JobService(get_engine())).sync()
