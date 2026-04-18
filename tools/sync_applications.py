from db.connection import get_engine
from services.wanted_client import WantedClient
from services.remember_client import RememberClient
from services.job_service import JobService


def sync_applications(source: str = "wanted") -> str:
    """지원현황을 동기화한다. source: "wanted" (기본) 또는 "remember"."""
    engine = get_engine()
    service = JobService(engine)

    if source == "remember":
        try:
            client = RememberClient()
            apps = client.fetch_applications()
        except PermissionError as e:
            return str(e)
        except ValueError as e:
            return str(e)
        return service.upsert_applications(apps, source="remember")

    try:
        client = WantedClient()
        apps = client.fetch_applications()
    except PermissionError as e:
        return str(e)
    except ValueError as e:
        return str(e)
    return service.upsert_applications(apps, source="wanted")
