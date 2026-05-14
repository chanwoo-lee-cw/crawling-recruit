import httpx
from services.kt.kt_constants import KT_LIST_URL


class KTClient:
    def fetch_jobs(self) -> list[dict]:
        resp = httpx.get(
            KT_LIST_URL,
            params={"isPost": 1, "isInprogress": 1, "isContainsContents": 0},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("data") or []
