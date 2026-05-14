import httpx
from services.sk.sk_constants import SK_LIST_URL, SK_DETAIL_BASE_URL


class SKClient:
    _HEADERS = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }

    def fetch_jobs(self) -> list[dict]:
        resp = httpx.post(
            SK_LIST_URL,
            data={
                "sort": "2",
                "searchText": "",
                "corpCode": "",
                "jobRole": "0",
                "recruitType": "",
                "workingType": "",
                "workingRegion": "",
            },
            headers=self._HEADERS,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json().get("list") or []

    def fetch_job_detail(self, platform_id: int) -> str | None:
        try:
            resp = httpx.get(
                f"{SK_DETAIL_BASE_URL}{platform_id}",
                headers=self._HEADERS,
                timeout=30,
            )
            resp.raise_for_status()
            return resp.text
        except Exception:
            return None
