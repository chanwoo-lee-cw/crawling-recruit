import os
import time
import httpx
from dotenv import load_dotenv
from domain import JobDetail
from services.wanted.wanted_constants import WantedClientConst, WantedJobSort

load_dotenv()

_UNSET = object()


class WantedClient:
    def __init__(self, cookie: str | None = _UNSET, user_id: str | None = _UNSET):
        self.cookie = cookie if cookie is not _UNSET else os.getenv("WANTED_COOKIE")
        self.user_id = user_id if user_id is not _UNSET else os.getenv("WANTED_USER_ID")

    def _get(self, url: str, params: dict, headers: dict | None = None):
        resp = None
        for attempt in range(WantedClientConst.MAX_RETRIES):
            resp = httpx.get(url, params=params, headers=headers or {}, timeout=30)
            if resp.status_code != 429:
                return resp
            wait = int(resp.headers.get("Retry-After", 1))
            time.sleep(wait)
        raise RuntimeError(f"Rate limit exceeded after {WantedClientConst.MAX_RETRIES} retries: {url}")

    def fetch_jobs(
        self,
        job_group_id: int = 518,
        job_ids: list[int] | None = None,
        years: list[int] | None = None,
        locations: str = "all",
        limit_pages: int | None = None,
        job_sort: str = WantedJobSort.RECOMMEND_ORDER.value,
    ) -> list[dict]:
        params = {
            "job_group_id": job_group_id,
            "country": "kr",
            "job_sort": job_sort,
            "locations": locations,
            "limit": 20,
            "offset": 0,
        }
        if job_ids:
            params["job_ids"] = job_ids
        if years:
            params["years"] = years

        all_jobs = []
        page = 0

        while True:
            resp = self._get(WantedClientConst.JOBS_API_URL, params)
            data = resp.json()
            all_jobs.extend(data.get("data", []))
            page += 1

            if limit_pages and page >= limit_pages:
                break
            if not data.get("links", {}).get("next"):
                break

            params["offset"] += 20

        return all_jobs

    def fetch_applications(self) -> list[dict]:
        if not self.cookie:
            raise ValueError("WANTED_COOKIE가 .env에 설정되지 않았습니다.")
        if not self.user_id:
            raise ValueError("WANTED_USER_ID가 .env에 설정되지 않았습니다.")

        headers = {
            "Cookie": self.cookie,
            "wanted-user-agent": "user-web",
            "wanted-user-country": "KR",
            "wanted-user-language": "ko",
        }
        params = {
            "user_id": self.user_id,
            "sort": "-apply_time,-create_time",
            "limit": 10,
            "status": "complete,+pass,+hire,+reject",
            "includes": "summary",
            "page": 1,
            "offset": 0,
        }

        all_apps = []

        while True:
            resp = self._get(WantedClientConst.APPS_API_URL, params, headers=headers)

            if resp.status_code in (401, 403):
                raise PermissionError(
                    "쿠키가 만료되었습니다. .env의 WANTED_COOKIE를 갱신해주세요."
                )

            data = resp.json()
            all_apps.extend(data.get("applications", []))

            if not data.get("links", {}).get("next"):
                break

            params["offset"] += 10
            params["page"] += 1

        return all_apps

    def fetch_job_detail(self, job_id: int) -> JobDetail | None:
        """단일 공고 detail 조회. 실패 시 None 반환."""
        url = WantedClientConst.DETAIL_API_URL.format(job_id=job_id)
        try:
            resp = self._get(url, params={})
        except RuntimeError:
            return None
        if resp.status_code != 200:
            return None
        data = resp.json().get("data", {})
        job = data.get("job", {})
        detail = job.get("detail", {})
        return JobDetail(
            job_id=job_id,
            requirements=detail.get("requirements"),
            preferred_points=detail.get("preferred_points"),
            skill_tags=data.get("skill_tags", []),
        )
