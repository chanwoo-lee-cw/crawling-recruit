import os
import httpx
from dotenv import load_dotenv

load_dotenv()

JOBS_SEARCH_URL = "https://career-api.rememberapp.co.kr/job_postings/search"
APPLICATIONS_URL = "https://career-api.rememberapp.co.kr/open_profiles/me/job_postings/application_histories"


class RememberClient:
    def __init__(self):
        self._cookie = os.getenv("REMEMBER_COOKIE")

    @property
    def _auth_headers(self) -> dict:
        return {"Cookie": self._cookie} if self._cookie else {}

    def fetch_jobs(
        self,
        job_category_names: list[dict],
        min_experience: int = 0,
        max_experience: int = 10,
        per: int = 30,
    ) -> list[dict]:
        all_jobs = []
        page = 1
        while True:
            payload = {
                "search": {
                    "job_category_names": job_category_names,
                    "min_experience": min_experience,
                    "max_experience": max_experience,
                    "include_applied_job_posting": False,
                },
                "sort": "recommended",
                "page": page,
                "per": per,
            }
            resp = httpx.post(JOBS_SEARCH_URL, json=payload, headers=self._auth_headers, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            all_jobs.extend(data.get("data", []))
            meta = data.get("meta", {})
            if page >= meta.get("total_pages", 1):
                break
            page += 1
        return all_jobs

    def fetch_applications(self) -> list[dict]:
        if not self._cookie:
            raise ValueError("REMEMBER_COOKIE가 .env에 설정되지 않았습니다.")

        all_apps = []
        page = 1
        while True:
            resp = httpx.get(
                APPLICATIONS_URL,
                params={"statuses[]": "applied", "page": page, "include_canceled": "false"},
                headers=self._auth_headers,
                timeout=30,
            )
            if resp.status_code in (401, 403):
                raise PermissionError("Remeber 쿠키가 만료되었습니다. .env의 REMEMBER_COOKIE를 갱신해주세요.")
            resp.raise_for_status()
            data = resp.json()
            all_apps.extend([item for item in data.get("data", []) if item.get("application")])
            meta = data.get("meta", {})
            if page >= meta.get("total_pages", 1):
                break
            page += 1
        return all_apps
