from db.connection import get_engine
from services.jobs.job_service import JobService


def list_search_presets() -> str:
    engine = get_engine()
    service = JobService(engine)
    return service.list_presets()
