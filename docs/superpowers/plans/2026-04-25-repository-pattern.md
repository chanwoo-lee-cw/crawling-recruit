# Repository Pattern Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `db/models.py`를 모델별 개별 파일로 분리하고, `JobService`의 인라인 SQL 쿼리를 6개 Repository 클래스로 추출한다.

**Architecture:** `db/models/` 패키지로 모델 분리 후 `__init__.py` re-export로 기존 import 경로 유지. 각 Repository는 `Session`을 생성자로 받고, `JobService`가 `with Session(engine)` 경계를 소유한다. Service 외부 인터페이스(시그니처·반환값)는 불변.

**Tech Stack:** Python 3.11, SQLAlchemy 2.x, MySQL (`sqlalchemy.dialects.mysql.insert`), pytest

---

### Task 1: db/models.py → db/models/ 패키지 분리

**Files:**
- Create: `db/models/base.py`
- Create: `db/models/job.py`
- Create: `db/models/application.py`
- Create: `db/models/job_detail.py`
- Create: `db/models/search_preset.py`
- Create: `db/models/job_skip.py`
- Create: `db/models/job_evaluation.py`
- Create: `db/models/__init__.py`
- Delete: `db/models.py`
- Test: `tests/test_db.py` (기존, 변경 없음)

- [ ] **Step 1: db/models/ 디렉터리 및 base.py 생성**

```python
# db/models/base.py
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass
```

- [ ] **Step 2: 모델 파일 6개 생성**

```python
# db/models/job.py
from datetime import datetime
from typing import Optional, List
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Integer, String, Boolean, DateTime, UniqueConstraint
from db.models.base import Base
from services.wanted.wanted_constants import WANTED

class Job(Base):
    __tablename__ = "jobs"
    internal_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default=WANTED)
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
    evaluation: Mapped[Optional["JobEvaluation"]] = relationship(back_populates="job", uselist=False)
```

```python
# db/models/application.py
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Integer, String, DateTime, ForeignKey, UniqueConstraint
from db.models.base import Base
from services.wanted.wanted_constants import WANTED

class Application(Base):
    __tablename__ = "applications"
    internal_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default=WANTED)
    platform_id: Mapped[int] = mapped_column(Integer, nullable=False)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.internal_id"), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    apply_time: Mapped[Optional[datetime]] = mapped_column(DateTime)
    synced_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    __table_args__ = (UniqueConstraint("source", "platform_id", name="uq_app_source_platform"),)
    job: Mapped[Optional["Job"]] = relationship(back_populates="applications")
```

```python
# db/models/job_detail.py
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Integer, DateTime, Text, JSON, ForeignKey
from db.models.base import Base

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
```

```python
# db/models/search_preset.py
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Integer, String, DateTime, JSON
from db.models.base import Base

class SearchPreset(Base):
    __tablename__ = "search_presets"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    params: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
```

```python
# db/models/job_skip.py
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Integer, String, DateTime, ForeignKey
from db.models.base import Base

class JobSkip(Base):
    __tablename__ = "job_skips"
    job_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("jobs.internal_id", ondelete="CASCADE"), primary_key=True
    )
    reason: Mapped[Optional[str]] = mapped_column(String(255))
    skipped_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    job: Mapped["Job"] = relationship(back_populates="skip")
```

```python
# db/models/job_evaluation.py
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Integer, String, DateTime, ForeignKey
from db.models.base import Base

class JobEvaluation(Base):
    __tablename__ = "job_evaluations"
    job_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("jobs.internal_id", ondelete="CASCADE"), primary_key=True
    )
    verdict: Mapped[str] = mapped_column(String(20), nullable=False)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    job: Mapped["Job"] = relationship(back_populates="evaluation")
```

- [ ] **Step 3: `db/models/__init__.py` 생성 (re-export)**

```python
# db/models/__init__.py
from db.models.base import Base
from db.models.job import Job
from db.models.application import Application
from db.models.job_detail import JobDetail
from db.models.search_preset import SearchPreset
from db.models.job_skip import JobSkip
from db.models.job_evaluation import JobEvaluation

__all__ = ["Base", "Job", "Application", "JobDetail", "SearchPreset", "JobSkip", "JobEvaluation"]
```

- [ ] **Step 4: `db/models.py` 삭제**

```bash
git rm db/models.py
```

- [ ] **Step 5: 기존 테스트 통과 확인**

```bash
pytest tests/test_db.py -v
```
Expected: 전체 PASS

- [ ] **Step 6: 커밋**

```bash
git add db/models/
git commit -m "refactor: split db/models.py into per-model files"
```

---

### Task 2: SearchPresetRepository + service 연결

**Files:**
- Create: `db/repositories/__init__.py`
- Create: `db/repositories/search_preset_repository.py`
- Modify: `services/jobs/job_service.py` (save_preset, list_presets, get_preset_params)
- Test: `tests/test_repositories.py` (신규)

- [ ] **Step 1: `tests/test_repositories.py` 에 실패하는 테스트 작성**

```python
# tests/test_repositories.py
from unittest.mock import MagicMock
from db.repositories.search_preset_repository import SearchPresetRepository


def test_find_by_name_returns_none_when_missing():
    mock_session = MagicMock()
    mock_session.scalars.return_value.first.return_value = None
    repo = SearchPresetRepository(mock_session)
    assert repo.find_by_name("없는이름") is None


def test_find_all_returns_list():
    mock_session = MagicMock()
    mock_preset = MagicMock()
    mock_preset.name = "테스트"
    mock_session.scalars.return_value.all.return_value = [mock_preset]
    repo = SearchPresetRepository(mock_session)
    result = repo.find_all()
    assert len(result) == 1
    assert result[0].name == "테스트"


def test_upsert_calls_execute():
    mock_session = MagicMock()
    repo = SearchPresetRepository(mock_session)
    repo.upsert({"name": "x", "params": {}, "created_at": None})
    assert mock_session.execute.called
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
pytest tests/test_repositories.py -v
```
Expected: `ImportError` 또는 `ModuleNotFoundError`

- [ ] **Step 3: `db/repositories/` 패키지 및 SearchPresetRepository 구현**

```python
# db/repositories/__init__.py
# (비워둠)
```

```python
# db/repositories/search_preset_repository.py
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.dialects.mysql import insert
from db.models import SearchPreset


class SearchPresetRepository:
    def __init__(self, session: Session):
        self.session = session

    def upsert(self, row: dict) -> None:
        stmt = insert(SearchPreset.__table__).values([row])
        self.session.execute(stmt.on_duplicate_key_update(
            params=stmt.inserted.params,
            created_at=stmt.inserted.created_at,
        ))

    def find_all(self) -> list[SearchPreset]:
        return list(self.session.scalars(
            select(SearchPreset).order_by(SearchPreset.created_at)
        ).all())

    def find_by_name(self, name: str) -> SearchPreset | None:
        return self.session.scalars(
            select(SearchPreset).where(SearchPreset.name == name)
        ).first()
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
pytest tests/test_repositories.py -v
```
Expected: 전체 PASS

- [ ] **Step 5: job_service.py 에서 save_preset, list_presets, get_preset_params 교체**

`save_preset`:
```python
def save_preset(self, name: str, params: dict) -> str:
    invalid_keys = set(params.keys()) - ALLOWED_PRESET_KEYS
    if invalid_keys:
        raise ValueError(
            f"유효하지 않은 파라미터 키: {sorted(invalid_keys)}. "
            f"허용 키: {', '.join(sorted(ALLOWED_PRESET_KEYS))}"
        )
    row = {
        "name": name,
        "params": params,
        "created_at": datetime.now(timezone.utc).replace(tzinfo=None),
    }
    with Session(self.engine) as session:
        SearchPresetRepository(session).upsert(row)
        session.commit()
    return f"프리셋 '{name}' 저장 완료"
```

`list_presets`:
```python
def list_presets(self) -> str:
    with Session(self.engine) as session:
        presets = SearchPresetRepository(session).find_all()
    if not presets:
        return "저장된 프리셋이 없습니다."
    return f"저장된 프리셋: {', '.join(r.name for r in presets)}"
```

`get_preset_params`:
```python
def get_preset_params(self, name: str) -> dict | None:
    with Session(self.engine) as session:
        preset = SearchPresetRepository(session).find_by_name(name)
    if not preset:
        return None
    params = preset.params
    return json.loads(params) if isinstance(params, str) else params
```

상단 import 추가:
```python
from db.repositories.search_preset_repository import SearchPresetRepository
```

- [ ] **Step 6: 전체 테스트 통과 확인**

```bash
pytest -v
```
Expected: 전체 PASS

- [ ] **Step 7: 커밋**

```bash
git add db/repositories/ tests/test_repositories.py services/jobs/job_service.py
git commit -m "feat: extract SearchPresetRepository, wire into JobService"
```

---

### Task 3: JobDetailRepository + service 연결

**Files:**
- Create: `db/repositories/job_detail_repository.py`
- Modify: `services/jobs/job_service.py` (upsert_job_details, get_jobs_without_details job_ids 경로)
- Test: `tests/test_repositories.py` (추가)

- [ ] **Step 1: 실패하는 테스트 추가 (test_repositories.py 에 append)**

```python
from db.repositories.job_detail_repository import JobDetailRepository


def test_job_detail_find_existing_job_ids():
    mock_session = MagicMock()
    mock_session.scalars.return_value.all.return_value = [101, 102]
    repo = JobDetailRepository(mock_session)
    result = repo.find_existing_job_ids([101, 102, 103])
    assert result == {101, 102}


def test_job_detail_upsert_calls_execute():
    mock_session = MagicMock()
    repo = JobDetailRepository(mock_session)
    repo.upsert([{"job_id": 1, "requirements": "Python", "preferred_points": None,
                  "skill_tags": [], "fetched_at": None}])
    assert mock_session.execute.called
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
pytest tests/test_repositories.py::test_job_detail_find_existing_job_ids -v
```
Expected: `ImportError`

- [ ] **Step 3: JobDetailRepository 구현**

```python
# db/repositories/job_detail_repository.py
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.dialects.mysql import insert
from db.models import JobDetail as OrmJobDetail


class JobDetailRepository:
    def __init__(self, session: Session):
        self.session = session

    def find_existing_job_ids(self, job_ids: list[int]) -> set[int]:
        return set(self.session.scalars(
            select(OrmJobDetail.job_id).where(OrmJobDetail.job_id.in_(job_ids))
        ).all())

    def upsert(self, rows: list[dict]) -> None:
        stmt = insert(OrmJobDetail.__table__).values(rows)
        self.session.execute(stmt.on_duplicate_key_update(
            requirements=stmt.inserted.requirements,
            preferred_points=stmt.inserted.preferred_points,
            skill_tags=stmt.inserted.skill_tags,
            fetched_at=stmt.inserted.fetched_at,
        ))
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
pytest tests/test_repositories.py -v
```
Expected: 전체 PASS

- [ ] **Step 5: job_service.py 에서 upsert_job_details, get_jobs_without_details(job_ids 경로) 교체**

`upsert_job_details`:
```python
def upsert_job_details(self, details: list[JobDetail]) -> str:
    if not details:
        return "완료: 0개 처리"
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    rows = [
        {
            "job_id": d.job_id,
            "requirements": d.requirements,
            "preferred_points": d.preferred_points,
            "skill_tags": d.skill_tags,
            "fetched_at": now,
        }
        for d in details
    ]
    with Session(self.engine) as session:
        JobDetailRepository(session).upsert(rows)
        session.commit()
    return f"완료: {len(rows)}개 처리"
```

`get_jobs_without_details` (job_ids 경로만 교체, 나머지는 Task 7에서):
```python
def get_jobs_without_details(
    self,
    job_ids: list[int] | None = None,
    limit: int | None = None,
) -> list[int]:
    if job_ids is not None:
        with Session(self.engine) as session:
            existing = JobDetailRepository(session).find_existing_job_ids(job_ids)
        missing = [jid for jid in job_ids if jid not in existing]
        return missing[:limit] if limit is not None else missing

    # job_ids=None 경로는 Task 7에서 처리 (임시로 기존 코드 유지)
    stmt = (
        select(Job.internal_id)
        .outerjoin(OrmJobDetail, Job.internal_id == OrmJobDetail.job_id)
        .where(OrmJobDetail.job_id.is_(None))
        .where(Job.is_active.is_(True))
        .where(Job.source == WANTED)
        .order_by(Job.internal_id)
    )
    if limit is not None:
        stmt = stmt.limit(limit)
    with Session(self.engine) as session:
        return list(session.scalars(stmt).all())
```

상단 import 추가:
```python
from db.repositories.job_detail_repository import JobDetailRepository
```

- [ ] **Step 6: 전체 테스트 통과 확인**

```bash
pytest -v
```
Expected: 전체 PASS

- [ ] **Step 7: 커밋**

```bash
git add db/repositories/job_detail_repository.py tests/test_repositories.py services/jobs/job_service.py
git commit -m "feat: extract JobDetailRepository, wire into JobService"
```

---

### Task 4: ApplicationRepository + service 연결

**Files:**
- Create: `db/repositories/application_repository.py`
- Modify: `services/jobs/job_service.py` (upsert_applications)
- Test: `tests/test_repositories.py` (추가)

- [ ] **Step 1: 실패하는 테스트 추가**

```python
from db.repositories.application_repository import ApplicationRepository


def test_application_upsert_calls_execute():
    mock_session = MagicMock()
    repo = ApplicationRepository(mock_session)
    repo.upsert([{"source": "wanted", "platform_id": 1, "job_id": 1,
                  "status": "complete", "apply_time": None, "synced_at": None}])
    assert mock_session.execute.called
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
pytest tests/test_repositories.py::test_application_upsert_calls_execute -v
```
Expected: `ImportError`

- [ ] **Step 3: ApplicationRepository 구현**

```python
# db/repositories/application_repository.py
from sqlalchemy.orm import Session
from sqlalchemy.dialects.mysql import insert
from db.models import Application


class ApplicationRepository:
    def __init__(self, session: Session):
        self.session = session

    def upsert(self, rows: list[dict]) -> None:
        stmt = insert(Application.__table__).values(rows)
        self.session.execute(stmt.on_duplicate_key_update(
            status=stmt.inserted.status,
            synced_at=stmt.inserted.synced_at,
        ))
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
pytest tests/test_repositories.py -v
```
Expected: 전체 PASS

- [ ] **Step 5: job_service.py 에서 upsert_applications 교체**

```python
def upsert_applications(self, raw_apps: list[dict], source: str = WANTED) -> str:
    if not raw_apps:
        return "지원현황 동기화 완료: 총 0건"

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    parsed = self._parse_applications(raw_apps, source)

    if not parsed:
        return "지원현황 동기화 완료: 총 0건"

    job_platform_ids = [p["job_platform_id"] for p in parsed]

    with Session(self.engine) as session:
        job_id_map = {
            row.platform_id: row.internal_id
            for row in session.execute(
                select(Job.platform_id, Job.internal_id)
                .where(Job.source == source)
                .where(Job.platform_id.in_(job_platform_ids))
            ).all()
        }

        rows = []
        for p in parsed:
            job_internal_id = job_id_map.get(p["job_platform_id"])
            if job_internal_id is None:
                continue
            apply_time = (
                datetime.fromisoformat(p["apply_time_str"]).replace(tzinfo=None)
                if p["apply_time_str"] else None
            )
            rows.append({
                "source": source,
                "platform_id": p["platform_id"],
                "job_id": job_internal_id,
                "status": p["status"],
                "apply_time": apply_time,
                "synced_at": now,
            })

        if not rows:
            return "지원현황 동기화 완료: 총 0건"

        ApplicationRepository(session).upsert(rows)
        session.commit()

    return f"지원현황 동기화 완료: 총 {len(rows)}건"
```

> 참고: `job_id_map` 조회는 Task 7에서 `JobRepository.find_platform_id_map`으로 교체된다.
> 지금은 `ApplicationRepository.upsert` 연결에만 집중하고, 기존 inline select는 그대로 둔다.

상단 import 추가:
```python
from db.repositories.application_repository import ApplicationRepository
```

- [ ] **Step 6: 전체 테스트 통과 확인**

```bash
pytest -v
```
Expected: 전체 PASS

- [ ] **Step 7: 커밋**

```bash
git add db/repositories/application_repository.py tests/test_repositories.py services/jobs/job_service.py
git commit -m "feat: extract ApplicationRepository, wire into JobService"
```

---

### Task 5: JobSkipRepository + service 연결

**Files:**
- Create: `db/repositories/job_skip_repository.py`
- Modify: `services/jobs/job_service.py` (skip_jobs)
- Test: `tests/test_repositories.py` (추가)

- [ ] **Step 1: 실패하는 테스트 추가**

```python
from db.repositories.job_skip_repository import JobSkipRepository


def test_job_skip_upsert_calls_execute():
    mock_session = MagicMock()
    repo = JobSkipRepository(mock_session)
    repo.upsert([{"job_id": 1, "reason": "연봉 낮음", "skipped_at": None}])
    assert mock_session.execute.called
```

- [ ] **Step 2: 테스트 실패 확인 후 구현**

```python
# db/repositories/job_skip_repository.py
from sqlalchemy.orm import Session
from sqlalchemy.dialects.mysql import insert
from db.models import JobSkip


class JobSkipRepository:
    def __init__(self, session: Session):
        self.session = session

    def upsert(self, rows: list[dict]) -> None:
        stmt = insert(JobSkip.__table__).values(rows)
        self.session.execute(stmt.on_duplicate_key_update(
            reason=stmt.inserted.reason,
            skipped_at=stmt.inserted.skipped_at,
        ))
```

- [ ] **Step 3: job_service.py 에서 skip_jobs 교체**

```python
def skip_jobs(self, job_ids: list[int], reason: str | None = None) -> str:
    if not job_ids:
        return "제외할 공고 ID를 입력해주세요."
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    rows = [{"job_id": jid, "reason": reason, "skipped_at": now} for jid in job_ids]
    with Session(self.engine) as session:
        JobSkipRepository(session).upsert(rows)
        session.commit()
    suffix = f" (사유: {reason})" if reason else ""
    return f"{len(job_ids)}개 공고 제외 완료{suffix}"
```

상단 import 추가:
```python
from db.repositories.job_skip_repository import JobSkipRepository
```

- [ ] **Step 4: 전체 테스트 통과 후 커밋**

```bash
pytest -v
git add db/repositories/job_skip_repository.py tests/test_repositories.py services/jobs/job_service.py
git commit -m "feat: extract JobSkipRepository, wire into JobService"
```

---

### Task 6: JobEvaluationRepository + service 연결

**Files:**
- Create: `db/repositories/job_evaluation_repository.py`
- Modify: `services/jobs/job_service.py` (save_job_evaluations)
- Test: `tests/test_repositories.py` (추가)

- [ ] **Step 1: 실패하는 테스트 추가**

```python
from db.repositories.job_evaluation_repository import JobEvaluationRepository


def test_job_evaluation_upsert_calls_execute():
    mock_session = MagicMock()
    repo = JobEvaluationRepository(mock_session)
    repo.upsert([{"job_id": 1, "verdict": "good", "evaluated_at": None}])
    assert mock_session.execute.called
```

- [ ] **Step 2: 테스트 실패 확인 후 구현**

```python
# db/repositories/job_evaluation_repository.py
from sqlalchemy.orm import Session
from sqlalchemy.dialects.mysql import insert
from db.models import JobEvaluation


class JobEvaluationRepository:
    def __init__(self, session: Session):
        self.session = session

    def upsert(self, rows: list[dict]) -> None:
        stmt = insert(JobEvaluation.__table__).values(rows)
        self.session.execute(stmt.on_duplicate_key_update(
            verdict=stmt.inserted.verdict,
            evaluated_at=stmt.inserted.evaluated_at,
        ))
```

- [ ] **Step 3: job_service.py 에서 save_job_evaluations 교체**

```python
def save_job_evaluations(self, evaluations: list[dict]) -> str:
    if not evaluations:
        return "0개 처리"
    invalid = [e.get("verdict") for e in evaluations if e.get("verdict") not in self.VALID_VERDICTS]
    if invalid:
        raise ValueError(f"유효하지 않은 verdict: {invalid}. 허용 값: good, pass, skip")
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    rows = [
        {"job_id": e["job_id"], "verdict": e["verdict"], "evaluated_at": now}
        for e in evaluations
    ]
    with Session(self.engine) as session:
        JobEvaluationRepository(session).upsert(rows)
        session.commit()
    return f"{len(rows)}개 평가 저장 완료"
```

상단 import 추가:
```python
from db.repositories.job_evaluation_repository import JobEvaluationRepository
```

- [ ] **Step 4: `test_save_job_evaluations_saves_rows` 테스트 수정**

`services.jobs.job_service.insert`는 Task 8에서 제거된다. 지금 미리 수정해 둔다.

`tests/test_job_service.py`의 `test_save_job_evaluations_saves_rows`를:
```python
# 수정 전
with patch("services.jobs.job_service.Session") as MockSession, \
     patch("services.jobs.job_service.insert") as mock_insert:
    ...
    mock_insert_instance.on_duplicate_key_update.assert_called_once()
```

아래로 교체:
```python
def test_save_job_evaluations_saves_rows():
    mock_engine = MagicMock()
    with patch("services.jobs.job_service.Session") as MockSession:
        mock_session = MagicMock()
        MockSession.return_value.__enter__ = MagicMock(return_value=mock_session)
        MockSession.return_value.__exit__ = MagicMock(return_value=False)

        service = JobService(engine=mock_engine)
        result = service.save_job_evaluations([
            {"job_id": 1, "verdict": "good"},
            {"job_id": 2, "verdict": "pass"},
        ])

    assert "2개" in result
    mock_session.execute.assert_called()
    mock_session.commit.assert_called_once()
```

- [ ] **Step 5: 전체 테스트 통과 후 커밋**

```bash
pytest -v
git add db/repositories/job_evaluation_repository.py tests/test_repositories.py tests/test_job_service.py services/jobs/job_service.py
git commit -m "feat: extract JobEvaluationRepository, wire into JobService"
```

---

### Task 7: JobRepository + service 연결 (나머지 메서드 전체)

**Files:**
- Create: `db/repositories/job_repository.py`
- Modify: `services/jobs/job_service.py` (upsert_jobs, upsert_applications 잔여, upsert_remember_details, get_jobs_without_details None 경로, get_unapplied_jobs, get_unapplied_job_rows)
- Test: `tests/test_repositories.py` (추가)

- [ ] **Step 1: 실패하는 테스트 추가**

```python
from db.repositories.job_repository import JobRepository


def test_job_find_existing_pairs():
    mock_session = MagicMock()
    mock_session.execute.return_value.all.return_value = [("wanted", 1001)]
    repo = JobRepository(mock_session)
    result = repo.find_existing_pairs("wanted", [1001, 1002])
    assert ("wanted", 1001) in result


def test_job_find_platform_id_map():
    mock_session = MagicMock()
    mock_row = MagicMock()
    mock_row.platform_id = 1001
    mock_row.internal_id = 42
    mock_session.execute.return_value.all.return_value = [mock_row]
    repo = JobRepository(mock_session)
    result = repo.find_platform_id_map("wanted", [1001])
    assert result == {1001: 42}


def test_job_find_without_details():
    mock_session = MagicMock()
    mock_session.scalars.return_value.all.return_value = [201, 202]
    repo = JobRepository(mock_session)
    result = repo.find_without_details("wanted", limit=10)
    assert result == [201, 202]


def test_job_find_unapplied_returns_rows():
    mock_session = MagicMock()
    mock_session.execute.return_value.mappings.return_value.all.return_value = [
        {"internal_id": 1, "source": "wanted", "platform_id": 1001,
         "company_name": "A사", "title": "Backend", "location": "서울", "employment_type": "regular"}
    ]
    repo = JobRepository(mock_session)
    result = repo.find_unapplied()
    assert len(result) == 1


def test_job_find_unapplied_with_details_returns_rows():
    mock_session = MagicMock()
    mock_session.execute.return_value.mappings.return_value.all.return_value = []
    repo = JobRepository(mock_session)
    result = repo.find_unapplied_with_details(include_evaluated=False)
    assert result == []
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
pytest tests/test_repositories.py::test_job_find_existing_pairs -v
```
Expected: `ImportError`

- [ ] **Step 3: JobRepository 구현**

```python
# db/repositories/job_repository.py
from sqlalchemy.orm import Session
from sqlalchemy import select, update, text, tuple_
from sqlalchemy.dialects.mysql import insert
from db.models import Job, JobDetail as OrmJobDetail, JobSkip, JobEvaluation, Application


class JobRepository:
    def __init__(self, session: Session):
        self.session = session

    def find_existing_pairs(self, source: str, platform_ids: list[int]) -> set[tuple]:
        pairs = [(source, pid) for pid in platform_ids]
        return set(self.session.execute(
            select(Job.source, Job.platform_id)
            .where(tuple_(Job.source, Job.platform_id).in_(pairs))
        ).all())

    def upsert(self, rows: list[dict]):
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
        return self.session.execute(stmt.on_duplicate_key_update(**update_dict))

    def deactivate_removed(self, source: str, synced_pairs: list[tuple]) -> None:
        self.session.execute(
            update(Job)
            .where(Job.source == source)
            .where(tuple_(Job.source, Job.platform_id).not_in(synced_pairs))
            .where(Job.is_active == True)
            .values(is_active=False)
        )

    def find_platform_id_map(self, source: str, platform_ids: list[int]) -> dict:
        rows = self.session.execute(
            select(Job.platform_id, Job.internal_id)
            .where(Job.source == source)
            .where(Job.platform_id.in_(platform_ids))
        ).all()
        return {row.platform_id: row.internal_id for row in rows}

    def find_without_details(self, source: str, limit: int | None = None) -> list[int]:
        stmt = (
            select(Job.internal_id)
            .outerjoin(OrmJobDetail, Job.internal_id == OrmJobDetail.job_id)
            .where(OrmJobDetail.job_id.is_(None))
            .where(Job.is_active.is_(True))
            .where(Job.source == source)
            .order_by(Job.internal_id)
        )
        if limit is not None:
            stmt = stmt.limit(limit)
        return list(self.session.scalars(stmt).all())

    def find_unapplied(
        self,
        job_group_id: int | None = None,
        location: str | None = None,
        employment_type: str | None = None,
        limit: int = 20,
    ) -> list:
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
        return self.session.execute(stmt).mappings().all()

    def find_unapplied_with_details(
        self,
        job_group_id: int | None = None,
        location: str | None = None,
        employment_type: str | None = None,
        include_evaluated: bool = False,
    ) -> list:
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
            .outerjoin(JobEvaluation, Job.internal_id == JobEvaluation.job_id)
            .where(tuple_(Job.company_name, Job.title).not_in(applied_pairs))
            .where(JobSkip.job_id.is_(None))
            .where(Job.is_active.is_(True))
        )
        if not include_evaluated:
            stmt = stmt.where(JobEvaluation.job_id.is_(None))
        if job_group_id is not None:
            stmt = stmt.where(Job.job_group_id == job_group_id)
        if location:
            stmt = stmt.where(Job.location.ilike(f"%{location}%"))
        if employment_type:
            stmt = stmt.where(Job.employment_type == employment_type)
        return self.session.execute(stmt).mappings().all()
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
pytest tests/test_repositories.py -v
```
Expected: 전체 PASS

- [ ] **Step 5: job_service.py 나머지 메서드 교체**

`upsert_jobs`:
```python
def upsert_jobs(self, raw_jobs: list[dict], source: str = WANTED, full_sync: bool = False) -> str:
    if not raw_jobs:
        return "동기화 완료: 신규 0개, 변경 0개, 유지 0개"

    rows = [self._parse_job(j, source=source) for j in raw_jobs]
    synced_pairs = [(source, r["platform_id"]) for r in rows]

    with Session(self.engine) as session:
        repo = JobRepository(session)
        existing_pairs = repo.find_existing_pairs(source, [r["platform_id"] for r in rows])
        new_count = len(rows) - len(existing_pairs)

        result = repo.upsert(rows)
        session.commit()

        if full_sync and synced_pairs:
            repo.deactivate_removed(source, synced_pairs)
            session.commit()

    updated_count = (result.rowcount - new_count) // 2
    unchanged_count = len(rows) - new_count - updated_count
    return f"동기화 완료: 신규 {new_count}개, 변경 {updated_count}개, 유지 {unchanged_count}개"
```

`upsert_applications` (job_id_map 조회 교체):
```python
def upsert_applications(self, raw_apps: list[dict], source: str = WANTED) -> str:
    if not raw_apps:
        return "지원현황 동기화 완료: 총 0건"

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    parsed = self._parse_applications(raw_apps, source)

    if not parsed:
        return "지원현황 동기화 완료: 총 0건"

    job_platform_ids = [p["job_platform_id"] for p in parsed]

    with Session(self.engine) as session:
        job_id_map = JobRepository(session).find_platform_id_map(source, job_platform_ids)

        rows = []
        for p in parsed:
            job_internal_id = job_id_map.get(p["job_platform_id"])
            if job_internal_id is None:
                continue
            apply_time = (
                datetime.fromisoformat(p["apply_time_str"]).replace(tzinfo=None)
                if p["apply_time_str"] else None
            )
            rows.append({
                "source": source,
                "platform_id": p["platform_id"],
                "job_id": job_internal_id,
                "status": p["status"],
                "apply_time": apply_time,
                "synced_at": now,
            })

        if not rows:
            return "지원현황 동기화 완료: 총 0건"

        ApplicationRepository(session).upsert(rows)
        session.commit()

    return f"지원현황 동기화 완료: 총 {len(rows)}건"
```

`upsert_remember_details`:
```python
def upsert_remember_details(self, raw_jobs: list[dict]) -> None:
    if not raw_jobs:
        return
    platform_ids = [r["id"] for r in raw_jobs]
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with Session(self.engine) as session:
        internal_id_map = JobRepository(session).find_platform_id_map(REMEMBER, platform_ids)
        detail_rows = []
        for raw in raw_jobs:
            internal_id = internal_id_map.get(raw["id"])
            if not internal_id:
                continue
            categories = raw.get("job_categories") or []
            skill_tags = [{"text": c["level2"]} for c in categories if c.get("level2")]
            detail_rows.append({
                "job_id": internal_id,
                "requirements": raw.get("qualifications"),
                "preferred_points": raw.get("preferred_qualifications"),
                "skill_tags": skill_tags,
                "fetched_at": now,
            })
        if not detail_rows:
            return
        JobDetailRepository(session).upsert(detail_rows)
        session.commit()
```

`get_jobs_without_details` (None 경로 교체):
```python
def get_jobs_without_details(
    self,
    job_ids: list[int] | None = None,
    limit: int | None = None,
) -> list[int]:
    if job_ids is not None:
        with Session(self.engine) as session:
            existing = JobDetailRepository(session).find_existing_job_ids(job_ids)
        missing = [jid for jid in job_ids if jid not in existing]
        return missing[:limit] if limit is not None else missing

    with Session(self.engine) as session:
        return JobRepository(session).find_without_details(source=WANTED, limit=limit)
```

`get_unapplied_jobs`:
```python
def get_unapplied_jobs(
    self,
    job_group_id: int | None = None,
    location: str | None = None,
    employment_type: str | None = None,
    limit: int = 20,
) -> str:
    if employment_type:
        employment_type = self.EMPLOYMENT_TYPE_MAP.get(employment_type, employment_type)
    with Session(self.engine) as session:
        rows = JobRepository(session).find_unapplied(
            job_group_id=job_group_id,
            location=location,
            employment_type=employment_type,
            limit=limit,
        )
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

`get_unapplied_job_rows`:
```python
def get_unapplied_job_rows(
    self,
    job_group_id: int | None = None,
    location: str | None = None,
    employment_type: str | None = None,
    include_evaluated: bool = False,
) -> list[JobCandidate]:
    if employment_type:
        employment_type = self.EMPLOYMENT_TYPE_MAP.get(employment_type, employment_type)
    with Session(self.engine) as session:
        rows = JobRepository(session).find_unapplied_with_details(
            job_group_id=job_group_id,
            location=location,
            employment_type=employment_type,
            include_evaluated=include_evaluated,
        )
    return [JobCandidate.from_row(r) for r in rows]
```

상단 import 추가:
```python
from db.repositories.job_repository import JobRepository
```

- [ ] **Step 6: `test_upsert_remember_details_inserts_skill_tags` 테스트 수정**

`services.jobs.job_service.insert`는 Task 8에서 제거된다. 지금 미리 수정해 둔다.

`tests/test_job_service.py`의 `test_upsert_remember_details_inserts_skill_tags`를:
```python
# 수정 전
with patch("services.jobs.job_service.Session") as MockSession, \
     patch("services.jobs.job_service.insert") as mock_insert:
    ...
    mock_ins.on_duplicate_key_update.assert_called_once()
```

아래로 교체:
```python
def test_upsert_remember_details_inserts_skill_tags():
    raw_jobs = [{
        "id": 999,
        "qualifications": "Python 3년",
        "preferred_qualifications": "Django 우대",
        "job_categories": [
            {"level1": "SW개발", "level2": "백엔드"},
            {"level1": "SW개발", "level2": "풀스택"},
        ],
    }]
    mock_engine = MagicMock()
    with patch("services.jobs.job_service.Session") as MockSession:
        mock_session = MagicMock()
        MockSession.return_value.__enter__ = MagicMock(return_value=mock_session)
        MockSession.return_value.__exit__ = MagicMock(return_value=False)

        mock_row = MagicMock()
        mock_row.platform_id = 999
        mock_row.internal_id = 1
        mock_session.execute.return_value.all.return_value = [mock_row]

        service = JobService(engine=mock_engine)
        service.upsert_remember_details(raw_jobs)

    mock_session.execute.assert_called()
    mock_session.commit.assert_called_once()
```

- [ ] **Step 7: 전체 테스트 통과 확인**

```bash
pytest -v
```
Expected: 전체 PASS

- [ ] **Step 8: 커밋**

```bash
git add db/repositories/job_repository.py tests/test_repositories.py tests/test_job_service.py services/jobs/job_service.py
git commit -m "feat: extract JobRepository, complete JobService repository wiring"
```

---

### Task 8: job_service.py 불필요 import 정리

**Files:**
- Modify: `services/jobs/job_service.py` (import 정리)

- [ ] **Step 1: job_service.py 상단 import 정리**

제거할 항목:
```python
# 제거
from sqlalchemy import select, update, text, tuple_
from sqlalchemy.dialects.mysql import insert
from db.models import Job, Application, JobDetail as OrmJobDetail, SearchPreset, JobSkip, JobEvaluation
```

유지할 항목:
```python
import json
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from services.wanted.wanted_constants import WANTED
from services.remember.remember_constants import REMEMBER
from domain import JobCandidate, JobDetail
from db.repositories.search_preset_repository import SearchPresetRepository
from db.repositories.job_detail_repository import JobDetailRepository
from db.repositories.application_repository import ApplicationRepository
from db.repositories.job_skip_repository import JobSkipRepository
from db.repositories.job_evaluation_repository import JobEvaluationRepository
from db.repositories.job_repository import JobRepository
```

- [ ] **Step 2: 전체 테스트 통과 확인**

```bash
pytest -v
```
Expected: 전체 PASS

- [ ] **Step 3: 커밋**

```bash
git add services/jobs/job_service.py
git commit -m "refactor: remove unused SQLAlchemy imports from JobService"
```
