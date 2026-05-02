from db.connection import get_engine
from services.kakaobank.kakaobank_syncer import KakaoBankSyncer
from services.jobs.job_service import JobService


def kakaobank_sync_jobs() -> str:
    """카카오뱅크 채용공고를 동기화한다."""
    return KakaoBankSyncer(JobService(get_engine())).sync()
