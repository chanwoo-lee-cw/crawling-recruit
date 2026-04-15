# SQLAlchemy ORM 마이그레이션 설계

**날짜:** 2026-04-15  
**목표:** `text()` raw SQL 쿼리를 SQLAlchemy ORM 표현식으로 교체하고, `Table` 객체를 ORM Mapped Classes로 전환한다.

---

## 배경 및 동기

현재 `job_service.py`에는 `text()` raw SQL이 4곳에 있다. 키 오타나 컬럼 변경 시 런타임까지 에러가 드러나지 않고, IDE 지원도 없다. ORM 표현식으로 전환하면 컬럼 참조가 Python 속성이 되어 타입 안전성과 자동완성을 확보한다.

---

## 설계 원칙

- **읽기 쿼리**: ORM 표현식(`select()`, `outerjoin()`, `where()`)으로 전환
- **쓰기(upsert)**: MySQL 전용 `insert().on_duplicate_key_update()` 유지 — Core로 처리. `Session.execute(Core stmt)` 방식으로 Session 안에서 혼용
- **연결 관리**: `engine.connect()` → `Session(self.engine)` 전환
- **구현 순서**: 이 ORM 마이그레이션을 먼저 적용한 뒤 domain dataclasses 스펙(`2026-04-15-domain-dataclasses-design.md`)을 적용한다

---

## 변경 파일

### `db/models.py` — `Table` → ORM Mapped Classes

독립 `Table` 객체(`jobs_table`, `applications_table` 등)를 삭제하고 `DeclarativeBase` 기반 mapped class로 교체한다. upsert에서는 `Job.__table__`로 접근한다.

```python
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import Integer, String, Boolean, DateTime, JSON, Text, ForeignKey
from typing import Optional

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

    detail: Mapped[Optional["JobDetail"]] = relationship(back_populates="job")
    applications: Mapped[list["Application"]] = relationship(back_populates="job")


class Application(Base):
    __tablename__ = "applications"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), nullable=False)  # relationship() 동작에 필수
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

---

### `db/connection.py` — `metadata` 소스 변경

`metadata` import를 `Base`로 교체. `get_engine()`과 `create_tables()` 모두 수정.

```python
# 변경 전
from db.models import metadata

def create_tables():
    engine = get_engine()
    metadata.create_all(engine)

# 변경 후
from sqlalchemy.orm import Session
from db.models import Base

def create_tables():
    engine = get_engine()
    Base.metadata.create_all(engine)
```

---

### `services/job_service.py` — 4개 `text()` 쿼리 → ORM 표현식

import 변경:
```python
# 삭제
from db.models import jobs_table, applications_table, search_presets_table, job_details_table

# 추가
from sqlalchemy.orm import Session
from db.models import Job, Application, JobDetail, SearchPreset
```

**`get_jobs_without_details`** — `text()` 2개 → ORM 1개 (LIMIT 조건 분기 제거):

```python
def get_jobs_without_details(self, job_ids=None, limit=None) -> list[int]:
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
```

**`get_unapplied_jobs`** — `text()` → ORM:

```python
def get_unapplied_jobs(self, job_group_id=None, location=None, employment_type=None, limit=20) -> str:
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
    ...
```

**`get_unapplied_job_rows`** — `text()` → ORM:

```python
def get_unapplied_job_rows(self, job_group_id=None, location=None, employment_type=None):
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
    ...  # skill_tags JSON 파싱은 현행 유지 (dataclasses 스펙에서 from_row()로 이동 예정)
```

**`upsert_jobs`** — 3곳 모두 Session으로 전환:

```python
# (1) 사전 조회: existing_ids
# 변경 전: select(jobs_table.c.id).where(jobs_table.c.id.in_(synced_ids))
# 변경 후:
session.scalars(select(Job.id).where(Job.id.in_(synced_ids))).all()

# (2) bulk upsert: 테이블 참조만 교체
# 변경 전: insert(jobs_table).values(rows)
# 변경 후:
stmt = insert(Job.__table__).values(rows)
# update_dict의 text("IF(...)") 는 MySQL 방언 표현식 — 의도적으로 text() 유지
result = session.execute(stmt.on_duplicate_key_update(**update_dict))

# (3) full_sync 비활성화 UPDATE
# 변경 전: jobs_table.update().where(jobs_table.c.id.not_in(...))...
# 변경 후:
from sqlalchemy import update
session.execute(
    update(Job)
    .where(Job.id.not_in(synced_ids))
    .where(Job.is_active == True)
    .values(is_active=False)
)
session.commit()
```

**`upsert_applications`** — `insert(applications_table)` → `insert(Application.__table__)`

**`upsert_job_details`** — `insert(job_details_table)` → `insert(JobDetail.__table__)`

**`save_preset`** — `insert(search_presets_table)` → `insert(SearchPreset.__table__)`, 그리고 `json.dumps(params)` 제거:

```python
# 변경 전
row = {"name": name, "params": json.dumps(params, ensure_ascii=False), ...}

# 변경 후
row = {"name": name, "params": params, ...}  # SQLAlchemy JSON 컬럼이 직렬화 처리
```

> `get_preset_params`의 `isinstance(params, str)` 분기는 기존 데이터 호환성을 위해 유지.

**`upsert_applications`, `upsert_job_details`** — 각각 `insert(Application.__table__)`, `insert(JobDetail.__table__)` 로 교체 (이외 로직 변경 없음).

**`list_presets`** — Core `table.select()` → ORM `select()`:

```python
# 변경 전
search_presets_table.select().order_by(search_presets_table.c.created_at)

# 변경 후
rows = session.scalars(
    select(SearchPreset).order_by(SearchPreset.created_at)
).all()
# row는 SearchPreset ORM 객체 → row.name 으로 접근
names = ", ".join(r.name for r in rows)
```

**`get_preset_params`** — Core → ORM:

```python
# 변경 전
search_presets_table.select().where(search_presets_table.c.name == name)
# row["params"] → json.loads(params) if isinstance(params, str) else params

# 변경 후
row = session.scalars(
    select(SearchPreset).where(SearchPreset.name == name)
).first()
if not row:
    return None
# JSON 컬럼은 SQLAlchemy가 자동 역직렬화 — row.params는 이미 dict
return row.params
```

> **주의**: `get_preset_params`의 `isinstance(params, str)` 분기는 ORM이 JSON 컬럼을 자동으로 dict으로 반환하므로 제거 가능. 단, 안전을 위해 기존 분기를 유지해도 무방.

---

### `tests/test_job_service.py` — mock 패턴 전환

`engine.connect()` mock → `Session` mock으로 전면 교체. 영향받는 테스트 전체:

```python
# 변경 전 (모든 테스트 공통 패턴)
mock_conn = MagicMock()
mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

# 변경 후
with patch("services.job_service.Session") as MockSession:
    mock_session = MagicMock()
    MockSession.return_value.__enter__ = MagicMock(return_value=mock_session)
    MockSession.return_value.__exit__ = MagicMock(return_value=False)
    # scalars().all() 패턴 (get_jobs_without_details, list_presets 등):
    mock_session.scalars.return_value.all.return_value = [...]
    # execute().mappings().all() 패턴 (get_unapplied_jobs, get_unapplied_job_rows):
    mock_session.execute.return_value.mappings.return_value.all.return_value = [...]
    # execute().rowcount 패턴 (upsert):
    mock_session.execute.return_value.rowcount = 1
```

**`test_upsert_jobs_calls_execute`** — 현재 `side_effect = [pre_query_result, upsert_result]` 두 번 호출 패턴. Session 전환 후 `scalars()`와 `execute()` 호출이 분리되므로 각각 mock:

```python
mock_session.scalars.return_value.all.return_value = []  # existing_ids 조회
upsert_result = MagicMock()
upsert_result.rowcount = 1
mock_session.execute.return_value = upsert_result
```

---

### `tests/test_db.py` — `Table` 객체 참조 → `Model.__table__` 으로 교체

```python
# 변경 전
from db.models import jobs_table, applications_table, search_presets_table

def test_models_defined():
    assert jobs_table is not None

def test_jobs_table_columns():
    col_names = {c.name for c in jobs_table.columns}

# 변경 후
from db.models import Job, Application, SearchPreset

def test_models_defined():
    assert Job.__table__ is not None
    assert Application.__table__ is not None
    assert SearchPreset.__table__ is not None

def test_jobs_table_columns():
    col_names = {c.name for c in Job.__table__.columns}
    # 검증 컬럼 집합은 동일
```

---

## 영향 없는 파일

- `tools/` 하위 전체 — `JobService` / `WantedClient` 호출만, DB 직접 접근 없음
- `services/wanted_client.py` — DB 미사용
- `tests/test_tools.py` — ORM 마이그레이션 범위에서는 변경 없음. 단, `from tools.recommend_jobs import recommend_jobs` (line 127)는 해당 파일이 이미 삭제된 pre-existing 실패이므로, 마이그레이션 후 `pytest` 실행 시 이 실패가 ORM 관련 회귀로 혼동되지 않도록 주의 (`sync_job_details` mock 수정은 dataclasses 스펙에서 처리)

---

## 구현 순서 (두 스펙 합산)

1. **ORM 마이그레이션** (이 문서)
   - `db/models.py` mapped classes 정의
   - `db/connection.py` Base.metadata 교체
   - `job_service.py` text() → ORM, engine.connect() → Session
   - 테스트 mock 패턴 교체
2. **Domain Dataclasses** (`2026-04-15-domain-dataclasses-design.md`)
   - `domain.py` 신규 작성
   - `get_unapplied_job_rows` 반환 타입 → `list[JobCandidate]`
   - `get_recommended_jobs` 시그니처 → `list[JobCandidate]`
   - `fetch_job_detail` 반환 타입 → `JobDetail`
   - 테스트 dict 접근 → 속성 접근
