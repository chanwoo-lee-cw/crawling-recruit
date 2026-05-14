from services.base_syncer import BaseSyncer
from services.kt.kt_client import KTClient
from services.kt.kt_constants import KT


class KTSyncer(BaseSyncer):
    async def sync(self) -> str:
        jobs = KTClient().fetch_jobs()
        return self.service.upsert_jobs(jobs, source=KT, full_sync=True)
