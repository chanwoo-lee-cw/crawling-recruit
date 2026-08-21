import time
import httpx
from constants import CRAWL_DELAY_SECONDS
from services.kakaobank.kakaobank_constants import KAKAOBANK_LIST_URL, KAKAOBANK_DETAIL_URL


class KakaoBankClient:
    _HEADERS = {"Accept": "application/json", "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"}

    def fetch_jobs(self, limit_pages: int | None = None) -> list[dict]:
        all_jobs: list[dict] = []
        page = 0
        while True:
            if page > 0:
                time.sleep(CRAWL_DELAY_SECONDS)
            resp = httpx.get(
                KAKAOBANK_LIST_URL,
                params={"pageSize": 20, "pageNumber": page},
                headers=self._HEADERS,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            jobs = data.get("list") or []
            all_jobs.extend(jobs)
            total_pages = data.get("paging", {}).get("totalPages", 1)
            page += 1
            if page >= total_pages:
                break
            if limit_pages is not None and page >= limit_pages:
                break
        return all_jobs

    def fetch_job_detail(self, job_id: int) -> dict | None:
        try:
            resp = httpx.get(f"{KAKAOBANK_DETAIL_URL}/{job_id}", timeout=30)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return None
