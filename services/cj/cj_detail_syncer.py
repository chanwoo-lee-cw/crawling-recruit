from services.base_syncer import BaseSyncer


class CJDetailSyncer(BaseSyncer):
    async def sync(self, **kwargs) -> str:
        return "CJ는 상세 동기화를 지원하지 않습니다."
