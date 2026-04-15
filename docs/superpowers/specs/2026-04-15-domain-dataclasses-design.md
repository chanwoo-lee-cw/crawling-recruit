# Domain Dataclasses 도입 설계

**날짜:** 2026-04-15  
**목표:** 프로젝트 내 `dict` 기반 데이터 흐름에 타입 안전성을 부여한다.

---

## 배경 및 동기

현재 코드는 공고 데이터를 `dict`로 주고받는다. IDE 자동완성이 안 되고, 어떤 필드가 있는지 코드만 봐선 알기 어렵고, `None` 가능 여부도 불명확하다. `t.get("text", "")` 같은 방어적 dict 접근이 코드 곳곳에 흩어져 있다.

---

## 설계 원칙

- **쓰기 경로(API → DB)**: `dict` 유지. `_parse_job`, `_parse_application`의 반환값과 SQLAlchemy `insert()`는 현상 유지.
- **읽기 경로(DB → tool 출력)**: `dataclass`로 전환. DB 조회 결과를 domain 객체로 변환한 뒤 tool까지 흘러가게 한다.
- **외부 API 파싱 내부**: Wanted API 응답 파싱은 `dict` 접근으로 유지. 반환값(경계)만 typed으로 바꾼다.

---

## 새 파일: `domain.py`

프로젝트 루트에 추가. `db/models.py`는 SQLAlchemy 스키마, `domain.py`는 Python 도메인 객체 담당.

```python
import json
from dataclasses import dataclass
from datetime import datetime

@dataclass
class SkillTag:
    text: str

@dataclass
class JobCandidate:
    """읽기 경로 전용: get_unapplied_job_rows → get_recommended_jobs → get_job_candidates"""
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
        """DB row(dict/Mapping) → JobCandidate. skill_tags JSON 파싱 포함."""
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
    """쓰기 경로 전용: fetch_job_detail → upsert_job_details"""
    job_id: int
    requirements: str | None
    preferred_points: str | None
    skill_tags: list[dict]  # raw API dict 보존 — DB JSON 컬럼에 그대로 저장
```

**SkillTag.skill_tags 분리 이유:**
- `JobCandidate.skill_tags`: `list[SkillTag]` — 읽기/매칭 전용, `text`만 필요
- `JobDetail.skill_tags`: `list[dict]` — DB 저장 전용, API 원본 필드(`tag_type_id` 등) 보존

---

## 변경 파일

### `services/job_service.py`

**읽기 경로:**

| 메서드 | 변경 전 | 변경 후 |
|--------|---------|---------|
| `get_unapplied_job_rows` | `-> list[dict]` | `-> list[JobCandidate]` |
| `get_recommended_jobs` | `rows: list[dict]` → `list[dict]` | `rows: list[JobCandidate]` → `list[JobCandidate]` |

`get_unapplied_job_rows` 내부의 JSON 파싱 로직(`json.loads(skill_tags)`)은 `JobCandidate.from_row()`로 이동.

`get_recommended_jobs` 내부의 `score()`:
```python
# 변경 전
return sum(1 for t in tags if t.get("text", "").lower() in skills_lower)

# 변경 후
return sum(1 for tag in row.skill_tags if tag.text.lower() in skills_lower)
```

`fetched_at` 체크:
```python
# 변경 전
with_detail = [r for r in rows if r.get("fetched_at") is not None]

# 변경 후
with_detail = [r for r in rows if r.fetched_at is not None]
```

**쓰기 경로:**

`upsert_job_details` 시그니처 변경:
```python
# 변경 전
def upsert_job_details(self, details: list[dict]) -> str:
    rows = [{"job_id": d["job_id"], "requirements": d.get("requirements"), ...} for d in details]

# 변경 후
def upsert_job_details(self, details: list[JobDetail]) -> str:
    rows = [{"job_id": d.job_id, "requirements": d.requirements,
             "preferred_points": d.preferred_points, "skill_tags": d.skill_tags,
             "fetched_at": now} for d in details]
    # SQLAlchemy insert는 그대로
```

`_parse_job`, `_parse_application`: **변경 없음** (write path, dict 유지).

---

### `services/wanted_client.py`

`fetch_job_detail` 반환 타입만 변경. 내부 파싱 로직(`job.get("detail", {})` 등)은 그대로 유지.

```python
# 변경 전
def fetch_job_detail(self, job_id: int) -> dict | None:
    ...
    return {"job_id": job_id, "requirements": ..., "skill_tags": ...}

# 변경 후
def fetch_job_detail(self, job_id: int) -> JobDetail | None:
    ...
    return JobDetail(
        job_id=job_id,
        requirements=detail.get("requirements"),
        preferred_points=detail.get("preferred_points"),
        skill_tags=data.get("skill_tags", []),
    )
```

---

### `tools/get_job_candidates.py`

`candidates`가 `list[JobCandidate]`이므로 속성 접근으로 전환:

```python
# 변경 전
result = [{"job_id": c["id"], "company_name": c["company_name"], ...} for c in candidates]

# 변경 후
result = [{
    "job_id": c.id,
    "company_name": c.company_name,
    "title": c.title,
    "location": c.location,
    "employment_type": c.employment_type,
    "skill_tags": [{"text": t.text} for t in c.skill_tags],
    "requirements": c.requirements,
    "preferred_points": c.preferred_points,
} for c in candidates]
```

---

### `tools/sync_job_details.py`

**변경 없음.** `fetch_job_detail`이 `JobDetail`을 반환하고 `upsert_job_details`가 `list[JobDetail]`을 받으므로 그대로 통과.

---

### `tests/test_job_service.py`

영향받는 테스트 3개 수정:

| 테스트 | 변경 내용 |
|--------|-----------|
| `test_get_unapplied_job_rows_returns_list` | `rows[0]["id"]` → `rows[0].id`, `rows[0]["fetched_at"]` → `rows[0].fetched_at` |
| `test_get_recommended_jobs_scores_skill_tags` | `all_rows` dict → `JobCandidate` 객체 리스트로 교체; `candidates[0]["id"]` → `candidates[0].id` |
| `test_upsert_job_details_calls_execute` | `RAW_DETAIL` dict → `JobDetail(...)` 객체로 교체 |

### `tests/test_tools.py`

**기존 broken import 제거 (pre-existing 이슈):**
- 127번째 줄 `from tools.recommend_jobs import recommend_jobs`와 128번째 줄 `import anthropic` 및 이를 사용하는 `test_recommend_jobs_calls_claude_and_returns_markdown`, `test_recommend_jobs_fallback_on_claude_failure` 테스트 2개 삭제. `tools/recommend_jobs.py`는 이전 리팩터링에서 이미 제거된 파일이다.

**`sync_job_details` 테스트 mock 수정:**

`fetch_job_detail` mock이 `dict`를 반환하던 것을 `JobDetail` 객체로 교체:

```python
# 변경 전 (test_sync_job_details_processes_missing, test_sync_job_details_skips_failed_fetch)
mock_client.fetch_job_detail.side_effect = [
    {"job_id": 101, "requirements": "req1", "preferred_points": "pref1", "skill_tags": []},
    ...
]

# 변경 후
from domain import JobDetail
mock_client.fetch_job_detail.side_effect = [
    JobDetail(job_id=101, requirements="req1", preferred_points="pref1", skill_tags=[]),
    ...
]
```

`upsert_job_details`에 전달된 인자 검증도 속성 접근으로 변경:

```python
# 변경 전
assert called_details[0]["job_id"] == 102

# 변경 후
assert called_details[0].job_id == 102
```

---

## 외부 API 파싱 원칙

Wanted API 응답(`resp.json()`)의 내부 파싱은 `dict` 접근으로 유지한다. 경계(반환값)에서만 domain 객체로 변환하는 Anticorruption Layer 패턴을 따른다. `WantedJobResponse` 같은 API 응답 전용 dataclass는 만들지 않는다.

---

## 영향 없는 파일

- `db/models.py` — SQLAlchemy 테이블 정의 변경 없음
- `tools/sync_jobs.py` — raw jobs → `_parse_job` → insert (write path)
- `tools/sync_applications.py` — raw apps → `_parse_application` → insert (write path)
- `tools/get_unapplied_jobs.py` — 직접 `get_unapplied_jobs()` 호출 (마크다운 반환, dict 경로)
- `tools/save_search_preset.py`, `tools/list_search_presets.py` — preset은 free-form params, 변경 없음
