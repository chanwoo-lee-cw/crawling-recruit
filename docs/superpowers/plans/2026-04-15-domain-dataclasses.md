
# Domain Dataclasses Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `SkillTag`, `JobCandidate`, `JobDetail` dataclass를 도입해 읽기/쓰기 경로에 타입 안전성을 부여한다.

**Architecture:** 새 `domain.py`에 dataclass 정의. 쓰기 경로(`_parse_job`, `_parse_application` → SQLAlchemy insert)는 dict 유지. 읽기 경로(`get_unapplied_job_rows` → tool)와 `fetch_job_detail` 반환값만 typed으로 전환.

**Tech Stack:** Python 3.11, stdlib `dataclasses`, pytest

**Spec:** `docs/superpowers/specs/2026-04-15-domain-dataclasses-design.md`

**사전 조건:** `2026-04-15-orm-migration.md` 플랜이 완료된 상태여야 한다.

---

## File Map

| 파일 | 변경 유형 | 주요 내용 |
|------|-----------|-----------|
| `domain.py` | 신규 생성 | `SkillTag`, `JobCandidate`, `JobDetail` dataclass |
| `services/wanted_client.py` | 수정 | `fetch_job_detail` 반환 타입 → `JobDetail \| None` |
| `services/job_service.py` | 수정 | `upsert_job_details`, `get_unapplied_job_rows`, `get_recommended_jobs` 시그니처/구현 |
| `tools/get_job_candidates.py` | 수정 | dict 접근 → 속성 접근 |
| `tests/test_job_service.py` | 수정 | 3개 테스트 (dict → dataclass) |
| `tests/test_tools.py` | 수정 | `sync_job_details` mock → `JobDetail` 객체, dict 접근 → 속성 접근 |

---

### Task 1: `domain.py` 신규 생성

**Files:**
- Create: `domain.py`

- [ ] **Step 1: `domain.py` 작성**

```python
import json
from dataclasses import dataclass
from datetime import datetime


@dataclass
class SkillTag:
    text: str


@dataclass
class JobCandidate:
    """DB 읽기 경로 전용: get_unapplied_job_rows → get_recommended_jobs → get_job_candidates"""
    id: int
    company_name: str
    title: str
    location: str | None
    employment_type: str | None
    requirements: str | None
    preferred_points: str | None
    skill_tags: list[SkillTag]   # text만 보존 — 매칭 전용
    fetched_at: datetime | None

    @classmethod
    def from_row(cls, row) -> "JobCandidate":
        """DB row(dict/Mapping) → JobCandidate. skill_tags JSON 파싱 포함.
        id, company_name, title은 DB NOT NULL 컬럼이므로 직접 접근."""
        raw_tags = row.get("skill_tags") or []
        if isinstance(raw_tags, str):
            try:
                raw_tags = json.loads(raw_tags)
            except (json.JSONDecodeError, TypeError):
                raw_tags = []
        return cls(
            id=row["id"],
            company_name=row["company_name"],
            title=row["title"],
            location=row.get("location"),
            employment_type=row.get("employment_type"),
            requirements=row.get("requirements"),
            preferred_points=row.get("preferred_points"),
            skill_tags=[SkillTag(text=t["text"]) for t in raw_tags if t.get("text")],
            fetched_at=row.get("fetched_at"),
        )


@dataclass
class JobDetail:
    """쓰기 경로 전용: fetch_job_detail → upsert_job_details.
    skill_tags는 raw API dict 보존 — DB JSON 컬럼에 그대로 저장."""
    job_id: int
    requirements: str | None
    preferred_points: str | None
    skill_tags: list[dict]
```

- [ ] **Step 2: import 확인**

```bash
python -c "from domain import SkillTag, JobCandidate, JobDetail; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: `JobCandidate.from_row` 단위 테스트 작성 및 확인**

`tests/test_job_service.py`에 아래 테스트 추가:

```python
def test_job_candidate_from_row_parses_skill_tags():
    from domain import JobCandidate, SkillTag
    row = {
        "id": 1, "company_name": "A사", "title": "Backend",
        "location": "서울", "employment_type": "regular",
        "requirements": "req", "preferred_points": None,
        "skill_tags": [{"tag_type_id": 1, "text": "Python"}, {"tag_type_id": 2, "text": "AWS"}],
        "fetched_at": None,
    }
    candidate = JobCandidate.from_row(row)
    assert candidate.id == 1
    assert candidate.company_name == "A사"
    assert len(candidate.skill_tags) == 2
    assert candidate.skill_tags[0] == SkillTag(text="Python")
    assert candidate.skill_tags[1] == SkillTag(text="AWS")


def test_job_candidate_from_row_handles_null_skill_tags():
    from domain import JobCandidate
    row = {
        "id": 2, "company_name": "B사", "title": "Frontend",
        "location": None, "employment_type": None,
        "requirements": None, "preferred_points": None,
        "skill_tags": None, "fetched_at": None,
    }
    candidate = JobCandidate.from_row(row)
    assert candidate.skill_tags == []
    assert candidate.fetched_at is None
```

```bash
pytest tests/test_job_service.py::test_job_candidate_from_row_parses_skill_tags \
       tests/test_job_service.py::test_job_candidate_from_row_handles_null_skill_tags -v
```

Expected: 2 tests PASS

- [ ] **Step 4: Commit**

```bash
git add domain.py tests/test_job_service.py
git commit -m "feat: domain.py — SkillTag, JobCandidate, JobDetail dataclass 추가"
```

---

### Task 2: `services/wanted_client.py` — `fetch_job_detail` 반환 타입 전환

**Files:**
- Modify: `services/wanted_client.py`

- [ ] **Step 1: `fetch_job_detail` 수정**

`services/wanted_client.py` 상단에 import 추가, `fetch_job_detail` 반환값 교체:

```python
from domain import JobDetail  # 상단 import에 추가
```

```python
def fetch_job_detail(self, job_id: int) -> JobDetail | None:
    """단일 공고 detail 조회. 실패 시 None 반환."""
    url = DETAIL_API_URL.format(job_id=job_id)
    try:
        resp = self._get(url, params={})
    except RuntimeError:
        return None
    if resp.status_code != 200:
        return None
    data = resp.json().get("data", {})
    job = data.get("job", {})
    detail = job.get("detail", {})
    return JobDetail(
        job_id=job_id,
        requirements=detail.get("requirements"),
        preferred_points=detail.get("preferred_points"),
        skill_tags=data.get("skill_tags", []),
    )
```

- [ ] **Step 2: import 확인**

```bash
python -c "from services.wanted_client import WantedClient; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add services/wanted_client.py
git commit -m "refactor: fetch_job_detail 반환 타입 → JobDetail"
```

---

### Task 3: `services/job_service.py` — 3개 메서드 시그니처 전환

**Files:**
- Modify: `services/job_service.py`

- [ ] **Step 1: import 정리 — ORM `JobDetail`을 alias로 교체**

`services/job_service.py` 상단 import를 아래처럼 교체한다.
`db.models.JobDetail`과 `domain.JobDetail`이 같은 이름이므로 ORM 클래스에 alias를 붙인다:

```python
# services/job_service.py import 섹션
from db.models import Job, Application, JobDetail as OrmJobDetail, SearchPreset
from domain import JobCandidate, JobDetail
```

- [ ] **Step 2: `upsert_job_details` 시그니처 + 구현 변경**

`insert(OrmJobDetail.__table__)` 사용에 주의 (`JobDetail.__table__`이 아님 — `JobDetail`은 이제 domain dataclass):

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
        stmt = insert(OrmJobDetail.__table__).values(rows)   # OrmJobDetail 사용
        upsert_stmt = stmt.on_duplicate_key_update(
            requirements=stmt.inserted.requirements,
            preferred_points=stmt.inserted.preferred_points,
            skill_tags=stmt.inserted.skill_tags,
            fetched_at=stmt.inserted.fetched_at,
        )
        session.execute(upsert_stmt)
        session.commit()
    return f"완료: {len(rows)}개 처리"
```

> `test_upsert_job_details_calls_execute`는 `RAW_DETAIL`을 `JobDetail` 객체로 교체(Task 5)하면 자동으로 수정된다. 해당 테스트 body는 변경 불필요.

- [ ] **Step 3: `get_unapplied_job_rows` 반환 타입 변경**

```python
def get_unapplied_job_rows(
    self,
    job_group_id: int | None = None,
    location: str | None = None,
    employment_type: str | None = None,
) -> list[JobCandidate]:
    if employment_type:
        employment_type = self.EMPLOYMENT_TYPE_MAP.get(employment_type, employment_type)
    stmt = (
        select(
            Job.id, Job.company_name, Job.title, Job.location, Job.employment_type,
            OrmJobDetail.requirements, OrmJobDetail.preferred_points,
            OrmJobDetail.skill_tags, OrmJobDetail.fetched_at,
        )
        .outerjoin(Application, Job.id == Application.job_id)
        .outerjoin(OrmJobDetail, Job.id == OrmJobDetail.job_id)
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

    return [JobCandidate.from_row(r) for r in rows]
```

- [ ] **Step 4: `get_recommended_jobs` 시그니처 + 구현 변경**

```python
def get_recommended_jobs(
    self,
    skills: list[str],
    rows: list[JobCandidate],
    top_k: int = 15,
) -> list[JobCandidate]:
    """전달된 rows에서 skill_tags 매칭 점수 기준 상위 top_k개 반환 (detail 없는 공고 제외)."""
    skills_lower = {s.lower() for s in skills}

    def score(row: JobCandidate) -> int:
        return sum(1 for tag in row.skill_tags if tag.text.lower() in skills_lower)

    with_detail = [r for r in rows if r.fetched_at is not None]
    scored = sorted(with_detail, key=score, reverse=True)
    return scored[:top_k]
```

- [ ] **Step 5: Commit**

```bash
git add services/job_service.py
git commit -m "refactor: job_service dataclass 시그니처 적용 (upsert_job_details, get_unapplied_job_rows, get_recommended_jobs)"
```

---

### Task 4: `tools/get_job_candidates.py` — 속성 접근으로 전환

**Files:**
- Modify: `tools/get_job_candidates.py`

- [ ] **Step 1: result 빌드 로직 교체**

```python
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
                "job_id": c.id,
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

- [ ] **Step 2: Commit**

```bash
git add tools/get_job_candidates.py
git commit -m "refactor: get_job_candidates dict 접근 → JobCandidate 속성 접근"
```

---

### Task 5: 테스트 업데이트

**Files:**
- Modify: `tests/test_job_service.py`
- Modify: `tests/test_tools.py`

- [ ] **Step 1: `tests/test_job_service.py` — 영향받는 테스트 교체**

`RAW_DETAIL` dict → `JobDetail` 객체, `test_get_unapplied_job_rows_returns_list`, `test_get_recommended_jobs_scores_skill_tags` 수정:

```python
# 상단 import에 추가
from domain import JobCandidate, JobDetail, SkillTag

# RAW_DETAIL 변경
RAW_DETAIL = JobDetail(
    job_id=1001,
    requirements="Python 3년 이상",
    preferred_points="FastAPI 경험자 우대",
    skill_tags=[{"tag_type_id": 1554, "text": "Python"}],
)
```

```python
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
    assert rows[0].id == 1001          # 속성 접근
    assert rows[0].fetched_at is None  # 속성 접근
```

```python
def test_get_recommended_jobs_scores_skill_tags():
    from datetime import datetime
    now = datetime.now()
    all_rows = [
        JobCandidate(
            id=1, company_name="A사", title="Backend",
            location="서울", employment_type="regular",
            requirements="Python req", preferred_points="AWS 우대",
            skill_tags=[SkillTag(text="Python"), SkillTag(text="AWS")],
            fetched_at=now,
        ),
        JobCandidate(
            id=2, company_name="B사", title="Frontend",
            location="서울", employment_type="regular",
            requirements="React req", preferred_points=None,
            skill_tags=[SkillTag(text="React")],
            fetched_at=now,
        ),
        JobCandidate(
            id=3, company_name="C사", title="Fullstack",
            location="서울", employment_type="regular",
            requirements=None, preferred_points=None,
            skill_tags=[], fetched_at=None,
        ),
    ]

    service = JobService(engine=MagicMock())
    candidates = service.get_recommended_jobs(
        skills=["Python", "AWS"],
        rows=all_rows,
        top_k=15,
    )

    assert len(candidates) == 2
    assert candidates[0].id == 1      # 속성 접근
    assert candidates[1].id == 2
    assert all(c.fetched_at is not None for c in candidates)
```

- [ ] **Step 2: `tests/test_tools.py` — `sync_job_details` mock JobDetail로 교체**

파일 상단 import 섹션에 추가:
```python
from domain import JobDetail
```

`test_sync_job_details_processes_missing` 함수 전체 교체:
```python
def test_sync_job_details_processes_missing():
    with patch("tools.sync_job_details.get_engine"), \
         patch("tools.sync_job_details.WantedClient") as MockClient, \
         patch("tools.sync_job_details.JobService") as MockService, \
         patch("tools.sync_job_details.time.sleep") as mock_sleep:

        mock_service = MagicMock()
        mock_service.get_jobs_without_details.return_value = [101, 102]
        mock_service.upsert_job_details.return_value = "완료: 2개 처리"
        MockService.return_value = mock_service

        mock_client = MagicMock()
        mock_client.fetch_job_detail.side_effect = [
            JobDetail(job_id=101, requirements="req1", preferred_points="pref1", skill_tags=[]),
            JobDetail(job_id=102, requirements="req2", preferred_points=None, skill_tags=[]),
        ]
        MockClient.return_value = mock_client

        result = sync_job_details()

    assert "2개 처리" in result
    assert mock_client.fetch_job_detail.call_count == 2
    mock_sleep.assert_called_once_with(1)
```

`test_sync_job_details_skips_failed_fetch` 함수 전체 교체:
```python
def test_sync_job_details_skips_failed_fetch():
    with patch("tools.sync_job_details.get_engine"), \
         patch("tools.sync_job_details.WantedClient") as MockClient, \
         patch("tools.sync_job_details.JobService") as MockService, \
         patch("tools.sync_job_details.time.sleep"):

        mock_service = MagicMock()
        mock_service.get_jobs_without_details.return_value = [101, 102]
        mock_service.upsert_job_details.return_value = "완료: 1개 처리"
        MockService.return_value = mock_service

        mock_client = MagicMock()
        mock_client.fetch_job_detail.side_effect = [
            None,  # 101 실패
            JobDetail(job_id=102, requirements="req2", preferred_points=None, skill_tags=[]),
        ]
        MockClient.return_value = mock_client

        result = sync_job_details()

    called_details = mock_service.upsert_job_details.call_args[0][0]
    assert len(called_details) == 1
    assert called_details[0].job_id == 102  # 속성 접근
```

- [ ] **Step 3: 전체 테스트 실행**

```bash
pytest tests/ -v
```

Expected: 전체 PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_job_service.py tests/test_tools.py
git commit -m "test: dataclass 전환에 맞춰 테스트 mock 및 assertion 업데이트"
```
