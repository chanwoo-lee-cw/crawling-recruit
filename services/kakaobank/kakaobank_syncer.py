from services.base_syncer import BaseSyncer
from services.kakaobank.kakaobank_client import KakaoBankClient
from services.kakaobank.kakaobank_constants import KAKAO_BANK


class KakaoBankSyncer(BaseSyncer):
    def sync(self, limit_pages: int | None = None) -> str:
        client = KakaoBankClient()
        jobs = client.fetch_jobs(limit_pages=limit_pages)
        return self.service.upsert_jobs(jobs, source=KAKAO_BANK, full_sync=True)
