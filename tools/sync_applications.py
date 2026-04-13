from db.connection import get_engine
from services.wanted_client import WantedClient
from services.job_service import JobService


def sync_applications() -> str:
    engine = get_engine()
    service = JobService(engine)
    client = WantedClient()

    try:
        apps = client.fetch_applications()
    except PermissionError as e:
        return str(e)
    except ValueError as e:
        return str(e)

    return service.upsert_applications(apps)
