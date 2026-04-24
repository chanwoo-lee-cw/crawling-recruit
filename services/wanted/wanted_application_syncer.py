from services.base_syncer import BaseSyncer
from services.wanted.wanted_client import WantedClient
from services.wanted.wanted_constants import WANTED


class WantedApplicationSyncer(BaseSyncer):
    def sync(self) -> str:
        try:
            client = WantedClient()
            apps = client.fetch_applications()
            return self.service.upsert_applications(apps, source=WANTED)
        except (PermissionError, ValueError) as e:
            return str(e)