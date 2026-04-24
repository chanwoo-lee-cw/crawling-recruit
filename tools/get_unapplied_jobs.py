from db.connection import get_engine
from services.jobs.job_service import JobService


def get_unapplied_jobs(
    job_group_id: int | None = None,
    location: str | None = None,
    employment_type: str | None = None,
    limit: int = 20,
) -> str:
    engine = get_engine()
    service = JobService(engine)
    return service.get_unapplied_jobs(
        job_group_id=job_group_id,
        location=location,
        employment_type=employment_type,
        limit=limit,
    )
