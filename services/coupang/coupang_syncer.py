from services.base_syncer import BaseSyncer
from services.coupang.coupang_client import CoupangClient
from services.coupang.coupang_constants import COUPANG


class CoupangSyncer(BaseSyncer):
    def sync(self) -> str:
        client = CoupangClient()
        jobs = client.fetch_jobs()
        return self.service.upsert_jobs(jobs, source=COUPANG, full_sync=True)
