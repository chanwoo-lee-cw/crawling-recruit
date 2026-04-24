from constants.wanted_constants import WANTED
from db.connection import get_engine
from services.job_service import JobService
from services.syncer import WantedApplicationSyncer, RememberApplicationSyncer


def sync_applications(source: str = WANTED) -> str:
    """지원현황을 동기화한다. source: WANTED (기본) 또는 "remember"."""
    engine = get_engine()
    service = JobService(engine)

    if source == "remember":
        return RememberApplicationSyncer(service).sync()

    return WantedApplicationSyncer(service).sync()
