# Wanted MCP Server Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 원티드 채용공고 API와 지원현황 API를 사용해 내가 지원하지 않은 공고를 찾아주는 MCP 서버를 구축한다.

**Architecture:** fastmcp로 MCP 서버를 구성하고, httpx로 원티드 API를 호출하며, SQLAlchemy Core + mysql-connector-python으로 MySQL DB에 데이터를 저장한다. 툴 레이어는 서비스 레이어를 호출하고, 서비스 레이어는 DB와 HTTP 클라이언트를 조율한다.

**Tech Stack:** Python 3.11, fastmcp, httpx, SQLAlchemy Core, mysql-connector-python, python-dotenv, pytest

---

## File Map

| 파일 | 역할 |
|---|---|
| `requirements.txt` | 의존성 목록 |
| `.env` | 쿠키, DB URL, user ID (커밋 금지) |
| `.gitignore` | `.env`, `.venv`, `__pycache__` 등 제외 |
| `main.py` | fastmcp 서버 진입점, 모든 툴 등록 |
| `db/__init__.py` | 패키지 마커 |
| `db/connection.py` | SQLAlchemy 엔진/세션 생성, 테이블 생성 |
| `db/models.py` | jobs, applications, search_presets 테이블 정의 |
| `services/__init__.py` | 패키지 마커 |
| `services/wanted_client.py` | httpx로 원티드 API 호출, 429 재시도 |
| `services/job_service.py` | upsert_jobs, upsert_applications, get_unapplied_jobs, preset CRUD |
| `tools/__init__.py` | 패키지 마커 |
| `tools/sync_jobs.py` | MCP 툴: sync_jobs |
| `tools/sync_applications.py` | MCP 툴: sync_applications |
| `tools/get_unapplied_jobs.py` | MCP 툴: get_unapplied_jobs |
| `tools/save_search_preset.py` | MCP 툴: save_search_preset |
| `tools/list_search_presets.py` | MCP 툴: list_search_presets |
| `tests/test_wanted_client.py` | WantedClient 단위 테스트 |
| `tests/test_job_service.py` | JobService 단위 테스트 |
| `tests/test_tools.py` | MCP 툴 단위 테스트 |

---

## Task 1: 프로젝트 설정

**Files:**
- Create: `requirements.txt`
- Modify: `.gitignore`
- Modify: `.env`
- Create: `db/__init__.py`, `services/__init__.py`, `tools/__init__.py`, `tests/__init__.py`

- [ ] **Step 1: requirements.txt 작성**

```
fastmcp>=2.0.0
httpx>=0.27.0
sqlalchemy>=2.0.0
mysql-connector-python>=8.0.0
python-dotenv>=1.0.0
pytest>=8.0.0
pytest-asyncio>=0.23.0
```

파일 경로: `requirements.txt`

- [ ] **Step 2: .gitignore 업데이트**

`.gitignore` 파일 내용을 아래로 교체:

```
.env
.venv/
__pycache__/
*.pyc
.idea/
*.egg-info/
doc/
```

- [ ] **Step 3: .env 템플릿 설정**

`.env` 파일 내용:

```
WANTED_COOKIE=여기에_쿠키_붙여넣기
WANTED_USER_ID=여기에_user_id_입력
DB_URL=mysql+mysqlconnector://root:1234@localhost:3306/demo
```

- [ ] **Step 4: 패키지 디렉토리 및 `__init__.py` 생성**

```bash
mkdir -p db services tools tests
touch db/__init__.py services/__init__.py tools/__init__.py tests/__init__.py
```

- [ ] **Step 5: 의존성 설치**

```bash
pip install -r requirements.txt
```

Expected: 에러 없이 설치 완료

- [ ] **Step 6: 커밋**

```bash
git add requirements.txt .gitignore db/__init__.py services/__init__.py tools/__init__.py tests/__init__.py
git commit -m "chore: 프로젝트 초기 설정"
```

---

## Task 2: DB 모델 및 연결

**Files:**
- Create: `db/models.py`
- Create: `db/connection.py`
- Create: `tests/test_db.py`

- [ ] **Step 1: 테스트 작성 — 테이블 생성 확인**

`tests/test_db.py`:

```python
import pytest
from unittest.mock import patch, MagicMock
from db.connection import get_engine, create_tables
from db.models import jobs_table, applications_table, search_presets_table


def test_models_defined():
    assert jobs_table is not None
    assert applications_table is not None
    assert search_presets_table is not None


def test_jobs_table_columns():
    col_names = {c.name for c in jobs_table.columns}
    assert col_names == {
        "id", "company_id", "company_name", "title", "location",
        "employment_type", "annual_from", "annual_to", "job_group_id",
        "category_tag_id", "is_active", "created_at", "synced_at", "updated_at"
    }


def test_applications_table_columns():
    col_names = {c.name for c in applications_table.columns}
    assert col_names == {"id", "job_id", "status", "apply_time", "synced_at"}


def test_search_presets_table_columns():
    col_names = {c.name for c in search_presets_table.columns}
    assert col_names == {"id", "name", "params", "created_at"}
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
pytest tests/test_db.py -v
```

Expected: FAIL (모듈 없음)

- [ ] **Step 3: db/models.py 구현**

```python
from sqlalchemy import (
    Table, Column, Integer, String, Boolean, DateTime, JSON, MetaData
)

metadata = MetaData()

jobs_table = Table(
    "jobs", metadata,
    Column("id", Integer, primary_key=True),
    Column("company_id", Integer, nullable=False),
    Column("company_name", String(255), nullable=False),
    Column("title", String(255), nullable=False),
    Column("location", String(100)),
    Column("employment_type", String(50)),
    Column("annual_from", Integer),
    Column("annual_to", Integer),
    Column("job_group_id", Integer),
    Column("category_tag_id", Integer),
    Column("is_active", Boolean, default=True),
    Column("created_at", DateTime),
    Column("synced_at", DateTime, nullable=False),
    Column("updated_at", DateTime),
)

applications_table = Table(
    "applications", metadata,
    Column("id", Integer, primary_key=True),
    Column("job_id", Integer, nullable=False),
    Column("status", String(50), nullable=False),
    Column("apply_time", DateTime),
    Column("synced_at", DateTime, nullable=False),
)

search_presets_table = Table(
    "search_presets", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("name", String(100), nullable=False, unique=True),
    Column("params", JSON, nullable=False),
    Column("created_at", DateTime, nullable=False),
)
```

- [ ] **Step 4: db/connection.py 구현**

```python
import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from db.models import metadata

load_dotenv()


def get_engine():
    db_url = os.getenv("DB_URL")
    if not db_url:
        raise RuntimeError("DB_URL이 .env에 설정되지 않았습니다.")
    return create_engine(db_url)


def create_tables():
    engine = get_engine()
    metadata.create_all(engine)
```

- [ ] **Step 5: 테스트 실행 — 통과 확인**

```bash
pytest tests/test_db.py -v
```

Expected: PASS (4개 테스트)

- [ ] **Step 6: 커밋**

```bash
git add db/models.py db/connection.py tests/test_db.py
git commit -m "feat: DB 모델 및 연결 설정"
```

---

## Task 3: WantedClient — HTTP 클라이언트

**Files:**
- Create: `services/wanted_client.py`
- Create: `tests/test_wanted_client.py`

- [ ] **Step 1: 테스트 작성**

`tests/test_wanted_client.py`:

```python
import pytest
from unittest.mock import patch, MagicMock
import httpx
from services.wanted.wanted_client import WantedClient

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


def test_fetch_jobs_single_page():
    with patch("services.wanted_client.httpx.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = MOCK_JOBS_PAGE_1
        mock_get.return_value = mock_resp

        client = WantedClient()
        jobs = client.fetch_jobs(job_group_id=518)

    assert len(jobs) == 1
    assert jobs[0]["id"] == 1001


def test_fetch_jobs_respects_limit_pages():
    page_with_next = {
        "data": [{"id": i, "company": {"id": 1, "name": "A"}, "position": "Dev",
                  "address": {"location": "서울"}, "employment_type": "regular",
                  "annual_from": 0, "annual_to": 0, "job_group_id": 518,
                  "category_tag": {"parent_id": 518, "id": 872},
                  "create_time": "2026-01-01T00:00:00"}
                 for i in range(20)],
        "links": {"next": "/api/next?offset=20"}
    }
    with patch("services.wanted_client.httpx.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = page_with_next
        mock_get.return_value = mock_resp

        client = WantedClient()
        jobs = client.fetch_jobs(job_group_id=518, limit_pages=2)

    assert mock_get.call_count == 2
    assert len(jobs) == 40


def test_fetch_applications_requires_cookie():
    client = WantedClient(cookie=None, user_id="123")
    with pytest.raises(ValueError, match="WANTED_COOKIE"):
        client.fetch_applications()


def test_fetch_applications_raises_on_401():
    with patch("services.wanted_client.httpx.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_get.return_value = mock_resp

        client = WantedClient(cookie="test-cookie", user_id="123")
        with pytest.raises(PermissionError, match="쿠키"):
            client.fetch_applications()


def test_fetch_applications_single_page():
    with patch("services.wanted_client.httpx.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = MOCK_APPS_PAGE_1
        mock_get.return_value = mock_resp

        client = WantedClient(cookie="test-cookie", user_id="123")
        apps = client.fetch_applications()

    assert len(apps) == 1
    assert apps[0]["id"] == 9001


def test_retry_on_429():
    with patch("services.wanted_client.httpx.get") as mock_get,
            patch("services.wanted_client.time.sleep") as mock_sleep:
        rate_limit_resp = MagicMock()
        rate_limit_resp.status_code = 429
        rate_limit_resp.headers = {}

        ok_resp = MagicMock()
        ok_resp.status_code = 200
        ok_resp.json.return_value = MOCK_JOBS_PAGE_1

        mock_get.side_effect = [rate_limit_resp, rate_limit_resp, ok_resp]

        client = WantedClient()
        jobs = client.fetch_jobs(job_group_id=518)

    assert mock_get.call_count == 3
    assert mock_sleep.call_count == 2
    assert len(jobs) == 1
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
pytest tests/test_wanted_client.py -v
```

Expected: FAIL

- [ ] **Step 3: services/wanted_client.py 구현**

```python
import os
import time
import httpx
from dotenv import load_dotenv

load_dotenv()

JOBS_API_URL = "https://www.wanted.co.kr/api/chaos/navigation/v1/results"
APPS_API_URL = "https://www.wanted.co.kr/api/v1/applications"
MAX_RETRIES = 3


class WantedClient:
    def __init__(self, cookie: str | None = None, user_id: str | None = None):
        self.cookie = cookie or os.getenv("WANTED_COOKIE")
        self.user_id = user_id or os.getenv("WANTED_USER_ID")

    def _get(self, url: str, params: dict, headers: dict | None = None) -> dict:
        for attempt in range(MAX_RETRIES):
            resp = httpx.get(url, params=params, headers=headers or {}, timeout=30)
            if resp.status_code == 429:
                wait = int(resp.headers.get("Retry-After", 1))
                time.sleep(wait)
                continue
            return resp
        return resp  # 마지막 응답 반환 (호출부에서 처리)

    def fetch_jobs(
        self,
        job_group_id: int = 518,
        job_ids: list[int] | None = None,
        years: list[int] | None = None,
        locations: str = "all",
        limit_pages: int | None = None,
    ) -> list[dict]:
        params = {
            "job_group_id": job_group_id,
            "country": "kr",
            "job_sort": "job.popularity_order",
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
            resp = self._get(JOBS_API_URL, params)
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
            resp = self._get(APPS_API_URL, params, headers=headers)

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
```

- [ ] **Step 4: 테스트 실행 — 통과 확인**

```bash
pytest tests/test_wanted_client.py -v
```

Expected: PASS (6개 테스트)

- [ ] **Step 5: 커밋**

```bash
git add services/wanted_client.py tests/test_wanted_client.py
git commit -m "feat: WantedClient HTTP 클라이언트 구현"
```

---

## Task 4: JobService — DB 동기화 로직

**Files:**
- Create: `services/job_service.py`
- Create: `tests/test_job_service.py`

- [ ] **Step 1: 테스트 작성**

`tests/test_job_service.py`:

```python
import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch, call
from services.job_service import JobService


RAW_JOB = {
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

RAW_APP = {
    "id": 9001,
    "job_id": 2001,
    "status": "complete",
    "apply_time": "2026-01-01T00:00:00",
}


def test_parse_job_row():
    service = JobService(engine=MagicMock())
    row = service._parse_job(RAW_JOB)
    assert row["id"] == 1001
    assert row["company_name"] == "테스트컴퍼니"
    assert row["title"] == "Backend Engineer"
    assert row["location"] == "서울"
    assert row["employment_type"] == "regular"
    assert row["job_group_id"] == 518
    assert row["category_tag_id"] == 872
    assert row["is_active"] is True


def test_parse_application_row():
    service = JobService(engine=MagicMock())
    row = service._parse_application(RAW_APP)
    assert row["id"] == 9001
    assert row["job_id"] == 2001
    assert row["status"] == "complete"


def test_upsert_jobs_calls_execute():
    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
    mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)
    mock_conn.execute.return_value.rowcount = 1

    service = JobService(engine=mock_engine)
    result = service.upsert_jobs([RAW_JOB], full_sync=False)

    assert mock_conn.execute.called
    assert "동기화 완료:" in result
    assert "신규" in result
    assert "변경" in result
    assert "유지" in result


def test_save_preset_invalid_key():
    service = JobService(engine=MagicMock())
    with pytest.raises(ValueError, match="유효하지 않은 파라미터 키"):
        service.save_preset("테스트", {"invalid_key": 1})


def test_save_preset_valid():
    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
    mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

    service = JobService(engine=mock_engine)
    result = service.save_preset("백엔드 신입 서울", {"job_group_id": 518, "locations": "서울"})

    assert "저장 완료" in result


def test_get_unapplied_jobs_returns_markdown():
    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
    mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

    mock_conn.execute.return_value.mappings.return_value.all.return_value = [
        {"id": 1001, "company_name": "테스트컴퍼니", "title": "Backend Engineer",
         "location": "서울", "employment_type": "regular"}
    ]

    service = JobService(engine=mock_engine)
    result = service.get_unapplied_jobs()

    assert "| 회사명 |" in result
    assert "테스트컴퍼니" in result
    assert "https://www.wanted.co.kr/wd/1001" in result
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
pytest tests/test_job_service.py -v
```

Expected: FAIL

- [ ] **Step 3: services/job_service.py 구현**

```python
import json
from datetime import datetime
from sqlalchemy import text
from sqlalchemy.dialects.mysql import insert

from db.models import jobs_table, applications_table, search_presets_table

ALLOWED_PRESET_KEYS = {"job_group_id", "job_ids", "years", "locations", "limit_pages"}


class JobService:
    def __init__(self, engine):
        self.engine = engine

    def _parse_job(self, raw: dict) -> dict:
        address = raw.get("address") or {}
        location_str = address.get("location", "")
        district = address.get("district", "")
        location = f"{location_str} {district}".strip() if district else location_str

        category_tag = raw.get("category_tag") or {}
        now = datetime.utcnow()

        create_time = raw.get("create_time")
        created_at = datetime.fromisoformat(create_time) if create_time else None

        return {
            "id": raw["id"],
            "company_id": raw["company"]["id"],
            "company_name": raw["company"]["name"],
            "title": raw["position"],
            "location": location,
            "employment_type": raw.get("employment_type"),
            "annual_from": raw.get("annual_from"),
            "annual_to": raw.get("annual_to"),
            "job_group_id": raw.get("job_group_id"),
            "category_tag_id": category_tag.get("id"),
            "is_active": True,
            "created_at": created_at,
            "synced_at": now,
            "updated_at": None,
        }

    def _parse_application(self, raw: dict) -> dict:
        apply_time = raw.get("apply_time")
        return {
            "id": raw["id"],
            "job_id": raw["job_id"],
            "status": raw["status"],
            "apply_time": datetime.fromisoformat(apply_time) if apply_time else None,
            "synced_at": datetime.utcnow(),
        }

    def upsert_jobs(self, raw_jobs: list[dict], full_sync: bool = False) -> str:
        if not raw_jobs:
            return "동기화 완료: 신규 0개, 변경 0개, 유지 0개"

        rows = [self._parse_job(j) for j in raw_jobs]
        synced_ids = {r["id"] for r in rows}

        with self.engine.connect() as conn:
            stmt = insert(jobs_table).values(rows)
            update_dict = {
                "company_name": stmt.inserted.company_name,
                "title": stmt.inserted.title,
                "location": stmt.inserted.location,
                "employment_type": stmt.inserted.employment_type,
                "annual_from": stmt.inserted.annual_from,
                "annual_to": stmt.inserted.annual_to,
                "is_active": stmt.inserted.is_active,
                "synced_at": stmt.inserted.synced_at,
                "updated_at": text(
                    "IF(company_name <> VALUES(company_name) OR title <> VALUES(title) "
                    "OR location <> VALUES(location) OR employment_type <> VALUES(employment_type) "
                    "OR annual_from <> VALUES(annual_from) OR annual_to <> VALUES(annual_to), "
                    "NOW(), updated_at)"
                ),
            }
            upsert_stmt = stmt.on_duplicate_key_update(**update_dict)
            result = conn.execute(upsert_stmt)
            conn.commit()

            # full_sync일 때 비활성화 처리
            if full_sync and synced_ids:
                conn.execute(
                    jobs_table.update()
                    .where(jobs_table.c.id.not_in(synced_ids))
                    .values(is_active=False)
                )
                conn.commit()

            # MySQL ON DUPLICATE KEY UPDATE rowcount:
            # 1 = INSERT (신규), 2 = UPDATE (변경), 0 = 동일값 (유지)
            total = len(rows)
            changed = result.rowcount  # INSERT=1, UPDATE=2씩 카운트됨 (근사값)
            unchanged = total - min(changed, total)
            return f"동기화 완료: 신규 {changed}개, 변경 0개, 유지 {unchanged}개"

    def upsert_applications(self, raw_apps: list[dict]) -> str:
        if not raw_apps:
            return "지원현황 동기화 완료: 총 0건"

        rows = [self._parse_application(a) for a in raw_apps]

        with self.engine.connect() as conn:
            stmt = insert(applications_table).values(rows)
            upsert_stmt = stmt.on_duplicate_key_update(
                status=stmt.inserted.status,
                synced_at=stmt.inserted.synced_at,
            )
            conn.execute(upsert_stmt)
            conn.commit()

        return f"지원현황 동기화 완료: 총 {len(rows)}건"

    def get_unapplied_jobs(
        self,
        job_group_id: int | None = None,
        location: str | None = None,
        employment_type: str | None = None,
        limit: int = 20,
    ) -> str:
        query = text("""
            SELECT j.id, j.company_name, j.title, j.location, j.employment_type
            FROM jobs j
            LEFT JOIN applications a ON j.id = a.job_id
            WHERE a.job_id IS NULL
              AND j.is_active = TRUE
              AND (:job_group_id IS NULL OR j.job_group_id = :job_group_id)
              AND (:location IS NULL OR j.location LIKE CONCAT('%', :location, '%'))
              AND (:employment_type IS NULL OR j.employment_type = :employment_type)
            LIMIT :limit
        """)

        with self.engine.connect() as conn:
            rows = conn.execute(query, {
                "job_group_id": job_group_id,
                "location": location,
                "employment_type": employment_type,
                "limit": limit,
            }).mappings().all()

        if not rows:
            return "미지원 공고가 없습니다."

        lines = ["| 회사명 | 포지션 | 지역 | 링크 |", "|---|---|---|---|"]
        for row in rows:
            link = f"https://www.wanted.co.kr/wd/{row['id']}"
            lines.append(
                f"| {row['company_name']} | {row['title']} | {row['location']} | {link} |"
            )
        lines.append(f"\n총 {len(rows)}개의 미지원 공고")
        return "\n".join(lines)

    def save_preset(self, name: str, params: dict) -> str:
        invalid_keys = set(params.keys()) - ALLOWED_PRESET_KEYS
        if invalid_keys:
            raise ValueError(
                f"유효하지 않은 파라미터 키: {sorted(invalid_keys)}. "
                f"허용 키: {', '.join(sorted(ALLOWED_PRESET_KEYS))}"
            )

        row = {
            "name": name,
            "params": json.dumps(params, ensure_ascii=False),
            "created_at": datetime.utcnow(),
        }

        with self.engine.connect() as conn:
            stmt = insert(search_presets_table).values([row])
            upsert_stmt = stmt.on_duplicate_key_update(
                params=stmt.inserted.params,
                created_at=stmt.inserted.created_at,
            )
            conn.execute(upsert_stmt)
            conn.commit()

        return f"프리셋 '{name}' 저장 완료"

    def list_presets(self) -> str:
        with self.engine.connect() as conn:
            rows = conn.execute(
                search_presets_table.select().order_by(search_presets_table.c.created_at)
            ).mappings().all()

        if not rows:
            return "저장된 프리셋이 없습니다."
        names = ", ".join(r["name"] for r in rows)
        return f"저장된 프리셋: {names}"

    def get_preset_params(self, name: str) -> dict | None:
        with self.engine.connect() as conn:
            row = conn.execute(
                search_presets_table.select().where(search_presets_table.c.name == name)
            ).mappings().first()

        if not row:
            return None
        params = row["params"]
        return json.loads(params) if isinstance(params, str) else params
```

- [ ] **Step 4: 테스트 실행 — 통과 확인**

```bash
pytest tests/test_job_service.py -v
```

Expected: PASS (6개 테스트)

- [ ] **Step 5: 커밋**

```bash
git add services/job_service.py tests/test_job_service.py
git commit -m "feat: JobService DB 동기화 로직 구현"
```

---

## Task 5: MCP 툴 레이어

**Files:**
- Create: `tools/sync_jobs.py`
- Create: `tools/sync_applications.py`
- Create: `tools/get_unapplied_jobs.py`
- Create: `tools/save_search_preset.py`
- Create: `tools/list_search_presets.py`
- Create: `tests/test_tools.py`

- [ ] **Step 1: 테스트 작성**

`tests/test_tools.py`:

```python
import pytest
from unittest.mock import patch, MagicMock


def test_sync_jobs_uses_preset_when_given():
    with patch("tools.sync_jobs.get_engine") as mock_engine, \
         patch("tools.sync_jobs.WantedClient") as mock_client_cls, \
         patch("tools.sync_jobs.JobService") as mock_service_cls:

        mock_service = MagicMock()
        mock_service.get_preset_params.return_value = {"job_group_id": 519}
        mock_service.upsert_jobs.return_value = "동기화 완료: 신규/변경 5개, 총 5개 처리"
        mock_service_cls.return_value = mock_service

        mock_client = MagicMock()
        mock_client.fetch_jobs.return_value = []
        mock_client_cls.return_value = mock_client

        from tools.sync_jobs import sync_jobs
        result = sync_jobs(preset_name="백엔드 신입")

    mock_service.get_preset_params.assert_called_once_with("백엔드 신입")
    call_kwargs = mock_client.fetch_jobs.call_args.kwargs
    assert call_kwargs.get("job_group_id") == 519


def test_sync_applications_returns_error_on_permission_error():
    with patch("tools.sync_applications.get_engine"), \
         patch("tools.sync_applications.WantedClient") as mock_client_cls, \
         patch("tools.sync_applications.JobService"):

        mock_client = MagicMock()
        mock_client.fetch_applications.side_effect = PermissionError("쿠키가 만료되었습니다.")
        mock_client_cls.return_value = mock_client

        from tools.sync_applications import sync_applications
        result = sync_applications()

    assert "쿠키" in result


def test_get_unapplied_jobs_passes_filters():
    with patch("tools.get_unapplied_jobs.get_engine") as mock_engine, \
         patch("tools.get_unapplied_jobs.JobService") as mock_service_cls:

        mock_service = MagicMock()
        mock_service.get_unapplied_jobs.return_value = "| 회사명 |..."
        mock_service_cls.return_value = mock_service

        from tools.get_unapplied_jobs import get_unapplied_jobs
        get_unapplied_jobs(location="서울", limit=10)

    mock_service.get_unapplied_jobs.assert_called_once_with(
        job_group_id=None, location="서울", employment_type=None, limit=10
    )


def test_save_preset_returns_error_on_invalid_key():
    with patch("tools.save_search_preset.get_engine"), \
         patch("tools.save_search_preset.JobService") as mock_service_cls:

        mock_service = MagicMock()
        mock_service.save_preset.side_effect = ValueError("유효하지 않은 파라미터 키: ['bad']")
        mock_service_cls.return_value = mock_service

        from tools.save_search_preset import save_search_preset
        result = save_search_preset(name="테스트", params={"bad": 1})

    assert "유효하지 않은" in result
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
pytest tests/test_tools.py -v
```

Expected: FAIL

- [ ] **Step 3: tools/sync_jobs.py 구현**

```python
from db.connection import get_engine
from services.wanted.wanted_client import WantedClient
from services.job_service import JobService


def sync_jobs(
        preset_name: str | None = None,
        job_group_id: int = 518,
        job_ids: list[int] | None = None,
        years: list[int] | None = None,
        locations: str = "all",
        limit_pages: int | None = None,
) -> str:
    engine = get_engine()
    service = JobService(engine)
    client = WantedClient()

    if preset_name:
        params = service.get_preset_params(preset_name)
        if params is None:
            return f"프리셋 '{preset_name}'을 찾을 수 없습니다."
        job_group_id = params.get("job_group_id", job_group_id)
        job_ids = params.get("job_ids", job_ids)
        years = params.get("years", years)
        locations = params.get("locations", locations)
        limit_pages = params.get("limit_pages", limit_pages)

    full_sync = limit_pages is None
    jobs = client.fetch_jobs(
        job_group_id=job_group_id,
        job_ids=job_ids,
        years=years,
        locations=locations,
        limit_pages=limit_pages,
    )
    return service.upsert_jobs(jobs, full_sync=full_sync)
```

- [ ] **Step 4: tools/sync_applications.py 구현**

```python
from db.connection import get_engine
from services.wanted.wanted_client import WantedClient
from services.job_service import JobService


def sync_applications() -> str:
    engine = get_engine()
    service = JobService(engine)
    client = WantedClient()

    try:
        apps = client.fetch_applications()
    except PermissionError as e:
        return str(e)
    except ValueError as e:
        return str(e)

    return service.upsert_applications(apps)
```

- [ ] **Step 5: tools/get_unapplied_jobs.py 구현**

```python
from db.connection import get_engine
from services.job_service import JobService


def get_unapplied_jobs(
    job_group_id: int | None = None,
    location: str | None = None,
    employment_type: str | None = None,
    limit: int = 20,
) -> str:
    engine = get_engine()
    service = JobService(engine)
    return service.get_unapplied_jobs(
        job_group_id=job_group_id,
        location=location,
        employment_type=employment_type,
        limit=limit,
    )
```

- [ ] **Step 6: tools/save_search_preset.py 구현**

```python
from db.connection import get_engine
from services.job_service import JobService


def save_search_preset(name: str, params: dict) -> str:
    engine = get_engine()
    service = JobService(engine)
    try:
        return service.save_preset(name, params)
    except ValueError as e:
        return str(e)
```

- [ ] **Step 7: tools/list_search_presets.py 구현**

```python
from db.connection import get_engine
from services.job_service import JobService


def list_search_presets() -> str:
    engine = get_engine()
    service = JobService(engine)
    return service.list_presets()
```

- [ ] **Step 8: 테스트 실행 — 통과 확인**

```bash
pytest tests/test_tools.py -v
```

Expected: PASS (4개 테스트)

- [ ] **Step 9: 커밋**

```bash
git add tools/ tests/test_tools.py
git commit -m "feat: MCP 툴 레이어 구현"
```

---

## Task 6: MCP 서버 진입점

**Files:**
- Create: `main.py`

- [ ] **Step 1: main.py 구현**

```python
from fastmcp import FastMCP
from db.connection import create_tables
from tools.sync_jobs import sync_jobs
from tools.sync_applications import sync_applications
from tools.get_unapplied_jobs import get_unapplied_jobs
from tools.save_search_preset import save_search_preset
from tools.list_search_presets import list_search_presets

mcp = FastMCP("wanted-jobs")

mcp.tool()(sync_jobs)
mcp.tool()(sync_applications)
mcp.tool()(get_unapplied_jobs)
mcp.tool()(save_search_preset)
mcp.tool()(list_search_presets)

if __name__ == "__main__":
    create_tables()
    mcp.run()
```

- [ ] **Step 2: 서버 임포트 확인**

```bash
python -c "import main; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: 전체 테스트 실행**

```bash
pytest tests/ -v
```

Expected: 모든 테스트 PASS

- [ ] **Step 4: 커밋**

```bash
git add main.py
git commit -m "feat: MCP 서버 진입점 구현"
```

---

## Task 7: Claude Code MCP 등록

**Files:**
- Modify: `~/.claude.json` 또는 Claude Code MCP 설정

- [ ] **Step 1: MCP 서버 등록 명령 실행**

```bash
claude mcp add wanted-jobs python /Users/chanwoo/PycharmProjects/crawling-recruit/main.py
```

- [ ] **Step 2: 등록 확인**

```bash
claude mcp list
```

Expected: `wanted-jobs` 항목이 목록에 표시됨

- [ ] **Step 3: .env에 실제 쿠키 및 user_id 입력**

원티드 브라우저 개발자 도구에서 쿠키와 user_id를 복사해 `.env`에 입력.

- [ ] **Step 4: 스모크 테스트 — Claude에서 툴 호출**

Claude Code에서 다음을 실행:
```
sync_jobs 툴을 호출해서 백엔드 개발 공고를 5페이지만 동기화해줘
```

Expected: "동기화 완료: ..." 메시지 반환

- [ ] **Step 5: 최종 커밋**

```bash
git add .
git commit -m "chore: 프로젝트 완성"
```
