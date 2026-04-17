# Remeber 플랫폼 통합 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remeber 채용공고·지원현황을 기존 jobs/applications 테이블에 통합해 `get_unapplied_jobs`, `get_job_candidates`, `skip_jobs` 툴이 두 플랫폼을 자동으로 커버하게 한다.

**Architecture:** `jobs`·`applications` 테이블에 `internal_id`(AUTO_INCREMENT PK), `source`, `platform_id`를 추가해 multi-source를 지원한다. `get_unapplied_job_rows`/`get_unapplied_jobs`는 `(company_name, title)` 서브쿼리로 cross-platform 중복 지원 필터링을 한다. `RememberClient`를 신규 생성하고 `sync_jobs(source="remember")` / `sync_applications(source="remember")`로 라우팅한다.

**Tech Stack:** Python 3.11, SQLAlchemy 2.x (`DeclarativeBase`, `Session`, `insert().on_duplicate_key_update()`, `tuple_()`), FastMCP, MySQL, httpx, pytest

**Spec:** `docs/superpowers/specs/2026-04-18-remember-integration-design.md`

---

## File Map

| 파일 | 변경 유형 |
|------|-----------|
| `db/models.py` | 수정 |
| `db/connection.py` | 수정 |
| `domain.py` | 수정 |
| `services/remember_client.py` | 신규 |
| `services/job_service.py` | 수정 |
| `tools/migrate_db.py` | 신규 |
| `tools/sync_jobs.py` | 수정 |
| `tools/sync_applications.py` | 수정 |
| `tools/get_unapplied_jobs.py` | 수정 |
| `tools/get_job_candidates.py` | 수정 |
| `main.py` | 수정 |
| `tests/test_db.py` | 수정 |
| `tests/test_remember_client.py` | 신규 |
| `tests/test_job_service.py` | 수정 |
| `tests/test_tools.py` | 수정 |

---

### Task 1: `db/models.py` — ORM 스키마 업데이트

**Files:**
- Modify: `db/models.py`
- Modify: `tests/test_db.py`

- [ ] **Step 1: `db/models.py` 전체 교체**

```python
from datetime import datetime
from typing import Optional, List
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import Integer, String, Boolean, DateTime, JSON, Text, ForeignKey, UniqueConstraint


class Base(DeclarativeBase):
    pass


class Job(Base):
    __tablename__ = "jobs"

    internal_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="wanted")
    platform_id: Mapped[int] = mapped_column(Integer, nullable=False)
    company_id: Mapped[Optional[int]] = mapped_column(Integer)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[Optional[str]] = mapped_column(String(100))
    employment_type: Mapped[Optional[str]] = mapped_column(String(50))
    annual_from: Mapped[Optional[int]] = mapped_column(Integer)
    annual_to: Mapped[Optional[int]] = mapped_column(Integer)
    job_group_id: Mapped[Optional[int]] = mapped_column(Integer)
    category_tag_id: Mapped[Optional[int]] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    synced_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    __table_args__ = (UniqueConstraint("source", "platform_id", name="uq_source_platform"),)

    detail: Mapped[Optional["JobDetail"]] = relationship(back_populates="job", uselist=False)
    applications: Mapped[List["Application"]] = relationship(back_populates="job")
    skip: Mapped[Optional["JobSkip"]] = relationship(back_populates="job", uselist=False)


class Application(Base):
    __tablename__ = "applications"

    internal_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="wanted")
    platform_id: Mapped[int] = mapped_column(Integer, nullable=False)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.internal_id"), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    apply_time: Mapped[Optional[datetime]] = mapped_column(DateTime)
    synced_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    __table_args__ = (UniqueConstraint("source", "platform_id", name="uq_app_source_platform"),)

    job: Mapped[Optional["Job"]] = relationship(back_populates="applications")


class JobDetail(Base):
    __tablename__ = "job_details"

    job_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("jobs.internal_id", ondelete="CASCADE"), primary_key=True
    )
    requirements: Mapped[Optional[str]] = mapped_column(Text)
    preferred_points: Mapped[Optional[str]] = mapped_column(Text)
    skill_tags: Mapped[Optional[list]] = mapped_column(JSON)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    job: Mapped["Job"] = relationship(back_populates="detail")


class SearchPreset(Base):
    __tablename__ = "search_presets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    params: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class JobSkip(Base):
    __tablename__ = "job_skips"

    job_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("jobs.internal_id", ondelete="CASCADE"), primary_key=True
    )
    reason: Mapped[Optional[str]] = mapped_column(String(255))
    skipped_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    job: Mapped["Job"] = relationship(back_populates="skip")
```

- [ ] **Step 2: import 확인**

```bash
python -c "from db.models import Job, Application, JobDetail, SearchPreset, JobSkip; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: `tests/test_db.py` 업데이트**

`test_jobs_table_columns`과 `test_applications_table_columns`을 아래로 교체:

```python
def test_jobs_table_columns():
    col_names = {c.name for c in Job.__table__.columns}
    assert col_names == {
        "internal_id", "source", "platform_id",
        "company_id", "company_name", "title", "location",
        "employment_type", "annual_from", "annual_to", "job_group_id",
        "category_tag_id", "is_active", "created_at", "synced_at", "updated_at"
    }


def test_applications_table_columns():
    col_names = {c.name for c in Application.__table__.columns}
    assert col_names == {"internal_id", "source", "platform_id", "job_id", "status", "apply_time", "synced_at"}
```

- [ ] **Step 4: 테스트 실행**

```bash
pytest tests/test_db.py -v
```

Expected: 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add db/models.py tests/test_db.py
git commit -m "feat: jobs/applications 테이블 multi-source 스키마로 ORM 업데이트"
```

---

### Task 2: `domain.py` — `JobCandidate` 필드 추가 + 영향받는 테스트 수정

**Files:**
- Modify: `domain.py`
- Modify: `tests/test_job_service.py`

- [ ] **Step 1: `domain.py`의 `JobCandidate` 교체**

`JobCandidate` 클래스를 아래로 교체 (`SkillTag`와 `JobDetail`은 변경 없음):

```python
@dataclass
class JobCandidate:
    """DB 읽기 경로 전용: get_unapplied_job_rows → get_recommended_jobs → get_job_candidates"""
    internal_id: int
    source: str
    platform_id: int
    company_name: str
    title: str
    location: str | None
    employment_type: str | None
    requirements: str | None
    preferred_points: str | None
    skill_tags: list[SkillTag]
    fetched_at: datetime | None

    @classmethod
    def from_row(cls, row) -> "JobCandidate":
        """DB row(dict/Mapping) → JobCandidate. skill_tags JSON 파싱 포함."""
        raw_tags = row.get("skill_tags") or []
        if isinstance(raw_tags, str):
            try:
                raw_tags = json.loads(raw_tags)
            except (json.JSONDecodeError, TypeError):
                raw_tags = []
        return cls(
            internal_id=row["internal_id"],
            source=row["source"],
            platform_id=row["platform_id"],
            company_name=row["company_name"],
            title=row["title"],
            location=row.get("location"),
            employment_type=row.get("employment_type"),
            requirements=row.get("requirements"),
            preferred_points=row.get("preferred_points"),
            skill_tags=[SkillTag(text=t["text"]) for t in raw_tags if t.get("text")],
            fetched_at=row.get("fetched_at"),
        )
```

- [ ] **Step 2: `tests/test_job_service.py`에서 `JobCandidate` 사용 부분 업데이트**

`test_get_recommended_jobs_scores_skill_tags` 안의 `JobCandidate(id=..., ...)` 호출 3개를 아래로 교체:

```python
        JobCandidate(
            internal_id=1, source="wanted", platform_id=1001,
            company_name="A사", title="Backend",
            location="서울", employment_type="regular",
            requirements="Python req", preferred_points="AWS 우대",
            skill_tags=[SkillTag(text="Python"), SkillTag(text="AWS")],
            fetched_at=now,
        ),
        JobCandidate(
            internal_id=2, source="wanted", platform_id=1002,
            company_name="B사", title="Frontend",
            location="서울", employment_type="regular",
            requirements="React req", preferred_points=None,
            skill_tags=[SkillTag(text="React")],
            fetched_at=now,
        ),
        JobCandidate(
            internal_id=3, source="wanted", platform_id=1003,
            company_name="C사", title="Fullstack",
            location="서울", employment_type="regular",
            requirements=None, preferred_points=None,
            skill_tags=[], fetched_at=None,
        ),
```

`assert candidates[0].id == 1` → `assert candidates[0].internal_id == 1`
`assert candidates[1].id == 2` → `assert candidates[1].internal_id == 2`

- [ ] **Step 3: `test_job_candidate_from_row_*` 테스트 업데이트**

`test_job_candidate_from_row_parses_skill_tags`의 row dict를:
```python
    row = {
        "internal_id": 1, "source": "wanted", "platform_id": 1001,
        "company_name": "A사", "title": "Backend",
        "location": "서울", "employment_type": "regular",
        "requirements": "req", "preferred_points": None,
        "skill_tags": [{"tag_type_id": 1, "text": "Python"}, {"tag_type_id": 2, "text": "AWS"}],
        "fetched_at": None,
    }
```
`assert candidate.id == 1` → `assert candidate.internal_id == 1`

`test_job_candidate_from_row_handles_null_skill_tags`의 row dict를:
```python
    row = {
        "internal_id": 2, "source": "wanted", "platform_id": 1002,
        "company_name": "B사", "title": "Frontend",
        "location": None, "employment_type": None,
        "requirements": None, "preferred_points": None,
        "skill_tags": None, "fetched_at": None,
    }
```

- [ ] **Step 4: `test_get_unapplied_job_rows_*` 테스트 mock 데이터 업데이트**

`test_get_unapplied_job_rows_returns_list`와 `test_get_unapplied_job_rows_with_skip_join`의 mock row를:
```python
        {
            "internal_id": 1001, "source": "wanted", "platform_id": 1001,
            "company_name": "테스트컴퍼니", "title": "Backend Engineer",
            "location": "서울", "employment_type": "regular",
            "requirements": None, "preferred_points": None,
            "skill_tags": None, "fetched_at": None,
        }
```
`rows[0].id == 1001` → `rows[0].internal_id == 1001`

- [ ] **Step 5: `test_get_unapplied_jobs_returns_markdown` mock 데이터 업데이트**

mock row를:
```python
        {"internal_id": 1001, "source": "wanted", "platform_id": 1001,
         "company_name": "테스트컴퍼니", "title": "Backend Engineer",
         "location": "서울", "employment_type": "regular"}
```
URL 어서션: `assert "https://www.wanted.co.kr/wd/1001" in result` 유지 (platform_id=1001이므로)

- [ ] **Step 6: 테스트 실행 — 일부 FAIL 확인 (domain 변경은 됐으나 service 메서드 미변경)**

```bash
pytest tests/test_job_service.py -v
```

Expected: `test_parse_job_row`, `test_get_unapplied_job_rows_*`, `test_get_unapplied_jobs_*` FAIL (service 미변경), 나머지 PASS

- [ ] **Step 7: Commit**

```bash
git add domain.py tests/test_job_service.py
git commit -m "feat: JobCandidate에 internal_id/source/platform_id 추가"
```

---

### Task 3: `db/connection.py` — `migrate()` 함수 + `tools/migrate_db.py` + `main.py`

**Files:**
- Modify: `db/connection.py`
- Create: `tools/migrate_db.py`
- Modify: `main.py`

- [ ] **Step 1: `db/connection.py`에 `migrate()` 함수 추가**

파일 끝에 추가:

```python
from sqlalchemy import text


def migrate(engine) -> str:
    """기존 DB를 multi-source 스키마로 마이그레이션. 멱등: 이미 완료된 경우 skip."""
    with engine.connect() as conn:
        result = conn.execute(text("SHOW COLUMNS FROM jobs LIKE 'platform_id'"))
        if result.fetchone():
            return "마이그레이션 이미 완료됨"

        # 1. FK 제약 제거
        conn.execute(text("ALTER TABLE applications DROP FOREIGN KEY applications_ibfk_1"))
        conn.execute(text("ALTER TABLE job_details DROP FOREIGN KEY job_details_ibfk_1"))
        conn.execute(text("ALTER TABLE job_skips DROP FOREIGN KEY job_skips_ibfk_1"))

        # 2. jobs: PK DROP + id를 platform_id로 rename (AUTO_INCREMENT 제거 포함)
        conn.execute(text(
            "ALTER TABLE jobs DROP PRIMARY KEY, CHANGE COLUMN id platform_id INT NOT NULL"
        ))

        # 3. internal_id AUTO_INCREMENT PK 추가
        conn.execute(text(
            "ALTER TABLE jobs ADD COLUMN internal_id INT AUTO_INCREMENT PRIMARY KEY FIRST"
        ))

        # 4. source 컬럼 + UNIQUE KEY
        conn.execute(text(
            "ALTER TABLE jobs ADD COLUMN source VARCHAR(20) NOT NULL DEFAULT 'wanted'"
        ))
        conn.execute(text(
            "ALTER TABLE jobs ADD UNIQUE KEY uq_source_platform (source, platform_id)"
        ))

        # 5. applications: FK 업데이트 전 job_id 값 재매핑
        conn.execute(text(
            "UPDATE applications a JOIN jobs j ON a.job_id = j.platform_id AND j.source = 'wanted' "
            "SET a.job_id = j.internal_id"
        ))
        conn.execute(text(
            "UPDATE job_details jd JOIN jobs j ON jd.job_id = j.platform_id AND j.source = 'wanted' "
            "SET jd.job_id = j.internal_id"
        ))
        conn.execute(text(
            "UPDATE job_skips js JOIN jobs j ON js.job_id = j.platform_id AND j.source = 'wanted' "
            "SET js.job_id = j.internal_id"
        ))

        # 6. applications 테이블 PK 교체
        conn.execute(text("ALTER TABLE applications DROP PRIMARY KEY, CHANGE COLUMN id platform_id INT NOT NULL"))
        conn.execute(text("ALTER TABLE applications ADD COLUMN internal_id INT AUTO_INCREMENT PRIMARY KEY FIRST"))
        conn.execute(text("ALTER TABLE applications ADD COLUMN source VARCHAR(20) NOT NULL DEFAULT 'wanted'"))
        conn.execute(text("ALTER TABLE applications ADD UNIQUE KEY uq_app_source_platform (source, platform_id)"))

        # 7. FK 재추가
        conn.execute(text(
            "ALTER TABLE applications ADD CONSTRAINT applications_ibfk_1 "
            "FOREIGN KEY (job_id) REFERENCES jobs(internal_id) ON DELETE CASCADE"
        ))
        conn.execute(text(
            "ALTER TABLE job_details ADD CONSTRAINT job_details_ibfk_1 "
            "FOREIGN KEY (job_id) REFERENCES jobs(internal_id) ON DELETE CASCADE"
        ))
        conn.execute(text(
            "ALTER TABLE job_skips ADD CONSTRAINT job_skips_ibfk_1 "
            "FOREIGN KEY (job_id) REFERENCES jobs(internal_id) ON DELETE CASCADE"
        ))

        conn.commit()

    return "마이그레이션 완료"
```

- [ ] **Step 2: `tools/migrate_db.py` 생성**

```python
from db.connection import get_engine, migrate


def migrate_db() -> str:
    """기존 DB를 multi-source 스키마로 마이그레이션한다. 이미 완료된 경우 skip.

    주의: 실서비스 DB에서 실행 전 반드시 백업할 것.
    """
    try:
        engine = get_engine()
        return migrate(engine)
    except Exception as e:
        return f"마이그레이션 오류: {e}"
```

- [ ] **Step 3: `main.py`에 `migrate_db` 툴 등록**

```python
from tools.migrate_db import migrate_db
# ...
mcp.tool()(migrate_db)
```

- [ ] **Step 4: import 확인**

```bash
python -c "from main import mcp; print('OK')"
```

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add db/connection.py tools/migrate_db.py main.py
git commit -m "feat: DB 마이그레이션 함수 및 migrate_db MCP 툴 추가"
```

---

### Task 4: `services/remember_client.py` — RememberClient

**Files:**
- Create: `services/remember_client.py`
- Create: `tests/test_remember_client.py`

- [ ] **Step 1: `tests/test_remember_client.py` 작성 (실패 테스트 먼저)**

```python
import pytest
from unittest.mock import patch, MagicMock


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


def test_fetch_jobs_success():
    with patch("services.remember_client.httpx") as mock_httpx:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": [SAMPLE_JOB],
            "meta": {"total_pages": 1, "page": 1},
        }
        mock_httpx.post.return_value = mock_resp

        from services.remember_client import RememberClient
        client = RememberClient()
        jobs = client.fetch_jobs(job_category_names=[{"level1": "SW개발", "level2": "백엔드"}])

    assert len(jobs) == 1
    assert jobs[0]["id"] == 308098
    assert jobs[0]["qualifications"] == "Python 3년 이상"
    assert jobs[0]["organization"]["name"] == "(주)이스트소프트"


def test_fetch_applications_success():
    with patch("services.remember_client.httpx") as mock_httpx, \
         patch.dict("os.environ", {"REMEMBER_COOKIE": "test_cookie"}):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": [SAMPLE_APPLICATION_JOB],
            "meta": {"total_pages": 1, "page": 1},
        }
        mock_httpx.get.return_value = mock_resp

        from services.remember_client import RememberClient
        client = RememberClient()
        apps = client.fetch_applications()

    assert len(apps) == 1
    assert apps[0]["id"] == 303872
    assert apps[0]["application"]["id"] == 3428290
    assert apps[0]["application"]["status"] == "applied"


def test_fetch_applications_raises_on_missing_cookie():
    with patch.dict("os.environ", {}, clear=True):
        from services.remember_client import RememberClient
        client = RememberClient()
        with pytest.raises(ValueError, match="REMEMBER_COOKIE"):
            client.fetch_applications()


def test_fetch_applications_raises_on_expired_cookie():
    with patch("services.remember_client.httpx") as mock_httpx, \
         patch.dict("os.environ", {"REMEMBER_COOKIE": "expired"}):
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_httpx.get.return_value = mock_resp

        from services.remember_client import RememberClient
        client = RememberClient()
        with pytest.raises(PermissionError, match="만료"):
            client.fetch_applications()


def test_fetch_jobs_http_error():
    with patch("services.remember_client.httpx") as mock_httpx:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = Exception("500 Server Error")
        mock_httpx.post.return_value = mock_resp

        from services.remember_client import RememberClient
        client = RememberClient()
        with pytest.raises(Exception, match="500"):
            client.fetch_jobs(job_category_names=[{"level1": "SW개발", "level2": "백엔드"}])
```

- [ ] **Step 2: 테스트 실행 → FAIL 확인**

```bash
pytest tests/test_remember_client.py -v
```

Expected: 5 tests FAIL (`remember_client` 모듈 없음)

- [ ] **Step 3: `services/remember_client.py` 구현**

```python
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
```

- [ ] **Step 4: 테스트 실행 → PASS 확인**

```bash
pytest tests/test_remember_client.py -v
```

Expected: 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add services/remember_client.py tests/test_remember_client.py
git commit -m "feat: RememberClient 추가 (fetch_jobs, fetch_applications)"
```

---

### Task 5: `services/job_service.py` — `_parse_job` 분리 + `upsert_jobs` source-aware

**Files:**
- Modify: `services/job_service.py`
- Modify: `tests/test_job_service.py`

- [ ] **Step 1: `test_parse_job_row` 업데이트 후 새 테스트 추가**

`test_parse_job_row`에서:
```python
    assert row["id"] == 1001
```
→
```python
    assert row["platform_id"] == 1001
    assert row["source"] == "wanted"
```
`row["id"]` 어서션 제거.

파일 끝에 추가:
```python
def test_parse_remember_job():
    raw = {
        "id": 308098,
        "title": "백엔드 개발",
        "organization": {"name": "(주)이스트소프트"},
        "addresses": [{"address_level1": "서울특별시", "address_level2": "서초구"}],
        "min_salary": None,
        "max_salary": None,
    }
    service = JobService(engine=MagicMock())
    row = service._parse_job(raw, source="remember")
    assert row["platform_id"] == 308098
    assert row["source"] == "remember"
    assert row["company_name"] == "(주)이스트소프트"
    assert row["location"] == "서울특별시 서초구"
    assert row["employment_type"] is None
    assert row["company_id"] is None


def test_upsert_jobs_remember_source():
    raw_remember_job = {
        "id": 308098,
        "title": "백엔드 개발",
        "organization": {"name": "(주)이스트소프트"},
        "addresses": [{"address_level1": "서울특별시", "address_level2": "서초구"}],
        "qualifications": "Python 3년",
        "preferred_qualifications": "FastAPI 경험",
        "min_salary": None,
        "max_salary": None,
    }
    mock_engine = MagicMock()
    with patch("services.job_service.Session") as MockSession:
        mock_session = MagicMock()
        MockSession.return_value.__enter__ = MagicMock(return_value=mock_session)
        MockSession.return_value.__exit__ = MagicMock(return_value=False)

        upsert_result = MagicMock()
        upsert_result.rowcount = 1
        # execute 호출 순서: 1) existing_pairs, 2) upsert, 3) internal_id_map, 4) detail_upsert
        mock_session.execute.side_effect = [
            MagicMock(**{"all.return_value": []}),  # existing_pairs
            upsert_result,                           # upsert
            MagicMock(**{"all.return_value": []}),  # internal_id_map (빈 결과 — detail 저장 skip)
        ]

        service = JobService(engine=mock_engine)
        result = service.upsert_jobs([raw_remember_job], source="remember", full_sync=False)

    assert "동기화 완료" in result
```

- [ ] **Step 2: 테스트 실행 → FAIL 확인**

```bash
pytest tests/test_job_service.py::test_parse_remember_job \
       tests/test_job_service.py::test_upsert_jobs_remember_source -v
```

Expected: 2 tests FAIL

- [ ] **Step 3: `job_service.py` import에 `tuple_` 추가**

```python
from sqlalchemy import select, update, text, tuple_
```

- [ ] **Step 4: `_parse_job` 분리 구현**

기존 `_parse_job` 메서드를 아래 세 메서드로 교체:

```python
def _parse_wanted_job(self, raw: dict) -> dict:
    address = raw.get("address") or {}
    location_str = address.get("location", "")
    district = address.get("district", "")
    location = f"{location_str} {district}".strip() if district else location_str

    category_tag = raw.get("category_tag") or {}
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    create_time = raw.get("create_time")
    created_at = datetime.fromisoformat(create_time) if create_time else None

    return {
        "source": "wanted",
        "platform_id": raw["id"],
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

def _parse_remember_job(self, raw: dict) -> dict:
    addresses = raw.get("addresses") or []
    if addresses:
        addr = addresses[0]
        parts = [addr.get("address_level1", ""), addr.get("address_level2", "")]
        location = " ".join(p for p in parts if p).strip() or None
    else:
        location = None

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    return {
        "source": "remember",
        "platform_id": raw["id"],
        "company_id": None,
        "company_name": raw["organization"]["name"],
        "title": raw["title"],
        "location": location,
        "employment_type": None,
        "annual_from": raw.get("min_salary"),
        "annual_to": raw.get("max_salary"),
        "job_group_id": None,
        "category_tag_id": None,
        "is_active": True,
        "created_at": None,
        "synced_at": now,
        "updated_at": None,
    }

def _parse_job(self, raw: dict, source: str = "wanted") -> dict:
    if source == "remember":
        return self._parse_remember_job(raw)
    return self._parse_wanted_job(raw)
```

- [ ] **Step 5: `upsert_jobs` source-aware로 교체**

기존 `upsert_jobs` 메서드를 아래로 교체:

```python
def upsert_jobs(self, raw_jobs: list[dict], source: str = "wanted", full_sync: bool = False) -> str:
    if not raw_jobs:
        return "동기화 완료: 신규 0개, 변경 0개, 유지 0개"

    rows = [self._parse_job(j, source=source) for j in raw_jobs]
    synced_pairs = [(source, r["platform_id"]) for r in rows]

    with Session(self.engine) as session:
        existing_pairs = set(session.execute(
            select(Job.source, Job.platform_id)
            .where(tuple_(Job.source, Job.platform_id).in_(synced_pairs))
        ).all())
        new_count = len(rows) - len(existing_pairs)

        stmt = insert(Job.__table__).values(rows)
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
                "IF(new.company_name <> jobs.company_name OR new.title <> jobs.title "
                "OR new.location <> jobs.location OR new.employment_type <> jobs.employment_type "
                "OR new.annual_from <> jobs.annual_from OR new.annual_to <> jobs.annual_to, "
                "NOW(), jobs.updated_at)"
            ),
        }
        upsert_stmt = stmt.on_duplicate_key_update(**update_dict)
        result = session.execute(upsert_stmt)
        session.commit()

        if full_sync and synced_pairs:
            session.execute(
                update(Job)
                .where(Job.source == source)
                .where(tuple_(Job.source, Job.platform_id).not_in(synced_pairs))
                .where(Job.is_active == True)
                .values(is_active=False)
            )
            session.commit()

        if source == "remember":
            platform_ids = [r["platform_id"] for r in rows]
            internal_id_map = {row.platform_id: row.internal_id for row in session.execute(
                select(Job.platform_id, Job.internal_id)
                .where(Job.source == "remember")
                .where(Job.platform_id.in_(platform_ids))
            ).all()}
            now = rows[0]["synced_at"]
            detail_rows = []
            for raw_job in raw_jobs:
                internal_id = internal_id_map.get(raw_job["id"])
                if internal_id:
                    detail_rows.append({
                        "job_id": internal_id,
                        "requirements": raw_job.get("qualifications"),
                        "preferred_points": raw_job.get("preferred_qualifications"),
                        "skill_tags": [],
                        "fetched_at": now,
                    })
            if detail_rows:
                detail_stmt = insert(OrmJobDetail.__table__).values(detail_rows)
                detail_upsert = detail_stmt.on_duplicate_key_update(
                    requirements=detail_stmt.inserted.requirements,
                    preferred_points=detail_stmt.inserted.preferred_points,
                    skill_tags=detail_stmt.inserted.skill_tags,
                    fetched_at=detail_stmt.inserted.fetched_at,
                )
                session.execute(detail_upsert)
                session.commit()

        updated_count = (result.rowcount - new_count) // 2
        unchanged_count = len(rows) - new_count - updated_count
        return f"동기화 완료: 신규 {new_count}개, 변경 {updated_count}개, 유지 {unchanged_count}개"
```

- [ ] **Step 6: 기존 `test_upsert_jobs_calls_execute` 업데이트**

`mock_session.scalars.return_value.all.return_value = []` →
`mock_session.execute.return_value.all.return_value = []`

`service.upsert_jobs([RAW_JOB], full_sync=False)` 유지 (source 기본값 "wanted")

어서션:
```python
    assert mock_session.execute.called
    assert "동기화 완료: 신규 1개" in result
```

- [ ] **Step 7: 테스트 실행 → PASS 확인**

```bash
pytest tests/test_job_service.py::test_parse_job_row \
       tests/test_job_service.py::test_parse_remember_job \
       tests/test_job_service.py::test_upsert_jobs_calls_execute \
       tests/test_job_service.py::test_upsert_jobs_remember_source -v
```

Expected: 4 tests PASS

- [ ] **Step 8: Commit**

```bash
git add services/job_service.py tests/test_job_service.py
git commit -m "feat: _parse_job source 분리 및 upsert_jobs multi-source 지원"
```

---

### Task 6: `services/job_service.py` — `upsert_applications` source-aware

**Files:**
- Modify: `services/job_service.py`
- Modify: `tests/test_job_service.py`

- [ ] **Step 1: 새 테스트 추가**

`tests/test_job_service.py` 끝에 추가:

```python
def test_parse_application_row_wanted():
    service = JobService(engine=MagicMock())
    # _parse_application은 이제 upsert_applications 내부에서 처리하므로
    # upsert_applications의 source="wanted" 경로를 직접 검증
    mock_engine = MagicMock()
    with patch("services.job_service.Session") as MockSession:
        mock_session = MagicMock()
        MockSession.return_value.__enter__ = MagicMock(return_value=mock_session)
        MockSession.return_value.__exit__ = MagicMock(return_value=False)
        # job_id 조회 mock
        job_row = MagicMock()
        job_row.platform_id = 2001
        job_row.internal_id = 99
        # execute 호출 순서: 1) job_id_map 조회, 2) upsert
        mock_session.execute.side_effect = [
            MagicMock(**{"all.return_value": [job_row]}),  # job_id_map
            MagicMock(),                                    # upsert
        ]

        service = JobService(engine=mock_engine)
        result = service.upsert_applications([RAW_APP], source="wanted")

    assert "1건" in result


def test_upsert_applications_remember_source():
    raw_app = {
        "id": 303872,
        "title": "System Engineer",
        "organization": {"name": "(주)휴머스온"},
        "application": {
            "id": 3428290,
            "status": "applied",
            "applied_at": "2026-04-12T18:28:24.676+09:00",
        },
    }
    mock_engine = MagicMock()
    with patch("services.job_service.Session") as MockSession:
        mock_session = MagicMock()
        MockSession.return_value.__enter__ = MagicMock(return_value=mock_session)
        MockSession.return_value.__exit__ = MagicMock(return_value=False)
        job_row = MagicMock()
        job_row.platform_id = 303872
        job_row.internal_id = 77
        # execute 호출 순서: 1) job_id_map 조회, 2) upsert
        mock_session.execute.side_effect = [
            MagicMock(**{"all.return_value": [job_row]}),  # job_id_map
            MagicMock(),                                    # upsert
        ]

        service = JobService(engine=mock_engine)
        result = service.upsert_applications([raw_app], source="remember")

    assert "1건" in result


def test_upsert_applications_empty():
    service = JobService(engine=MagicMock())
    result = service.upsert_applications([])
    assert "0건" in result
```

- [ ] **Step 2: 테스트 실행 → FAIL 확인**

```bash
pytest tests/test_job_service.py::test_parse_application_row_wanted \
       tests/test_job_service.py::test_upsert_applications_remember_source -v
```

Expected: FAIL

- [ ] **Step 3: `_parse_application` 제거 + `upsert_applications` 교체**

기존 `_parse_application` 메서드 삭제.

기존 `upsert_applications` 메서드를 아래로 교체:

```python
def upsert_applications(self, raw_apps: list[dict], source: str = "wanted") -> str:
    if not raw_apps:
        return "지원현황 동기화 완료: 총 0건"

    now = datetime.now(timezone.utc).replace(tzinfo=None)

    with Session(self.engine) as session:
        if source == "wanted":
            job_platform_ids = [app["job_id"] for app in raw_apps]
        else:
            job_platform_ids = [app["id"] for app in raw_apps]

        job_id_map = {row.platform_id: row.internal_id for row in session.execute(
            select(Job.platform_id, Job.internal_id)
            .where(Job.source == source)
            .where(Job.platform_id.in_(job_platform_ids))
        ).all()}

        rows = []
        for app in raw_apps:
            if source == "wanted":
                job_platform_id = app["job_id"]
                platform_id = app["id"]
                status = app["status"]
                apply_time_str = app.get("apply_time")
            else:
                job_platform_id = app["id"]
                application = app.get("application")
                if not application:
                    continue
                platform_id = application["id"]
                status = application["status"]
                apply_time_str = application.get("applied_at")

            job_internal_id = job_id_map.get(job_platform_id)
            if job_internal_id is None:
                continue

            apply_time = datetime.fromisoformat(apply_time_str).replace(tzinfo=None) if apply_time_str else None
            rows.append({
                "source": source,
                "platform_id": platform_id,
                "job_id": job_internal_id,
                "status": status,
                "apply_time": apply_time,
                "synced_at": now,
            })

        if not rows:
            return "지원현황 동기화 완료: 총 0건"

        stmt = insert(Application.__table__).values(rows)
        upsert_stmt = stmt.on_duplicate_key_update(
            status=stmt.inserted.status,
            synced_at=stmt.inserted.synced_at,
        )
        session.execute(upsert_stmt)
        session.commit()

    return f"지원현황 동기화 완료: 총 {len(rows)}건"
```

- [ ] **Step 4: 기존 `test_parse_application_row` 제거 또는 업데이트**

`_parse_application`이 더 이상 없으므로 `test_parse_application_row` 테스트를 삭제.

- [ ] **Step 5: 테스트 실행 → PASS 확인**

```bash
pytest tests/test_job_service.py -v
```

Expected: 전체 PASS (삭제한 test_parse_application_row 제외)

- [ ] **Step 6: Commit**

```bash
git add services/job_service.py tests/test_job_service.py
git commit -m "feat: upsert_applications multi-source 지원 (Wanted/Remeber)"
```

---

### Task 7: `services/job_service.py` — Query 메서드 + `ALLOWED_PRESET_KEYS`

**Files:**
- Modify: `services/job_service.py`
- Modify: `tests/test_job_service.py`

- [ ] **Step 1: 새 테스트 추가**

`tests/test_job_service.py` 끝에 추가:

```python
def test_get_unapplied_job_rows_cross_platform_filter():
    mock_engine = MagicMock()
    with patch("services.job_service.Session") as MockSession:
        mock_session = MagicMock()
        MockSession.return_value.__enter__ = MagicMock(return_value=mock_session)
        MockSession.return_value.__exit__ = MagicMock(return_value=False)

        mock_session.execute.return_value.mappings.return_value.all.return_value = [
            {
                "internal_id": 1001, "source": "wanted", "platform_id": 1001,
                "company_name": "테스트컴퍼니", "title": "Backend Engineer",
                "location": "서울", "employment_type": "regular",
                "requirements": None, "preferred_points": None,
                "skill_tags": None, "fetched_at": None,
            }
        ]

        service = JobService(engine=mock_engine)
        rows = service.get_unapplied_job_rows()

    assert isinstance(rows, list)
    assert len(rows) == 1
    assert rows[0].internal_id == 1001
    assert rows[0].source == "wanted"
    assert rows[0].platform_id == 1001


def test_get_unapplied_jobs_includes_internal_id():
    mock_engine = MagicMock()
    with patch("services.job_service.Session") as MockSession:
        mock_session = MagicMock()
        MockSession.return_value.__enter__ = MagicMock(return_value=mock_session)
        MockSession.return_value.__exit__ = MagicMock(return_value=False)

        mock_session.execute.return_value.mappings.return_value.all.return_value = [
            {"internal_id": 42, "source": "wanted", "platform_id": 1001,
             "company_name": "테스트컴퍼니", "title": "Backend Engineer",
             "location": "서울", "employment_type": "regular"}
        ]

        service = JobService(engine=mock_engine)
        result = service.get_unapplied_jobs()

    assert "| 42 |" in result
    assert "https://www.wanted.co.kr/wd/1001" in result


def test_get_unapplied_jobs_remember_url():
    mock_engine = MagicMock()
    with patch("services.job_service.Session") as MockSession:
        mock_session = MagicMock()
        MockSession.return_value.__enter__ = MagicMock(return_value=mock_session)
        MockSession.return_value.__exit__ = MagicMock(return_value=False)

        mock_session.execute.return_value.mappings.return_value.all.return_value = [
            {"internal_id": 99, "source": "remember", "platform_id": 308098,
             "company_name": "이스트소프트", "title": "백엔드 개발",
             "location": "서울 서초구", "employment_type": None}
        ]

        service = JobService(engine=mock_engine)
        result = service.get_unapplied_jobs()

    assert "https://career.rememberapp.co.kr/job/308098" in result
    assert "| 99 |" in result


def test_save_preset_remember_keys():
    service = JobService(engine=MagicMock())
    with pytest.raises(ValueError):
        service.save_preset("테스트", {"unknown_key": 1})

    mock_engine = MagicMock()
    with patch("services.job_service.Session") as MockSession:
        mock_session = MagicMock()
        MockSession.return_value.__enter__ = MagicMock(return_value=mock_session)
        MockSession.return_value.__exit__ = MagicMock(return_value=False)
        service = JobService(engine=mock_engine)
        result = service.save_preset("리멤버 백엔드", {
            "source": "remember",
            "job_category_names": [{"level1": "SW개발", "level2": "백엔드"}],
            "min_experience": 2,
            "max_experience": 5,
        })
    assert "저장 완료" in result
```

- [ ] **Step 2: 테스트 실행 → FAIL 확인**

```bash
pytest tests/test_job_service.py::test_get_unapplied_job_rows_cross_platform_filter \
       tests/test_job_service.py::test_get_unapplied_jobs_includes_internal_id \
       tests/test_job_service.py::test_get_unapplied_jobs_remember_url \
       tests/test_job_service.py::test_save_preset_remember_keys -v
```

Expected: 4 tests FAIL

- [ ] **Step 3: `ALLOWED_PRESET_KEYS` 확장**

```python
# 변경 전
ALLOWED_PRESET_KEYS = {"job_group_id", "job_ids", "years", "locations", "limit_pages"}

# 변경 후
ALLOWED_PRESET_KEYS = {
    "job_group_id", "job_ids", "years", "locations", "limit_pages",
    "job_category_names", "min_experience", "max_experience", "source",
}
```

- [ ] **Step 4: URL 상수 추가**

`WANTED_JOB_BASE_URL` 아래에 추가:

```python
REMEMBER_JOB_BASE_URL = "https://career.rememberapp.co.kr/job"

JOB_BASE_URLS = {
    "wanted": WANTED_JOB_BASE_URL,
    "remember": REMEMBER_JOB_BASE_URL,
}
```

- [ ] **Step 5: `get_unapplied_job_rows` 교체**

```python
def get_unapplied_job_rows(
    self,
    job_group_id: int | None = None,
    location: str | None = None,
    employment_type: str | None = None,
) -> list[JobCandidate]:
    from sqlalchemy import tuple_
    if employment_type:
        employment_type = self.EMPLOYMENT_TYPE_MAP.get(employment_type, employment_type)

    applied_pairs = (
        select(Job.company_name, Job.title)
        .join(Application, Job.internal_id == Application.job_id)
    )

    stmt = (
        select(
            Job.internal_id, Job.source, Job.platform_id,
            Job.company_name, Job.title, Job.location, Job.employment_type,
            OrmJobDetail.requirements, OrmJobDetail.preferred_points,
            OrmJobDetail.skill_tags, OrmJobDetail.fetched_at,
        )
        .outerjoin(OrmJobDetail, Job.internal_id == OrmJobDetail.job_id)
        .outerjoin(JobSkip, Job.internal_id == JobSkip.job_id)
        .where(tuple_(Job.company_name, Job.title).not_in(applied_pairs))
        .where(JobSkip.job_id.is_(None))
        .where(Job.is_active.is_(True))
    )

    if job_group_id is not None:
        stmt = stmt.where(Job.job_group_id == job_group_id)
    if location:
        stmt = stmt.where(Job.location.ilike(f"%{location}%"))
    if employment_type:
        stmt = stmt.where(Job.employment_type == employment_type)

    with Session(self.engine) as session:
        rows = session.execute(stmt).mappings().all()

    return [JobCandidate.from_row(r) for r in rows]
```

- [ ] **Step 6: `get_unapplied_jobs` 교체**

```python
def get_unapplied_jobs(
    self,
    job_group_id: int | None = None,
    location: str | None = None,
    employment_type: str | None = None,
    limit: int = 20,
) -> str:
    from sqlalchemy import tuple_
    if employment_type:
        employment_type = self.EMPLOYMENT_TYPE_MAP.get(employment_type, employment_type)

    applied_pairs = (
        select(Job.company_name, Job.title)
        .join(Application, Job.internal_id == Application.job_id)
    )

    stmt = (
        select(
            Job.internal_id, Job.source, Job.platform_id,
            Job.company_name, Job.title, Job.location, Job.employment_type,
        )
        .outerjoin(JobSkip, Job.internal_id == JobSkip.job_id)
        .where(tuple_(Job.company_name, Job.title).not_in(applied_pairs))
        .where(JobSkip.job_id.is_(None))
        .where(Job.is_active.is_(True))
    )

    if job_group_id is not None:
        stmt = stmt.where(Job.job_group_id == job_group_id)
    if location:
        stmt = stmt.where(Job.location.ilike(f"%{location}%"))
    if employment_type:
        stmt = stmt.where(Job.employment_type == employment_type)
    stmt = stmt.limit(limit)

    with Session(self.engine) as session:
        rows = session.execute(stmt).mappings().all()

    if not rows:
        return "미지원 공고가 없습니다."

    lines = ["| internal_id | 회사명 | 포지션 | 지역 | 링크 |", "|---|---|---|---|---|"]
    for row in rows:
        base_url = JOB_BASE_URLS.get(row["source"], WANTED_JOB_BASE_URL)
        link = f"{base_url}/{row['platform_id']}"
        lines.append(
            f"| {row['internal_id']} | {row['company_name']} | {row['title']} | {row['location']} | {link} |"
        )
    lines.append(f"총 {len(rows)}개의 미지원 공고")
    return "\n".join(lines)
```

- [ ] **Step 7: `get_jobs_without_details` 교체**

```python
def get_jobs_without_details(
    self,
    job_ids: list[int] | None = None,
    limit: int | None = None,
) -> list[int]:
    if job_ids is not None:
        with Session(self.engine) as session:
            existing = set(session.scalars(
                select(OrmJobDetail.job_id).where(OrmJobDetail.job_id.in_(job_ids))
            ).all())
        missing = [jid for jid in job_ids if jid not in existing]
        return missing[:limit] if limit is not None else missing

    stmt = (
        select(Job.internal_id)
        .outerjoin(OrmJobDetail, Job.internal_id == OrmJobDetail.job_id)
        .where(OrmJobDetail.job_id.is_(None))
        .where(Job.is_active.is_(True))
        .where(Job.source == "wanted")
        .order_by(Job.internal_id)
    )
    if limit is not None:
        stmt = stmt.limit(limit)
    with Session(self.engine) as session:
        return list(session.scalars(stmt).all())
```

- [ ] **Step 8: 기존 `test_get_unapplied_jobs_returns_markdown` 업데이트**

mock row에 `internal_id`, `source`, `platform_id` 추가 (Step 1에서 Task 2에 이미 업데이트했다면 생략):
```python
        {"internal_id": 1001, "source": "wanted", "platform_id": 1001,
         "company_name": "테스트컴퍼니", "title": "Backend Engineer",
         "location": "서울", "employment_type": "regular"}
```
어서션: `assert "https://www.wanted.co.kr/wd/1001" in result`, `assert "| 1001 |" in result` 추가

- [ ] **Step 9: 전체 테스트 실행**

```bash
pytest tests/test_job_service.py -v
```

Expected: 전체 PASS

- [ ] **Step 10: Commit**

```bash
git add services/job_service.py tests/test_job_service.py
git commit -m "feat: query 메서드 cross-platform 필터 적용, URL source-aware, ALLOWED_PRESET_KEYS 확장"
```

---

### Task 8: `tools/sync_jobs.py` + `tools/sync_applications.py` — source 라우팅

**Files:**
- Modify: `tools/sync_jobs.py`
- Modify: `tools/sync_applications.py`
- Modify: `tests/test_tools.py`

- [ ] **Step 1: 새 테스트 추가**

`tests/test_tools.py` 끝에 추가:

```python
def test_sync_jobs_remember_calls_remember_client():
    with patch("tools.sync_jobs.get_engine"), \
         patch("tools.sync_jobs.RememberClient") as MockRememberClient, \
         patch("tools.sync_jobs.JobService") as MockService:

        mock_service = MagicMock()
        mock_service.upsert_jobs.return_value = "동기화 완료: 신규 3개, 변경 0개, 유지 0개"
        MockService.return_value = mock_service

        mock_client = MagicMock()
        mock_client.fetch_jobs.return_value = []
        MockRememberClient.return_value = mock_client

        from tools.sync_jobs import sync_jobs
        result = sync_jobs(
            source="remember",
            job_category_names=[{"level1": "SW개발", "level2": "백엔드"}],
            min_experience=2,
            max_experience=5,
        )

    mock_client.fetch_jobs.assert_called_once_with(
        job_category_names=[{"level1": "SW개발", "level2": "백엔드"}],
        min_experience=2,
        max_experience=5,
    )
    mock_service.upsert_jobs.assert_called_once_with([], source="remember", full_sync=True)


def test_sync_applications_remember_calls_remember_client():
    with patch("tools.sync_applications.get_engine"), \
         patch("tools.sync_applications.RememberClient") as MockRememberClient, \
         patch("tools.sync_applications.JobService") as MockService:

        mock_service = MagicMock()
        mock_service.upsert_applications.return_value = "지원현황 동기화 완료: 총 2건"
        MockService.return_value = mock_service

        mock_client = MagicMock()
        mock_client.fetch_applications.return_value = []
        MockRememberClient.return_value = mock_client

        from tools.sync_applications import sync_applications
        result = sync_applications(source="remember")

    mock_client.fetch_applications.assert_called_once()
    mock_service.upsert_applications.assert_called_once_with([], source="remember")
```

- [ ] **Step 2: 테스트 실행 → FAIL 확인**

```bash
pytest tests/test_tools.py::test_sync_jobs_remember_calls_remember_client \
       tests/test_tools.py::test_sync_applications_remember_calls_remember_client -v
```

Expected: 2 tests FAIL

- [ ] **Step 3: `tools/sync_jobs.py` 교체**

```python
from db.connection import get_engine
from services.wanted_client import WantedClient
from services.remember_client import RememberClient
from services.job_service import JobService


def sync_jobs(
    source: str = "wanted",
    preset_name: str | None = None,
    job_group_id: int = 518,
    job_ids: list[int] | None = None,
    years: list[int] | None = None,
    locations: str = "all",
    limit_pages: int | None = None,
    job_category_names: list[dict] | None = None,
    min_experience: int = 0,
    max_experience: int = 10,
) -> str:
    """채용공고를 동기화한다.

    source: "wanted" (기본) 또는 "remember"
    Wanted: preset_name, job_group_id, job_ids, years, locations, limit_pages 사용
    Remeber: job_category_names, min_experience, max_experience 사용
    """
    engine = get_engine()
    service = JobService(engine)

    if preset_name:
        params = service.get_preset_params(preset_name)
        if params is None:
            return f"프리셋 '{preset_name}'을 찾을 수 없습니다."
        source = params.get("source", source)
        job_group_id = params.get("job_group_id", job_group_id)
        job_ids = params.get("job_ids", job_ids)
        years = params.get("years", years)
        locations = params.get("locations", locations)
        limit_pages = params.get("limit_pages", limit_pages)
        job_category_names = params.get("job_category_names", job_category_names)
        min_experience = params.get("min_experience", min_experience)
        max_experience = params.get("max_experience", max_experience)

    if source == "remember":
        if not job_category_names:
            return "Remeber 동기화에는 job_category_names가 필요합니다."
        client = RememberClient()
        jobs = client.fetch_jobs(
            job_category_names=job_category_names,
            min_experience=min_experience,
            max_experience=max_experience,
        )
        return service.upsert_jobs(jobs, source="remember", full_sync=True)

    client = WantedClient()
    full_sync = limit_pages is None
    jobs = client.fetch_jobs(
        job_group_id=job_group_id,
        job_ids=job_ids,
        years=years,
        locations=locations,
        limit_pages=limit_pages,
    )
    for job in jobs:
        if not job.get("job_group_id") and job_group_id:
            job["job_group_id"] = job_group_id
    return service.upsert_jobs(jobs, source="wanted", full_sync=full_sync)
```

- [ ] **Step 4: `tools/sync_applications.py` 교체**

```python
from db.connection import get_engine
from services.wanted_client import WantedClient
from services.remember_client import RememberClient
from services.job_service import JobService


def sync_applications(source: str = "wanted") -> str:
    """지원현황을 동기화한다. source: "wanted" (기본) 또는 "remember"."""
    engine = get_engine()
    service = JobService(engine)

    if source == "remember":
        try:
            client = RememberClient()
            apps = client.fetch_applications()
        except PermissionError as e:
            return str(e)
        except ValueError as e:
            return str(e)
        return service.upsert_applications(apps, source="remember")

    try:
        client = WantedClient()
        apps = client.fetch_applications()
    except PermissionError as e:
        return str(e)
    except ValueError as e:
        return str(e)
    return service.upsert_applications(apps, source="wanted")
```

- [ ] **Step 5: 기존 `test_sync_jobs_uses_preset_when_given` 업데이트**

`service.upsert_jobs` 호출 어서션을 source 파라미터 포함으로 수정:
```python
    mock_service.upsert_jobs.assert_called_once()
    call_kwargs = mock_client.fetch_jobs.call_args.kwargs
    assert call_kwargs.get("job_group_id") == 519
```

- [ ] **Step 6: 전체 테스트 실행**

```bash
pytest tests/test_tools.py -v
```

Expected: 전체 PASS

- [ ] **Step 7: Commit**

```bash
git add tools/sync_jobs.py tools/sync_applications.py tests/test_tools.py
git commit -m "feat: sync_jobs/sync_applications source 파라미터 추가 (Remeber 라우팅)"
```

---

### Task 9: `tools/get_unapplied_jobs.py` + `tools/get_job_candidates.py` — output 업데이트

**Files:**
- Modify: `tools/get_unapplied_jobs.py` (변경 없음 — service 레이어에서 이미 처리)
- Modify: `tools/get_job_candidates.py`
- Modify: `tests/test_tools.py`

> `get_unapplied_jobs.py`는 `service.get_unapplied_jobs()`를 그대로 호출하므로 변경 없음. `get_job_candidates.py`는 `c.id` → `c.platform_id`로, `internal_id` 추가, source-aware URL이 필요.

- [ ] **Step 1: 새 테스트 추가**

`tests/test_tools.py` 끝에 추가:

```python
def test_get_job_candidates_includes_internal_id():
    from domain import JobCandidate, SkillTag
    from datetime import datetime

    mock_candidate = JobCandidate(
        internal_id=42,
        source="wanted",
        platform_id=1001,
        company_name="테스트컴퍼니",
        title="Backend Engineer",
        location="서울",
        employment_type="regular",
        requirements="Python req",
        preferred_points=None,
        skill_tags=[SkillTag(text="Python")],
        fetched_at=datetime.now(),
    )

    with patch("tools.get_job_candidates.get_engine"), \
         patch("tools.get_job_candidates.JobService") as MockService:

        mock_service = MagicMock()
        mock_service.get_unapplied_job_rows.return_value = [mock_candidate]
        mock_service.get_recommended_jobs.return_value = [mock_candidate]
        MockService.return_value = mock_service

        from tools.get_job_candidates import get_job_candidates
        result_str = get_job_candidates(skills=["Python"])

    import json
    result = json.loads(result_str)
    assert result[0]["internal_id"] == 42
    assert result[0]["url"] == "https://www.wanted.co.kr/wd/1001"
```

- [ ] **Step 2: 테스트 실행 → FAIL 확인**

```bash
pytest tests/test_tools.py::test_get_job_candidates_includes_internal_id -v
```

Expected: FAIL

- [ ] **Step 3: `tools/get_job_candidates.py` 교체**

```python
import json
from db.connection import get_engine
from services.job_service import JobService, JOB_BASE_URLS, WANTED_JOB_BASE_URL


def get_job_candidates(
    skills: list[str],
    job_group_id: int | None = None,
    location: str | None = None,
    employment_type: str | None = None,
    top_n: int = 30,
) -> str:
    """미지원 공고 중 skill_tags 매칭 점수 기준 상위 top_n개 후보를 JSON으로 반환.

    Claude Code가 직접 추론할 수 있도록 공고 데이터만 제공.
    employment_type은 한국어("정규직", "인턴", "계약직") 또는 영어("regular", "intern", "contract") 모두 허용.
    internal_id는 skip_jobs 툴 호출 시 사용.
    """
    try:
        engine = get_engine()
        service = JobService(engine)

        rows = service.get_unapplied_job_rows(
            job_group_id=job_group_id,
            location=location,
            employment_type=employment_type,
        )
        if not rows:
            return "조건에 맞는 미지원 공고가 없습니다."

        candidates = service.get_recommended_jobs(skills=skills, rows=rows, top_k=top_n)
        if not candidates:
            return "추천 후보가 없습니다. sync_job_details를 먼저 실행해 공고 상세 정보를 수집해주세요."

        result = [
            {
                "internal_id": c.internal_id,
                "url": f"{JOB_BASE_URLS.get(c.source, WANTED_JOB_BASE_URL)}/{c.platform_id}",
                "company_name": c.company_name,
                "title": c.title,
                "location": c.location,
                "employment_type": c.employment_type,
                "skill_tags": [{"text": t.text} for t in c.skill_tags],
                "requirements": c.requirements,
                "preferred_points": c.preferred_points,
            }
            for c in candidates
        ]
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        return f"오류가 발생했습니다: {e}"
```

- [ ] **Step 4: 테스트 실행 → PASS 확인**

```bash
pytest tests/test_tools.py -v
```

Expected: 전체 PASS

- [ ] **Step 5: 전체 테스트 실행**

```bash
pytest tests/ -v
```

Expected: 전체 PASS

- [ ] **Step 6: Commit**

```bash
git add tools/get_job_candidates.py tests/test_tools.py
git commit -m "feat: get_job_candidates에 internal_id 추가 및 source-aware URL 적용"
```

---

### 완료 확인

```bash
pytest tests/ -v
python -c "from main import mcp; print('OK')"
```

Expected: 전체 PASS, `OK`
