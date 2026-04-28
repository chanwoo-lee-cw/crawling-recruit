import os
import httpx
from dotenv import load_dotenv
from services.nhn.nhn_constants import NHNClientConst

load_dotenv()


class NHNClient:
    def __init__(self):
        self._email = os.getenv("NHN_EMAIL")
        self._password = os.getenv("NHN_PASSWORD")
        self._cookies: dict = {}
        if not self._email or not self._password:
            raise ValueError("NHN_EMAIL 또는 NHN_PASSWORD가 .env에 설정되지 않았습니다.")
        self._login()

    def _login(self) -> None:
        resp = httpx.post(
            NHNClientConst.LOGIN_URL,
            json={"email": self._email, "password": self._password},
            timeout=30,
        )
        if resp.status_code in (401, 403):
            raise PermissionError("NHN 로그인 실패: 이메일 또는 패스워드를 확인해주세요.")
        resp.raise_for_status()
        self._cookies = dict(resp.cookies)

    def fetch_jobs(
        self,
        job_group_id: str = NHNClientConst.TECH_GROUP_ID,
        job_series_ids: list[str] | None = None,
        limit_pages: int | None = None,
    ) -> list[dict]:
        all_jobs: list[dict] = []
        page = 0
        size = NHNClientConst.PAGE_SIZE

        while True:
            params: dict = {
                "jobGroupId": job_group_id,
                "page": page,
                "size": size,
            }
            if job_series_ids:
                params["jobSeriesId"] = job_series_ids

            resp = httpx.get(
                NHNClientConst.JOBS_URL,
                params=params,
                cookies=self._cookies,
                timeout=30,
            )
            resp.raise_for_status()
            result = resp.json().get("result") or []
            all_jobs.extend(result)
            page += 1

            if not result or len(result) < size:
                break
            if limit_pages is not None and page >= limit_pages:
                break

        return all_jobs

    def fetch_applications(self) -> list[dict]:
        resp = httpx.get(
            NHNClientConst.APPLICATIONS_URL,
            cookies=self._cookies,
            timeout=30,
        )
        if resp.status_code in (401, 403):
            raise PermissionError("NHN 쿠키가 만료되었습니다. 재실행하면 자동 로그인됩니다.")
        resp.raise_for_status()
        return resp.json().get("result") or []

    def fetch_job_detail(self, job_id: str) -> dict | None:
        url = NHNClientConst.DETAIL_URL.format(job_id=job_id)
        try:
            resp = httpx.get(url, cookies=self._cookies, timeout=30)
        except Exception:
            return None
        if resp.status_code != 200:
            return None
        return resp.json().get("result")
