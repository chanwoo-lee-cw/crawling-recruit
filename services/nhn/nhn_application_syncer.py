from services.base_syncer import BaseSyncer
from services.nhn.nhn_client import NHNClient
from services.nhn.nhn_constants import NHN


class NHNApplicationSyncer(BaseSyncer):
    def sync(self) -> str:
        try:
            client = NHNClient()
            apps = client.fetch_applications()
            return self.service.upsert_applications(apps, source=NHN)
        except (PermissionError, ValueError) as e:
            return str(e)
        except Exception as e:
            return f"오류가 발생했습니다: {e}"
