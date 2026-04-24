# Repository Pattern 도입 설계

## 목적

`JobService`에 인라인으로 박혀 있는 SQLAlchemy 쿼리를 `Repository` 레이어로 분리한다.
`JobService`는 파싱·비즈니스 로직·오케스트레이션만 담당하고, DB 쿼리는 각 Repository가 전담한다.

---

## 파일 구조

```
db/
  models.py                          # 변경 없음
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

---

## Repository 인터페이스

### `JobRepository`

| 메서드 | 설명 |
|---|---|
| `find_existing_pairs(source, platform_ids) → set[tuple]` | upsert 전 기존 row 확인 |
| `upsert(rows) → CursorResult` | jobs 테이블 upsert |
| `deactivate_removed(source, synced_pairs)` | full_sync 시 누락 공고 비활성화 |
| `find_platform_id_map(source, platform_ids) → dict` | platform_id → internal_id 매핑 |
| `find_without_details(limit) → list[int]` | detail 미수집 공고 ID 목록 |
| `find_unapplied(filters) → list[RowMapping]` | 미지원 공고 (마크다운용) |
| `find_unapplied_with_details(filters) → list[RowMapping]` | 미지원 공고 + detail join (추천용) |

### `ApplicationRepository`

| 메서드 | 설명 |
|---|---|
| `upsert(rows)` | applications 테이블 upsert |

### `JobDetailRepository`

| 메서드 | 설명 |
|---|---|
| `find_existing_job_ids(job_ids) → set[int]` | detail 보유 job_id 집합 조회 |
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
# 예시
def save_preset(self, name: str, params: dict) -> str:
    ...
    with Session(self.engine) as session:
        SearchPresetRepository(session).upsert(row)
        session.commit()
    return f"프리셋 '{name}' 저장 완료"
```

복수의 repository가 하나의 session을 공유해야 할 때도 service가 session을 생성해 각 repo에 넘긴다.

```python
def upsert_applications(self, raw_apps, source):
    ...
    with Session(self.engine) as session:
        job_id_map = JobRepository(session).find_platform_id_map(source, platform_ids)
        ApplicationRepository(session).upsert(rows)
        session.commit()
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

### 변화하는 것
- 각 public 메서드 내부: 인라인 쿼리 → repository 호출로 교체

---

## 테스트 전략

### Repository 테스트 (신규)

mock session을 직접 주입해 patch 없이 테스트한다.

```python
def test_find_by_name_returns_none():
    mock_session = MagicMock()
    mock_session.scalars.return_value.first.return_value = None
    repo = SearchPresetRepository(mock_session)
    assert repo.find_by_name("없는이름") is None
```

### Service 테스트 (기존 유지)

기존 테스트는 `patch("services.jobs.job_service.Session")`으로 동작하던 것을
repository 모듈 경로(`patch("db.repositories.job_repository.Session")` 등)로 패치 위치만 변경한다.
시그니처·반환값은 그대로이므로 assert 로직은 변경 불필요.

---

## 마이그레이션 순서

1. `db/repositories/` 디렉터리 생성 및 `__init__.py`
2. 각 Repository 클래스 구현 (쿼리 이동)
3. `JobService` 내 인라인 쿼리를 Repository 호출로 교체
4. 기존 테스트 패치 경로 수정 + Repository 단위 테스트 추가
5. `pytest` 전체 통과 확인
