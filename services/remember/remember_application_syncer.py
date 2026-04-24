from services.remember.remember_client import RememberClient
from services.remember.remember_constants import REMEMBER
from services.base_syncer import BaseSyncer


class RememberApplicationSyncer(BaseSyncer):
    def sync(self) -> str:
        try:
            client = RememberClient()
            apps = client.fetch_applications()
            return self.service.upsert_applications(apps, source=REMEMBER)
        except (PermissionError, ValueError) as e:
            return str(e)
        except Exception as e:
            return f"오류가 발생했습니다: {e}"
