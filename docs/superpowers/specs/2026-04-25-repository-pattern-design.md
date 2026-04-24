# Repository Pattern 도입 설계

## 목적

`JobService`에 인라인으로 박혀 있는 SQLAlchemy 쿼리를 `Repository` 레이어로 분리한다.
`JobService`는 파싱·비즈니스 로직·오케스트레이션만 담당하고, DB 쿼리는 각 Repository가 전담한다.
아울러 `db/models.py`를 모델별 개별 파일로 분리한다.

---

## 파일 구조

```
db/
  models/
    __init__.py          # 모든 모델 re-export — 기존 import 경로 유지
    base.py              # Base = DeclarativeBase
    job.py               # Job
    application.py       # Application
    job_detail.py        # JobDetail
    search_preset.py     # SearchPreset
    job_skip.py          # JobSkip
    job_evaluation.py    # JobEvaluation
  connection.py                      # 변경 없음
  repositories/
    __init__.py
    job_repository.py
    application_repository.py
    job_detail_repository.py
    job_skip_repository.py
    job_evaluation_repository.py
    search_preset_repository.py
services/
  jobs/
    job_service.py                   # 파싱 + 비즈니스 로직 + repo 오케스트레이션만
```

### models `__init__.py` 규칙

`from db.models import Job, Application, ...` 형태의 기존 import가 변경 없이 동작하도록
`db/models/__init__.py`에서 모든 모델을 re-export한다.

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

---

## Repository 인터페이스

### `JobRepository`

| 메서드 | 설명 |
|---|---|
| `find_existing_pairs(source, platform_ids) → set[tuple]` | upsert 전 기존 row 확인 |
| `upsert(rows) → CursorResult` | jobs 테이블 upsert |
| `deactivate_removed(source, synced_pairs)` | full_sync 시 누락 공고 비활성화. `upsert`와 같은 session을 사용하되 별도 `commit`으로 분리한다 |
| `find_platform_id_map(source, platform_ids) → dict` | platform_id → internal_id 매핑. `upsert_applications`, `upsert_remember_details` 양쪽에서 사용 |
| `find_without_details(source, limit) → list[int]` | 지정 source의 detail 미수집 활성 공고 ID 목록. `get_jobs_without_details(job_ids=None)` 경로에서 사용. 현재는 `WANTED` 전용 |
| `find_unapplied(filters) → list[RowMapping]` | 미지원 공고 (마크다운용) |
| `find_unapplied_with_details(filters, include_evaluated) → list[RowMapping]` | 미지원 공고 + detail join (추천용). `include_evaluated=False`이면 `job_evaluations IS NULL` 조건 추가 |

### `ApplicationRepository`

| 메서드 | 설명 |
|---|---|
| `upsert(rows)` | applications 테이블 upsert |

### `JobDetailRepository`

| 메서드 | 설명 |
|---|---|
| `find_existing_job_ids(job_ids) → set[int]` | detail 보유 job_id 집합 조회. `get_jobs_without_details(job_ids=...)` 경로에서 사용 |
| `upsert(rows)` | job_details 테이블 upsert |

### `JobSkipRepository`

| 메서드 | 설명 |
|---|---|
| `upsert(rows)` | job_skips 테이블 upsert |

### `JobEvaluationRepository`

| 메서드 | 설명 |
|---|---|
| `upsert(rows)` | job_evaluations 테이블 upsert |

### `SearchPresetRepository`

| 메서드 | 설명 |
|---|---|
| `upsert(row)` | search_presets 테이블 upsert |
| `find_all() → list[SearchPreset]` | 전체 프리셋 조회 |
| `find_by_name(name) → SearchPreset | None` | 이름으로 프리셋 조회 |

---

## Session 관리

Repository는 `session: Session`을 생성자로 받는다.
Session 생명주기(`with Session(engine)`)는 `JobService`가 소유한다.

```python
# 단일 repo 예시
def save_preset(self, name: str, params: dict) -> str:
    ...
    with Session(self.engine) as session:
        SearchPresetRepository(session).upsert(row)
        session.commit()
    return f"프리셋 '{name}' 저장 완료"
```

복수의 repository가 하나의 session을 공유해야 할 때도 service가 session을 생성해 각 repo에 넘긴다.

```python
# 복수 repo 예시
def upsert_applications(self, raw_apps, source):
    ...
    with Session(self.engine) as session:
        job_id_map = JobRepository(session).find_platform_id_map(source, platform_ids)
        ApplicationRepository(session).upsert(rows)
        session.commit()
```

### `upsert_jobs`의 이중 commit 패턴

`upsert_jobs`는 upsert 후 `full_sync=True`일 때 비활성화를 추가로 실행한다.
두 작업은 같은 session 안에서 `commit`을 두 번 호출한다.

```python
def upsert_jobs(self, raw_jobs, source, full_sync=False):
    ...
    with Session(self.engine) as session:
        repo = JobRepository(session)
        result = repo.upsert(rows)
        session.commit()
        if full_sync and synced_pairs:
            repo.deactivate_removed(source, synced_pairs)
            session.commit()
    return ...
```

---

## JobService 변화

### 제거되는 것
- 모든 `with Session(...) as session:` 블록 내 인라인 쿼리

### 유지되는 것
- `_parse_wanted_job`, `_parse_remember_job`, `_parse_job` (파싱 로직)
- `_parse_wanted_applications`, `_parse_remember_applications`, `_parse_applications`
- `get_recommended_jobs` (순수 Python 스킬 매칭 로직)
- 각 public 메서드의 시그니처와 반환 타입 (외부 인터페이스 불변)

### 변화하는 것 (public 메서드 전체)
- `upsert_jobs` → `JobRepository.find_existing_pairs`, `upsert`, `deactivate_removed`
- `upsert_applications` → `JobRepository.find_platform_id_map`, `ApplicationRepository.upsert`
- `upsert_job_details` → `JobDetailRepository.upsert`
- `upsert_remember_details` → `JobRepository.find_platform_id_map`, `JobDetailRepository.upsert`
- `get_jobs_without_details(job_ids=...)` → `JobDetailRepository.find_existing_job_ids` + Python 필터 (limit 슬라이싱은 Service에서)
- `get_jobs_without_details(job_ids=None)` → `JobRepository.find_without_details(source=WANTED, ...)`
- `get_unapplied_jobs` → `JobRepository.find_unapplied`
- `get_unapplied_job_rows` → `JobRepository.find_unapplied_with_details`
- `skip_jobs` → `JobSkipRepository.upsert`
- `save_job_evaluations` → `JobEvaluationRepository.upsert`
- `save_preset` → `SearchPresetRepository.upsert`
- `list_presets` → `SearchPresetRepository.find_all`
- `get_preset_params` → `SearchPresetRepository.find_by_name`

---

## 쿼리 패턴 규칙

Repository 메서드는 아래 규칙을 따른다.

| 용도 | 패턴 |
|---|---|
| 스칼라 리스트 조회 | `session.scalars(stmt).all()` |
| 단일 row 조회 | `session.scalars(stmt).first()` |
| 다중 컬럼 row 조회 | `session.execute(stmt).mappings().all()` |
| insert / upsert | `session.execute(stmt)` |

---

## 테스트 전략

### Repository 테스트 (신규)

mock session을 직접 주입해 `patch` 없이 테스트한다.

```python
def test_find_by_name_returns_none():
    mock_session = MagicMock()
    mock_session.scalars.return_value.first.return_value = None
    repo = SearchPresetRepository(mock_session)
    assert repo.find_by_name("없는이름") is None
```

### Service 테스트 (기존 유지)

`Session` 생명주기는 `JobService`가 소유하므로 패치 위치는 변경 없이 그대로 유지한다.

```python
with patch("services.jobs.job_service.Session") as MockSession:
    ...
```

시그니처·반환값은 그대로이므로 assert 로직도 변경 불필요.

---

## 마이그레이션 순서

1. `db/models.py` → `db/models/` 패키지로 분리 (base, 모델 6개, __init__ re-export)
2. `db/repositories/` 디렉터리 생성 및 `__init__.py`
3. 각 Repository 클래스 구현 (쿼리 이동)
4. `JobService` 내 인라인 쿼리를 Repository 호출로 교체
5. Repository 단위 테스트 추가
6. `pytest` 전체 통과 확인
