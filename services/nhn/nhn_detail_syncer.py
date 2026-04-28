from services.base_syncer import BaseSyncer


class NHNDetailSyncer(BaseSyncer):
    def sync(self, **kwargs) -> str:
        return "NHN 상세 동기화 미구현"
