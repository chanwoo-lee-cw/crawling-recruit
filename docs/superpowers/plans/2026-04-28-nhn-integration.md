# NHN 채용공고 통합 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** NHN 채용 API를 기존 Wanted/Remember와 동일한 패턴으로 통합하여 공고 동기화, 지원현황 동기화, 상세정보 수집을 MCP 툴로 제공한다.

**Architecture:** 기존 `services/{source}/` 패턴에 `services/nhn/` 폴더 추가. DB의 `platform_id` 컬럼을 INT → BIGINT로 마이그레이션(NHN ID가 int64). Detail syncer도 소스별 클래스로 분리하여 `sync_job_details` 툴이 dispatcher 역할을 한다.

**Tech Stack:** Python 3.11, SQLAlchemy 2.x, httpx, FastMCP, MySQL

---

## File Map

### 신규 생성
| 파일 | 역할 |
|------|------|
| `services/nhn/__init__.py` | 패키지 |
| `services/nhn/nhn_constants.py` | NHN source 상수, URL, TECH_GROUP_ID |
| `services/nhn/nhn_client.py` | 로그인, 공고목록, 지원현황, 상세 API 호출 |
| `services/nhn/nhn_syncer.py` | BaseSyncer 구현 — 공고 동기화 |
| `services/nhn/nhn_application_syncer.py` | BaseSyncer 구현 — 지원현황 동기화 |
| `services/nhn/nhn_detail_syncer.py` | BaseSyncer 구현 — 상세정보 동기화 |
| `services/wanted/wanted_detail_syncer.py` | 기존 sync_job_details 로직 이동 |
| `services/remember/remember_detail_syncer.py` | stub — 미지원 메시지 반환 |
| `tools/nhn_sync_jobs.py` | MCP 툴 — NHN 공고 동기화 |
| `tests/test_nhn.py` | NHN 파서 유닛 테스트 |

### 수정
| 파일 | 변경 내용 |
|------|-----------|
| `db/models/job.py` | `platform_id`: `Integer` → `BigInteger` |
| `db/models/application.py` | `platform_id`: `Integer` → `BigInteger` |
| `db/connection.py` | `migrate_bigint()` 추가 |
| `tools/migrate_db.py` | `migrate_bigint()` 체인 호출 |
| `services/jobs/job_service.py` | NHN 파서 3개 추가, `get_jobs_without_details` source 파라미터, `ALLOWED_PRESET_KEYS` + `JOB_BASE_URLS` 업데이트 |
| `tools/sync_applications.py` | NHN case 추가 |
| `tools/sync_job_details.py` | source param + WantedDetailSyncer/RememberDetailSyncer/NHNDetailSyncer dispatcher |
| `main.py` | `nhn_sync_jobs` 등록 |

---

## Task 1: DB BigInteger 마이그레이션

**Files:**
- Modify: `db/models/job.py`
- Modify: `db/models/application.py`
- Modify: `db/connection.py`
- Modify: `tools/migrate_db.py`

- [ ] **Step 1: `db/models/job.py` — `platform_id` 타입 변경**

```python
# 기존
from sqlalchemy import Integer, String, Boolean, DateTime, UniqueConstraint
platform_id: Mapped[int] = mapped_column(Integer, nullable=False)

# 변경 후 — BigInteger import 추가, platform_id 타입 변경
from sqlalchemy import BigInteger, Integer, String, Boolean, DateTime, UniqueConstraint
platform_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
```

- [ ] **Step 2: `db/models/application.py` — `platform_id` 타입 변경**

```python
# 기존
from sqlalchemy import Integer, String, DateTime, ForeignKey, UniqueConstraint
platform_id: Mapped[int] = mapped_column(Integer, nullable=False)

# 변경 후
from sqlalchemy import BigInteger, Integer, String, DateTime, ForeignKey, UniqueConstraint
platform_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
```

- [ ] **Step 3: `db/connection.py` — `migrate_bigint()` 추가**

파일 맨 아래 `migrate()` 함수 다음에 추가:

```python
def migrate_bigint(engine) -> str:
    """jobs, applications의 platform_id를 BIGINT로 변환. 멱등."""
    def is_bigint(conn, table):
        r = conn.execute(text(
            f"SELECT DATA_TYPE FROM information_schema.COLUMNS "
            f"WHERE TABLE_NAME='{table}' AND COLUMN_NAME='platform_id' AND TABLE_SCHEMA=DATABASE()"
        ))
        row = r.fetchone()
        return row and row[0].lower() == "bigint"

    with engine.connect() as conn:
        jobs_done = is_bigint(conn, "jobs")
        apps_done = is_bigint(conn, "applications")
        if jobs_done and apps_done:
            return "BigInteger 마이그레이션 이미 완료됨"
        if not jobs_done:
            conn.execute(text("ALTER TABLE jobs MODIFY platform_id BIGINT NOT NULL"))
        if not apps_done:
            conn.execute(text("ALTER TABLE applications MODIFY platform_id BIGINT NOT NULL"))
        conn.commit()
    return "BigInteger 마이그레이션 완료"
```

- [ ] **Step 4: `tools/migrate_db.py` — `migrate_bigint` 체인 추가**

```python
from db.connection import get_engine, migrate, migrate_bigint


def migrate_db() -> str:
    """기존 DB를 multi-source 스키마로 마이그레이션한다. 이미 완료된 경우 skip.

    주의: 실서비스 DB에서 실행 전 반드시 백업할 것.
    """
    try:
        engine = get_engine()
        result1 = migrate(engine)
        result2 = migrate_bigint(engine)
        return f"{result1} / {result2}"
    except Exception as e:
        return f"마이그레이션 오류: {e}"
```

- [ ] **Step 5: 기존 테스트 실행 — 모델 변경으로 회귀 없는지 확인**

```bash
pytest tests/ -v
```

Expected: 모든 기존 테스트 PASS (BigInteger는 하위 호환)

- [ ] **Step 6: 커밋**

```bash
git add db/models/job.py db/models/application.py db/connection.py tools/migrate_db.py
git commit -m "feat: migrate platform_id to BigInteger for NHN int64 IDs"
```

---

## Task 2: NHN 상수 및 디렉토리 생성

**Files:**
- Create: `services/nhn/__init__.py`
- Create: `services/nhn/nhn_constants.py`

- [ ] **Step 1: `services/nhn/__init__.py` 생성 (빈 파일)**

```python
```

- [ ] **Step 2: `services/nhn/nhn_detail_syncer.py` — stub 생성 (Task 7에서 완성)**

Task 3에서 `sync_job_details.py`가 이 파일을 import하므로 미리 stub을 만들어 둔다.

```python
from services.base_syncer import BaseSyncer


class NHNDetailSyncer(BaseSyncer):
    def sync(self, **kwargs) -> str:
        return "NHN 상세 동기화 미구현"
```

- [ ] **Step 3: `services/nhn/nhn_constants.py` 생성**

```python
NHN = "nhn"
NHN_JOB_BASE_URL = "https://careers.nhn.com/job-postings"


class NHNClientConst:
    LOGIN_URL = "https://careers.nhn.com/v1/accounts/sign-in"
    JOBS_URL = "https://careers.nhn.com/v1/job-postings"
    APPLICATIONS_URL = "https://careers.nhn.com/v1/applicants/me/job-postings"
    DETAIL_URL = "https://careers.nhn.com/v1/job-postings/{job_id}"
    TECH_GROUP_ID = "3645799730550663017"
    PAGE_SIZE = 30
```

- [ ] **Step 4: 커밋**

```bash
git add services/nhn/
git commit -m "feat: add NHN package structure, constants, and detail syncer stub"
```

---

## Task 3: Detail Syncer 리팩터 (Wanted / Remember)

기존 `sync_job_details.py`의 로직을 `WantedDetailSyncer`로 이동하고, `RememberDetailSyncer` stub 추가. `sync_job_details.py`는 dispatcher로 전환.

**Files:**
- Create: `services/wanted/wanted_detail_syncer.py`
- Create: `services/remember/remember_detail_syncer.py`
- Modify: `services/jobs/job_service.py` (get_jobs_without_details source param)
- Modify: `tools/sync_job_details.py`

- [ ] **Step 1: `services/wanted/wanted_detail_syncer.py` 생성**

기존 `tools/sync_job_details.py`의 로직을 그대로 이동:

```python
import time

from constants import CRAWL_DELAY_SECONDS
from domain import JobDetail
from services.base_syncer import BaseSyncer
from services.wanted.wanted_client import WantedClient
from services.wanted.wanted_constants import WANTED


class WantedDetailSyncer(BaseSyncer):
    def sync(
        self,
        job_ids: list[int] | None = None,
        limit: int | None = None,
    ) -> str:
        client = WantedClient()
        target_ids = self.service.get_jobs_without_details(
            source=WANTED, job_ids=job_ids, limit=limit
        )
        if not target_ids:
            return "처리할 공고가 없습니다."

        fetched: list[JobDetail] = []
        for i, job_id in enumerate(target_ids):
            if i > 0:
                time.sleep(CRAWL_DELAY_SECONDS)
            detail = client.fetch_job_detail(job_id)
            if detail is None:
                continue
            fetched.append(detail)

        if not fetched:
            return "상세 정보를 가져온 공고가 없습니다."
        return self.service.upsert_job_details(fetched)
```

- [ ] **Step 2: `services/remember/remember_detail_syncer.py` 생성 (stub)**

```python
from services.base_syncer import BaseSyncer


class RememberDetailSyncer(BaseSyncer):
    def sync(self, **kwargs) -> str:
        return "Remember 상세 동기화는 지원하지 않습니다."
```

- [ ] **Step 3: `services/jobs/job_service.py` — `get_jobs_without_details` source 파라미터 추가**

현재 코드 (line 223-234):
```python
@transactional()
def get_jobs_without_details(
    self,
    job_ids: list[int] | None = None,
    limit: int | None = None,
) -> list[int]:
    session = get_current_session()
    if job_ids is not None:
        existing = JobDetailRepository(session).find_existing_job_ids(job_ids)
        missing = [jid for jid in job_ids if jid not in existing]
        return missing[:limit] if limit is not None else missing
    return JobRepository(session).find_without_details(source=WANTED, limit=limit)
```

변경 후:
```python
@transactional()
def get_jobs_without_details(
    self,
    source: str = WANTED,
    job_ids: list[int] | None = None,
    limit: int | None = None,
) -> list[int]:
    session = get_current_session()
    if job_ids is not None:
        existing = JobDetailRepository(session).find_existing_job_ids(job_ids)
        missing = [jid for jid in job_ids if jid not in existing]
        return missing[:limit] if limit is not None else missing
    return JobRepository(session).find_without_details(source=source, limit=limit)
```

- [ ] **Step 4: `tools/sync_job_details.py` — dispatcher로 전환**

```python
from db.connection import get_engine
from services.jobs.job_service import JobService
from services.nhn.nhn_constants import NHN
from services.nhn.nhn_detail_syncer import NHNDetailSyncer
from services.remember.remember_constants import REMEMBER
from services.remember.remember_detail_syncer import RememberDetailSyncer
from services.wanted.wanted_constants import WANTED
from services.wanted.wanted_detail_syncer import WantedDetailSyncer


def sync_job_details(
    source: str = WANTED,
    job_ids: list[int] | None = None,
    limit: int | None = None,
) -> str:
    """공고 상세정보를 동기화한다. source: WANTED (기본), NHN. REMEMBER는 미지원."""
    service = JobService(get_engine())
    if source == REMEMBER:
        return RememberDetailSyncer(service).sync()
    if source == NHN:
        return NHNDetailSyncer(service).sync(job_ids=job_ids, limit=limit)
    return WantedDetailSyncer(service).sync(job_ids=job_ids, limit=limit)
```

Note: `NHNDetailSyncer`는 Task 7에서 생성. 임시로 import만 추가하고 파일 생성은 다음 task에서.

- [ ] **Step 5: 기존 테스트 실행 — 리팩터로 회귀 없는지 확인**

```bash
pytest tests/ -v
```

Expected: 모든 기존 테스트 PASS

- [ ] **Step 6: 커밋**

```bash
git add services/wanted/wanted_detail_syncer.py services/remember/remember_detail_syncer.py services/jobs/job_service.py tools/sync_job_details.py
git commit -m "refactor: extract WantedDetailSyncer/RememberDetailSyncer, add source param to get_jobs_without_details"
```

---

## Task 4: JobService NHN 파서 + 유닛 테스트

**Files:**
- Modify: `services/jobs/job_service.py`
- Create: `tests/test_nhn.py`

- [ ] **Step 1: `tests/test_nhn.py` — 파서 테스트 작성 (실패하는 테스트)**

```python
import pytest
from unittest.mock import MagicMock
from services.jobs.job_service import JobService
from services.nhn.nhn_constants import NHN

RAW_NHN_JOB = {
    "id": "4317632272881051418",
    "corporation": {
        "id": "3673339512358903254",
        "name": "NHN COMMERCE",
    },
    "name": "커머스 솔루션 QA 담당자",
    "finishYn": "N",
    "employeeType": {"name": "정규"},
    "jobSeries": [
        {"id": "aaa", "name": "QA"},
        {"id": "aaa", "name": "QA"},  # 중복
        {"id": "bbb", "name": "Backend"},
    ],
}

RAW_NHN_APPS = [
    {
        "jobPostingName": "백엔드 개발",
        "jobPostingId": "3710991316958061032",
        "applicationId": "4079920720933035925",
        "displayStepButtonCd": "application-completed",
        "finalSubmitYn": "Y",
        "finalSubmitDatetime": "2026-04-20 12:18",
    },
    {
        "jobPostingName": "미완료 지원",
        "jobPostingId": "1111111111111111111",
        "applicationId": "2222222222222222222",
        "displayStepButtonCd": "write",
        "finalSubmitYn": "N",
        "finalSubmitDatetime": None,
    },
]


def test_parse_nhn_job():
    service = JobService(engine=MagicMock())
    row = service._parse_nhn_job(RAW_NHN_JOB)
    assert row["source"] == NHN
    assert row["platform_id"] == 4317632272881051418
    assert row["company_id"] is None
    assert row["company_name"] == "NHN COMMERCE"
    assert row["title"] == "커머스 솔루션 QA 담당자"
    assert row["employment_type"] == "regular"
    assert row["location"] is None
    assert row["job_group_id"] is None
    assert row["category_tag_id"] is None
    assert row["is_active"] is True


def test_parse_nhn_applications_skips_incomplete():
    service = JobService(engine=MagicMock())
    result = service._parse_nhn_applications(RAW_NHN_APPS)
    # finalSubmitYn=N 항목은 제외
    assert len(result) == 1
    assert result[0]["job_platform_id"] == 3710991316958061032
    assert result[0]["platform_id"] == 4079920720933035925
    assert result[0]["status"] == "application-completed"
    # 시간 정규화: "HH:MM" → "HH:MM:00"
    assert result[0]["apply_time_str"] == "2026-04-20 12:18:00"
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
pytest tests/test_nhn.py -v
```

Expected: FAIL (메서드 미구현)

- [ ] **Step 3: `services/jobs/job_service.py` — NHN 상수 import 및 파서 추가**

파일 상단 import에 추가:
```python
from services.nhn.nhn_constants import NHN, NHN_JOB_BASE_URL
```

`ALLOWED_PRESET_KEYS` 에 `"job_series_ids"` 추가:
```python
ALLOWED_PRESET_KEYS = {
    "job_group_id", "job_ids", "years", "locations", "limit_pages",
    "job_category_names", "min_experience", "max_experience", "source",
    "job_series_ids",
}
```

`JOB_BASE_URLS` 에 NHN 추가:
```python
JOB_BASE_URLS = {
    WANTED: WANTED_JOB_BASE_URL,
    REMEMBER: REMEMBER_JOB_BASE_URL,
    NHN: NHN_JOB_BASE_URL,
}
```

`_parse_remember_job` 다음에 `_parse_nhn_job` 추가:
```python
def _parse_nhn_job(self, raw: dict) -> dict:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    emp_type_raw = (raw.get("employeeType") or {}).get("name")
    employment_type = self.EMPLOYMENT_TYPE_MAP.get(emp_type_raw) if emp_type_raw else None
    return {
        "source": NHN,
        "platform_id": int(raw["id"]),
        "company_id": None,
        "company_name": raw["corporation"]["name"],
        "title": raw["name"],
        "location": None,
        "employment_type": employment_type,
        "annual_from": None,
        "annual_to": None,
        "job_group_id": None,
        "category_tag_id": None,
        "is_active": True,
        "created_at": None,
        "synced_at": now,
        "updated_at": None,
    }
```

`_parse_remember_applications` 다음에 `_parse_nhn_applications` 추가:
```python
def _parse_nhn_applications(self, raw_apps: list[dict]) -> list[dict]:
    result = []
    for raw in raw_apps:
        if raw.get("finalSubmitYn") != "Y":
            continue
        apply_time_str = raw.get("finalSubmitDatetime")
        if apply_time_str and len(apply_time_str) == 16:
            apply_time_str = apply_time_str + ":00"
        result.append({
            "job_platform_id": int(raw["jobPostingId"]),
            "platform_id": int(raw["applicationId"]),
            "status": raw.get("displayStepButtonCd", ""),
            "apply_time_str": apply_time_str,
        })
    return result
```

`_parse_job` 분기에 NHN 추가:
```python
def _parse_job(self, raw: dict, source: str = WANTED) -> dict:
    if source == REMEMBER:
        return self._parse_remember_job(raw)
    if source == NHN:
        return self._parse_nhn_job(raw)
    return self._parse_wanted_job(raw)
```

`_parse_applications` 분기에 NHN 추가:
```python
def _parse_applications(self, raw_apps: list[dict], source: str) -> list[dict]:
    if source == REMEMBER:
        return self._parse_remember_applications(raw_apps)
    if source == NHN:
        return self._parse_nhn_applications(raw_apps)
    return self._parse_wanted_applications(raw_apps)
```

- [ ] **Step 4: 테스트 실행 — 통과 확인**

```bash
pytest tests/test_nhn.py -v
```

Expected: PASS

- [ ] **Step 5: 전체 테스트 실행 — 회귀 없는지 확인**

```bash
pytest tests/ -v
```

Expected: 모든 테스트 PASS

- [ ] **Step 6: 커밋**

```bash
git add services/jobs/job_service.py tests/test_nhn.py
git commit -m "feat: add NHN job/application parsers to JobService"
```

---

## Task 5: NHNClient

**Files:**
- Create: `services/nhn/nhn_client.py`

- [ ] **Step 1: `services/nhn/nhn_client.py` 생성**

```python
import os
import httpx
from dotenv import load_dotenv
from domain import JobDetail
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
```

- [ ] **Step 2: 커밋**

```bash
git add services/nhn/nhn_client.py
git commit -m "feat: add NHNClient with auto-login and job/application/detail API calls"
```

---

## Task 6: NHNSyncer + NHNApplicationSyncer

**Files:**
- Create: `services/nhn/nhn_syncer.py`
- Create: `services/nhn/nhn_application_syncer.py`

- [ ] **Step 1: `services/nhn/nhn_syncer.py` 생성**

```python
from services.base_syncer import BaseSyncer
from services.nhn.nhn_client import NHNClient
from services.nhn.nhn_constants import NHN, NHNClientConst


class NHNSyncer(BaseSyncer):
    def sync(
        self,
        job_group_id: str = NHNClientConst.TECH_GROUP_ID,
        job_series_ids: list[str] | None = None,
        limit_pages: int | None = None,
    ) -> str:
        try:
            client = NHNClient()
        except ValueError as e:
            return str(e)
        jobs = client.fetch_jobs(
            job_group_id=job_group_id,
            job_series_ids=job_series_ids,
            limit_pages=limit_pages,
        )
        full_sync = limit_pages is None
        return self.service.upsert_jobs(jobs, source=NHN, full_sync=full_sync)
```

- [ ] **Step 2: `services/nhn/nhn_application_syncer.py` 생성**

```python
from services.base_syncer import BaseSyncer
from services.nhn.nhn_client import NHNClient
from services.nhn.nhn_constants import NHN


class NHNApplicationSyncer(BaseSyncer):
    def sync(self) -> str:
        try:
            client = NHNClient()
            apps = client.fetch_applications()
            return self.service.upsert_applications(apps, source=NHN)
        except (PermissionError, ValueError) as e:
            return str(e)
        except Exception as e:
            return f"오류가 발생했습니다: {e}"
```

- [ ] **Step 3: 커밋**

```bash
git add services/nhn/nhn_syncer.py services/nhn/nhn_application_syncer.py
git commit -m "feat: add NHNSyncer and NHNApplicationSyncer"
```

---

## Task 7: NHNDetailSyncer + 파서 테스트

**Files:**
- Create: `services/nhn/nhn_detail_syncer.py`
- Modify: `tests/test_nhn.py`

- [ ] **Step 1: `tests/test_nhn.py` — `_parse_nhn_detail` 테스트 추가**

기존 파일에 아래 추가:

```python
from services.nhn.nhn_detail_syncer import NHNDetailSyncer

RAW_NHN_DETAIL = {
    "id": "4317632272881051418",
    "jobSeries": [
        {"id": "aaa", "name": "QA"},
        {"id": "aaa", "name": "QA"},   # 중복
        {"id": "bbb", "name": "Backend"},
    ],
    "jobPostingContentsItems": [
        {
            "title": "이런 분들을 찾고 있어요 (자격요건)",
            "contents": ["Python 3년 이상", "AWS 경험"],
        },
        {
            "title": "이런 분이면 더 좋아요 (우대사항)",
            "contents": ["FastAPI 경험자 우대"],
        },
        {
            "title": "주요업무",
            "contents": ["서비스 개발"],
        },
    ],
}


def test_parse_nhn_detail():
    parsed = NHNDetailSyncer._parse_nhn_detail(RAW_NHN_DETAIL)
    assert parsed["requirements"] == "Python 3년 이상\nAWS 경험"
    assert parsed["preferred_points"] == "FastAPI 경험자 우대"
    # 중복 제거: QA(id=aaa) 1개 + Backend(id=bbb) 1개
    assert len(parsed["skill_tags"]) == 2
    tag_names = {t["text"] for t in parsed["skill_tags"]}
    assert "QA" in tag_names
    assert "Backend" in tag_names


def test_parse_nhn_detail_missing_sections():
    raw = {"id": "1", "jobSeries": [], "jobPostingContentsItems": []}
    parsed = NHNDetailSyncer._parse_nhn_detail(raw)
    assert parsed["requirements"] is None
    assert parsed["preferred_points"] is None
    assert parsed["skill_tags"] == []
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
pytest tests/test_nhn.py::test_parse_nhn_detail tests/test_nhn.py::test_parse_nhn_detail_missing_sections -v
```

Expected: FAIL (NHNDetailSyncer 미구현)

- [ ] **Step 3: `services/nhn/nhn_detail_syncer.py` 생성**

```python
import time

from constants import CRAWL_DELAY_SECONDS
from domain import JobDetail
from services.base_syncer import BaseSyncer
from services.nhn.nhn_client import NHNClient
from services.nhn.nhn_constants import NHN


class NHNDetailSyncer(BaseSyncer):
    def sync(
        self,
        job_ids: list[int] | None = None,
        limit: int | None = None,
    ) -> str:
        try:
            client = NHNClient()
        except ValueError as e:
            return str(e)

        target_ids = self.service.get_jobs_without_details(
            source=NHN, job_ids=job_ids, limit=limit
        )
        if not target_ids:
            return "처리할 공고가 없습니다."

        fetched: list[JobDetail] = []
        for i, job_id in enumerate(target_ids):
            if i > 0:
                time.sleep(CRAWL_DELAY_SECONDS)
            raw_detail = client.fetch_job_detail(str(job_id))
            if raw_detail is None:
                continue
            parsed = self._parse_nhn_detail(raw_detail)
            fetched.append(JobDetail(
                job_id=job_id,
                requirements=parsed["requirements"],
                preferred_points=parsed["preferred_points"],
                skill_tags=parsed["skill_tags"],
            ))

        if not fetched:
            return "상세 정보를 가져온 공고가 없습니다."
        return self.service.upsert_job_details(fetched)

    @staticmethod
    def _parse_nhn_detail(raw: dict) -> dict:
        items = raw.get("jobPostingContentsItems") or []
        requirements = None
        preferred_points = None
        for item in items:
            title = item.get("title", "")
            contents = item.get("contents") or []
            text = "\n".join(contents) if contents else None
            if "자격요건" in title:
                requirements = text
            elif "우대사항" in title:
                preferred_points = text

        seen_ids: set = set()
        skill_tags: list[dict] = []
        for series in (raw.get("jobSeries") or []):
            sid = series.get("id")
            if sid and sid not in seen_ids:
                seen_ids.add(sid)
                skill_tags.append({"text": series["name"]})

        return {
            "requirements": requirements,
            "preferred_points": preferred_points,
            "skill_tags": skill_tags,
        }
```

- [ ] **Step 4: 테스트 실행 — 통과 확인**

```bash
pytest tests/test_nhn.py -v
```

Expected: 모든 테스트 PASS

- [ ] **Step 5: 전체 테스트 실행**

```bash
pytest tests/ -v
```

Expected: 모든 테스트 PASS

- [ ] **Step 6: 커밋**

```bash
git add services/nhn/nhn_detail_syncer.py tests/test_nhn.py
git commit -m "feat: add NHNDetailSyncer with jobPostingContentsItems parsing"
```

---

## Task 8: MCP 툴 연결 및 main.py 등록

**Files:**
- Create: `tools/nhn_sync_jobs.py`
- Modify: `tools/sync_applications.py`
- Modify: `main.py`

- [ ] **Step 1: `tools/nhn_sync_jobs.py` 생성**

```python
from constants import DEFAULT_LIMIT_PAGES
from db.connection import get_engine
from db.models import SearchPreset
from services.jobs.job_service import JobService
from services.nhn.nhn_constants import NHN, NHNClientConst
from services.nhn.nhn_syncer import NHNSyncer


def nhn_sync_jobs(
    job_group_id: str = NHNClientConst.TECH_GROUP_ID,
    job_series_ids: list[str] | None = None,
    limit_pages: int | None = DEFAULT_LIMIT_PAGES,
) -> str:
    """NHN 채용공고를 동기화한다."""
    engine = get_engine()
    service = JobService(engine)

    preset: SearchPreset | None = service.get_preset_params(NHN)
    if preset:
        p = preset.params
        job_group_id = p.get("job_group_id", job_group_id)
        job_series_ids = p.get("job_series_ids", job_series_ids)
        limit_pages = p.get("limit_pages", limit_pages)

    return NHNSyncer(service).sync(
        job_group_id=job_group_id,
        job_series_ids=job_series_ids,
        limit_pages=limit_pages,
    )
```

- [ ] **Step 2: `tools/sync_applications.py` — NHN case 추가**

```python
from services.nhn.nhn_application_syncer import NHNApplicationSyncer
from services.nhn.nhn_constants import NHN
from services.remember.remember_application_syncer import RememberApplicationSyncer
from services.remember.remember_constants import REMEMBER
from services.wanted.wanted_application_syncer import WantedApplicationSyncer
from services.wanted.wanted_constants import WANTED
from db.connection import get_engine
from services.jobs.job_service import JobService


def sync_applications(source: str = WANTED) -> str:
    """지원현황을 동기화한다. source: WANTED (기본), REMEMBER, NHN."""
    engine = get_engine()
    service = JobService(engine)

    if source == REMEMBER:
        return RememberApplicationSyncer(service).sync()
    if source == NHN:
        return NHNApplicationSyncer(service).sync()
    return WantedApplicationSyncer(service).sync()
```

- [ ] **Step 3: `main.py` — `nhn_sync_jobs` 등록**

기존 import/tool 목록에 추가:

```python
from tools.nhn_sync_jobs import nhn_sync_jobs

# ...
mcp.tool()(nhn_sync_jobs)
```

- [ ] **Step 4: 전체 테스트 실행 — 최종 회귀 확인**

```bash
pytest tests/ -v
```

Expected: 모든 테스트 PASS

- [ ] **Step 5: 커밋**

```bash
git add tools/nhn_sync_jobs.py tools/sync_applications.py main.py
git commit -m "feat: register NHN MCP tools (nhn_sync_jobs, sync_applications NHN)"
```

---

## 완료 체크리스트

- [ ] `pytest tests/ -v` 전체 PASS
- [ ] `db/models/job.py`, `db/models/application.py` — BigInteger 확인
- [ ] `services/nhn/` 폴더 6개 파일 존재
- [ ] `tools/nhn_sync_jobs.py` 존재
- [ ] `main.py`에 `nhn_sync_jobs` 등록
- [ ] `sync_applications`에 NHN case 존재
- [ ] `sync_job_details`에 source 파라미터 및 NHN/REMEMBER 분기 존재
- [ ] `.env`에 `NHN_EMAIL`, `NHN_PASSWORD` 추가 필요 (실행 전)
