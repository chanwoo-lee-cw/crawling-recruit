import time
import httpx
from constants import CRAWL_DELAY_SECONDS
from services.cj.cj_constants import CJ_LIST_URL, CJ_PAGE_SIZE, CJ_JOB_URL_PREFIX


class CJClient:
    _HEADERS = {"Content-Type": "application/json"}
    _DETAIL_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }

    def fetch_job_detail(self, platform_id: int) -> str | None:
        """공고 상세 HTML. platform_id는 'J' 접두어가 빠진 zz_jo_num."""
        try:
            resp = httpx.get(
                f"{CJ_JOB_URL_PREFIX}{platform_id}",
                headers=self._DETAIL_HEADERS,
                timeout=30,
                follow_redirects=True,
            )
            resp.raise_for_status()
            return resp.text
        except Exception:
            return None

    def fetch_jobs(self, limit_pages: int | None = None) -> list[dict]:
        all_jobs: list[dict] = []
        page = 1
        total = None
        while True:
            if page > 1:
                time.sleep(CRAWL_DELAY_SECONDS)
            body = {
                "pageVal": str(page),
                "pageIndex": str(CJ_PAGE_SIZE),
                "orderDesc": "1",
                "sch_title": "",
                "arrGubun": "",
                "arrRecBu": "",
                "arrRecJob": "IR",
                "arrRecArea": "",
                "schArea": "Y",
                "recJobbox": "IR",
            }
            resp = httpx.post(CJ_LIST_URL, json=body, headers=self._HEADERS, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            jobs = data.get("ds_newRecruitList") or []
            if total is None and jobs:
                total = int(jobs[0].get("tot_cnt", 0))
            all_jobs.extend(jobs)
            if not jobs or len(all_jobs) >= (total or 0):
                break
            if limit_pages is not None and page >= limit_pages:
                break
            page += 1
        return all_jobs
