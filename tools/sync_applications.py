from services.remember.remember_constants import REMEMBER
from services.wanted.wanted_constants import WANTED
from db.connection import get_engine
from services.jobs.job_service import JobService
from services.wanted.wanted_application_syncer import WantedApplicationSyncer
from services.remember.remember_application_syncer import RememberApplicationSyncer


def sync_applications(source: str = WANTED) -> str:
    """지원현황을 동기화한다. source: WANTED (기본) 또는 REMEMBER."""
    engine = get_engine()
    service = JobService(engine)

    if source == REMEMBER:
        return RememberApplicationSyncer(service).sync()

    return WantedApplicationSyncer(service).sync()
