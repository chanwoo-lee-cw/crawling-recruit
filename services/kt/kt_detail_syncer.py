from services.base_syncer import BaseSyncer


class KTDetailSyncer(BaseSyncer):
    async def sync(self, **kwargs) -> str:
        return "KT는 상세 동기화를 지원하지 않습니다."
