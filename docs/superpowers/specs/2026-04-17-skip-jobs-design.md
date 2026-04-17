# Skip Jobs 기능 설계

**목표:** 사용자가 지원하지 않을 공고를 명시적으로 제외 표시해 이후 추천/목록에서 자동으로 제외한다.

**배경:** `get_unapplied_jobs`와 `get_job_candidates` 결과에 관심 없는 공고가 반복 노출되는 문제를 해결한다. Claude Code와 Claude Desktop 모두 MCP 툴을 통해 동일하게 사용한다.

> `get_job_candidates`는 내부적으로 `get_unapplied_job_rows()`를 경유하므로, `get_unapplied_job_rows` 쿼리에 skip 필터를 추가하면 `get_job_candidates`도 자동으로 제외 대상이 반영된다. `tools/get_job_candidates.py` 수정 불필요.

---

## 1. DB 스키마

### 신규 테이블: `job_skips`

| 컬럼 | 타입 | 제약 | 설명 |
|------|------|------|------|
| `job_id` | INT | PK, FK(jobs.id, CASCADE) | 제외된 공고 |
| `reason` | VARCHAR(255) | NULL 허용 | 제외 사유 (예: "연봉 낮음", "기술스택 불일치") |
| `skipped_at` | DATETIME | NOT NULL | 제외 시각 (UTC naive: `datetime.now(timezone.utc).replace(tzinfo=None)`) |

- `job_id`가 PK이므로 동일 공고를 중복 제외해도 upsert로 처리 (이미 제외된 공고의 reason/skipped_at 갱신).
- `jobs` 삭제 시 CASCADE로 함께 삭제.

### ORM 클래스 (`db/models.py` 추가)

```python
class JobSkip(Base):
    __tablename__ = "job_skips"

    job_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("jobs.id", ondelete="CASCADE"), primary_key=True
    )
    reason: Mapped[Optional[str]] = mapped_column(String(255))
    skipped_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    job: Mapped["Job"] = relationship(back_populates="skip")
```

`Job` 클래스에 역방향 relationship 추가:
```python
skip: Mapped[Optional["JobSkip"]] = relationship(back_populates="job", uselist=False)
```

---

## 2. JobService 변경 (`services/job_service.py`)

### import 수정

```python
from db.models import Job, Application, JobDetail as OrmJobDetail, SearchPreset, JobSkip
```

### 신규 메서드: `skip_jobs`

```python
def skip_jobs(self, job_ids: list[int], reason: str | None = None) -> str:
    """job_ids를 제외 목록에 추가. 이미 제외된 공고는 reason/skipped_at을 갱신."""
```

- 빈 리스트 입력 시 조기 반환: `"제외할 공고 ID를 입력해주세요."`
- `skipped_at = datetime.now(timezone.utc).replace(tzinfo=None)` (프로젝트 전체 UTC naive 패턴 준수).
- `insert(JobSkip.__table__).on_duplicate_key_update(reason=stmt.inserted.reason, skipped_at=stmt.inserted.skipped_at)` 패턴 사용.
- 반환: `"N개 공고 제외 완료"` 또는 `"N개 공고 제외 완료 (사유: {reason})"`

### 기존 메서드 수정: `get_unapplied_job_rows`

`job_skips` LEFT OUTER JOIN 추가, 제외 공고 필터:

```python
.outerjoin(JobSkip, Job.id == JobSkip.job_id)
.where(JobSkip.job_id.is_(None))
```

### 기존 메서드 수정: `get_unapplied_jobs`

동일하게 `job_skips` LEFT OUTER JOIN + `JobSkip.job_id.is_(None)` 조건 추가.

---

## 3. MCP 툴

### 신규 파일: `tools/skip_jobs.py`

```python
def skip_jobs(job_ids: list[int], reason: str | None = None) -> str:
    """공고를 제외 목록에 추가. 이후 get_unapplied_jobs, get_job_candidates 결과에서 제외됨.

    job_ids: 제외할 공고 ID 목록
    reason: 제외 사유 (선택. 예: "연봉 낮음", "기술스택 불일치")
    """
    try:
        engine = get_engine()
        service = JobService(engine)
        return service.skip_jobs(job_ids, reason)
    except Exception as e:
        return f"오류가 발생했습니다: {e}"
```

- DB 쓰기 작업이므로 `get_job_candidates`와 동일하게 `try/except Exception` 으로 감싼다.

### `main.py` 수정

`skip_jobs` 툴 등록 추가.

---

## 4. 테스트

### `tests/test_job_service.py` 추가

- `test_skip_jobs_calls_execute`: Session mock으로 execute/commit 호출 확인, 반환 문자열 검증
- `test_skip_jobs_empty_list`: 빈 리스트 입력 시 DB 호출 없이 조기 반환 검증
- `test_get_unapplied_job_rows_with_skip_join`: Session mock으로 execute 호출 확인 (실제 SQL 필터는 mock 환경에서 검증 불가; mock이 반환하는 row 목록이 `JobCandidate` 리스트로 변환되는지 확인)

### `tests/test_tools.py` 추가

- `test_skip_jobs_tool_calls_service`: MCP 툴이 `service.skip_jobs(job_ids, reason)`을 올바른 인자로 호출하는지 mock 검증

---

## 파일 맵

| 파일 | 변경 유형 | 내용 |
|------|-----------|------|
| `db/models.py` | 수정 | `JobSkip` ORM 클래스 추가, `Job`에 `skip` relationship |
| `services/job_service.py` | 수정 | import에 `JobSkip` 추가; `skip_jobs` 메서드 추가; `get_unapplied_job_rows`/`get_unapplied_jobs` 쿼리에 skip 필터 추가 |
| `tools/skip_jobs.py` | 신규 생성 | MCP 툴 (`try/except` 포함) |
| `main.py` | 수정 | 툴 등록 |
| `tests/test_job_service.py` | 수정 | 3개 테스트 추가 |
| `tests/test_tools.py` | 수정 | 1개 테스트 추가 |
