# Async Listing Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wanted·Remember listing HTTP 클라이언트를 async로 전환하고, 두 사이트를 병렬 수집하는 `sync_all_jobs` MCP 툴을 추가한다.

**Architecture:** `WantedClient`·`RememberClient`를 `httpx.AsyncClient` 기반으로 전환하고, `BaseSyncer.sync()`를 `async def`로 변경한다. 파급 변경으로 모든 syncer·tool이 `async def`가 되며, `sync_all_jobs`는 `asyncio.gather(..., return_exceptions=True)`로 두 syncer를 병렬 실행한다.

**Tech Stack:** Python 3.11, httpx AsyncClient, asyncio.gather, pytest-asyncio (asyncio_mode=auto), AsyncMock

---

## File Structure

| 파일 | 변경 |
|------|------|
| `pytest.ini` | 신규: asyncio_mode = "auto" |
| `services/wanted/wanted_client.py` | 수정: httpx.AsyncClient, async 메서드 |
| `services/remember/remember_client.py` | 수정: httpx.AsyncClient, async 메서드 |
| `services/base_syncer.py` | 수정: `async def sync()` abstract |
| `services/wanted/wanted_syncer.py` | 수정: `async def sync()` |
| `services/remember/remember_syncer.py` | 수정: `async def sync()` |
| `services/wanted/wanted_application_syncer.py` | 수정: `async def sync()` |
| `services/remember/remember_application_syncer.py` | 수정: `async def sync()` |
| `tools/wanted_sync_jobs.py` | 수정: `async def` |
| `tools/remember_sync_jobs.py` | 수정: `async def` |
| `tools/sync_applications.py` | 수정: `async def` |
| `tools/sync_job_details.py` | 수정: `async def`, `await asyncio.sleep`, `await fetch_job_detail` |
| `tools/sync_all_jobs.py` | 신규: asyncio.gather 병렬 툴 |
| `main.py` | 수정: sync_all_jobs 등록 |
| `tests/wanted/test_wanted_client.py` | 수정: async def + AsyncMock |
| `tests/remember/test_remember_client.py` | 수정: async def + AsyncMock |
| `tests/test_syncer.py` | 수정: async def + AsyncMock |
| `tests/test_tools.py` | 수정: affected tool tests → async def + AsyncMock |

---

## Task 1: pytest.ini 추가

**Files:**
- Create: `pytest.ini`

- [ ] **Step 1: pytest.ini 생성**

```ini
[pytest]
asyncio_mode = auto
```

- [ ] **Step 2: 기존 테스트가 여전히 통과하는지 확인**

```bash
pytest --tb=short -q
```

Expected: 기존 sync 테스트 전부 PASS (async_mode=auto는 기존 sync 테스트에 영향 없음)

- [ ] **Step 3: 커밋**

```bash
git add pytest.ini
git commit -m "test: add pytest.ini with asyncio_mode=auto"
```

---

## Task 2: WantedClient async 전환 (TDD)

**Files:**
- Modify: `tests/wanted/test_wanted_client.py`
- Modify: `services/wanted/wanted_client.py`

- [ ] **Step 1: 테스트를 async + AsyncMock으로 교체**

`tests/wanted/test_wanted_client.py` 전체를 아래로 교체한다:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from services.wanted.wanted_client import WantedClient
from domain import JobDetail


MOCK_JOBS_PAGE_1 = {
    "data": [
        {
            "id": 1001,
            "company": {"id": 10, "name": "테스트컴퍼니"},
            "position": "Backend Engineer",
            "address": {"location": "서울"},
            "employment_type": "regular",
            "annual_from": 0,
            "annual_to": 100,
            "job_group_id": 518,
            "category_tag": {"parent_id": 518, "id": 872},
            "create_time": "2026-01-01T00:00:00",
        }
    ],
    "links": {"next": None}
}

MOCK_APPS_PAGE_1 = {
    "applications": [
        {
            "id": 9001,
            "job_id": 2001,
            "status": "complete",
            "apply_time": "2026-01-01T00:00:00",
        }
    ],
    "total": 1,
    "links": {"next": None}
}


def _make_http_mock(status_code=200, json_data=None):
    """httpx.AsyncClient 인스턴스 mock을 반환한다."""
    mock_http = AsyncMock()
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    if json_data is not None:
        mock_resp.json.return_value = json_data
    mock_http.get.return_value = mock_resp
    mock_http.post.return_value = mock_resp
    return mock_http, mock_resp


async def test_fetch_jobs_single_page():
    with patch("services.wanted.wanted_client.httpx.AsyncClient") as mock_cls:
        mock_http, _ = _make_http_mock(200, MOCK_JOBS_PAGE_1)
        mock_cls.return_value = mock_http

        client = WantedClient()
        jobs = await client.fetch_jobs(job_group_id=518)

    assert len(jobs) == 1
    assert jobs[0]["id"] == 1001


async def test_fetch_jobs_respects_limit_pages():
    page_with_next = {
        "data": [{"id": i, "company": {"id": 1, "name": "A"}, "position": "Dev",
                  "address": {"location": "서울"}, "employment_type": "regular",
                  "annual_from": 0, "annual_to": 0, "job_group_id": 518,
                  "category_tag": {"parent_id": 518, "id": 872},
                  "create_time": "2026-01-01T00:00:00"}
                 for i in range(20)],
        "links": {"next": "/api/next?offset=20"}
    }
    with patch("services.wanted.wanted_client.httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_cls.return_value = mock_http
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = page_with_next
        mock_http.get.return_value = mock_resp

        client = WantedClient()
        jobs = await client.fetch_jobs(job_group_id=518, limit_pages=2)

    assert mock_http.get.call_count == 2
    assert len(jobs) == 40


async def test_fetch_applications_requires_cookie():
    client = WantedClient(cookie=None, user_id="123")
    with pytest.raises(ValueError, match="WANTED_COOKIE"):
        await client.fetch_applications()


async def test_fetch_applications_raises_on_401():
    with patch("services.wanted.wanted_client.httpx.AsyncClient") as mock_cls:
        mock_http, _ = _make_http_mock(status_code=401)
        mock_cls.return_value = mock_http

        client = WantedClient(cookie="test-cookie", user_id="123")
        with pytest.raises(PermissionError, match="쿠키"):
            await client.fetch_applications()


async def test_fetch_applications_single_page():
    with patch("services.wanted.wanted_client.httpx.AsyncClient") as mock_cls:
        mock_http, _ = _make_http_mock(200, MOCK_APPS_PAGE_1)
        mock_cls.return_value = mock_http

        client = WantedClient(cookie="test-cookie", user_id="123")
        apps = await client.fetch_applications()

    assert len(apps) == 1
    assert apps[0]["id"] == 9001


async def test_retry_on_429():
    with patch("services.wanted.wanted_client.httpx.AsyncClient") as mock_cls, \
         patch("services.wanted.wanted_client.asyncio.sleep") as mock_sleep:
        mock_http = AsyncMock()
        mock_cls.return_value = mock_http

        rate_limit_resp = MagicMock()
        rate_limit_resp.status_code = 429
        rate_limit_resp.headers = {}

        ok_resp = MagicMock()
        ok_resp.status_code = 200
        ok_resp.json.return_value = MOCK_JOBS_PAGE_1

        mock_http.get.side_effect = [rate_limit_resp, rate_limit_resp, ok_resp]

        client = WantedClient()
        jobs = await client.fetch_jobs(job_group_id=518)

    assert mock_http.get.call_count == 3
    assert mock_sleep.call_count == 2
    assert len(jobs) == 1


async def test_retry_exhausted_raises():
    with patch("services.wanted.wanted_client.httpx.AsyncClient") as mock_cls, \
         patch("services.wanted.wanted_client.asyncio.sleep"):
        mock_http = AsyncMock()
        mock_cls.return_value = mock_http

        rate_limit_resp = MagicMock()
        rate_limit_resp.status_code = 429
        rate_limit_resp.headers = {}
        mock_http.get.return_value = rate_limit_resp

        client = WantedClient()
        with pytest.raises(RuntimeError, match="Rate limit exceeded"):
            await client.fetch_jobs(job_group_id=518)


MOCK_DETAIL_RESPONSE = {
    "error_code": None,
    "message": "ok",
    "data": {
        "job": {
            "id": 210918,
            "detail": {
                "requirements": "Python 3년 이상",
                "preferred_points": "FastAPI 경험자 우대",
            }
        },
        "skill_tags": [
            {"tag_type_id": 1554, "text": "Python"},
            {"tag_type_id": 1562, "text": "SQL"},
        ]
    }
}


async def test_fetch_job_detail_success():
    with patch("services.wanted.wanted_client.httpx.AsyncClient") as mock_cls:
        mock_http, _ = _make_http_mock(200, MOCK_DETAIL_RESPONSE)
        mock_cls.return_value = mock_http

        client = WantedClient()
        result = await client.fetch_job_detail(210918)

    assert result is not None
    assert isinstance(result, JobDetail)
    assert result.job_id == 210918
    assert result.requirements == "Python 3년 이상"
    assert result.preferred_points == "FastAPI 경험자 우대"
    assert result.skill_tags == [
        {"tag_type_id": 1554, "text": "Python"},
        {"tag_type_id": 1562, "text": "SQL"},
    ]


async def test_fetch_job_detail_returns_none_on_error():
    with patch("services.wanted.wanted_client.httpx.AsyncClient") as mock_cls:
        mock_http, _ = _make_http_mock(404)
        mock_cls.return_value = mock_http

        client = WantedClient()
        result = await client.fetch_job_detail(99999)

    assert result is None
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
pytest tests/wanted/test_wanted_client.py -v
```

Expected: FAIL (WantedClient 메서드가 아직 sync라 `await` 불가)

- [ ] **Step 3: WantedClient async 전환**

`services/wanted/wanted_client.py` 전체를 아래로 교체한다:

```python
import asyncio
import os
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
        self._http = httpx.AsyncClient(timeout=30)

    async def _get(self, url: str, params: dict, headers: dict | None = None):
        for attempt in range(WantedClientConst.MAX_RETRIES):
            resp = await self._http.get(url, params=params, headers=headers or {})
            if resp.status_code != 429:
                return resp
            wait = int(resp.headers.get("Retry-After", 1))
            await asyncio.sleep(wait)
        raise RuntimeError(f"Rate limit exceeded after {WantedClientConst.MAX_RETRIES} retries: {url}")

    async def fetch_jobs(
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
            resp = await self._get(WantedClientConst.JOBS_API_URL, params)
            data = resp.json()
            all_jobs.extend(data.get("data", []))
            page += 1

            if limit_pages and page >= limit_pages:
                break
            if not data.get("links", {}).get("next"):
                break

            params["offset"] += 20

        return all_jobs

    async def fetch_applications(self) -> list[dict]:
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
            resp = await self._get(WantedClientConst.APPS_API_URL, params, headers=headers)

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

    async def fetch_job_detail(self, job_id: int) -> JobDetail | None:
        url = WantedClientConst.DETAIL_API_URL.format(job_id=job_id)
        try:
            resp = await self._get(url, params={})
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
```

- [ ] **Step 4: 테스트 실행 — 통과 확인**

```bash
pytest tests/wanted/test_wanted_client.py -v
```

Expected: 전부 PASS

- [ ] **Step 5: 커밋**

```bash
git add services/wanted/wanted_client.py tests/wanted/test_wanted_client.py
git commit -m "feat: convert WantedClient to async httpx"
```

---

## Task 3: RememberClient async 전환 (TDD)

**Files:**
- Modify: `tests/remember/test_remember_client.py`
- Modify: `services/remember/remember_client.py`

- [ ] **Step 1: 테스트를 async + AsyncMock으로 교체**

`tests/remember/test_remember_client.py` 전체를 아래로 교체한다:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


SAMPLE_JOB = {
    "id": 308098,
    "title": "[ESTsecurity] 백엔드 개발",
    "qualifications": "Python 3년 이상",
    "preferred_qualifications": "FastAPI 경험자 우대",
    "organization": {"id": 21961, "name": "(주)이스트소프트", "company_id": 4494},
    "addresses": [{"address_level1": "서울특별시", "address_level2": "서초구"}],
    "min_salary": None,
    "max_salary": None,
    "application": None,
}

SAMPLE_APPLICATION_JOB = {
    **SAMPLE_JOB,
    "id": 303872,
    "application": {
        "id": 3428290,
        "status": "applied",
        "applied_at": "2026-04-12T18:28:24.676+09:00",
    },
}


def _make_http_mock(status_code=200, json_data=None):
    mock_http = AsyncMock()
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.raise_for_status = MagicMock()
    if json_data is not None:
        mock_resp.json.return_value = json_data
    mock_http.post.return_value = mock_resp
    mock_http.get.return_value = mock_resp
    return mock_http, mock_resp


async def test_fetch_jobs_success():
    with patch("services.remember.remember_client.httpx.AsyncClient") as mock_cls:
        mock_http, _ = _make_http_mock(200, {
            "data": [SAMPLE_JOB],
            "meta": {"total_pages": 1, "page": 1},
        })
        mock_cls.return_value = mock_http

        from services.remember.remember_client import RememberClient
        client = RememberClient()
        jobs = await client.fetch_jobs(job_category_names=[{"level1": "SW개발", "level2": "백엔드"}])

    assert len(jobs) == 1
    assert jobs[0]["id"] == 308098
    assert jobs[0]["qualifications"] == "Python 3년 이상"
    assert jobs[0]["organization"]["name"] == "(주)이스트소프트"


async def test_fetch_applications_success():
    with patch("services.remember.remember_client.httpx.AsyncClient") as mock_cls, \
         patch.dict("os.environ", {"REMEMBER_COOKIE": "test_cookie", "REMEMBER_AUTH_TOKEN": "test_token"}):
        mock_http, _ = _make_http_mock(200, {
            "data": [SAMPLE_APPLICATION_JOB],
            "meta": {"total_pages": 1, "page": 1},
        })
        mock_cls.return_value = mock_http

        from services.remember.remember_client import RememberClient
        client = RememberClient()
        apps = await client.fetch_applications()

    assert len(apps) == 1
    assert apps[0]["id"] == 303872
    assert apps[0]["application"]["id"] == 3428290
    assert apps[0]["application"]["status"] == "applied"


async def test_fetch_applications_raises_on_missing_cookie():
    with patch.dict("os.environ", {}, clear=True):
        from services.remember.remember_client import RememberClient
        client = RememberClient()
        with pytest.raises(ValueError, match="REMEMBER_COOKIE"):
            await client.fetch_applications()


async def test_fetch_applications_raises_on_expired_cookie():
    with patch("services.remember.remember_client.httpx.AsyncClient") as mock_cls, \
         patch.dict("os.environ", {"REMEMBER_COOKIE": "expired", "REMEMBER_AUTH_TOKEN": "tok"}):
        mock_http, _ = _make_http_mock(401)
        mock_cls.return_value = mock_http

        from services.remember.remember_client import RememberClient
        client = RememberClient()
        with pytest.raises(PermissionError, match="만료"):
            await client.fetch_applications()


async def test_fetch_jobs_http_error():
    with patch("services.remember.remember_client.httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_cls.return_value = mock_http
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = Exception("500 Server Error")
        mock_http.post.return_value = mock_resp

        from services.remember.remember_client import RememberClient
        client = RememberClient()
        with pytest.raises(Exception, match="500"):
            await client.fetch_jobs(job_category_names=[{"level1": "SW개발", "level2": "백엔드"}])
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
pytest tests/remember/test_remember_client.py -v
```

Expected: FAIL

- [ ] **Step 3: RememberClient async 전환**

`services/remember/remember_client.py` 전체를 아래로 교체한다:

```python
import os
import httpx
from dotenv import load_dotenv

from services.remember.remember_constants import RememberClientConst

load_dotenv()


class RememberClient:
    def __init__(self):
        self._cookie = os.getenv("REMEMBER_COOKIE")
        self._auth_token = os.getenv("REMEMBER_AUTH_TOKEN")
        self._http = httpx.AsyncClient(timeout=30)

    @property
    def _auth_headers(self) -> dict:
        if self._auth_token:
            return {"Authorization": f"Token token={self._auth_token}"}
        raise ValueError("REMEMBER_AUTH_TOKEN이 .env에 설정되지 않았습니다.")

    def _validate_auth_values(self):
        for key, value in [("REMEMBER_COOKIE", self._cookie), ("REMEMBER_AUTH_TOKEN", self._auth_token)]:
            if value:
                try:
                    value.encode("ascii")
                except UnicodeEncodeError:
                    raise ValueError(f"{key} 값에 한글이 포함되어 있습니다. .env에 실제 브라우저 값을 붙여넣어 주세요.")

    async def fetch_jobs(
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
            resp = await self._http.post(
                RememberClientConst.JOBS_SEARCH_URL,
                json=payload,
                headers=self._auth_headers,
            )
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

    async def fetch_applications(self) -> list[dict]:
        if not self._cookie and not self._auth_token:
            raise ValueError("REMEMBER_COOKIE 또는 REMEMBER_AUTH_TOKEN이 .env에 설정되지 않았습니다.")
        self._validate_auth_values()

        all_apps = []
        page = 1
        while True:
            resp = await self._http.get(
                RememberClientConst.APPLICATIONS_URL,
                params={"statuses[]": "applied", "page": page, "include_canceled": "false"},
                headers=self._auth_headers,
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
```

- [ ] **Step 4: 테스트 실행 — 통과 확인**

```bash
pytest tests/remember/test_remember_client.py -v
```

Expected: 전부 PASS

- [ ] **Step 5: 커밋**

```bash
git add services/remember/remember_client.py tests/remember/test_remember_client.py
git commit -m "feat: convert RememberClient to async httpx"
```

---

## Task 4: Syncer 계층 async 전환 (TDD)

**Files:**
- Modify: `services/base_syncer.py`
- Modify: `services/wanted/wanted_syncer.py`
- Modify: `services/remember/remember_syncer.py`
- Modify: `tests/test_syncer.py`

- [ ] **Step 1: test_syncer.py의 WantedSyncer·RememberSyncer 테스트를 async로 교체**

`tests/test_syncer.py`에서 아래 두 함수를 교체한다 (application syncer 테스트는 Task 5에서 교체):

```python
# 기존 test_wanted_syncer_calls_client_and_service 교체
async def test_wanted_syncer_calls_client_and_service():
    mock_service = MagicMock()
    mock_service.upsert_jobs.return_value = "동기화 완료: 신규 2개, 변경 0개, 유지 0개"

    with patch("services.wanted.wanted_syncer.WantedClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.fetch_jobs.return_value = [{"id": 1}, {"id": 2}]
        MockClient.return_value = mock_client

        syncer = WantedSyncer(mock_service)
        result = await syncer.sync(
            job_group_id=518, job_ids=None, years=None,
            locations="all", limit_pages=2, job_sort="job.popularity_order",
        )

    mock_client.fetch_jobs.assert_called_once_with(
        job_group_id=518, job_ids=None, years=None,
        locations="all", limit_pages=2, job_sort="job.popularity_order",
    )
    mock_service.upsert_jobs.assert_called_once()
    assert "동기화 완료" in result


# 기존 test_remember_syncer_calls_client_upsert_and_details 교체
async def test_remember_syncer_calls_client_upsert_and_details():
    mock_service = MagicMock()
    mock_service.upsert_jobs.return_value = "동기화 완료: 신규 1개, 변경 0개, 유지 0개"

    with patch("services.remember.remember_syncer.RememberClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.fetch_jobs.return_value = [{"id": 10}]
        MockClient.return_value = mock_client

        syncer = RememberSyncer(mock_service)
        result = await syncer.sync(
            job_category_names=[{"level1": "SW개발", "level2": "백엔드"}],
            min_experience=0, max_experience=5, limit_pages=None,
        )

    mock_client.fetch_jobs.assert_called_once()
    mock_service.upsert_jobs.assert_called_once_with([{"id": 10}], source=REMEMBER, full_sync=True)
    mock_service.upsert_remember_details.assert_called_once_with([{"id": 10}])
    assert "동기화 완료" in result


# 기존 test_remember_syncer_returns_error_without_job_categories 교체
async def test_remember_syncer_returns_error_without_job_categories():
    syncer = RememberSyncer(service=MagicMock())
    result = await syncer.sync(job_category_names=None, min_experience=0, max_experience=5, limit_pages=None)
    assert "job_category_names" in result
```

파일 상단에 `from unittest.mock import AsyncMock, MagicMock, patch` 추가 (기존 `MagicMock` import 교체).

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
pytest tests/test_syncer.py::test_wanted_syncer_calls_client_and_service tests/test_syncer.py::test_remember_syncer_calls_client_upsert_and_details tests/test_syncer.py::test_remember_syncer_returns_error_without_job_categories -v
```

Expected: FAIL

- [ ] **Step 3: BaseSyncer를 abstract async로 변경**

`services/base_syncer.py`:

```python
from abc import ABC, abstractmethod

from services.jobs.job_service import JobService


class BaseSyncer(ABC):
    def __init__(self, service: JobService):
        self.service = service

    @abstractmethod
    async def sync(self, **kwargs) -> str:
        ...
```

- [ ] **Step 4: WantedSyncer async 전환**

`services/wanted/wanted_syncer.py`:

```python
from services.base_syncer import BaseSyncer
from services.wanted.wanted_client import WantedClient
from services.wanted.wanted_constants import WANTED


class WantedSyncer(BaseSyncer):
    async def sync(
        self,
        job_group_id: int = 518,
        job_ids: list[int] | None = None,
        years: list[int] | None = None,
        locations: str = "all",
        limit_pages: int | None = None,
        job_sort: str = "job.popularity_order",
    ) -> str:
        client = WantedClient()
        full_sync = limit_pages is None
        jobs = await client.fetch_jobs(
            job_group_id=job_group_id,
            job_ids=job_ids,
            years=years,
            locations=locations,
            limit_pages=limit_pages,
            job_sort=job_sort,
        )
        for job in jobs:
            if not job.get("job_group_id") and job_group_id:
                job["job_group_id"] = job_group_id
        return self.service.upsert_jobs(jobs, source=WANTED, full_sync=full_sync)
```

- [ ] **Step 5: RememberSyncer async 전환**

`services/remember/remember_syncer.py`:

```python
from services.remember.remember_client import RememberClient
from services.remember.remember_constants import REMEMBER
from services.base_syncer import BaseSyncer


class RememberSyncer(BaseSyncer):
    async def sync(
        self,
        job_category_names: list[dict] | None = None,
        min_experience: int = 0,
        max_experience: int = 10,
        limit_pages: int | None = None,
    ) -> str:
        if not job_category_names:
            return "Remember 동기화에는 job_category_names가 필요합니다."
        client = RememberClient()
        jobs = await client.fetch_jobs(
            job_category_names=job_category_names,
            min_experience=min_experience,
            max_experience=max_experience,
            limit_pages=limit_pages,
        )
        result = self.service.upsert_jobs(jobs, source=REMEMBER, full_sync=True)
        self.service.upsert_remember_details(jobs)
        return result
```

- [ ] **Step 6: 테스트 실행 — 통과 확인**

```bash
pytest tests/test_syncer.py -v
```

Expected: 전부 PASS (`test_base_syncer_is_abstract` 포함)

- [ ] **Step 7: 커밋**

```bash
git add services/base_syncer.py services/wanted/wanted_syncer.py services/remember/remember_syncer.py tests/test_syncer.py
git commit -m "feat: convert BaseSyncer, WantedSyncer, RememberSyncer to async"
```

---

## Task 5: Application Syncer async 전환 (TDD)

**Files:**
- Modify: `services/wanted/wanted_application_syncer.py`
- Modify: `services/remember/remember_application_syncer.py`
- Modify: `tests/test_syncer.py`

- [ ] **Step 1: test_syncer.py의 application syncer 테스트를 async로 교체**

`tests/test_syncer.py`에서 아래 함수들을 교체한다:

```python
# 기존 test_wanted_application_syncer_calls_client_and_service 교체
async def test_wanted_application_syncer_calls_client_and_service():
    mock_service = MagicMock()
    mock_service.upsert_applications.return_value = "지원현황 동기화 완료: 총 3건"

    with patch("services.wanted.wanted_application_syncer.WantedClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.fetch_applications.return_value = [{"id": 1}, {"id": 2}, {"id": 3}]
        MockClient.return_value = mock_client

        syncer = WantedApplicationSyncer(mock_service)
        result = await syncer.sync()

    mock_client.fetch_applications.assert_called_once()
    mock_service.upsert_applications.assert_called_once()
    assert "3건" in result


# 기존 test_wanted_application_syncer_returns_error_on_permission_error 교체
async def test_wanted_application_syncer_returns_error_on_permission_error():
    mock_service = MagicMock()

    with patch("services.wanted.wanted_application_syncer.WantedClient") as MockClient:
        MockClient.return_value.fetch_applications = AsyncMock(
            side_effect=PermissionError("쿠키가 만료되었습니다.")
        )

        syncer = WantedApplicationSyncer(mock_service)
        result = await syncer.sync()

    assert "쿠키" in result


# 기존 test_remember_application_syncer_calls_client_and_service 교체
async def test_remember_application_syncer_calls_client_and_service():
    mock_service = MagicMock()
    mock_service.upsert_applications.return_value = "지원현황 동기화 완료: 총 2건"

    with patch("services.remember.remember_application_syncer.RememberClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.fetch_applications.return_value = [{"id": 10}, {"id": 11}]
        MockClient.return_value = mock_client

        syncer = RememberApplicationSyncer(mock_service)
        result = await syncer.sync()

    mock_client.fetch_applications.assert_called_once()
    mock_service.upsert_applications.assert_called_once_with([{"id": 10}, {"id": 11}], source=REMEMBER)
    assert "2건" in result


# 기존 test_remember_application_syncer_returns_error_on_permission_error 교체
async def test_remember_application_syncer_returns_error_on_permission_error():
    mock_service = MagicMock()

    with patch("services.remember.remember_application_syncer.RememberClient") as MockClient:
        MockClient.return_value.fetch_applications = AsyncMock(
            side_effect=PermissionError("Remeber 쿠키 만료")
        )

        syncer = RememberApplicationSyncer(mock_service)
        result = await syncer.sync()

    assert "쿠키" in result


# 기존 test_remember_application_syncer_catches_generic_exception 교체
async def test_remember_application_syncer_catches_generic_exception():
    mock_service = MagicMock()

    with patch("services.remember.remember_application_syncer.RememberClient") as MockClient:
        MockClient.return_value.fetch_applications = AsyncMock(
            side_effect=RuntimeError("네트워크 오류")
        )

        syncer = RememberApplicationSyncer(mock_service)
        result = await syncer.sync()

    assert "오류" in result
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
pytest tests/test_syncer.py::test_wanted_application_syncer_calls_client_and_service tests/test_syncer.py::test_remember_application_syncer_calls_client_and_service -v
```

Expected: FAIL

- [ ] **Step 3: WantedApplicationSyncer async 전환**

`services/wanted/wanted_application_syncer.py`:

```python
from services.base_syncer import BaseSyncer
from services.wanted.wanted_client import WantedClient
from services.wanted.wanted_constants import WANTED


class WantedApplicationSyncer(BaseSyncer):
    async def sync(self) -> str:
        try:
            client = WantedClient()
            apps = await client.fetch_applications()
            return self.service.upsert_applications(apps, source=WANTED)
        except (PermissionError, ValueError) as e:
            return str(e)
```

- [ ] **Step 4: RememberApplicationSyncer async 전환**

`services/remember/remember_application_syncer.py`:

```python
from services.remember.remember_client import RememberClient
from services.remember.remember_constants import REMEMBER
from services.base_syncer import BaseSyncer


class RememberApplicationSyncer(BaseSyncer):
    async def sync(self) -> str:
        try:
            client = RememberClient()
            apps = await client.fetch_applications()
            return self.service.upsert_applications(apps, source=REMEMBER)
        except (PermissionError, ValueError) as e:
            return str(e)
        except Exception as e:
            return f"오류가 발생했습니다: {e}"
```

- [ ] **Step 5: 테스트 실행 — 통과 확인**

```bash
pytest tests/test_syncer.py -v
```

Expected: 전부 PASS

- [ ] **Step 6: 커밋**

```bash
git add services/wanted/wanted_application_syncer.py services/remember/remember_application_syncer.py tests/test_syncer.py
git commit -m "feat: convert application syncers to async"
```

---

## Task 6: 기존 Tool 4개 async 전환

**Files:**
- Modify: `tools/wanted_sync_jobs.py`
- Modify: `tools/remember_sync_jobs.py`
- Modify: `tools/sync_applications.py`
- Modify: `tools/sync_job_details.py`
- Modify: `tests/test_tools.py`

- [ ] **Step 1: test_tools.py의 영향받는 테스트를 async로 교체**

`tests/test_tools.py`에서 아래 함수들을 교체한다:

```python
# 기존 test_sync_jobs_uses_preset_when_given 교체
async def test_sync_jobs_uses_preset_when_given():
    with patch("tools.wanted_sync_jobs.get_engine") as mock_engine, \
         patch("services.wanted.wanted_syncer.WantedClient") as mock_client_cls, \
         patch("tools.wanted_sync_jobs.JobService") as mock_service_cls:

        mock_service = MagicMock()
        mock_service.get_preset_params.return_value = MagicMock(params={"job_group_id": 519})
        mock_service.upsert_jobs.return_value = "동기화 완료: 신규/변경 5개, 총 5개 처리"
        mock_service_cls.return_value = mock_service

        mock_client = AsyncMock()
        mock_client.fetch_jobs.return_value = []
        mock_client_cls.return_value = mock_client

        from tools.wanted_sync_jobs import wanted_sync_jobs
        result = await wanted_sync_jobs(preset_name="백엔드 신입")

    mock_service.get_preset_params.assert_called_once_with("백엔드 신입")
    mock_service.upsert_jobs.assert_called_once()
    call_kwargs = mock_client.fetch_jobs.call_args.kwargs
    assert call_kwargs.get("job_group_id") == 519


# 기존 test_sync_applications_returns_error_on_permission_error 교체
async def test_sync_applications_returns_error_on_permission_error():
    with patch("tools.sync_applications.get_engine"), \
         patch("services.wanted.wanted_application_syncer.WantedClient") as mock_client_cls, \
         patch("tools.sync_applications.JobService"):

        mock_client = AsyncMock()
        mock_client.fetch_applications = AsyncMock(side_effect=PermissionError("쿠키가 만료되었습니다."))
        mock_client_cls.return_value = mock_client

        from tools.sync_applications import sync_applications
        result = await sync_applications()

    assert "쿠키" in result


# 기존 test_sync_job_details_processes_missing 교체
async def test_sync_job_details_processes_missing():
    with patch("tools.sync_job_details.get_engine"), \
         patch("tools.sync_job_details.WantedClient") as MockClient, \
         patch("tools.sync_job_details.JobService") as MockService, \
         patch("tools.sync_job_details.asyncio.sleep") as mock_sleep:

        mock_service = MagicMock()
        mock_service.get_jobs_without_details.return_value = [101, 102]
        mock_service.upsert_job_details.return_value = "완료: 2개 처리"
        MockService.return_value = mock_service

        mock_client = AsyncMock()
        mock_client.fetch_job_detail.side_effect = [
            JobDetail(job_id=101, requirements="req1", preferred_points="pref1", skill_tags=[]),
            JobDetail(job_id=102, requirements="req2", preferred_points=None, skill_tags=[]),
        ]
        MockClient.return_value = mock_client

        from tools.sync_job_details import sync_job_details
        result = await sync_job_details()

    assert "2개 처리" in result
    assert mock_client.fetch_job_detail.call_count == 2
    mock_sleep.assert_called_once_with(CRAWL_DELAY_SECONDS)


# 기존 test_sync_job_details_skips_failed_fetch 교체
async def test_sync_job_details_skips_failed_fetch():
    with patch("tools.sync_job_details.get_engine"), \
         patch("tools.sync_job_details.WantedClient") as MockClient, \
         patch("tools.sync_job_details.JobService") as MockService, \
         patch("tools.sync_job_details.asyncio.sleep"):

        mock_service = MagicMock()
        mock_service.get_jobs_without_details.return_value = [101, 102]
        mock_service.list_keywords.return_value = []
        mock_service.enrich_skill_tags.side_effect = lambda d, kw: d
        mock_service.upsert_job_details.return_value = "완료: 1개 처리"
        MockService.return_value = mock_service

        mock_client = AsyncMock()
        mock_client.fetch_job_detail.side_effect = [
            None,
            JobDetail(job_id=102, requirements="req2", preferred_points=None, skill_tags=[]),
        ]
        MockClient.return_value = mock_client

        from tools.sync_job_details import sync_job_details
        result = await sync_job_details()

    called_details = mock_service.upsert_job_details.call_args[0][0]
    assert len(called_details) == 1
    assert called_details[0].job_id == 102


# 기존 test_sync_job_details_calls_enrich_for_each_detail 교체
async def test_sync_job_details_calls_enrich_for_each_detail():
    detail_101 = JobDetail(job_id=101, requirements="Python 경험", preferred_points=None, skill_tags=[])
    detail_102 = JobDetail(job_id=102, requirements="Java 경험", preferred_points=None, skill_tags=[])

    with patch("tools.sync_job_details.get_engine"), \
         patch("tools.sync_job_details.WantedClient") as MockClient, \
         patch("tools.sync_job_details.JobService") as MockService, \
         patch("tools.sync_job_details.asyncio.sleep"):

        mock_service = MagicMock()
        mock_service.get_jobs_without_details.return_value = [101, 102]
        mock_service.list_keywords.return_value = ["Python", "Java"]
        mock_service.enrich_skill_tags.side_effect = lambda d, kw: d
        mock_service.upsert_job_details.return_value = "완료: 2개 처리"
        MockService.return_value = mock_service

        mock_client = AsyncMock()
        mock_client.fetch_job_detail.side_effect = [detail_101, detail_102]
        MockClient.return_value = mock_client

        from tools.sync_job_details import sync_job_details
        await sync_job_details()

    mock_service.list_keywords.assert_called_once()
    assert mock_service.enrich_skill_tags.call_count == 2
    mock_service.enrich_skill_tags.assert_any_call(detail_101, ["Python", "Java"])
```

파일 상단 import에 `from unittest.mock import AsyncMock, MagicMock, patch` 추가.

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
pytest tests/test_tools.py::test_sync_jobs_uses_preset_when_given tests/test_tools.py::test_sync_applications_returns_error_on_permission_error tests/test_tools.py::test_sync_job_details_processes_missing -v
```

Expected: FAIL

- [ ] **Step 3: wanted_sync_jobs.py를 async로 전환**

`tools/wanted_sync_jobs.py`:

```python
from constants import DEFAULT_LIMIT_PAGES
from db.connection import get_engine
from db.models import SearchPreset
from services.jobs.job_service import JobService
from services.wanted.wanted_constants import WantedJobGroupId, WANTED
from services.wanted.wanted_syncer import WantedSyncer


async def wanted_sync_jobs(
        job_group_id: int = WantedJobGroupId.SERVER_DEVELOPER.value,
        job_ids: list[int] | None = None,
        years: list[int] | None = None,
        locations: str = "all",
        limit_pages: int | None = DEFAULT_LIMIT_PAGES,
        job_sort: str = "job.popularity_order",
        preset_name: str | None = None,
) -> str:
    """채용공고를 동기화한다."""
    engine = get_engine()
    service = JobService(engine)

    preset: SearchPreset | None = service.get_preset_params(preset_name or WANTED)
    if preset:
        p = preset.params
        job_group_id = p.get("job_group_id", job_group_id)
        job_ids = p.get("job_ids", job_ids)
        years = p.get("years", years)
        locations = p.get("locations", locations)
        limit_pages = p.get("limit_pages", limit_pages)
        job_sort = p.get("job_sort", job_sort)

    return await WantedSyncer(service).sync(
        job_group_id=job_group_id,
        job_ids=job_ids,
        years=years,
        locations=locations,
        limit_pages=limit_pages,
        job_sort=job_sort,
    )
```

- [ ] **Step 4: remember_sync_jobs.py를 async로 전환**

`tools/remember_sync_jobs.py`:

```python
from constants import DEFAULT_LIMIT_PAGES
from db.connection import get_engine
from db.models import SearchPreset
from services.jobs.job_service import JobService
from services.remember.remember_constants import REMEMBER
from services.remember.remember_syncer import RememberSyncer


async def remember_sync_jobs(
        limit_pages: int | None = DEFAULT_LIMIT_PAGES,
        job_category_names: list[dict] | None = None,
        min_experience: int = 0,
        max_experience: int = 10,
) -> str:
    """채용공고를 동기화한다."""
    engine = get_engine()
    service = JobService(engine)

    preset: SearchPreset | None = service.get_preset_params(REMEMBER)
    if preset:
        p = preset.params
        limit_pages = p.get("limit_pages", limit_pages)
        job_category_names = p.get("job_category_names", job_category_names)
        min_experience = p.get("min_experience", min_experience)
        max_experience = p.get("max_experience", max_experience)

    return await RememberSyncer(service).sync(
        job_category_names=job_category_names,
        min_experience=min_experience,
        max_experience=max_experience,
        limit_pages=limit_pages,
    )
```

- [ ] **Step 5: sync_applications.py를 async로 전환**

`tools/sync_applications.py`:

```python
from services.remember.remember_constants import REMEMBER
from services.wanted.wanted_constants import WANTED
from db.connection import get_engine
from services.jobs.job_service import JobService
from services.wanted.wanted_application_syncer import WantedApplicationSyncer
from services.remember.remember_application_syncer import RememberApplicationSyncer


async def sync_applications(source: str = WANTED) -> str:
    """지원현황을 동기화한다. source: WANTED (기본) 또는 REMEMBER."""
    engine = get_engine()
    service = JobService(engine)

    if source == REMEMBER:
        return await RememberApplicationSyncer(service).sync()

    return await WantedApplicationSyncer(service).sync()
```

- [ ] **Step 6: sync_job_details.py를 async로 전환**

`tools/sync_job_details.py`:

```python
import asyncio

from constants import CRAWL_DELAY_SECONDS
from db.connection import get_engine
from services.jobs.job_service import JobService
from services.wanted.wanted_client import WantedClient


async def sync_job_details(
    job_ids: list[int] | None = None,
    limit: int | None = None,
) -> str:
    engine = get_engine()
    service = JobService(engine)
    client = WantedClient()

    target_ids = service.get_jobs_without_details(job_ids=job_ids, limit=limit)
    if not target_ids:
        return "처리할 공고가 없습니다."

    fetched = []
    for i, job_id in enumerate(target_ids):
        if i > 0:
            await asyncio.sleep(CRAWL_DELAY_SECONDS)
        detail = await client.fetch_job_detail(job_id)
        if detail is None:
            continue
        fetched.append(detail)

    if not fetched:
        return "상세 정보를 가져온 공고가 없습니다."

    keywords = service.list_keywords()
    fetched = [service.enrich_skill_tags(d, keywords) for d in fetched]

    return service.upsert_job_details(fetched)
```

- [ ] **Step 7: 테스트 실행 — 통과 확인**

```bash
pytest tests/test_tools.py -v
```

Expected: 전부 PASS

- [ ] **Step 8: 커밋**

```bash
git add tools/wanted_sync_jobs.py tools/remember_sync_jobs.py tools/sync_applications.py tools/sync_job_details.py tests/test_tools.py
git commit -m "feat: convert sync tools to async"
```

---

## Task 7: sync_all_jobs 툴 신규 추가 (TDD)

**Files:**
- Create: `tools/sync_all_jobs.py`
- Modify: `tests/test_tools.py`

- [ ] **Step 1: sync_all_jobs 테스트 추가**

`tests/test_tools.py` 끝에 추가한다:

```python
async def test_sync_all_jobs_returns_both_results():
    with patch("tools.sync_all_jobs.get_engine"), \
         patch("tools.sync_all_jobs.JobService") as mock_service_cls, \
         patch("tools.sync_all_jobs.WantedSyncer") as mock_wanted_cls, \
         patch("tools.sync_all_jobs.RememberSyncer") as mock_remember_cls:

        mock_service = MagicMock()
        mock_service.get_preset_params.return_value = None
        mock_service_cls.return_value = mock_service

        mock_wanted = AsyncMock()
        mock_wanted.sync.return_value = "Wanted: 신규 5개"
        mock_wanted_cls.return_value = mock_wanted

        mock_remember = AsyncMock()
        mock_remember.sync.return_value = "Remember: 신규 3개"
        mock_remember_cls.return_value = mock_remember

        from tools.sync_all_jobs import sync_all_jobs
        result = await sync_all_jobs()

    assert "[Wanted]" in result
    assert "Wanted: 신규 5개" in result
    assert "[Remember]" in result
    assert "Remember: 신규 3개" in result


async def test_sync_all_jobs_handles_partial_failure():
    with patch("tools.sync_all_jobs.get_engine"), \
         patch("tools.sync_all_jobs.JobService") as mock_service_cls, \
         patch("tools.sync_all_jobs.WantedSyncer") as mock_wanted_cls, \
         patch("tools.sync_all_jobs.RememberSyncer") as mock_remember_cls:

        mock_service = MagicMock()
        mock_service.get_preset_params.return_value = None
        mock_service_cls.return_value = mock_service

        mock_wanted = AsyncMock()
        mock_wanted.sync.side_effect = PermissionError("쿠키가 만료되었습니다.")
        mock_wanted_cls.return_value = mock_wanted

        mock_remember = AsyncMock()
        mock_remember.sync.return_value = "Remember: 신규 3개"
        mock_remember_cls.return_value = mock_remember

        from tools.sync_all_jobs import sync_all_jobs
        result = await sync_all_jobs()

    assert "[Wanted]" in result
    assert "오류" in result
    assert "[Remember]" in result
    assert "Remember: 신규 3개" in result
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
pytest tests/test_tools.py::test_sync_all_jobs_returns_both_results tests/test_tools.py::test_sync_all_jobs_handles_partial_failure -v
```

Expected: FAIL (ImportError: `tools.sync_all_jobs` 없음)

- [ ] **Step 3: sync_all_jobs.py 구현**

`tools/sync_all_jobs.py` 신규 생성:

```python
import asyncio

from constants import DEFAULT_LIMIT_PAGES
from db.connection import get_engine
from db.models import SearchPreset
from services.jobs.job_service import JobService
from services.wanted.wanted_constants import WantedJobGroupId, WANTED
from services.wanted.wanted_syncer import WantedSyncer
from services.remember.remember_constants import REMEMBER
from services.remember.remember_syncer import RememberSyncer


async def sync_all_jobs(
    wanted_job_group_id: int = WantedJobGroupId.SERVER_DEVELOPER.value,
    wanted_job_ids: list[int] | None = None,
    wanted_years: list[int] | None = None,
    wanted_locations: str = "all",
    wanted_limit_pages: int | None = DEFAULT_LIMIT_PAGES,
    wanted_job_sort: str = "job.popularity_order",
    remember_limit_pages: int | None = DEFAULT_LIMIT_PAGES,
    remember_job_category_names: list[dict] | None = None,
    remember_min_experience: int = 0,
    remember_max_experience: int = 10,
) -> str:
    """모든 채용 사이트에서 채용공고를 병렬로 동기화한다."""
    engine = get_engine()
    wanted_service = JobService(engine)
    remember_service = JobService(engine)

    wanted_preset: SearchPreset | None = wanted_service.get_preset_params(WANTED)
    if wanted_preset:
        p = wanted_preset.params
        wanted_job_group_id = p.get("job_group_id", wanted_job_group_id)
        wanted_job_ids = p.get("job_ids", wanted_job_ids)
        wanted_years = p.get("years", wanted_years)
        wanted_locations = p.get("locations", wanted_locations)
        wanted_limit_pages = p.get("limit_pages", wanted_limit_pages)
        wanted_job_sort = p.get("job_sort", wanted_job_sort)

    remember_preset: SearchPreset | None = remember_service.get_preset_params(REMEMBER)
    if remember_preset:
        p = remember_preset.params
        remember_limit_pages = p.get("limit_pages", remember_limit_pages)
        remember_job_category_names = p.get("job_category_names", remember_job_category_names)
        remember_min_experience = p.get("min_experience", remember_min_experience)
        remember_max_experience = p.get("max_experience", remember_max_experience)

    wanted_result, remember_result = await asyncio.gather(
        WantedSyncer(wanted_service).sync(
            job_group_id=wanted_job_group_id,
            job_ids=wanted_job_ids,
            years=wanted_years,
            locations=wanted_locations,
            limit_pages=wanted_limit_pages,
            job_sort=wanted_job_sort,
        ),
        RememberSyncer(remember_service).sync(
            job_category_names=remember_job_category_names,
            min_experience=remember_min_experience,
            max_experience=remember_max_experience,
            limit_pages=remember_limit_pages,
        ),
        return_exceptions=True,
    )

    if isinstance(wanted_result, Exception):
        wanted_result = f"Wanted 오류: {wanted_result}"
    if isinstance(remember_result, Exception):
        remember_result = f"Remember 오류: {remember_result}"

    return f"[Wanted]\n{wanted_result}\n\n[Remember]\n{remember_result}"
```

- [ ] **Step 4: 테스트 실행 — 통과 확인**

```bash
pytest tests/test_tools.py::test_sync_all_jobs_returns_both_results tests/test_tools.py::test_sync_all_jobs_handles_partial_failure -v
```

Expected: 전부 PASS

- [ ] **Step 5: 커밋**

```bash
git add tools/sync_all_jobs.py tests/test_tools.py
git commit -m "feat: add sync_all_jobs tool with asyncio.gather parallelism"
```

---

## Task 8: main.py 등록 + 전체 테스트 실행

**Files:**
- Modify: `main.py`

- [ ] **Step 1: main.py에 sync_all_jobs 등록**

`main.py`:

```python
from fastmcp import FastMCP

from db.connection import create_tables
from tools.get_job_candidates import get_job_candidates
from tools.get_unapplied_jobs import get_unapplied_jobs
from tools.list_search_presets import list_search_presets
from tools.migrate_db import migrate_db
from tools.remember_sync_jobs import remember_sync_jobs
from tools.add_skill_keyword import add_skill_keyword
from tools.delete_skill_keyword import delete_skill_keyword
from tools.list_skill_keywords import list_skill_keywords
from tools.save_job_evaluations import save_job_evaluations
from tools.save_search_preset import save_search_preset
from tools.skip_jobs import skip_jobs
from tools.sync_all_jobs import sync_all_jobs
from tools.sync_applications import sync_applications
from tools.sync_job_details import sync_job_details
from tools.wanted_sync_jobs import wanted_sync_jobs

mcp = FastMCP("wanted-jobs")

mcp.tool()(wanted_sync_jobs)
mcp.tool()(remember_sync_jobs)
mcp.tool()(sync_all_jobs)
mcp.tool()(sync_applications)
mcp.tool()(get_unapplied_jobs)
mcp.tool()(save_search_preset)
mcp.tool()(list_search_presets)
mcp.tool()(sync_job_details)
mcp.tool()(get_job_candidates)
mcp.tool()(skip_jobs)
mcp.tool()(migrate_db)
mcp.tool()(save_job_evaluations)
mcp.tool()(add_skill_keyword)
mcp.tool()(list_skill_keywords)
mcp.tool()(delete_skill_keyword)

if __name__ == "__main__":
    create_tables()
    mcp.run()
```

- [ ] **Step 2: 전체 테스트 실행 — 모두 통과 확인**

```bash
pytest --tb=short -q
```

Expected: 전부 PASS, 0 errors

- [ ] **Step 3: 커밋**

```bash
git add main.py
git commit -m "feat: register sync_all_jobs in MCP server"
```
