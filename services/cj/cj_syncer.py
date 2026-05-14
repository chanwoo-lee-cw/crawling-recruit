from services.base_syncer import BaseSyncer
from services.cj.cj_client import CJClient
from services.cj.cj_constants import CJ


class CJSyncer(BaseSyncer):
    async def sync(self, limit_pages: int | None = None) -> str:
        client = CJClient()
        jobs = client.fetch_jobs(limit_pages=limit_pages)
        return self.service.upsert_jobs(jobs, source=CJ, full_sync=True)
