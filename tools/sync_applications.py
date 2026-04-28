from db.connection import get_engine
from services.jobs.job_service import JobService
from services.nhn.nhn_application_syncer import NHNApplicationSyncer
from services.nhn.nhn_constants import NHN
from services.remember.remember_application_syncer import RememberApplicationSyncer
from services.remember.remember_constants import REMEMBER
from services.wanted.wanted_application_syncer import WantedApplicationSyncer
from services.wanted.wanted_constants import WANTED


def sync_applications(source: str = WANTED) -> str:
    """지원현황을 동기화한다. source: WANTED (기본), REMEMBER, NHN."""
    engine = get_engine()
    service = JobService(engine)

    if source == REMEMBER:
        return RememberApplicationSyncer(service).sync()
    if source == NHN:
        return NHNApplicationSyncer(service).sync()
    return WantedApplicationSyncer(service).sync()
