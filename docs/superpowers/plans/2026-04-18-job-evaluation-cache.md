# Job Evaluation Cache Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Claude가 평가한 공고 verdict를 DB에 저장해 `get_job_candidates`가 이미 평가된 공고를 제외, 다음 세션에서 같은 공고를 다시 읽지 않도록 한다.

**Architecture:** 새 테이블 `job_evaluations(job_id PK, verdict, evaluated_at)`을 추가한다. `get_unapplied_job_rows`에 `include_evaluated` 파라미터를 추가해 기본값 `False`로 평가된 공고를 제외한다. `save_job_evaluations` MCP 툴을 만들어 Claude가 추천 후 자동으로 호출하도록 한다. `get_job_candidates`는 반환 JSON에 `job_id`를 포함해 Claude가 `save_job_evaluations` 호출 시 사용할 수 있게 한다.

**Tech Stack:** Python 3.11, SQLAlchemy 2.x, FastMCP, MySQL, pytest, unittest.mock

---

### Task 1: JobEvaluation DB 모델 추가

**Files:**
- Modify: `db/models.py` (전체 파일 — `Job` 클래스 + 새 `JobEvaluation` 클래스)
- Test: `tests/test_db.py`

현재 `db/models.py` 구조: `Job`, `Application`, `JobDetail`, `SearchPreset`, `JobSkip` 순서.
`JobSkip` 패턴을 그대로 따른다 (`job_id` PK FK → `jobs.internal_id` CASCADE, back_populates relationship).

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_db.py` 맨 아래에 추가:

```python
def test_job_evaluation_model_columns():
    from db.models import JobEvaluation
    cols = {c.name for c in JobEvaluation.__table__.columns}
    assert cols == {"job_id", "verdict", "evaluated_at"}


def test_job_model_has_evaluation_relationship():
    from db.models import Job
    assert hasattr(Job, "evaluation")
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
pytest tests/test_db.py::test_job_evaluation_model_columns tests/test_db.py::test_job_model_has_evaluation_relationship -v
```

Expected: FAIL — `ImportError: cannot import name 'JobEvaluation'`

- [ ] **Step 3: 모델 구현**

`db/models.py`에서 `Job` 클래스 안에 `skip` relationship 바로 아래에 추가:

```python
    evaluation: Mapped[Optional["JobEvaluation"]] = relationship(back_populates="job", uselist=False)
```

파일 맨 아래 `JobSkip` 클래스 다음에 추가:

```python
class JobEvaluation(Base):
    __tablename__ = "job_evaluations"

    job_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("jobs.internal_id", ondelete="CASCADE"), primary_key=True
    )
    verdict: Mapped[str] = mapped_column(String(20), nullable=False)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    job: Mapped["Job"] = relationship(back_populates="evaluation")
```

- [ ] **Step 4: 테스트 실행 — 통과 확인**

```bash
pytest tests/test_db.py::test_job_evaluation_model_columns tests/test_db.py::test_job_model_has_evaluation_relationship -v
```

Expected: PASS

- [ ] **Step 5: 전체 테스트 통과 확인**

```bash
pytest
```

Expected: 모두 PASS

- [ ] **Step 6: Commit**

```bash
git add db/models.py tests/test_db.py
git commit -m "feat: JobEvaluation 모델 추가 (job_evaluations 테이블)"
```

---

### Task 2: save_job_evaluations 서비스 메서드

**Files:**
- Modify: `services/job_service.py` (import 라인 + 새 메서드)
- Test: `tests/test_job_service.py`

`skip_jobs` 메서드(line 389-403)가 완벽한 참고 패턴이다. `save_job_evaluations`도 동일하게 `datetime.now(timezone.utc).replace(tzinfo=None)`을 사용하고 `on_duplicate_key_update`로 upsert한다.

**주의**: `VALID_VERDICTS`는 `EMPLOYMENT_TYPE_MAP`과 함께 `JobService` **클래스 최상단**에 선언한다. 메서드 사이에 넣으면 안 된다.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_job_service.py` 맨 아래에 추가:

```python
def test_save_job_evaluations_saves_rows():
    mock_engine = MagicMock()
    with patch("services.job_service.Session") as MockSession, \
         patch("services.job_service.insert") as mock_insert:

        mock_session = MagicMock()
        MockSession.return_value.__enter__ = MagicMock(return_value=mock_session)
        MockSession.return_value.__exit__ = MagicMock(return_value=False)

        mock_insert_instance = MagicMock()
        mock_insert.return_value = mock_insert_instance
        mock_insert_instance.values.return_value = mock_insert_instance
        mock_insert_instance.on_duplicate_key_update.return_value = mock_insert_instance

        service = JobService(engine=mock_engine)
        result = service.save_job_evaluations([
            {"job_id": 1, "verdict": "good"},
            {"job_id": 2, "verdict": "pass"},
        ])

    assert "2개" in result
    mock_session.commit.assert_called_once()
    mock_insert_instance.on_duplicate_key_update.assert_called_once()


def test_save_job_evaluations_invalid_verdict():
    service = JobService(engine=MagicMock())
    try:
        service.save_job_evaluations([{"job_id": 1, "verdict": "wrong"}])
        assert False, "ValueError가 발생해야 함"
    except ValueError as e:
        assert "wrong" in str(e)


def test_save_job_evaluations_empty():
    service = JobService(engine=MagicMock())
    result = service.save_job_evaluations([])
    assert "0개" in result
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
pytest tests/test_job_service.py::test_save_job_evaluations_saves_rows tests/test_job_service.py::test_save_job_evaluations_invalid_verdict tests/test_job_service.py::test_save_job_evaluations_empty -v
```

Expected: FAIL — `AttributeError: 'JobService' object has no attribute 'save_job_evaluations'`

- [ ] **Step 3: 구현**

`services/job_service.py` 상단 import 수정:

```python
from db.models import Job, Application, JobDetail as OrmJobDetail, SearchPreset, JobSkip, JobEvaluation
```

`JobService` 클래스 최상단(`EMPLOYMENT_TYPE_MAP` 바로 아래)에 클래스 변수 추가:

```python
    VALID_VERDICTS = {"good", "pass", "skip"}
```

`skip_jobs` 메서드 바로 다음에 새 메서드 추가:

```python
    def save_job_evaluations(self, evaluations: list[dict]) -> str:
        if not evaluations:
            return "0개 처리"
        invalid = [e["verdict"] for e in evaluations if e.get("verdict") not in self.VALID_VERDICTS]
        if invalid:
            raise ValueError(
                f"유효하지 않은 verdict: {invalid}. 허용 값: good, pass, skip"
            )
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        rows = [
            {"job_id": e["job_id"], "verdict": e["verdict"], "evaluated_at": now}
            for e in evaluations
        ]
        with Session(self.engine) as session:
            stmt = insert(JobEvaluation.__table__).values(rows)
            upsert_stmt = stmt.on_duplicate_key_update(
                verdict=stmt.inserted.verdict,
                evaluated_at=stmt.inserted.evaluated_at,
            )
            session.execute(upsert_stmt)
            session.commit()
        return f"{len(rows)}개 평가 저장 완료"
```

- [ ] **Step 4: 테스트 실행 — 통과 확인**

```bash
pytest tests/test_job_service.py::test_save_job_evaluations_saves_rows tests/test_job_service.py::test_save_job_evaluations_invalid_verdict tests/test_job_service.py::test_save_job_evaluations_empty -v
```

Expected: PASS

- [ ] **Step 5: 전체 테스트 통과 확인**

```bash
pytest
```

Expected: 모두 PASS

- [ ] **Step 6: Commit**

```bash
git add services/job_service.py tests/test_job_service.py
git commit -m "feat: save_job_evaluations 서비스 메서드 추가"
```

---

### Task 3: get_unapplied_job_rows — include_evaluated 파라미터

**Files:**
- Modify: `services/job_service.py:349-387` (`get_unapplied_job_rows` 메서드)
- Test: `tests/test_job_service.py`

현재 메서드는 `JobSkip`을 `outerjoin`해 `JobSkip.job_id IS NULL`로 필터링한다. `JobEvaluation`도 동일하게 `outerjoin`하고, `include_evaluated=False`일 때 `JobEvaluation.job_id IS NULL` 조건을 추가한다.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_job_service.py` 맨 아래에 추가:

```python
def test_get_unapplied_job_rows_accepts_include_evaluated():
    """include_evaluated 파라미터가 오류 없이 동작해야 한다."""
    mock_engine = MagicMock()
    with patch("services.job_service.Session") as MockSession:
        mock_session = MagicMock()
        MockSession.return_value.__enter__ = MagicMock(return_value=mock_session)
        MockSession.return_value.__exit__ = MagicMock(return_value=False)
        mock_session.execute.return_value.mappings.return_value.all.return_value = []

        service = JobService(engine=mock_engine)
        rows_default = service.get_unapplied_job_rows()
        rows_with_evaluated = service.get_unapplied_job_rows(include_evaluated=True)

    assert rows_default == []
    assert rows_with_evaluated == []


def test_get_unapplied_job_rows_excludes_evaluated_in_sql():
    """include_evaluated=False일 때 SQL에 job_evaluations IS NULL 조건이 포함돼야 한다."""
    mock_engine = MagicMock()
    captured = []

    with patch("services.job_service.Session") as MockSession:
        mock_session = MagicMock()
        MockSession.return_value.__enter__ = MagicMock(return_value=mock_session)
        MockSession.return_value.__exit__ = MagicMock(return_value=False)

        def capture_execute(stmt):
            captured.append(stmt)
            m = MagicMock()
            m.mappings.return_value.all.return_value = []
            return m

        mock_session.execute.side_effect = capture_execute

        service = JobService(engine=mock_engine)
        service.get_unapplied_job_rows(include_evaluated=False)

    assert len(captured) == 1
    sql = str(captured[0])
    assert "job_evaluations" in sql
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
pytest tests/test_job_service.py::test_get_unapplied_job_rows_accepts_include_evaluated tests/test_job_service.py::test_get_unapplied_job_rows_excludes_evaluated_in_sql -v
```

Expected: FAIL — `TypeError: get_unapplied_job_rows() got an unexpected keyword argument 'include_evaluated'`

- [ ] **Step 3: 구현**

`services/job_service.py` `get_unapplied_job_rows` 메서드(line 349) 수정:

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

        with Session(self.engine) as session:
            rows = session.execute(stmt).mappings().all()

        return [JobCandidate.from_row(r) for r in rows]
```

- [ ] **Step 4: 테스트 실행 — 통과 확인**

```bash
pytest tests/test_job_service.py::test_get_unapplied_job_rows_accepts_include_evaluated tests/test_job_service.py::test_get_unapplied_job_rows_excludes_evaluated_in_sql -v
```

Expected: PASS

- [ ] **Step 5: 전체 테스트 통과 확인**

```bash
pytest
```

Expected: 모두 PASS

- [ ] **Step 6: Commit**

```bash
git add services/job_service.py tests/test_job_service.py
git commit -m "feat: get_unapplied_job_rows에 include_evaluated 파라미터 추가"
```

---

### Task 4: save_job_evaluations MCP 툴 + main.py 등록

**Files:**
- Create: `tools/save_job_evaluations.py`
- Modify: `main.py`
- Test: `tests/test_tools.py`

`tools/skip_jobs.py`가 완벽한 참고 패턴이다. 동일한 구조로 작성한다.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_tools.py` 맨 아래에 추가:

```python
def test_save_job_evaluations_tool_calls_service():
    with patch("tools.save_job_evaluations.get_engine"), \
         patch("tools.save_job_evaluations.JobService") as MockService:

        mock_service = MagicMock()
        mock_service.save_job_evaluations.return_value = "2개 평가 저장 완료"
        MockService.return_value = mock_service

        from tools.save_job_evaluations import save_job_evaluations
        result = save_job_evaluations([
            {"job_id": 1, "verdict": "good"},
            {"job_id": 2, "verdict": "pass"},
        ])

    assert "2개" in result
    mock_service.save_job_evaluations.assert_called_once_with([
        {"job_id": 1, "verdict": "good"},
        {"job_id": 2, "verdict": "pass"},
    ])


def test_save_job_evaluations_tool_returns_error_on_invalid_verdict():
    with patch("tools.save_job_evaluations.get_engine"), \
         patch("tools.save_job_evaluations.JobService") as MockService:

        mock_service = MagicMock()
        mock_service.save_job_evaluations.side_effect = ValueError("유효하지 않은 verdict: ['wrong']")
        MockService.return_value = mock_service

        from tools.save_job_evaluations import save_job_evaluations
        result = save_job_evaluations([{"job_id": 1, "verdict": "wrong"}])

    assert "유효하지 않은" in result
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
pytest tests/test_tools.py::test_save_job_evaluations_tool_calls_service tests/test_tools.py::test_save_job_evaluations_tool_returns_error_on_invalid_verdict -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'tools.save_job_evaluations'`

- [ ] **Step 3: 툴 파일 생성**

`tools/save_job_evaluations.py` 생성:

```python
from db.connection import get_engine
from services.job_service import JobService


def save_job_evaluations(evaluations: list[dict]) -> str:
    """Claude가 평가한 공고 verdict를 저장한다.

    evaluations: [{"job_id": int, "verdict": "good"|"pass"|"skip"}, ...]
    - good: 지원 고려 대상
    - pass: 이번엔 해당 없음 (다음 세션에서 다시 나오지 않음)
    - skip: 영구 제외
    get_job_candidates는 이미 평가된 공고를 기본 제외하므로,
    받은 모든 공고에 verdict를 저장해야 다음 세션에서 재처리되지 않는다.
    """
    try:
        engine = get_engine()
        service = JobService(engine)
        return service.save_job_evaluations(evaluations)
    except ValueError as e:
        return str(e)
    except Exception as e:
        return f"오류가 발생했습니다: {e}"
```

- [ ] **Step 4: main.py에 툴 등록**

`main.py` 수정:

```python
from tools.save_job_evaluations import save_job_evaluations
```
(기존 import 목록에 추가)

```python
mcp.tool()(save_job_evaluations)
```
(기존 `mcp.tool()` 목록에 추가)

- [ ] **Step 5: 테스트 실행 — 통과 확인**

```bash
pytest tests/test_tools.py::test_save_job_evaluations_tool_calls_service tests/test_tools.py::test_save_job_evaluations_tool_returns_error_on_invalid_verdict -v
```

Expected: PASS

- [ ] **Step 6: 전체 테스트 통과 확인**

```bash
pytest
```

Expected: 모두 PASS

- [ ] **Step 7: Commit**

```bash
git add tools/save_job_evaluations.py main.py tests/test_tools.py
git commit -m "feat: save_job_evaluations MCP 툴 추가 및 main.py 등록"
```

---

### Task 5: get_job_candidates — job_id 반환 + include_evaluated 파라미터

**Files:**
- Modify: `tools/get_job_candidates.py`
- Test: `tests/test_tools.py`

두 가지 변경:
1. 반환 JSON에 `"job_id": c.internal_id` 추가 — Claude가 `save_job_evaluations` 호출 시 필요
2. `include_evaluated: bool = False` 파라미터 추가 → `get_unapplied_job_rows`에 전달
3. `rows`가 비어 있고 `include_evaluated=False`일 때, 힌트 메시지 반환

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_tools.py` 맨 아래에 추가:

```python
def test_get_job_candidates_includes_job_id():
    from domain import JobCandidate, SkillTag
    from datetime import datetime

    mock_candidate = JobCandidate(
        internal_id=42,
        source="remember",
        platform_id=307222,
        company_name="랭디",
        title="백엔드 개발자",
        location="서울 관악구",
        employment_type=None,
        requirements="Kotlin 필수",
        preferred_points=None,
        skill_tags=[SkillTag(text="백엔드")],
        fetched_at=datetime.now(),
    )

    with patch("tools.get_job_candidates.get_engine"), \
         patch("tools.get_job_candidates.JobService") as MockService:

        mock_service = MagicMock()
        mock_service.get_unapplied_job_rows.return_value = [mock_candidate]
        mock_service.get_recommended_jobs.return_value = [mock_candidate]
        MockService.return_value = mock_service

        from tools.get_job_candidates import get_job_candidates
        result_str = get_job_candidates(skills=["Kotlin"])

    import json
    result = json.loads(result_str)
    assert result[0]["job_id"] == 42
    assert result[0]["url"] == "https://career.rememberapp.co.kr/job/posting/307222"


def test_get_job_candidates_no_new_jobs_hint():
    """미평가 공고 없을 때 include_evaluated 힌트 메시지를 반환해야 한다."""
    with patch("tools.get_job_candidates.get_engine"), \
         patch("tools.get_job_candidates.JobService") as MockService:

        mock_service = MagicMock()
        mock_service.get_unapplied_job_rows.return_value = []
        MockService.return_value = mock_service

        from tools.get_job_candidates import get_job_candidates
        result = get_job_candidates(skills=["Python"])

    assert "새로 평가할 공고가 없습니다" in result
    assert "include_evaluated=True" in result


def test_get_job_candidates_passes_include_evaluated():
    with patch("tools.get_job_candidates.get_engine"), \
         patch("tools.get_job_candidates.JobService") as MockService:

        mock_service = MagicMock()
        mock_service.get_unapplied_job_rows.return_value = []
        MockService.return_value = mock_service

        from tools.get_job_candidates import get_job_candidates
        get_job_candidates(skills=["Python"], include_evaluated=True)

    mock_service.get_unapplied_job_rows.assert_called_once_with(
        job_group_id=None,
        location=None,
        employment_type=None,
        include_evaluated=True,
    )
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
pytest tests/test_tools.py::test_get_job_candidates_includes_job_id tests/test_tools.py::test_get_job_candidates_no_new_jobs_hint tests/test_tools.py::test_get_job_candidates_passes_include_evaluated -v
```

Expected:
- `test_get_job_candidates_includes_job_id` — FAIL (`KeyError: 'job_id'`, `job_id`가 반환 JSON에 없음)
- `test_get_job_candidates_no_new_jobs_hint` — FAIL (`AssertionError`, 현재 메시지는 "조건에 맞는 미지원 공고가 없습니다.")
- `test_get_job_candidates_passes_include_evaluated` — FAIL (`TypeError: unexpected keyword argument 'include_evaluated'`)

- [ ] **Step 3: 구현**

`tools/get_job_candidates.py` 전체 교체:

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
    include_evaluated: bool = False,
) -> str:
    """미지원 공고 중 skill_tags 매칭 점수 기준 상위 top_n개 후보를 JSON으로 반환.

    Claude Code가 직접 추론할 수 있도록 공고 데이터만 제공.
    employment_type은 한국어("정규직", "인턴", "계약직") 또는 영어("regular", "intern", "contract") 모두 허용.
    추천 후 save_job_evaluations를 호출해 각 공고 verdict를 저장할 것. job_id 필드 사용.
    """
    try:
        engine = get_engine()
        service = JobService(engine)

        rows = service.get_unapplied_job_rows(
            job_group_id=job_group_id,
            location=location,
            employment_type=employment_type,
            include_evaluated=include_evaluated,
        )
        if not rows:
            if not include_evaluated:
                return "새로 평가할 공고가 없습니다. 이미 평가된 공고를 보려면 include_evaluated=True로 호출하세요."
            return "조건에 맞는 미지원 공고가 없습니다."

        candidates = service.get_recommended_jobs(skills=skills, rows=rows, top_k=top_n)
        if not candidates:
            return "추천 후보가 없습니다. sync_job_details를 먼저 실행해 공고 상세 정보를 수집해주세요."

        result = [
            {
                "job_id": c.internal_id,
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

- [ ] **Step 4: 테스트 실행 — 통과 확인**

```bash
pytest tests/test_tools.py::test_get_job_candidates_includes_job_id tests/test_tools.py::test_get_job_candidates_no_new_jobs_hint tests/test_tools.py::test_get_job_candidates_passes_include_evaluated -v
```

Expected: PASS

- [ ] **Step 5: 전체 테스트 통과 확인**

```bash
pytest
```

Expected: 모두 PASS

- [ ] **Step 6: Commit**

```bash
git add tools/get_job_candidates.py tests/test_tools.py
git commit -m "feat: get_job_candidates에 job_id 반환 및 include_evaluated 파라미터 추가"
```

---

### Task 6: DB 테이블 생성 + 통합 확인

**Files:**
- 코드 변경 없음 — DB에 새 테이블 생성

`Base.metadata.create_all`이 `job_evaluations` 테이블을 자동으로 생성한다. 기존 DB에는 `create_tables()`를 한 번 실행해야 한다.

- [ ] **Step 1: MCP 툴로 테이블 생성**

Claude Code에서 실행:
```
migrate_db()
```

또는 직접 실행:
```bash
python -c "from db.connection import create_tables; create_tables()"
```

Expected: 오류 없이 완료

- [ ] **Step 2: 테이블 존재 확인**

```bash
python -c "
from db.connection import get_engine
from sqlalchemy import text
engine = get_engine()
with engine.connect() as conn:
    result = conn.execute(text('SHOW TABLES LIKE \"job_evaluations\"'))
    print('테이블 존재:', result.fetchone() is not None)
"
```

Expected: `테이블 존재: True`

- [ ] **Step 3: 최종 커밋 없음**

코드 변경이 없으므로 커밋 불필요. 이미 Task 1~5에서 모든 코드가 커밋됨.
