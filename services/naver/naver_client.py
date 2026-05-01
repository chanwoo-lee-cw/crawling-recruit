import httpx
import time

from constants import CRAWL_DELAY_SECONDS
from services.naver.naver_constants import NAVER_LIST_URL, NAVER_DETAIL_URL, PAGE_SIZE


class NaverClient:
    def fetch_jobs(self, limit_pages: int | None = None) -> list[dict]:
        all_jobs: list[dict] = []
        first_index = 0
        page = 0

        while True:
            if page > 0:
                time.sleep(CRAWL_DELAY_SECONDS)

            params = {
                "subJobCdArr": "",
                "sysCompanyCdArr": "",
                "empTypeCdArr": "",
                "entTypeCdArr": "",
                "workAreaCdArr": "",
                "sw": "",
                "firstIndex": first_index,
            }
            resp = httpx.get(NAVER_LIST_URL, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            jobs = data.get("list") or []
            total_size = data.get("totalSize", 0)
            all_jobs.extend(jobs)

            first_index += PAGE_SIZE
            page += 1

            if not jobs or first_index >= total_size:
                break
            if limit_pages is not None and page >= limit_pages:
                break

        return all_jobs

    def fetch_job_detail(self, anno_id: int) -> str | None:
        try:
            resp = httpx.get(
                NAVER_DETAIL_URL,
                params={"annoId": anno_id},
                timeout=30,
            )
            resp.raise_for_status()
            return resp.text
        except Exception:
            return None
