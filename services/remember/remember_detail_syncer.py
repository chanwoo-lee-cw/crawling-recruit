from services.base_syncer import BaseSyncer


class RememberDetailSyncer(BaseSyncer):
    def sync(self, **kwargs) -> str:
        return "Remember 상세 동기화는 지원하지 않습니다."
