from services.base_syncer import BaseSyncer


class SamsungApplicationSyncer(BaseSyncer):
    async def sync(self) -> str:
        return "삼성은 지원현황 API를 지원하지 않습니다."
