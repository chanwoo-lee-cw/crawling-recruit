from services.base_syncer import BaseSyncer
from services.woowahan.woowahan_client import WoowahanClient
from services.woowahan.woowahan_constants import WOOWAHAN


class WoowahanApplicationSyncer(BaseSyncer):
    def sync(self) -> str:
        try:
            client = WoowahanClient()
            cookie = client.login()
            apps = client.fetch_applications(cookie)
            return self.service.upsert_applications(apps, source=WOOWAHAN)
        except (PermissionError, ValueError) as e:
            return str(e)
        except Exception as e:
            return f"오류가 발생했습니다: {e}"
