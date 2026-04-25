import os
import httpx
from dotenv import load_dotenv

from services.remember.remember_constants import RememberClientConst

load_dotenv()


class RememberClient:
    def __init__(self):
        self._cookie = os.getenv("REMEMBER_COOKIE")
        self._auth_token = os.getenv("REMEMBER_AUTH_TOKEN")

    @property
    def _auth_headers(self) -> dict:
        headers = {}
        if self._auth_token:
            headers["Authorization"] = f"Token token={self._auth_token}"
        else:
            raise ValueError("REMEMBER_AUTH_TOKEN이 .env에 설정되지 않았습니다.")
        return headers

    def _validate_auth_values(self):
        for key, value in [("REMEMBER_COOKIE", self._cookie), ("REMEMBER_AUTH_TOKEN", self._auth_token)]:
            if value:
                try:
                    value.encode("ascii")
                except UnicodeEncodeError:
                    raise ValueError(f"{key} 값에 한글이 포함되어 있습니다. .env에 실제 브라우저 값을 붙여넣어 주세요.")

    def fetch_jobs(
            self,
            job_category_names: list[dict],
            min_experience: int = 0,
            max_experience: int = 10,
            per: int = 30,
            limit_pages: int | None = None,
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
            resp = httpx.post(RememberClientConst.JOBS_SEARCH_URL, json=payload, headers=self._auth_headers, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            all_jobs.extend(data.get("data", []))
            meta = data.get("meta", {})
            if page >= meta.get("total_pages", 1):
                break
            if limit_pages and page >= limit_pages:
                break
            page += 1
        return all_jobs

    def fetch_applications(self) -> list[dict]:
        if not self._cookie and not self._auth_token:
            raise ValueError("REMEMBER_COOKIE 또는 REMEMBER_AUTH_TOKEN이 .env에 설정되지 않았습니다.")
        self._validate_auth_values()

        all_apps = []
        page = 1
        while True:
            resp = httpx.get(
                RememberClientConst.APPLICATIONS_URL,
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
