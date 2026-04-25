# Remeber 플랫폼 통합 설계

**목표:** Remeber 채용공고와 지원 현황을 크롤링해 기존 Wanted 데이터와 통합 관리한다. `get_unapplied_jobs`, `get_job_candidates`, `skip_jobs` 등 기존 툴이 두 플랫폼을 자동으로 커버한다.

**배경:** Wanted 외에도 Remeber(career-api.rememberapp.co.kr)에서 채용공고를 검색하고 지원한다. 두 플랫폼의 데이터를 하나의 DB에서 통합 관리해 중복 추천을 방지하고, 이후 다른 플랫폼 추가도 동일한 패턴으로 확장 가능하게 한다.

---

## 1. DB 스키마 마이그레이션

### 핵심 변경: `jobs` 테이블

| 변경 | 내용 |
|------|------|
| `id` → `platform_id` | 각 플랫폼 원래 ID (Wanted job ID, Remeber job posting ID) |
| `internal_id` 추가 | INT AUTO_INCREMENT, 새 PK — 내부 참조용 |
| `source` 추가 | VARCHAR(20) NOT NULL DEFAULT 'wanted' ("wanted" / "remember") |
| UNIQUE 제약 추가 | `(source, platform_id)` |

**migration SQL — 순서 중요 (MySQL FK/PK 제약 조건 대응):**

```sql
-- 1. FK 제약 먼저 제거 (참조하는 테이블의 PK 변경 전 필수)
ALTER TABLE applications DROP FOREIGN KEY applications_ibfk_1;  -- job_id FK
ALTER TABLE job_details DROP FOREIGN KEY job_details_ibfk_1;
ALTER TABLE job_skips DROP FOREIGN KEY job_skips_ibfk_1;

-- 2. jobs: PK DROP + AUTO_INCREMENT 제거 + rename을 단일 ALTER TABLE로 처리
--    (MySQL은 AUTO_INCREMENT 컬럼의 PK DROP 후 중간 상태를 허용하지 않음)
ALTER TABLE jobs
    DROP PRIMARY KEY,
    CHANGE COLUMN id platform_id INT NOT NULL;

-- 3. 새 AUTO_INCREMENT PK 추가
ALTER TABLE jobs ADD COLUMN internal_id INT AUTO_INCREMENT PRIMARY KEY FIRST;

-- 4. source 컬럼 추가 및 기존 데이터 설정
ALTER TABLE jobs ADD COLUMN source VARCHAR(20) NOT NULL DEFAULT 'wanted';
ALTER TABLE jobs ADD UNIQUE KEY uq_source_platform (source, platform_id);

-- 5. applications 테이블 job_id를 internal_id 기준으로 업데이트
UPDATE applications a JOIN jobs j ON a.job_id = j.platform_id AND j.source = 'wanted'
SET a.job_id = j.internal_id;

-- 6. job_details, job_skips 동일하게 업데이트
UPDATE job_details jd JOIN jobs j ON jd.job_id = j.platform_id AND j.source = 'wanted'
SET jd.job_id = j.internal_id;
UPDATE job_skips js JOIN jobs j ON js.job_id = j.platform_id AND j.source = 'wanted'
SET js.job_id = j.internal_id;

-- 7. FK 재추가 (internal_id 참조)
ALTER TABLE applications ADD CONSTRAINT applications_ibfk_1
    FOREIGN KEY (job_id) REFERENCES jobs(internal_id) ON DELETE CASCADE;
ALTER TABLE job_details ADD CONSTRAINT job_details_ibfk_1
    FOREIGN KEY (job_id) REFERENCES jobs(internal_id) ON DELETE CASCADE;
ALTER TABLE job_skips ADD CONSTRAINT job_skips_ibfk_1
    FOREIGN KEY (job_id) REFERENCES jobs(internal_id) ON DELETE CASCADE;
```

### `applications` 테이블

| 변경 | 내용 |
|------|------|
| `id` → `platform_id` | Wanted application ID 또는 Remeber application ID |
| `internal_id` 추가 | INT AUTO_INCREMENT, 새 PK |
| `source` 추가 | VARCHAR(20) NOT NULL DEFAULT 'wanted' |
| `job_id` | `jobs.internal_id` 참조 (migration 후) |

```sql
ALTER TABLE applications DROP PRIMARY KEY;
ALTER TABLE applications RENAME COLUMN id TO platform_id;
ALTER TABLE applications ADD COLUMN internal_id INT AUTO_INCREMENT PRIMARY KEY FIRST;
ALTER TABLE applications ADD COLUMN source VARCHAR(20) NOT NULL DEFAULT 'wanted';
ALTER TABLE applications ADD UNIQUE KEY uq_app_source_platform (source, platform_id);
```

### ORM 클래스 변경 (`db/models.py`)

```python
class Job(Base):
    __tablename__ = "jobs"
    internal_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="wanted")
    platform_id: Mapped[int] = mapped_column(Integer, nullable=False)
    company_id: Mapped[Optional[int]] = mapped_column(Integer)  # Wanted only
    company_name: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    location: Mapped[Optional[str]] = mapped_column(String(100))
    employment_type: Mapped[Optional[str]] = mapped_column(String(20))
    annual_from: Mapped[Optional[int]] = mapped_column(Integer)
    annual_to: Mapped[Optional[int]] = mapped_column(Integer)
    job_group_id: Mapped[Optional[int]] = mapped_column(Integer)  # Wanted only
    category_tag_id: Mapped[Optional[int]] = mapped_column(Integer)  # Wanted only
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    __table_args__ = (UniqueConstraint("source", "platform_id", name="uq_source_platform"),)

    applications: Mapped[list["Application"]] = relationship(back_populates="job")
    detail: Mapped[Optional["JobDetail"]] = relationship(back_populates="job", uselist=False)
    skip: Mapped[Optional["JobSkip"]] = relationship(back_populates="job", uselist=False)
```

```python
class Application(Base):
    __tablename__ = "applications"
    internal_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="wanted")
    platform_id: Mapped[int] = mapped_column(Integer, nullable=False)
    job_id: Mapped[int] = mapped_column(Integer, ForeignKey("jobs.internal_id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    apply_time: Mapped[Optional[datetime]] = mapped_column(DateTime)
    synced_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    __table_args__ = (UniqueConstraint("source", "platform_id", name="uq_app_source_platform"),)
    job: Mapped["Job"] = relationship(back_populates="applications")
```

---

## 2. `domain.py` 변경

`Job.id` → `Job.internal_id` 변경에 따라 `JobCandidate` 필드명도 변경한다.

```python
@dataclass
class JobCandidate:
    internal_id: int        # jobs.internal_id (기존 id → internal_id)
    source: str             # "wanted" | "remember"
    platform_id: int        # 플랫폼 원래 ID (URL 생성용)
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
        # skill_tags: None / JSON string / list 처리 (기존 try/except 패턴 유지)
        import json
        raw_tags = row["skill_tags"] or []
        if isinstance(raw_tags, str):
            try:
                raw_tags = json.loads(raw_tags)
            except (json.JSONDecodeError, TypeError):
                raw_tags = []
        tags = [SkillTag(text=t["text"]) for t in raw_tags]
        return cls(
            internal_id=row["internal_id"],
            source=row["source"],
            platform_id=row["platform_id"],
            company_name=row["company_name"],
            title=row["title"],
            location=row["location"],
            employment_type=row["employment_type"],
            requirements=row["requirements"],
            preferred_points=row["preferred_points"],
            skill_tags=tags,
            fetched_at=row["fetched_at"],
        )
```

---

## 3. URL 상수

```python
# services/job_service.py
WANTED_JOB_BASE_URL = "https://www.wanted.co.kr/wd"
REMEMBER_JOB_BASE_URL = "https://career.rememberapp.co.kr/job/posting"  # 실제 URL 확인 필요

JOB_BASE_URLS = {
    "wanted": WANTED_JOB_BASE_URL,
    "remember": REMEMBER_JOB_BASE_URL,
}
```

`get_unapplied_jobs` / `get_unapplied_job_rows`에서 URL 생성:
```python
base_url = JOB_BASE_URLS.get(row["source"], WANTED_JOB_BASE_URL)
url = f"{base_url}/{row['platform_id']}"
```

---

## 4. Cross-Platform 중복 지원 필터

같은 회사의 동일 직책에 이미 지원했다면 다른 플랫폼의 동일 공고도 제외한다.

`get_unapplied_job_rows` / `get_unapplied_jobs` 쿼리:

```python
from sqlalchemy import tuple_

# 이미 지원한 (company_name, title) 쌍 서브쿼리
applied_pairs = (
    select(Job.company_name, Job.title)
    .join(Application, Job.internal_id == Application.job_id)
)
stmt = stmt.where(tuple_(Job.company_name, Job.title).not_in(applied_pairs))
```

> 기존 `Application.job_id.is_(None)` LEFT OUTER JOIN 방식을 제거하고 `(company_name, title)` 서브쿼리 방식으로 교체한다. LEFT OUTER JOIN은 동일 `internal_id`만 필터링하므로 cross-platform 케이스를 커버할 수 없다.

---

## 5. `skip_jobs` 호환성: `internal_id` 노출

`skip_jobs` 툴이 `job_ids: list[int]`를 받는다. migration 후 이 값은 `internal_id`여야 한다. Claude Code가 `get_unapplied_jobs` / `get_job_candidates` 결과에서 `internal_id`를 알 수 있도록 두 툴의 출력에 `internal_id`를 포함한다.

**`get_unapplied_jobs` 마크다운 테이블 변경:**
```
| internal_id | 회사명 | 포지션 | 지역 | 링크 |
```

**`get_job_candidates` JSON 출력 변경:**
```python
{
    "internal_id": c.internal_id,   # skip_jobs 호출 시 사용
    "url": f"{base_url}/{c.platform_id}",
    "company_name": c.company_name,
    ...
}
```

---

## 6. 새 클라이언트: `services/remember_client.py`

`WantedClient`와 동일한 구조를 따른다.

```python
class RememberClient:
    BASE_URL = "https://career-api.rememberapp.co.kr"

    def __init__(self):
        cookie = os.getenv("REMEMBER_COOKIE")
        self.headers = {"Cookie": cookie}

    def fetch_jobs(
        self,
        job_category_names: list[dict],  # [{"level1": "SW개발", "level2": "백엔드"}, ...]
        min_experience: int = 0,
        max_experience: int = 10,
        page: int = 1,
        per: int = 30,
    ) -> list[dict]:
        """공고 목록 + 상세(qualifications, preferred_qualifications) 반환."""
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
        # POST /job_postings/search → response["data"] 반환
        ...

    def fetch_applications(self, page: int = 1) -> list[dict]:
        """지원한 공고 목록 반환. application 객체가 각 공고에 임베드됨."""
        # GET /open_profiles/me/job_postings/application_histories
        # ?statuses[]=applied&page={page}&include_canceled=false
        # → response["data"] 반환 (application != null인 항목만)
        ...
```

### Remeber API 필드 매핑

**Jobs:**
| DB 컬럼 | Remeber 필드 | 비고 |
|---------|-------------|------|
| `platform_id` | `data[].id` | |
| `company_name` | `data[].organization.name` | |
| `title` | `data[].title` | |
| `location` | `data[].addresses[0].address_level1 + " " + address_level2` | null-safe |
| `employment_type` | null | Remeber 미제공 |
| `annual_from` | `data[].min_salary` | |
| `annual_to` | `data[].max_salary` | |
| `company_id` | null | |
| `job_group_id` | null | |

**Job Details (sync 시 함께 저장):**
| DB 컬럼 | Remeber 필드 |
|---------|-------------|
| `requirements` | `data[].qualifications` |
| `preferred_points` | `data[].preferred_qualifications` |
| `skill_tags` | `"[]"` (Remeber 미제공) |

**Applications:**
| DB 컬럼 | Remeber 필드 |
|---------|-------------|
| `platform_id` | `data[].application.id` |
| `status` | `data[].application.status` |
| `apply_time` | `data[].application.applied_at` |

---

## 7. `JobService` 변경

### `_parse_job(raw, source)` 분기

```python
def _parse_job(self, raw: dict, source: str = "wanted") -> dict:
    if source == "remember":
        return self._parse_remember_job(raw)
    return self._parse_wanted_job(raw)
```

### `upsert_jobs(raw_jobs, source, full_sync)` source-aware upsert

- `(source, platform_id)` 기준 ON DUPLICATE KEY UPDATE (MySQL은 UNIQUE KEY 위반 시 트리거됨)
- 기존 `existing_ids` 카운팅 로직: `Job.id.in_(synced_ids)` → `(source, platform_id)` 쌍 기준으로 변경:
  ```python
  existing_pairs = set(session.execute(
      select(Job.source, Job.platform_id)
      .where(tuple_(Job.source, Job.platform_id).in_([(source, r["platform_id"]) for r in rows]))
  ).all())
  new_count = len(rows) - len(existing_pairs)
  ```
- `full_sync=True` 비활성화 쿼리: `Job.id.not_in(synced_ids)` → source-aware로 변경:
  ```python
  session.execute(
      update(Job)
      .where(Job.source == source)
      .where(tuple_(Job.source, Job.platform_id).not_in([(source, r["platform_id"]) for r in rows]))
      .where(Job.is_active == True)
      .values(is_active=False)
  )
  ```
- source="remember"일 때 `job_details`도 동일 세션에서 함께 upsert

### `upsert_applications(raw_apps, source)` source-aware

- source="remember"일 때:
  1. 배치 조회로 `job_id` 매핑 (`job_platform_ids`와 `application_platform_id`를 명확히 구분):
     ```python
     # app["id"] = 공고 platform_id (jobs.platform_id 조회용)
     job_platform_ids = [app["id"] for app in raw_apps]
     job_map = {row.platform_id: row.internal_id for row in session.execute(
         select(Job.platform_id, Job.internal_id)
         .where(Job.source == "remember")
         .where(Job.platform_id.in_(job_platform_ids))
     ).all()}
     # app["application"]["id"] = 지원 자체의 platform_id (applications 테이블 PK 식별용)
     rows = [{
         "source": "remember",
         "platform_id": app["application"]["id"],   # 지원 ID
         "job_id": job_map[app["id"]],               # jobs.internal_id
         "status": app["application"]["status"],
         "apply_time": datetime.fromisoformat(app["application"]["applied_at"]).replace(tzinfo=None),
         "synced_at": now,
     } for app in raw_apps if app.get("application") and app["id"] in job_map]
     ```
- upsert: `(source, platform_id)` 기준 ON DUPLICATE KEY UPDATE

### `get_unapplied_job_rows` / `get_unapplied_jobs` 변경

- `Application.job_id.is_(None)` LEFT OUTER JOIN 제거
- `(company_name, title)` 서브쿼리 필터로 교체 (Section 4 참고)
- SELECT에 `Job.internal_id`, `Job.source`, `Job.platform_id` 추가
- URL 생성 시 `JOB_BASE_URLS[source]` 사용

### `get_jobs_without_details` 변경

`Job.id` → `Job.internal_id`로 교체:
```python
# 변경 전
select(Job.id).outerjoin(OrmJobDetail, Job.id == OrmJobDetail.job_id)

# 변경 후
select(Job.internal_id).outerjoin(OrmJobDetail, Job.internal_id == OrmJobDetail.job_id)
```
반환 타입 및 `get_jobs_without_details(job_ids)` 파라미터도 `internal_id` 기준으로 동작. `sync_job_details`가 내부적으로 이 메서드를 호출하므로 함께 확인.

---

## 8. MCP 툴 변경

### `sync_jobs(source="wanted", ...)` 확장

```python
def sync_jobs(
    source: str = "wanted",  # "wanted" | "remember"
    # Wanted params
    job_group_id: int | None = None,
    job_ids: list[int] | None = None,
    years: int | None = None,
    locations: list[str] | None = None,
    limit_pages: int | None = None,
    # Remeber params
    job_category_names: list[dict] | None = None,
    min_experience: int = 0,
    max_experience: int = 10,
    preset: str | None = None,
) -> str:
```

- source="wanted": 기존 WantedClient 로직 (변경 없음)
- source="remember": RememberClient.fetch_jobs() 호출 → upsert_jobs(source="remember") + job_details 함께 저장

### `sync_applications(source="wanted")` 확장

```python
def sync_applications(source: str = "wanted") -> str:
```

- source="wanted": 기존 Wanted 로직 (변경 없음)
- source="remember": RememberClient.fetch_applications() 전체 페이지 순회 → upsert_applications(source="remember")

### `sync_job_details` — Wanted 전용 유지

Remeber는 sync_jobs에서 이미 처리하므로 변경 없음.

---

## 9. `db/connection.py` 마이그레이션 실행 방식

기존 `create_tables()`는 `Base.metadata.create_all(engine)`만 호출한다. 마이그레이션 SQL은 **별도 `migrate(engine)` 함수**로 분리해 구현한다.

```python
def migrate(engine) -> str:
    """기존 DB를 multi-source 스키마로 마이그레이션. 이미 완료된 경우 skip."""
    with engine.connect() as conn:
        # 멱등성 보장: platform_id 컬럼이 이미 존재하면 skip
        result = conn.execute(text("SHOW COLUMNS FROM jobs LIKE 'platform_id'"))
        if result.fetchone():
            return "이미 마이그레이션 완료"
        # ... migration SQL 실행 ...
    return "마이그레이션 완료"
```

- `migrate()`는 `create_tables()` 이후 수동으로 한 번만 호출한다 (서버 자동 시작 시 실행 안 함)
- MCP 툴 `migrate_db()` 를 신규 등록해 Claude Code에서 명시적으로 호출 가능하게 한다

### `ALLOWED_PRESET_KEYS` 확장

Remeber 검색 프리셋 지원을 위해 추가:

```python
ALLOWED_PRESET_KEYS = {
    # Wanted
    "job_group_id", "job_ids", "years", "locations", "limit_pages",
    # Remeber
    "job_category_names", "min_experience", "max_experience",
    # 공통
    "source",
}
```

---

## 10. 테스트

### `tests/test_db.py` 수정

- Job/Application 테이블 컬럼 검증: `internal_id`, `source`, `platform_id` 포함 확인

### `tests/test_remember_client.py` 신규

- `test_fetch_jobs_success`: httpx mock으로 응답 파싱 검증 (qualifications, organization.name 등)
- `test_fetch_applications_success`: application 임베드 파싱 검증
- `test_fetch_jobs_http_error`: 비정상 응답 처리 검증

### `tests/test_job_service.py` 추가

- `test_upsert_jobs_remember_source`: source="remember" upsert + job_details 동시 저장 검증
- `test_upsert_applications_remember_source`: 배치 job_id 조회 및 매핑 검증
- `test_get_unapplied_job_rows_cross_platform_filter`: `(company_name, title)` 서브쿼리 방식으로 rows 반환 검증

### `tests/test_tools.py` 추가

- `test_sync_jobs_remember_calls_service`: source="remember"일 때 RememberClient 경로 검증
- `test_sync_applications_remember_calls_service`: source="remember" 경로 검증

---

## 11. 파일 맵

| 파일 | 변경 유형 | 내용 |
|------|-----------|------|
| `db/models.py` | 수정 | Job/Application에 `internal_id`, `source`, `platform_id` 추가; FK 업데이트 |
| `db/connection.py` | 수정 | `migrate(engine)` 함수 추가 (멱등 마이그레이션 SQL); `create_tables()` 변경 없음 |
| `domain.py` | 수정 | `JobCandidate`: `id` → `internal_id`, `source`, `platform_id` 필드 추가/변경; `from_row` 업데이트 |
| `services/remember_client.py` | 신규 | RememberClient: fetch_jobs, fetch_applications |
| `services/job_service.py` | 수정 | source-aware upsert + full_sync 비활성화, (source, platform_id) 카운팅, cross-platform 필터, get_jobs_without_details `Job.id→internal_id`, URL 상수 추가, ALLOWED_PRESET_KEYS 확장 |
| `tools/sync_jobs.py` | 수정 | `source` 파라미터 추가, Remeber 라우팅 |
| `tools/sync_applications.py` | 수정 | `source` 파라미터 추가, Remeber 라우팅 |
| `tools/migrate_db.py` | 신규 | `migrate_db()` MCP 툴 (migrate 함수 호출) |
| `tools/get_unapplied_jobs.py` | 수정 | `internal_id` 컬럼 추가 |
| `tools/get_job_candidates.py` | 수정 | `internal_id` 필드 추가, URL 생성 source-aware |
| `main.py` | 수정 | `migrate_db` 툴 등록 |
| `tests/test_db.py` | 수정 | Job/Application 새 컬럼 검증 추가 |
| `tests/test_remember_client.py` | 신규 | RememberClient 단위 테스트 |
| `tests/test_job_service.py` | 수정 | source-aware 메서드 테스트 추가 |
| `tests/test_tools.py` | 수정 | source 파라미터 테스트 추가 |
