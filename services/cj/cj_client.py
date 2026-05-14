import time
import httpx
from constants import CRAWL_DELAY_SECONDS
from services.cj.cj_constants import CJ_LIST_URL, CJ_PAGE_SIZE


class CJClient:
    _HEADERS = {"Content-Type": "application/json"}

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
