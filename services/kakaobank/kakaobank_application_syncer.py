from services.base_syncer import BaseSyncer


class KakaoBankApplicationSyncer(BaseSyncer):
    def sync(self) -> str:
        return "카카오뱅크는 지원현황 API를 지원하지 않습니다."
