from db.connection import get_engine
from services.jobs.job_service import JobService


def save_search_preset(name: str, params: dict) -> str:
    engine = get_engine()
    service = JobService(engine)
    try:
        return service.save_preset(name, params)
    except ValueError as e:
        return str(e)
