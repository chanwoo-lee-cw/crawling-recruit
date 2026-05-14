from services.base_syncer import BaseSyncer
from services.samsung.samsung_client import SamsungClient
from services.samsung.samsung_constants import SAMSUNG


class SamsungSyncer(BaseSyncer):
    async def sync(self) -> str:
        jobs = SamsungClient().fetch_jobs()
        return self.service.upsert_jobs(jobs, source=SAMSUNG, full_sync=True)
