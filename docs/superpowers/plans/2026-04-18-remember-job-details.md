# Remember Job Details Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `sync_jobs(source="remember")` 실행 시 `job_details` 테이블에 `skill_tags`(job_categories 기반)를 포함한 상세 정보를 함께 저장해 `get_job_candidates`가 Remember 공고를 올바르게 반환하도록 한다.

**Architecture:** 구현의 골격은 `services/job_service.py`의 `upsert_jobs` Remember 분기(lines 150–178)에 이미 존재한다. 수정은 한 곳: `skill_tags`를 `[]`에서 `job_categories[*].level2` 추출로 교체한다. `fetched_at`은 `datetime.now()`를 단순히 사용한다 (모든 row가 동시에 파싱되므로 per-row 차이 없음).

**Tech Stack:** Python 3.11, SQLAlchemy 2.x, pytest, MySQL

---

### Task 1: skill_tags 추출 수정

**Files:**
- Modify: `services/job_service.py:157-168`
- Test: `tests/test_job_service.py`

현재 코드 (`job_service.py:157-168`):
```python
now = rows[0]["synced_at"]
detail_rows = []
for raw_job in raw_jobs:
    internal_id = internal_id_map.get(raw_job["id"])
    if internal_id:
        detail_rows.append({
            "job_id": internal_id,
            "requirements": raw_job.get("qualifications"),
            "preferred_points": raw_job.get("preferred_qualifications"),
            "skill_tags": [],
            "fetched_at": now,
        })
```

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_job_service.py` 맨 아래에 추가:

```python
def test_upsert_jobs_remember_detail_skill_tags():
    """sync_jobs(remember) 시 detail insert에 skill_tags가 level2 목록으로 전달된다."""
    from unittest.mock import call
    raw_jobs = [
        {
            "id": 999,
            "title": "백엔드 개발자",
            "organization": {"id": 1, "name": "테스트사", "company_id": 42},
            "addresses": [{"address_level1": "서울특별시", "address_level2": "강남구"}],
            "min_salary": None,
            "max_salary": None,
            "qualifications": "Python 3년 이상",
            "preferred_qualifications": "Django 우대",
            "job_categories": [
                {"id": 310, "level1": "SW개발", "level2": "백엔드"},
                {"id": 312, "level1": "SW개발", "level2": "풀스택"},
            ],
        }
    ]

    mock_engine = MagicMock()
    captured_detail_values = []

    with patch("services.job_service.Session") as MockSession, \
         patch("services.job_service.insert") as mock_insert:

        mock_session = MagicMock()
        MockSession.return_value.__enter__ = MagicMock(return_value=mock_session)
        MockSession.return_value.__exit__ = MagicMock(return_value=False)
        mock_session.execute.return_value.all.return_value = []

        # internal_id_map 조회용 mock: platform_id=999 → internal_id=1
        from unittest.mock import PropertyMock
        mock_row = MagicMock()
        mock_row.platform_id = 999
        mock_row.internal_id = 1
        # 두 번째 execute().all() 호출(internal_id_map)에서 반환
        mock_session.execute.return_value.all.side_effect = [[], [mock_row]]

        # insert().values() 호출을 캡처
        mock_insert_instance = MagicMock()
        mock_insert.return_value = mock_insert_instance
        mock_insert_instance.values.side_effect = lambda rows: captured_detail_values.extend(rows) or mock_insert_instance

        service = JobService(engine=mock_engine)
        service.upsert_jobs(raw_jobs, source="remember", full_sync=False)

    # detail insert에 전달된 skill_tags 확인
    detail_row = next((r for r in captured_detail_values if "skill_tags" in r), None)
    assert detail_row is not None, "detail_rows가 insert에 전달되지 않음"
    assert detail_row["skill_tags"] == ["백엔드", "풀스택"]


def test_parse_remember_job_fields():
    """_parse_remember_job이 기본 필드를 올바르게 파싱한다."""
    raw = {
        "id": 123,
        "title": "Backend Engineer",
        "organization": {"id": 1, "name": "(주)테스트", "company_id": 99},
        "addresses": [{"address_level1": "서울특별시", "address_level2": "서초구"}],
        "min_salary": 5000,
        "max_salary": 8000,
        "qualifications": "Python 필수",
        "preferred_qualifications": "Django 우대",
        "job_categories": [{"id": 310, "level1": "SW개발", "level2": "백엔드"}],
    }
    service = JobService(engine=MagicMock())
    result = service._parse_remember_job(raw)

    assert result["platform_id"] == 123
    assert result["company_id"] == 99
    assert result["company_name"] == "(주)테스트"
    assert result["location"] == "서울특별시 서초구"
    assert result["annual_from"] == 5000
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
pytest tests/test_job_service.py::test_upsert_jobs_remember_detail_skill_tags -v
```

Expected: FAIL — `detail_row["skill_tags"] == []`이므로 assertion 실패

- [ ] **Step 3: skill_tags 추출 수정**

`services/job_service.py:157-168` 수정:

```python
# Before:
now = rows[0]["synced_at"]
detail_rows = []
for raw_job in raw_jobs:
    internal_id = internal_id_map.get(raw_job["id"])
    if internal_id:
        detail_rows.append({
            "job_id": internal_id,
            "requirements": raw_job.get("qualifications"),
            "preferred_points": raw_job.get("preferred_qualifications"),
            "skill_tags": [],
            "fetched_at": now,
        })

# After:
now = datetime.now(timezone.utc).replace(tzinfo=None)
detail_rows = []
for raw_job in raw_jobs:
    internal_id = internal_id_map.get(raw_job["id"])
    if internal_id:
        categories = raw_job.get("job_categories") or []
        skill_tags = [c["level2"] for c in categories if c.get("level2")]
        detail_rows.append({
            "job_id": internal_id,
            "requirements": raw_job.get("qualifications"),
            "preferred_points": raw_job.get("preferred_qualifications"),
            "skill_tags": skill_tags,
            "fetched_at": now,
        })
```

`datetime`과 `timezone`은 이미 파일 상단에 import되어 있음 (`from datetime import datetime, timezone`).

- [ ] **Step 4: 테스트 실행 — 통과 확인**

```bash
pytest tests/test_job_service.py::test_upsert_jobs_remember_detail_skill_tags tests/test_job_service.py::test_parse_remember_job_fields -v
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
git commit -m "fix: remember upsert_jobs skill_tags를 job_categories.level2에서 추출"
```

---

### Task 2: 기존 Remember 공고 재동기화

이미 DB에 저장된 318개 공고의 `skill_tags`가 `[]`이므로, `sync_jobs`를 재실행해 올바른 값으로 덮어쓴다.

- [ ] **Step 1: MCP 툴로 재동기화**

Claude Code에서 실행:
```
sync_jobs(source="remember", job_category_names=[{"level1": "SW개발", "level2": "백엔드"}], min_experience=2, max_experience=5)
```

Expected: `동기화 완료: 신규 0개, 변경 0개, 유지 318개`
(jobs 테이블 컬럼은 변경 없고 job_details만 업데이트되므로 `유지`로 표시됨)

- [ ] **Step 2: DB에서 skill_tags 샘플 확인**

```bash
python -c "
from db.connection import get_engine
from sqlalchemy import text
engine = get_engine()
with engine.connect() as conn:
    rows = conn.execute(text(
        'SELECT j.title, jd.skill_tags FROM jobs j JOIN job_details jd ON j.internal_id = jd.job_id WHERE j.source=\"remember\" LIMIT 5'
    )).fetchall()
    for r in rows:
        print(r[0], '->', r[1])
"
```

Expected: `skill_tags`에 `["백엔드"]` 등 level2 값이 담겨있음 (빈 배열이면 재동기화 실패)
