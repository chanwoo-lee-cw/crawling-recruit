# 트랜잭션 데코레이터 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** JobService에 분산된 세션/트랜잭션 관리를 `@transactional` 데코레이터로 중앙화한다.

**Architecture:** `db/transaction.py`에 ContextVar 기반 세션 관리와 Spring-like Propagation(REQUIRED, REQUIRES_NEW, NESTED)을 구현한다. JobService 메서드는 `@transactional()` 데코레이터를 붙이고, 내부에서 `get_current_session()`으로 세션에 접근한다. `test_session_context(session)`으로 테스트에서 세션을 주입한다. tools/ 호출부는 변경 없다.

**Tech Stack:** Python 3.11, SQLAlchemy 2.x, contextvars.ContextVar

---

## 파일 구조

| 파일 | 변경 |
|---|---|
| `db/transaction.py` | NEW: Propagation enum, _session_var, get_current_session(), test_session_context(), @transactional |
| `tests/test_transaction.py` | NEW: 데코레이터 단위 테스트 |
| `services/jobs/job_service.py` | MODIFY: @transactional 적용, Session 관리 코드 제거 |
| `tests/test_job_service.py` | MODIFY: patch(Session) → test_session_context() 패턴 교체 |

---

### Task 1: db/transaction.py 구현 (전체 Propagation)

**Files:**
- Create: `db/transaction.py`
- Create: `tests/test_transaction.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_transaction.py`:

```python
import pytest
from unittest.mock import MagicMock, patch
from db.transaction import transactional, get_current_session, Propagation, test_session_context


def _make_svc():
    engine = MagicMock()

    class _Svc:
        def __init__(self):
            self.engine = engine

        @transactional()
        def write(self):
            return get_current_session()

        @transactional()
        def fail(self):
            raise ValueError("오류")

        @transactional(Propagation.REQUIRES_NEW)
        def requires_new(self):
            return get_current_session()

        @transactional(Propagation.NESTED)
        def nested(self):
            return get_current_session()

    return _Svc(), engine


def _mock_session_ctx(engine):
    """Session(engine) 컨텍스트 매니저를 mock하는 헬퍼"""
    mock_sess = MagicMock()
    patcher = patch("db.transaction.Session")
    MockSession = patcher.start()
    MockSession.return_value.__enter__ = MagicMock(return_value=mock_sess)
    MockSession.return_value.__exit__ = MagicMock(return_value=False)
    return patcher, MockSession, mock_sess


# --- get_current_session ---

def test_get_current_session_raises_outside_transaction():
    with pytest.raises(RuntimeError, match="트랜잭션 컨텍스트"):
        get_current_session()


# --- test_session_context ---

def test_test_session_context_sets_and_resets():
    mock_sess = MagicMock()
    with test_session_context(mock_sess):
        assert get_current_session() is mock_sess
    with pytest.raises(RuntimeError):
        get_current_session()


# --- REQUIRED ---

def test_required_creates_session_and_commits():
    svc, engine = _make_svc()
    patcher, MockSession, mock_sess = _mock_session_ctx(engine)
    try:
        result = svc.write()
    finally:
        patcher.stop()
    MockSession.assert_called_once_with(engine)
    mock_sess.commit.assert_called_once()
    assert result is mock_sess


def test_required_joins_existing_without_commit():
    svc, _ = _make_svc()
    mock_sess = MagicMock()
    with test_session_context(mock_sess):
        result = svc.write()
    mock_sess.commit.assert_not_called()
    assert result is mock_sess


def test_required_rolls_back_on_exception():
    svc, engine = _make_svc()
    patcher, _, mock_sess = _mock_session_ctx(engine)
    try:
        with pytest.raises(ValueError):
            svc.fail()
    finally:
        patcher.stop()
    mock_sess.rollback.assert_called_once()
    mock_sess.commit.assert_not_called()


# --- REQUIRES_NEW ---

def test_requires_new_creates_new_session_ignoring_existing():
    svc, engine = _make_svc()
    existing = MagicMock()
    patcher, MockSession, new_sess = _mock_session_ctx(engine)
    try:
        with test_session_context(existing):
            result = svc.requires_new()
    finally:
        patcher.stop()
    assert result is new_sess
    new_sess.commit.assert_called_once()
    existing.commit.assert_not_called()


# --- NESTED ---

def test_nested_uses_savepoint_with_existing_session():
    svc, _ = _make_svc()
    existing = MagicMock()
    existing.begin_nested.return_value.__enter__ = MagicMock(return_value=existing)
    existing.begin_nested.return_value.__exit__ = MagicMock(return_value=False)
    with test_session_context(existing):
        result = svc.nested()
    existing.begin_nested.assert_called_once()
    assert result is existing


def test_nested_falls_back_to_required_when_no_session():
    svc, engine = _make_svc()
    patcher, MockSession, mock_sess = _mock_session_ctx(engine)
    try:
        result = svc.nested()
    finally:
        patcher.stop()
    MockSession.assert_called_once_with(engine)
    mock_sess.commit.assert_called_once()
    assert result is mock_sess
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
pytest tests/test_transaction.py -v
```

Expected: `ModuleNotFoundError: No module named 'db.transaction'`

- [ ] **Step 3: db/transaction.py 구현**

```python
import functools
from contextlib import contextmanager
from contextvars import ContextVar
from enum import Enum

from sqlalchemy.orm import Session

_session_var: ContextVar[Session | None] = ContextVar("session", default=None)


def get_current_session() -> Session:
    session = _session_var.get()
    if session is None:
        raise RuntimeError("트랜잭션 컨텍스트 밖에서 세션에 접근했습니다.")
    return session


@contextmanager
def test_session_context(session: Session):
    token = _session_var.set(session)
    try:
        yield session
    finally:
        _session_var.reset(token)


class Propagation(Enum):
    REQUIRED = "REQUIRED"
    REQUIRES_NEW = "REQUIRES_NEW"
    NESTED = "NESTED"


def _run_in_new_session(engine, func, args, kwargs):
    with Session(engine) as session:
        token = _session_var.set(session)
        try:
            result = func(*args, **kwargs)
            session.commit()
            return result
        except Exception:
            session.rollback()
            raise
        finally:
            _session_var.reset(token)


def transactional(propagation: Propagation = Propagation.REQUIRED):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            current = _session_var.get()

            if propagation == Propagation.REQUIRED:
                if current is not None:
                    return func(self, *args, **kwargs)
                return _run_in_new_session(self.engine, lambda *a, **kw: func(self, *a, **kw), args, kwargs)

            if propagation == Propagation.REQUIRES_NEW:
                return _run_in_new_session(self.engine, lambda *a, **kw: func(self, *a, **kw), args, kwargs)

            if propagation == Propagation.NESTED:
                if current is not None:
                    with current.begin_nested():
                        return func(self, *args, **kwargs)
                return _run_in_new_session(self.engine, lambda *a, **kw: func(self, *a, **kw), args, kwargs)

        return wrapper
    return decorator
```

- [ ] **Step 4: 테스트 실행 — 통과 확인**

```bash
pytest tests/test_transaction.py -v
```

Expected: 8 passed

- [ ] **Step 5: 커밋**

```bash
git add db/transaction.py tests/test_transaction.py
git commit -m "feat: add @transactional decorator with REQUIRED, REQUIRES_NEW, NESTED propagation"
```

---

### Task 2: job_service.py 리팩토링

**Files:**
- Modify: `services/jobs/job_service.py`

- [ ] **Step 1: 기존 테스트 현황 확인**

```bash
pytest tests/test_job_service.py -v
```

Expected: all pass (변경 전 기준)

- [ ] **Step 2: job_service.py 전체 교체**

`services/jobs/job_service.py`:

```python
import json
from datetime import datetime, timezone

from services.wanted.wanted_constants import WANTED
from services.remember.remember_constants import REMEMBER
from db.repositories.search_preset_repository import SearchPresetRepository
from db.repositories.job_detail_repository import JobDetailRepository
from db.repositories.application_repository import ApplicationRepository
from db.repositories.job_skip_repository import JobSkipRepository
from db.repositories.job_evaluation_repository import JobEvaluationRepository
from db.repositories.job_repository import JobRepository
from db.transaction import transactional, get_current_session
from domain import JobCandidate, JobDetail

ALLOWED_PRESET_KEYS = {
    "job_group_id", "job_ids", "years", "locations", "limit_pages",
    "job_category_names", "min_experience", "max_experience", "source",
}
WANTED_JOB_BASE_URL = "https://www.wanted.co.kr/wd"
REMEMBER_JOB_BASE_URL = "https://career.rememberapp.co.kr/job/posting"

JOB_BASE_URLS = {
    WANTED: WANTED_JOB_BASE_URL,
    REMEMBER: REMEMBER_JOB_BASE_URL,
}


class JobService:
    EMPLOYMENT_TYPE_MAP = {
        "정규직": "regular",
        "인턴": "intern",
        "계약직": "contract",
    }
    VALID_VERDICTS = {"good", "pass", "skip"}

    def __init__(self, engine):
        self.engine = engine

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
            "source": WANTED,
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
            "source": REMEMBER,
            "platform_id": raw["id"],
            "company_id": raw["organization"].get("company_id"),
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

    def _parse_job(self, raw: dict, source: str = WANTED) -> dict:
        if source == REMEMBER:
            return self._parse_remember_job(raw)
        return self._parse_wanted_job(raw)

    def _parse_wanted_applications(self, raw_apps: list[dict]) -> list[dict]:
        return [
            {
                "job_platform_id": app["job_id"],
                "platform_id": app["id"],
                "status": app["status"],
                "apply_time_str": app.get("apply_time"),
            }
            for app in raw_apps
        ]

    def _parse_remember_applications(self, raw_apps: list[dict]) -> list[dict]:
        result = []
        for app in raw_apps:
            application = app.get("application")
            if not application:
                continue
            result.append({
                "job_platform_id": app["id"],
                "platform_id": application["id"],
                "status": application["status"],
                "apply_time_str": application.get("applied_at"),
            })
        return result

    def _parse_applications(self, raw_apps: list[dict], source: str) -> list[dict]:
        if source == REMEMBER:
            return self._parse_remember_applications(raw_apps)
        return self._parse_wanted_applications(raw_apps)

    @transactional()
    def upsert_jobs(self, raw_jobs: list[dict], source: str = WANTED, full_sync: bool = False) -> str:
        if not raw_jobs:
            return "동기화 완료: 신규 0개, 변경 0개, 유지 0개"
        rows = [self._parse_job(j, source=source) for j in raw_jobs]
        synced_pairs = [(source, r["platform_id"]) for r in rows]
        session = get_current_session()
        repo = JobRepository(session)
        existing_pairs = repo.find_existing_pairs(source, [r["platform_id"] for r in rows])
        new_count = len(rows) - len(existing_pairs)
        result = repo.upsert(rows)
        if full_sync and synced_pairs:
            repo.deactivate_removed(source, synced_pairs)
        updated_count = (result.rowcount - new_count) // 2
        unchanged_count = len(rows) - new_count - updated_count
        return f"동기화 완료: 신규 {new_count}개, 변경 {updated_count}개, 유지 {unchanged_count}개"

    @transactional()
    def upsert_applications(self, raw_apps: list[dict], source: str = WANTED) -> str:
        if not raw_apps:
            return "지원현황 동기화 완료: 총 0건"
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        parsed = self._parse_applications(raw_apps, source)
        if not parsed:
            return "지원현황 동기화 완료: 총 0건"
        job_platform_ids = [p["job_platform_id"] for p in parsed]
        session = get_current_session()
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
        return f"지원현황 동기화 완료: 총 {len(rows)}건"

    @transactional()
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
        JobDetailRepository(get_current_session()).upsert(rows)
        return f"완료: {len(rows)}개 처리"

    @transactional()
    def upsert_remember_details(self, raw_jobs: list[dict]) -> None:
        if not raw_jobs:
            return
        platform_ids = [r["id"] for r in raw_jobs]
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        session = get_current_session()
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

    @transactional()
    def get_unapplied_jobs(
        self,
        job_group_id: int | None = None,
        location: str | None = None,
        employment_type: str | None = None,
        limit: int = 20,
    ) -> str:
        if employment_type:
            employment_type = self.EMPLOYMENT_TYPE_MAP.get(employment_type, employment_type)
        rows = JobRepository(get_current_session()).find_unapplied(
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

    @transactional()
    def get_unapplied_job_rows(
        self,
        job_group_id: int | None = None,
        location: str | None = None,
        employment_type: str | None = None,
        include_evaluated: bool = False,
    ) -> list[JobCandidate]:
        if employment_type:
            employment_type = self.EMPLOYMENT_TYPE_MAP.get(employment_type, employment_type)
        rows = JobRepository(get_current_session()).find_unapplied_with_details(
            job_group_id=job_group_id,
            location=location,
            employment_type=employment_type,
            include_evaluated=include_evaluated,
        )
        return [JobCandidate.from_row(r) for r in rows]

    @transactional()
    def skip_jobs(self, job_ids: list[int], reason: str | None = None) -> str:
        if not job_ids:
            return "제외할 공고 ID를 입력해주세요."
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        rows = [{"job_id": jid, "reason": reason, "skipped_at": now} for jid in job_ids]
        JobSkipRepository(get_current_session()).upsert(rows)
        suffix = f" (사유: {reason})" if reason else ""
        return f"{len(job_ids)}개 공고 제외 완료{suffix}"

    @transactional()
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
        JobEvaluationRepository(get_current_session()).upsert(rows)
        return f"{len(rows)}개 평가 저장 완료"

    @transactional()
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
        SearchPresetRepository(get_current_session()).upsert(row)
        return f"프리셋 '{name}' 저장 완료"

    @transactional()
    def list_presets(self) -> str:
        presets = SearchPresetRepository(get_current_session()).find_all()
        if not presets:
            return "저장된 프리셋이 없습니다."
        return f"저장된 프리셋: {', '.join(r.name for r in presets)}"

    @transactional()
    def get_preset_params(self, name: str) -> dict | None:
        preset = SearchPresetRepository(get_current_session()).find_by_name(name)
        if not preset:
            return None
        params = preset.params
        return json.loads(params) if isinstance(params, str) else params

    def get_recommended_jobs(
        self,
        skills: list[str],
        rows: list[JobCandidate],
        top_k: int = 15,
    ) -> list[JobCandidate]:
        skills_lower = {s.lower() for s in skills}

        def score(row: JobCandidate) -> int:
            return sum(1 for tag in row.skill_tags if tag.text.lower() in skills_lower)

        with_detail = [r for r in rows if r.fetched_at is not None]
        scored = sorted(with_detail, key=score, reverse=True)
        return scored[:top_k]
```

---

### Task 3: test_job_service.py 업데이트

**Files:**
- Modify: `tests/test_job_service.py`

**핵심 변경 원칙:**
- `patch("services.jobs.job_service.Session")` 블록 → `test_session_context(mock_session)` 로 교체
- 데코레이터가 기존 세션을 감지하면(REQUIRED) commit하지 않으므로 `mock_session.commit.assert_called_once()` 단언 제거
- `@transactional` 메서드를 세션 없이 호출하면 `Session(MagicMock())` 생성을 시도하므로, 세션이 필요 없는 테스트도 `test_session_context(MagicMock())`로 감쌈

- [ ] **Step 1: test_job_service.py 전체 교체**

`tests/test_job_service.py`:

```python
import pytest
from unittest.mock import MagicMock
from services.wanted.wanted_constants import WANTED
from services.remember.remember_constants import REMEMBER
from services.jobs.job_service import JobService
from db.transaction import test_session_context
from domain import JobCandidate, JobDetail, SkillTag


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

RAW_DETAIL = JobDetail(
    job_id=1001,
    requirements="Python 3년 이상",
    preferred_points="FastAPI 경험자 우대",
    skill_tags=[{"tag_type_id": 1554, "text": "Python"}],
)


def test_parse_job_row():
    service = JobService(engine=MagicMock())
    row = service._parse_job(RAW_JOB)
    assert row["platform_id"] == 1001
    assert row["source"] == WANTED
    assert row["company_name"] == "테스트컴퍼니"
    assert row["title"] == "Backend Engineer"
    assert row["location"] == "서울"
    assert row["employment_type"] == "regular"
    assert row["job_group_id"] == 518
    assert row["category_tag_id"] == 872
    assert row["is_active"] is True


def test_upsert_jobs_calls_execute():
    mock_session = MagicMock()
    upsert_result = MagicMock()
    upsert_result.rowcount = 1
    mock_session.execute.side_effect = [
        MagicMock(**{"all.return_value": []}),
        upsert_result,
    ]
    service = JobService(engine=MagicMock())
    with test_session_context(mock_session):
        result = service.upsert_jobs([RAW_JOB], full_sync=False)
    assert mock_session.execute.called
    assert "동기화 완료: 신규 1개" in result


def test_save_preset_invalid_key():
    service = JobService(engine=MagicMock())
    with test_session_context(MagicMock()):
        with pytest.raises(ValueError, match="유효하지 않은 파라미터 키"):
            service.save_preset("테스트", {"invalid_key": 1})


def test_save_preset_valid():
    mock_session = MagicMock()
    service = JobService(engine=MagicMock())
    with test_session_context(mock_session):
        result = service.save_preset("백엔드 신입 서울", {"job_group_id": 518, "locations": "서울"})
    assert "저장 완료" in result


def test_get_unapplied_jobs_returns_markdown():
    mock_session = MagicMock()
    mock_session.execute.return_value.mappings.return_value.all.return_value = [
        {"internal_id": 1001, "source": WANTED, "platform_id": 1001,
         "company_name": "테스트컴퍼니", "title": "Backend Engineer",
         "location": "서울", "employment_type": "regular"}
    ]
    service = JobService(engine=MagicMock())
    with test_session_context(mock_session):
        result = service.get_unapplied_jobs()
    assert "테스트컴퍼니" in result
    assert "https://www.wanted.co.kr/wd/1001" in result
    assert "| 1001 |" in result


def test_upsert_job_details_calls_execute():
    mock_session = MagicMock()
    mock_session.execute.return_value = MagicMock()
    service = JobService(engine=MagicMock())
    with test_session_context(mock_session):
        result = service.upsert_job_details([RAW_DETAIL])
    assert mock_session.execute.called
    assert "1개 처리" in result


def test_get_unapplied_job_rows_returns_list():
    mock_session = MagicMock()
    mock_session.execute.return_value.mappings.return_value.all.return_value = [
        {
            "internal_id": 1001, "source": WANTED, "platform_id": 1001,
            "company_name": "테스트컴퍼니", "title": "Backend Engineer",
            "location": "서울", "employment_type": "regular",
            "requirements": None, "preferred_points": None,
            "skill_tags": None, "fetched_at": None,
        }
    ]
    service = JobService(engine=MagicMock())
    with test_session_context(mock_session):
        rows = service.get_unapplied_job_rows()
    assert isinstance(rows, list)
    assert rows[0].internal_id == 1001
    assert rows[0].fetched_at is None


def test_get_jobs_without_details_filters_existing():
    mock_session = MagicMock()
    mock_session.scalars.return_value.all.return_value = [101]
    service = JobService(engine=MagicMock())
    with test_session_context(mock_session):
        result = service.get_jobs_without_details(job_ids=[101, 102, 103], limit=2)
    assert result == [102, 103]


def test_get_jobs_without_details_no_job_ids():
    mock_session = MagicMock()
    mock_session.scalars.return_value.all.return_value = [201, 202]
    service = JobService(engine=MagicMock())
    with test_session_context(mock_session):
        result = service.get_jobs_without_details(limit=10)
    assert result == [201, 202]


def test_get_recommended_jobs_scores_skill_tags():
    from datetime import datetime
    now = datetime.now()
    all_rows = [
        JobCandidate(
            internal_id=1, source=WANTED, platform_id=1001,
            company_name="A사", title="Backend", location="서울",
            employment_type="regular", requirements="Python req",
            preferred_points="AWS 우대",
            skill_tags=[SkillTag(text="Python"), SkillTag(text="AWS")],
            fetched_at=now,
        ),
        JobCandidate(
            internal_id=2, source=WANTED, platform_id=1002,
            company_name="B사", title="Frontend", location="서울",
            employment_type="regular", requirements="React req",
            preferred_points=None, skill_tags=[SkillTag(text="React")],
            fetched_at=now,
        ),
        JobCandidate(
            internal_id=3, source=WANTED, platform_id=1003,
            company_name="C사", title="Fullstack", location="서울",
            employment_type="regular", requirements=None,
            preferred_points=None, skill_tags=[], fetched_at=None,
        ),
    ]
    service = JobService(engine=MagicMock())
    candidates = service.get_recommended_jobs(skills=["Python", "AWS"], rows=all_rows, top_k=15)
    assert len(candidates) == 2
    assert candidates[0].internal_id == 1
    assert candidates[1].internal_id == 2


def test_job_candidate_from_row_parses_skill_tags():
    row = {
        "internal_id": 1, "source": WANTED, "platform_id": 1001,
        "company_name": "A사", "title": "Backend", "location": "서울",
        "employment_type": "regular", "requirements": "req",
        "preferred_points": None,
        "skill_tags": [{"tag_type_id": 1, "text": "Python"}, {"tag_type_id": 2, "text": "AWS"}],
        "fetched_at": None,
    }
    candidate = JobCandidate.from_row(row)
    assert len(candidate.skill_tags) == 2
    assert candidate.skill_tags[0] == SkillTag(text="Python")


def test_job_candidate_from_row_handles_null_skill_tags():
    row = {
        "internal_id": 2, "source": WANTED, "platform_id": 1002,
        "company_name": "B사", "title": "Frontend", "location": None,
        "employment_type": None, "requirements": None,
        "preferred_points": None, "skill_tags": None, "fetched_at": None,
    }
    candidate = JobCandidate.from_row(row)
    assert candidate.skill_tags == []


def test_skip_jobs_calls_execute():
    mock_session = MagicMock()
    mock_session.execute.return_value = MagicMock()
    service = JobService(engine=MagicMock())
    with test_session_context(mock_session):
        result = service.skip_jobs([101, 102], reason="연봉 낮음")
    assert mock_session.execute.called
    assert "2개 공고 제외 완료" in result
    assert "연봉 낮음" in result


def test_skip_jobs_empty_list():
    service = JobService(engine=MagicMock())
    with test_session_context(MagicMock()):
        result = service.skip_jobs([])
    assert result == "제외할 공고 ID를 입력해주세요."


def test_get_unapplied_job_rows_with_skip_join():
    mock_session = MagicMock()
    mock_session.execute.return_value.mappings.return_value.all.return_value = [
        {
            "internal_id": 1001, "source": WANTED, "platform_id": 1001,
            "company_name": "테스트컴퍼니", "title": "Backend Engineer",
            "location": "서울", "employment_type": "regular",
            "requirements": None, "preferred_points": None,
            "skill_tags": None, "fetched_at": None,
        }
    ]
    service = JobService(engine=MagicMock())
    with test_session_context(mock_session):
        rows = service.get_unapplied_job_rows()
    assert len(rows) == 1
    assert rows[0].internal_id == 1001


def test_get_unapplied_jobs_with_skip_join():
    mock_session = MagicMock()
    mock_session.execute.return_value.mappings.return_value.all.return_value = [
        {"internal_id": 1001, "source": WANTED, "platform_id": 1001,
         "company_name": "테스트컴퍼니", "title": "Backend Engineer",
         "location": "서울", "employment_type": "regular"}
    ]
    service = JobService(engine=MagicMock())
    with test_session_context(mock_session):
        result = service.get_unapplied_jobs()
    assert "테스트컴퍼니" in result
    assert "https://www.wanted.co.kr/wd/1001" in result


def test_parse_remember_job():
    raw = {
        "id": 308098, "title": "백엔드 개발",
        "organization": {"name": "(주)이스트소프트"},
        "addresses": [{"address_level1": "서울특별시", "address_level2": "서초구"}],
        "min_salary": None, "max_salary": None,
    }
    service = JobService(engine=MagicMock())
    row = service._parse_job(raw, source=REMEMBER)
    assert row["platform_id"] == 308098
    assert row["source"] == REMEMBER
    assert row["location"] == "서울특별시 서초구"
    assert row["company_id"] is None


def test_upsert_jobs_remember_source():
    raw_remember_job = {
        "id": 308098, "title": "백엔드 개발",
        "organization": {"name": "(주)이스트소프트"},
        "addresses": [{"address_level1": "서울특별시", "address_level2": "서초구"}],
        "qualifications": "Python 3년", "preferred_qualifications": "FastAPI 경험",
        "min_salary": None, "max_salary": None,
    }
    mock_session = MagicMock()
    upsert_result = MagicMock()
    upsert_result.rowcount = 1
    mock_session.execute.side_effect = [
        MagicMock(**{"all.return_value": []}),
        upsert_result,
    ]
    service = JobService(engine=MagicMock())
    with test_session_context(mock_session):
        result = service.upsert_jobs([raw_remember_job], source=REMEMBER, full_sync=False)
    assert "동기화 완료" in result


def test_parse_application_row_wanted():
    mock_session = MagicMock()
    job_row = MagicMock()
    job_row.platform_id = 2001
    job_row.internal_id = 99
    mock_session.execute.side_effect = [
        MagicMock(**{"all.return_value": [job_row]}),
        MagicMock(),
    ]
    service = JobService(engine=MagicMock())
    with test_session_context(mock_session):
        result = service.upsert_applications([RAW_APP], source=WANTED)
    assert "1건" in result


def test_upsert_applications_remember_source():
    raw_app = {
        "id": 303872, "title": "System Engineer",
        "organization": {"name": "(주)휴머스온"},
        "application": {"id": 3428290, "status": "applied",
                        "applied_at": "2026-04-12T18:28:24.676+09:00"},
    }
    mock_session = MagicMock()
    job_row = MagicMock()
    job_row.platform_id = 303872
    job_row.internal_id = 77
    mock_session.execute.side_effect = [
        MagicMock(**{"all.return_value": [job_row]}),
        MagicMock(),
    ]
    service = JobService(engine=MagicMock())
    with test_session_context(mock_session):
        result = service.upsert_applications([raw_app], source=REMEMBER)
    assert "1건" in result


def test_upsert_applications_empty():
    service = JobService(engine=MagicMock())
    with test_session_context(MagicMock()):
        result = service.upsert_applications([])
    assert "0건" in result


def test_get_unapplied_job_rows_cross_platform_filter():
    mock_session = MagicMock()
    mock_session.execute.return_value.mappings.return_value.all.return_value = [
        {
            "internal_id": 1001, "source": WANTED, "platform_id": 1001,
            "company_name": "테스트컴퍼니", "title": "Backend Engineer",
            "location": "서울", "employment_type": "regular",
            "requirements": None, "preferred_points": None,
            "skill_tags": None, "fetched_at": None,
        }
    ]
    service = JobService(engine=MagicMock())
    with test_session_context(mock_session):
        rows = service.get_unapplied_job_rows()
    assert rows[0].source == WANTED
    assert rows[0].platform_id == 1001


def test_get_unapplied_jobs_includes_internal_id():
    mock_session = MagicMock()
    mock_session.execute.return_value.mappings.return_value.all.return_value = [
        {"internal_id": 42, "source": WANTED, "platform_id": 1001,
         "company_name": "테스트컴퍼니", "title": "Backend Engineer",
         "location": "서울", "employment_type": "regular"}
    ]
    service = JobService(engine=MagicMock())
    with test_session_context(mock_session):
        result = service.get_unapplied_jobs()
    assert "| 42 |" in result
    assert "https://www.wanted.co.kr/wd/1001" in result


def test_get_unapplied_jobs_remember_url():
    mock_session = MagicMock()
    mock_session.execute.return_value.mappings.return_value.all.return_value = [
        {"internal_id": 99, "source": REMEMBER, "platform_id": 308098,
         "company_name": "이스트소프트", "title": "백엔드 개발",
         "location": "서울 서초구", "employment_type": None}
    ]
    service = JobService(engine=MagicMock())
    with test_session_context(mock_session):
        result = service.get_unapplied_jobs()
    assert "https://career.rememberapp.co.kr/job/posting/308098" in result
    assert "| 99 |" in result


def test_save_preset_remember_keys():
    service = JobService(engine=MagicMock())
    with test_session_context(MagicMock()):
        with pytest.raises(ValueError):
            service.save_preset("테스트", {"unknown_key": 1})

    mock_session = MagicMock()
    service = JobService(engine=MagicMock())
    with test_session_context(mock_session):
        result = service.save_preset("리멤버 백엔드", {
            "source": REMEMBER,
            "job_category_names": [{"level1": "SW개발", "level2": "백엔드"}],
            "min_experience": 2,
            "max_experience": 5,
        })
    assert "저장 완료" in result


def test_parse_remember_job_fields():
    raw = {
        "id": 123, "title": "Backend Engineer",
        "organization": {"id": 1, "name": "(주)테스트", "company_id": 99},
        "addresses": [{"address_level1": "서울특별시", "address_level2": "서초구"}],
        "min_salary": 5000, "max_salary": 8000,
        "qualifications": "Python 필수", "preferred_qualifications": "Django 우대",
        "job_categories": [{"id": 310, "level1": "SW개발", "level2": "백엔드"}],
    }
    service = JobService(engine=MagicMock())
    result = service._parse_remember_job(raw)
    assert result["platform_id"] == 123
    assert result["company_id"] == 99
    assert result["location"] == "서울특별시 서초구"
    assert result["annual_from"] == 5000


def test_save_job_evaluations_saves_rows():
    mock_session = MagicMock()
    service = JobService(engine=MagicMock())
    with test_session_context(mock_session):
        result = service.save_job_evaluations([
            {"job_id": 1, "verdict": "good"},
            {"job_id": 2, "verdict": "pass"},
        ])
    assert "2개" in result
    mock_session.execute.assert_called()


def test_save_job_evaluations_invalid_verdict():
    service = JobService(engine=MagicMock())
    with test_session_context(MagicMock()):
        with pytest.raises(ValueError, match="wrong"):
            service.save_job_evaluations([{"job_id": 1, "verdict": "wrong"}])


def test_save_job_evaluations_empty():
    service = JobService(engine=MagicMock())
    with test_session_context(MagicMock()):
        result = service.save_job_evaluations([])
    assert "0개" in result


def test_upsert_remember_details_inserts_skill_tags():
    raw_jobs = [{
        "id": 999,
        "qualifications": "Python 3년", "preferred_qualifications": "Django 우대",
        "job_categories": [
            {"level1": "SW개발", "level2": "백엔드"},
            {"level1": "SW개발", "level2": "풀스택"},
        ],
    }]
    mock_session = MagicMock()
    mock_row = MagicMock()
    mock_row.platform_id = 999
    mock_row.internal_id = 1
    mock_session.execute.return_value.all.return_value = [mock_row]
    service = JobService(engine=MagicMock())
    with test_session_context(mock_session):
        service.upsert_remember_details(raw_jobs)
    mock_session.execute.assert_called()


def test_get_unapplied_job_rows_accepts_include_evaluated():
    mock_session = MagicMock()
    mock_session.execute.return_value.mappings.return_value.all.return_value = []
    service = JobService(engine=MagicMock())
    with test_session_context(mock_session):
        rows_default = service.get_unapplied_job_rows()
        rows_with_evaluated = service.get_unapplied_job_rows(include_evaluated=True)
    assert rows_default == []
    assert rows_with_evaluated == []


def test_get_unapplied_job_rows_excludes_evaluated_in_sql():
    mock_session = MagicMock()
    captured = []

    def capture_execute(stmt):
        captured.append(stmt)
        m = MagicMock()
        m.mappings.return_value.all.return_value = []
        return m

    mock_session.execute.side_effect = capture_execute
    service = JobService(engine=MagicMock())
    with test_session_context(mock_session):
        service.get_unapplied_job_rows(include_evaluated=False)
    assert len(captured) == 1
    assert "job_evaluations" in str(captured[0])
```

- [ ] **Step 2: 전체 테스트 실행**

```bash
pytest tests/test_job_service.py tests/test_transaction.py -v
```

Expected: 모두 pass

- [ ] **Step 3: 전체 스위트 실행**

```bash
pytest -v
```

Expected: 기존 테스트 포함 모두 pass

- [ ] **Step 4: 커밋 (job_service + 테스트 함께)**

```bash
git add services/jobs/job_service.py tests/test_job_service.py
git commit -m "refactor: apply @transactional to JobService, migrate tests to test_session_context"
```
