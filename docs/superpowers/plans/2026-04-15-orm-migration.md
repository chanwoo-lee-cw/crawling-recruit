# ORM Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `Table` 객체와 `text()` raw SQL을 SQLAlchemy ORM Mapped Classes + 표현식으로 교체한다.

**Architecture:** `db/models.py`를 `DeclarativeBase` 기반 mapped class로 전면 교체하고, `job_service.py`의 `engine.connect()` 패턴을 `Session`으로 전환한다. upsert는 `insert(Model.__table__).on_duplicate_key_update()`로 Core를 유지한다.

**Tech Stack:** Python 3.11, SQLAlchemy 2.x (`DeclarativeBase`, `Mapped`, `Session`), MySQL, pytest

**Spec:** `docs/superpowers/specs/2026-04-15-orm-migration-design.md`

---

## File Map

| 파일 | 변경 유형 | 주요 내용 |
|------|-----------|-----------|
| `db/models.py` | 전면 교체 | `Table` → ORM mapped classes |
| `db/connection.py` | 수정 | `metadata` → `Base.metadata`, `Session` import |
| `services/job_service.py` | 수정 | `engine.connect()` → `Session`, `text()` → ORM 표현식, table refs → `Model.__table__` |
| `tests/test_db.py` | 수정 | `jobs_table` → `Job.__table__` 등 |
| `tests/test_job_service.py` | 수정 | `engine.connect()` mock → `Session` mock 전환 |

---

### Task 1: `db/models.py` — ORM Mapped Classes 정의

**Files:**
- Modify: `db/models.py`

- [ ] **Step 1: `db/models.py` 전체 교체**

```python
from datetime import datetime
from typing import Optional, List
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import Integer, String, Boolean, DateTime, JSON, Text, ForeignKey


class Base(DeclarativeBase):
    pass


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(Integer, nullable=False)
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

    detail: Mapped[Optional["JobDetail"]] = relationship(back_populates="job", uselist=False)
    applications: Mapped[List["Application"]] = relationship(back_populates="job")


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    apply_time: Mapped[Optional[datetime]] = mapped_column(DateTime)
    synced_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    job: Mapped[Optional["Job"]] = relationship(back_populates="applications")


class JobDetail(Base):
    __tablename__ = "job_details"

    job_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("jobs.id", ondelete="CASCADE"), primary_key=True
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
```

- [ ] **Step 2: `tests/test_db.py` 전체 교체**

```python
from db.models import Job, Application, JobDetail, SearchPreset


def test_models_defined():
    assert Job.__table__ is not None
    assert Application.__table__ is not None
    assert JobDetail.__table__ is not None
    assert SearchPreset.__table__ is not None


def test_jobs_table_columns():
    col_names = {c.name for c in Job.__table__.columns}
    assert col_names == {
        "id", "company_id", "company_name", "title", "location",
        "employment_type", "annual_from", "annual_to", "job_group_id",
        "category_tag_id", "is_active", "created_at", "synced_at", "updated_at"
    }


def test_applications_table_columns():
    col_names = {c.name for c in Application.__table__.columns}
    assert col_names == {"id", "job_id", "status", "apply_time", "synced_at"}


def test_job_details_table_columns():
    col_names = {c.name for c in JobDetail.__table__.columns}
    assert col_names == {"job_id", "requirements", "preferred_points", "skill_tags", "fetched_at"}


def test_search_presets_table_columns():
    col_names = {c.name for c in SearchPreset.__table__.columns}
    assert col_names == {"id", "name", "params", "created_at"}
```

- [ ] **Step 3: 테스트 실행 및 통과 확인**

```bash
pytest tests/test_db.py -v
```

Expected: 4 tests PASS

- [ ] **Step 4: Commit**

```bash
git add db/models.py tests/test_db.py
git commit -m "refactor: Table 객체를 SQLAlchemy ORM mapped classes로 교체"
```

---

### Task 2: `db/connection.py` — Base.metadata로 교체

**Files:**
- Modify: `db/connection.py`

- [ ] **Step 1: `db/connection.py` 수정**

```python
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from dotenv import load_dotenv
from db.models import Base


def get_engine():
    load_dotenv()
    db_url = os.getenv("DB_URL")
    if not db_url:
        raise RuntimeError("DB_URL이 .env에 설정되지 않았습니다.")
    return create_engine(db_url)


def create_tables():
    engine = get_engine()
    Base.metadata.create_all(engine)
```

- [ ] **Step 2: import 오류 없는지 확인**

```bash
python -c "from db.connection import get_engine, create_tables; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add db/connection.py
git commit -m "refactor: db/connection.py metadata → Base.metadata"
```

---

### Task 3: `tests/test_job_service.py` — Session mock 패턴으로 전환

**Files:**
- Modify: `tests/test_job_service.py`

- [ ] **Step 1: `tests/test_job_service.py` 전체 교체**

기존 `engine.connect()` mock을 `Session` mock으로 전환한다. `RAW_DETAIL`도 아직은 dict 유지 (dataclasses 스펙에서 변경).

```python
import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch
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

RAW_DETAIL = {
    "job_id": 1001,
    "requirements": "Python 3년 이상",
    "preferred_points": "FastAPI 경험자 우대",
    "skill_tags": [{"tag_type_id": 1554, "text": "Python"}],
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
    with patch("services.job_service.Session") as MockSession:
        mock_session = MagicMock()
        MockSession.return_value.__enter__ = MagicMock(return_value=mock_session)
        MockSession.return_value.__exit__ = MagicMock(return_value=False)

        mock_session.scalars.return_value.all.return_value = []  # existing_ids → empty (all new)
        upsert_result = MagicMock()
        upsert_result.rowcount = 1
        mock_session.execute.return_value = upsert_result

        service = JobService(engine=mock_engine)
        result = service.upsert_jobs([RAW_JOB], full_sync=False)

    assert mock_session.scalars.called
    assert mock_session.execute.called
    assert "동기화 완료: 신규 1개, 변경 0개, 유지 0개" == result


def test_save_preset_invalid_key():
    service = JobService(engine=MagicMock())
    with pytest.raises(ValueError, match="유효하지 않은 파라미터 키"):
        service.save_preset("테스트", {"invalid_key": 1})


def test_save_preset_valid():
    mock_engine = MagicMock()
    with patch("services.job_service.Session") as MockSession:
        mock_session = MagicMock()
        MockSession.return_value.__enter__ = MagicMock(return_value=mock_session)
        MockSession.return_value.__exit__ = MagicMock(return_value=False)

        service = JobService(engine=mock_engine)
        result = service.save_preset("백엔드 신입 서울", {"job_group_id": 518, "locations": "서울"})

    assert "저장 완료" in result


def test_get_unapplied_jobs_returns_markdown():
    mock_engine = MagicMock()
    with patch("services.job_service.Session") as MockSession:
        mock_session = MagicMock()
        MockSession.return_value.__enter__ = MagicMock(return_value=mock_session)
        MockSession.return_value.__exit__ = MagicMock(return_value=False)

        mock_session.execute.return_value.mappings.return_value.all.return_value = [
            {"id": 1001, "company_name": "테스트컴퍼니", "title": "Backend Engineer",
             "location": "서울", "employment_type": "regular"}
        ]

        service = JobService(engine=mock_engine)
        result = service.get_unapplied_jobs()

    assert "| 회사명 |" in result
    assert "테스트컴퍼니" in result
    assert "https://www.wanted.co.kr/wd/1001" in result


def test_upsert_job_details_calls_execute():
    mock_engine = MagicMock()
    with patch("services.job_service.Session") as MockSession:
        mock_session = MagicMock()
        MockSession.return_value.__enter__ = MagicMock(return_value=mock_session)
        MockSession.return_value.__exit__ = MagicMock(return_value=False)
        mock_session.execute.return_value = MagicMock()

        service = JobService(engine=mock_engine)
        result = service.upsert_job_details([RAW_DETAIL])

    assert mock_session.execute.called
    assert "1개 처리" in result


def test_get_unapplied_job_rows_returns_list():
    mock_engine = MagicMock()
    with patch("services.job_service.Session") as MockSession:
        mock_session = MagicMock()
        MockSession.return_value.__enter__ = MagicMock(return_value=mock_session)
        MockSession.return_value.__exit__ = MagicMock(return_value=False)

        mock_session.execute.return_value.mappings.return_value.all.return_value = [
            {
                "id": 1001, "company_name": "테스트컴퍼니", "title": "Backend Engineer",
                "location": "서울", "employment_type": "regular",
                "requirements": None, "preferred_points": None,
                "skill_tags": None, "fetched_at": None,
            }
        ]

        service = JobService(engine=mock_engine)
        rows = service.get_unapplied_job_rows()

    assert isinstance(rows, list)
    assert rows[0]["id"] == 1001
    assert rows[0]["fetched_at"] is None


def test_get_jobs_without_details_filters_existing():
    mock_engine = MagicMock()
    with patch("services.job_service.Session") as MockSession:
        mock_session = MagicMock()
        MockSession.return_value.__enter__ = MagicMock(return_value=mock_session)
        MockSession.return_value.__exit__ = MagicMock(return_value=False)
        mock_session.scalars.return_value.all.return_value = [101]

        service = JobService(engine=mock_engine)
        result = service.get_jobs_without_details(job_ids=[101, 102, 103], limit=2)

    assert result == [102, 103]


def test_get_jobs_without_details_no_job_ids():
    mock_engine = MagicMock()
    with patch("services.job_service.Session") as MockSession:
        mock_session = MagicMock()
        MockSession.return_value.__enter__ = MagicMock(return_value=mock_session)
        MockSession.return_value.__exit__ = MagicMock(return_value=False)
        mock_session.scalars.return_value.all.return_value = [201, 202]

        service = JobService(engine=mock_engine)
        result = service.get_jobs_without_details(limit=10)

    assert result == [201, 202]


def test_get_recommended_jobs_scores_skill_tags():
    mock_engine = MagicMock()
    now = datetime.now()
    all_rows = [
        {
            "id": 1, "company_name": "A사", "title": "Backend",
            "location": "서울", "employment_type": "regular",
            "requirements": "Python req", "preferred_points": "AWS 우대",
            "skill_tags": [{"tag_type_id": 1554, "text": "Python"}, {"tag_type_id": 1698, "text": "AWS"}],
            "fetched_at": now,
        },
        {
            "id": 2, "company_name": "B사", "title": "Frontend",
            "location": "서울", "employment_type": "regular",
            "requirements": "React req", "preferred_points": None,
            "skill_tags": [{"tag_type_id": 1600, "text": "React"}],
            "fetched_at": now,
        },
        {
            "id": 3, "company_name": "C사", "title": "Fullstack",
            "location": "서울", "employment_type": "regular",
            "requirements": None, "preferred_points": None,
            "skill_tags": None, "fetched_at": None,
        },
    ]

    service = JobService(engine=mock_engine)
    candidates = service.get_recommended_jobs(
        skills=["Python", "AWS"],
        rows=all_rows,
        top_k=15,
    )

    assert len(candidates) == 2
    assert candidates[0]["id"] == 1
    assert candidates[1]["id"] == 2
    assert all(c["fetched_at"] is not None for c in candidates)
```

- [ ] **Step 2: 현재 테스트 실행 → 대부분 FAIL 확인 (Session import 없으므로)**

```bash
pytest tests/test_job_service.py -v
```

Expected: Session 관련 테스트들 FAIL (job_service가 아직 engine.connect() 사용 중)

---

### Task 4: `services/job_service.py` — Session + ORM 표현식으로 전환

**Files:**
- Modify: `services/job_service.py`

- [ ] **Step 1: `services/job_service.py` 전체 교체**

```python
import json
from datetime import datetime, timezone
from sqlalchemy import select, update, text
from sqlalchemy.dialects.mysql import insert
from sqlalchemy.orm import Session

from db.models import Job, Application, JobDetail, SearchPreset

ALLOWED_PRESET_KEYS = {"job_group_id", "job_ids", "years", "locations", "limit_pages"}


class JobService:
    EMPLOYMENT_TYPE_MAP = {
        "정규직": "regular",
        "인턴": "intern",
        "계약직": "contract",
    }

    def __init__(self, engine):
        self.engine = engine

    def _parse_job(self, raw: dict) -> dict:
        address = raw.get("address") or {}
        location_str = address.get("location", "")
        district = address.get("district", "")
        location = f"{location_str} {district}".strip() if district else location_str

        category_tag = raw.get("category_tag") or {}
        now = datetime.now(timezone.utc).replace(tzinfo=None)

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
            "synced_at": datetime.now(timezone.utc).replace(tzinfo=None),
        }

    def upsert_jobs(self, raw_jobs: list[dict], full_sync: bool = False) -> str:
        if not raw_jobs:
            return "동기화 완료: 신규 0개, 변경 0개, 유지 0개"

        rows = [self._parse_job(j) for j in raw_jobs]
        synced_ids = {r["id"] for r in rows}

        with Session(self.engine) as session:
            existing_ids = set(session.scalars(
                select(Job.id).where(Job.id.in_(synced_ids))
            ).all())
            new_count = len(synced_ids - existing_ids)

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

            if full_sync and synced_ids:
                session.execute(
                    update(Job)
                    .where(Job.id.not_in(synced_ids))
                    .where(Job.is_active == True)
                    .values(is_active=False)
                )
                session.commit()

            updated_count = (result.rowcount - new_count) // 2
            unchanged_count = len(rows) - new_count - updated_count
            return f"동기화 완료: 신규 {new_count}개, 변경 {updated_count}개, 유지 {unchanged_count}개"

    def upsert_applications(self, raw_apps: list[dict]) -> str:
        if not raw_apps:
            return "지원현황 동기화 완료: 총 0건"

        rows = [self._parse_application(a) for a in raw_apps]

        with Session(self.engine) as session:
            stmt = insert(Application.__table__).values(rows)
            upsert_stmt = stmt.on_duplicate_key_update(
                status=stmt.inserted.status,
                synced_at=stmt.inserted.synced_at,
            )
            session.execute(upsert_stmt)
            session.commit()

        return f"지원현황 동기화 완료: 총 {len(rows)}건"

    def upsert_job_details(self, details: list[dict]) -> str:
        if not details:
            return "완료: 0개 처리"
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        rows = [
            {
                "job_id": d["job_id"],
                "requirements": d.get("requirements"),
                "preferred_points": d.get("preferred_points"),
                "skill_tags": d.get("skill_tags", []),
                "fetched_at": now,
            }
            for d in details
        ]
        with Session(self.engine) as session:
            stmt = insert(JobDetail.__table__).values(rows)
            upsert_stmt = stmt.on_duplicate_key_update(
                requirements=stmt.inserted.requirements,
                preferred_points=stmt.inserted.preferred_points,
                skill_tags=stmt.inserted.skill_tags,
                fetched_at=stmt.inserted.fetched_at,
            )
            session.execute(upsert_stmt)
            session.commit()
        return f"완료: {len(rows)}개 처리"

    def get_jobs_without_details(
        self,
        job_ids: list[int] | None = None,
        limit: int | None = None,
    ) -> list[int]:
        if job_ids is not None:
            with Session(self.engine) as session:
                existing = set(session.scalars(
                    select(JobDetail.job_id).where(JobDetail.job_id.in_(job_ids))
                ).all())
            missing = [jid for jid in job_ids if jid not in existing]
            return missing[:limit] if limit is not None else missing

        stmt = (
            select(Job.id)
            .outerjoin(JobDetail, Job.id == JobDetail.job_id)
            .where(JobDetail.job_id.is_(None))
            .where(Job.is_active.is_(True))
            .order_by(Job.id)
        )
        if limit is not None:
            stmt = stmt.limit(limit)
        with Session(self.engine) as session:
            return list(session.scalars(stmt).all())

    def get_unapplied_jobs(
        self,
        job_group_id: int | None = None,
        location: str | None = None,
        employment_type: str | None = None,
        limit: int = 20,
    ) -> str:
        stmt = (
            select(Job.id, Job.company_name, Job.title, Job.location, Job.employment_type)
            .outerjoin(Application, Job.id == Application.job_id)
            .where(Application.job_id.is_(None))
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

        lines = ["| 회사명 | 포지션 | 지역 | 링크 |", "|---|---|---|---|"]
        for row in rows:
            link = f"https://www.wanted.co.kr/wd/{row['id']}"
            lines.append(
                f"| {row['company_name']} | {row['title']} | {row['location']} | {link} |"
            )
        lines.append(f"총 {len(rows)}개의 미지원 공고")
        return "\n".join(lines)

    def get_unapplied_job_rows(
        self,
        job_group_id: int | None = None,
        location: str | None = None,
        employment_type: str | None = None,
    ) -> list[dict]:
        if employment_type:
            employment_type = self.EMPLOYMENT_TYPE_MAP.get(employment_type, employment_type)
        stmt = (
            select(
                Job.id, Job.company_name, Job.title, Job.location, Job.employment_type,
                JobDetail.requirements, JobDetail.preferred_points,
                JobDetail.skill_tags, JobDetail.fetched_at,
            )
            .outerjoin(Application, Job.id == Application.job_id)
            .outerjoin(JobDetail, Job.id == JobDetail.job_id)
            .where(Application.job_id.is_(None))
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

        result = []
        for r in rows:
            row = dict(r)
            if isinstance(row.get("skill_tags"), str):
                try:
                    row["skill_tags"] = json.loads(row["skill_tags"])
                except (json.JSONDecodeError, TypeError):
                    row["skill_tags"] = []
            result.append(row)
        return result

    def save_preset(self, name: str, params: dict) -> str:
        invalid_keys = set(params.keys()) - ALLOWED_PRESET_KEYS
        if invalid_keys:
            raise ValueError(
                f"유효하지 않은 파라미터 키: {sorted(invalid_keys)}. "
                f"허용 키: {', '.join(sorted(ALLOWED_PRESET_KEYS))}"
            )

        row = {
            "name": name,
            "params": params,  # raw dict — SQLAlchemy JSON column handles serialization
            "created_at": datetime.now(timezone.utc).replace(tzinfo=None),
        }

        with Session(self.engine) as session:
            stmt = insert(SearchPreset.__table__).values([row])
            upsert_stmt = stmt.on_duplicate_key_update(
                params=stmt.inserted.params,
                created_at=stmt.inserted.created_at,
            )
            session.execute(upsert_stmt)
            session.commit()

        return f"프리셋 '{name}' 저장 완료"

    def list_presets(self) -> str:
        with Session(self.engine) as session:
            presets = session.scalars(
                select(SearchPreset).order_by(SearchPreset.created_at)
            ).all()

        if not presets:
            return "저장된 프리셋이 없습니다."
        names = ", ".join(r.name for r in presets)
        return f"저장된 프리셋: {names}"

    def get_preset_params(self, name: str) -> dict | None:
        with Session(self.engine) as session:
            preset = session.scalars(
                select(SearchPreset).where(SearchPreset.name == name)
            ).first()

        if not preset:
            return None
        params = preset.params
        return json.loads(params) if isinstance(params, str) else params

    def get_recommended_jobs(
        self,
        skills: list[str],
        rows: list[dict],
        top_k: int = 15,
    ) -> list[dict]:
        """전달된 rows에서 skill_tags 매칭 점수 기준 상위 top_k개 반환 (detail 없는 공고 제외)."""
        skills_lower = {s.lower() for s in skills}

        def score(row: dict) -> int:
            tags = row.get("skill_tags") or []
            return sum(1 for t in tags if t.get("text", "").lower() in skills_lower)

        with_detail = [r for r in rows if r.get("fetched_at") is not None]
        scored = sorted(with_detail, key=score, reverse=True)
        return scored[:top_k]
```

- [ ] **Step 2: 전체 테스트 실행**

```bash
pytest tests/ -v --ignore=tests/test_tools.py
```

Expected: 전체 PASS. `test_tools.py`는 `tools.recommend_jobs` pre-existing broken import 때문에 제외.

- [ ] **Step 3: Commit**

```bash
git add services/job_service.py tests/test_job_service.py
git commit -m "refactor: job_service Session 전환 및 text() 쿼리 ORM 표현식으로 교체"
```

---

### Task 5: `tests/test_tools.py` — pre-existing 깨진 import 제거

**Files:**
- Modify: `tests/test_tools.py`

- [ ] **Step 1: `from tools.recommend_jobs import recommend_jobs` 와 관련 테스트 2개 제거**

`tests/test_tools.py` 127번째 줄부터 마지막까지 삭제:
- `from tools.recommend_jobs import recommend_jobs` (line 127)
- `import anthropic` (line 128)
- `test_recommend_jobs_calls_claude_and_returns_markdown` 함수 전체
- `test_recommend_jobs_fallback_on_claude_failure` 함수 전체

- [ ] **Step 2: 전체 테스트 실행**

```bash
pytest tests/ -v
```

Expected: 전체 PASS (recommend_jobs 관련 2개 테스트 삭제로 더 이상 import error 없음)

- [ ] **Step 3: Commit**

```bash
git add tests/test_tools.py
git commit -m "test: 삭제된 tools.recommend_jobs 관련 테스트 제거"
```
