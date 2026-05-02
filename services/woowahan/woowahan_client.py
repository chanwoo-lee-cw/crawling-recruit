import os
import time
import httpx
from constants import CRAWL_DELAY_SECONDS
from services.woowahan.woowahan_constants import (
    WOOWAHAN_LIST_URL, WOOWAHAN_DETAIL_URL,
    WOOWAHAN_LOGIN_URL, WOOWAHAN_APPLICATIONS_URL,
    WOOWAHAN_DEFAULT_JOB_GROUP,
)


class WoowahanClient:
    def fetch_jobs(
        self,
        job_group_codes: str = WOOWAHAN_DEFAULT_JOB_GROUP,
        limit_pages: int | None = None,
    ) -> list[dict]:
        all_jobs: list[dict] = []
        page = 0
        while True:
            if page > 0:
                time.sleep(CRAWL_DELAY_SECONDS)
            resp = httpx.get(
                WOOWAHAN_LIST_URL,
                params={
                    "jobGroupCodes": job_group_codes,
                    "recruitCampaignSeq": 0,
                    "page": page,
                    "size": 100,
                    "sort": "updateDate,desc",
                },
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json().get("data", {})
            jobs = data.get("list") or []
            all_jobs.extend(jobs)
            total_pages = data.get("totalPageNumber", 1)
            page += 1
            if page >= total_pages:
                break
            if limit_pages is not None and page >= limit_pages:
                break
        return all_jobs

    def fetch_job_detail(self, recruit_number: str) -> dict | None:
        try:
            resp = httpx.get(f"{WOOWAHAN_DETAIL_URL}/{recruit_number}", timeout=30)
            resp.raise_for_status()
            return resp.json().get("data")
        except Exception:
            return None

    def login(self) -> str:
        email = os.environ.get("WOOWAHAN_EMAIL")
        password = os.environ.get("WOOWAHAN_PASSWORD")
        if not email or not password:
            raise ValueError("WOOWAHAN_EMAIL, WOOWAHAN_PASSWORD 환경변수가 설정되지 않았습니다.")
        resp = httpx.post(
            WOOWAHAN_LOGIN_URL,
            json={"applicantEmail": email, "applicantPassword": password},
            timeout=30,
        )
        resp.raise_for_status()
        cookie = resp.cookies.get("X-Authorization")
        if not cookie:
            raise PermissionError("우아한형제들 로그인 실패: X-Authorization 쿠키를 받지 못했습니다.")
        return cookie

    def fetch_applications(self, cookie: str) -> list[dict]:
        all_apps: list[dict] = []
        page = 0
        while True:
            if page > 0:
                time.sleep(CRAWL_DELAY_SECONDS)
            resp = httpx.get(
                WOOWAHAN_APPLICATIONS_URL,
                params={"page": page, "size": 100, "sort": "applicationDate,desc"},
                cookies={"X-Authorization": cookie},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json().get("data", {})
            apps = data.get("list") or []
            all_apps.extend(apps)
            total_pages = data.get("totalPageNumber", 1)
            page += 1
            if page >= total_pages:
                break
        return all_apps
