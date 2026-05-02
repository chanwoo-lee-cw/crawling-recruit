from db.connection import get_engine
from services.coupang.coupang_syncer import CoupangSyncer
from services.jobs.job_service import JobService


def coupang_sync_jobs() -> str:
    """쿠팡 채용공고를 동기화한다."""
    return CoupangSyncer(JobService(get_engine())).sync()
