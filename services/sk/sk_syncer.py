from services.base_syncer import BaseSyncer
from services.sk.sk_client import SKClient
from services.sk.sk_constants import SK


class SKSyncer(BaseSyncer):
    async def sync(self) -> str:
        jobs = SKClient().fetch_jobs()
        return self.service.upsert_jobs(jobs, source=SK, full_sync=True)
