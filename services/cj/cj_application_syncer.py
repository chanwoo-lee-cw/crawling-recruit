from services.base_syncer import BaseSyncer


class CJApplicationSyncer(BaseSyncer):
    async def sync(self) -> str:
        return "CJ는 지원현황 API를 지원하지 않습니다."
