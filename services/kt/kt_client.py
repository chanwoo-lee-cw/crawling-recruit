import httpx
from services.kt.kt_constants import KT_LIST_URL


class KTClient:
    def fetch_jobs(self, include_contents: bool = False) -> list[dict]:
        """KT 채용공고 목록. include_contents=True면 각 공고의 본문 HTML(contents)까지 함께 온다."""
        resp = httpx.get(
            KT_LIST_URL,
            params={
                "isPost": 1,
                "isInprogress": 1,
                "isContainsContents": 1 if include_contents else 0,
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("data") or []
