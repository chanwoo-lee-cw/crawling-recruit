from services.base_syncer import BaseSyncer


class CoupangApplicationSyncer(BaseSyncer):
    def sync(self) -> str:
        return "쿠팡은 지원현황 API를 지원하지 않습니다."
